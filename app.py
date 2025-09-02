"""
app.py

功能：
- 为人大科研处、学生处网站构建一个基于BM25的简易搜索引擎。
- 支持惰性加载索引，首次查询时自动构建。
- 提供一个满足评测要求的 evaluate 函数。

使用：
- 和评测客户端 client.py 放在同一目录。
- 确保 DEFAULT_JSON_DIRS 和 DEFAULT_HTML_DIRS 指向你爬取的数据目录。
- 直接运行 `python app.py` 可进入本地测试模式。
"""
import os
import re
import json
import math
import glob
from collections import Counter, defaultdict
from typing import List, Dict, Tuple

try:
    import jieba
    import jieba.analyse
except ImportError:
    raise RuntimeError("请先安装jieba库：pip install jieba")

# ===================== 配置区 (在这里调整你的设置) =====================

# 目标网站域名
ALLOWED_PREFIXES = (
    "http://keyan.ruc.edu.cn/",
    "http://xsc.ruc.edu.cn/",
)

# 默认的数据目录, 如果环境变量 CRAWL_JSON_DIRS 未设置, 则会使用这里
# ** 注意：请务必修改为你的实际路径 **
DEFAULT_JSON_DIRS = [
    "/Users/xiexuyan/Desktop/人工智能综合设计/Project/crawler_data/data_output"
]
DEFAULT_HTML_DIRS = [
    "/Users/xiexuyan/Desktop/人工智能综合设计/Project/crawler_data/html_output"
]

# 给标题词条加权，乘以这个倍数
TITLE_TOKEN_DUP = 3

# BM25 的两个经验参数
K1 = 1.5
B = 0.75

# 过滤掉一些常见但无意义的词
STOPWORDS = {
    "的", "了", "和", "是", "在", "与", "及", "或", "并", "为", "而", "对", "以",
    "以及", "等", "各", "其", "也", "都", "更", "再", "很", "着", "于", "中",
    "你", "我", "他", "她", "它", "他们", "我们", "你们", "的", "地", "得", "……"
}

# =================================================================

# ---------- 全局变量 (程序运行时会把索引加载到这里) ----------
_INDEX_READY = False
_doc_urls: Dict[int, str] = {}
_doc_html_paths: Dict[int, str] = {}
_doc_json_paths: Dict[int, str] = {}
_postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
_doc_freq: Dict[str, int] = {}
_doc_lens: Dict[int, int] = {}
_avg_doc_len: float = 1.0
_num_docs: int = 0


def _discover_json_dirs() -> List[str]:
    """
    智能发现存放JSON的目录。
    优先用环境变量 CRAWL_JSON_DIRS, 方便在服务器上部署。
    如果环境变量没有，就用咱们在上面配置的 DEFAULT_JSON_DIRS。
    """
    env_dirs = os.environ.get("CRAWL_JSON_DIRS", "").strip()
    if env_dirs:
        # 按冒号分割环境变量里的路径
        dirs = [p.strip() for p in env_dirs.split(":") if p.strip() and os.path.isdir(p)]
        if dirs:
            return dirs
    
    # 环境变量没有, 就回到默认配置
    valid_default_dirs = [p for p in DEFAULT_JSON_DIRS if os.path.isdir(p) and glob.glob(os.path.join(p, "*.json"))]
    if not valid_default_dirs:
        raise FileNotFoundError(
            "没找到存有.json文件的数据目录! 请检查 DEFAULT_JSON_DIRS 配置或设置 CRAWL_JSON_DIRS 环境变量。"
        )
    return valid_default_dirs

def _discover_html_dirs() -> Dict[int, str]:
    """扫描HTML目录, 建立 doc_id -> html文件路径 的映射。"""
    html_map = {}
    for d in DEFAULT_HTML_DIRS:
        if not os.path.isdir(d):
            continue
        for fp in glob.glob(os.path.join(d, "*.html")):
            try:
                # 文件名就是 doc_id
                doc_id = int(os.path.splitext(os.path.basename(fp))[0])
                html_map[doc_id] = fp
            except (ValueError, IndexError):
                # 文件名不规范就跳过
                continue
    return html_map


def _is_allowed_url(u: str) -> bool:
    """检查URL是否属于目标域名。"""
    if not u:
        return False
    return any(u.startswith(pref) for pref in ALLOWED_PREFIXES)


# 预编译正则表达式, 提高效率
_PUNCT_RE = re.compile(r"[\s\u3000，。、“”‘’：；？！《》—\-—_,.;:!?()（）\[\]【】{}<>~`@#$%^&*+=|\\/]+")

def _tokenize(text: str) -> List[str]:
    """一个简单的中文分词器。"""
    if not text:
        return []
    # 先用正则把一堆乱七八糟的符号换成空格
    cleaned = _PUNCT_RE.sub(" ", text.strip())
    # 用结巴分词(搜索模式), 并过滤掉停用词和空字符串
    tokens = [t.strip().lower() for t in jieba.cut_for_search(cleaned) if t.strip()]
    return [t for t in tokens if t not in STOPWORDS]


def _yield_docs(json_dirs: List[str]):
    """遍历所有JSON文件, 每次返回一个解析好的文档。"""
    for d in json_dirs:
        for fp in glob.glob(os.path.join(d, "*.json")):
            try:
                doc_id = int(os.path.splitext(os.path.basename(fp))[0])
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue # 文件有问题就跳过
            
            url = data.get("url", "")
            if not _is_allowed_url(url):
                continue

            title = data.get("title", "").strip()
            text = data.get("text", "").strip()
            
            # 直接用分词好的结果, 速度更快
            title_tokens = data.get("title_segmented", _tokenize(title))
            text_tokens = data.get("text_segmented", _tokenize(text))

            yield doc_id, url, title_tokens, text_tokens


def _build_index():
    """
    核心函数：构建倒排索引和计算BM25所需的统计量。
    这个函数只在第一次查询时被调用。
    """
    global _INDEX_READY, _doc_urls, _doc_html_paths, _postings, _doc_freq
    global _doc_lens, _avg_doc_len, _num_docs, _doc_json_paths

    if _INDEX_READY:
        return

    print("首次查询，正在努力构建索引，请稍等...")
    
    json_dirs = _discover_json_dirs()
    _doc_html_paths = _discover_html_dirs()
    valid_json_dir = json_dirs[0] if json_dirs else None

    total_len = 0
    # 开始处理每个文档
    for doc_id, url, title_tokens, text_tokens in _yield_docs(json_dirs):
        # 必须同时有html和json文件才处理
        if doc_id not in _doc_html_paths:
            continue
        
        if valid_json_dir:
            json_path = os.path.join(valid_json_dir, f"{doc_id}.json")
            if os.path.exists(json_path):
                 _doc_json_paths[doc_id] = json_path

        # 标题内容重复几次，变相加权
        tokens = text_tokens + title_tokens * int(TITLE_TOKEN_DUP)
        if not tokens:
            continue

        _doc_urls[doc_id] = url
        _doc_lens[doc_id] = len(tokens)
        total_len += len(tokens)

        # 统计词频(tf)并更新倒排列表
        tf = Counter(tokens)
        for term, freq in tf.items():
            _postings[term].append((doc_id, freq))
    
    _num_docs = len(_doc_lens)
    _avg_doc_len = (total_len / _num_docs) if _num_docs > 0 else 1.0
    _doc_freq = {term: len(p) for term, p in _postings.items()}
    
    _INDEX_READY = True
    print(f"索引构建完成！共索引了 {_num_docs} 个文档。")


def _bm25_idf(df: int, N: int) -> float:
    """BM25的IDF部分, 加了0.5平滑。"""
    return math.log((N - df + 0.5) / (df + 0.5) + 1.0)


def _score_bm25(query_terms: List[str]) -> Dict[int, float]:
    """为所有可能相关的文档计算BM25分数。"""
    scores = defaultdict(float)
    if not query_terms or _num_docs == 0:
        return scores

    # 只考虑索引里存在的查询词
    q_tf = Counter([t for t in query_terms if t in _postings])

    for term, qf in q_tf.items():
        postings = _postings.get(term, [])
        df = _doc_freq.get(term, 0)
        if df == 0:
            continue
        
        idf = _bm25_idf(df, _num_docs)

        # 累加每个词对每个文档的分数贡献
        for doc_id, tf in postings:
            dl = _doc_lens[doc_id]
            # 这是BM25的核心公式
            score_part = (tf * (K1 + 1)) / (tf + K1 * (1 - B + B * (dl / _avg_doc_len)))
            scores[doc_id] += idf * score_part

    return scores


def _get_doc_meta(doc_id: int) -> Dict[str, str]:
    """工具函数：根据doc_id拿到文档的标题和URL。"""
    json_path = _doc_json_paths.get(doc_id)
    if not json_path:
        url = _doc_urls.get(doc_id, "URL丢失")
        return {"title": "无标题 (JSON文件丢失)", "url": url}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            title = data.get("title", "无标题").strip()
            url = data.get("url", "无URL").strip()
            return {"title": title, "url": url}
    except Exception as e:
        url = _doc_urls.get(doc_id, "URL丢失")
        return {"title": "无标题 (JSON读取失败)", "url": url}


def _get_ranked_doc_ids(query: str) -> List[int]:
    """封装了搜索和排序的核心逻辑, 返回排好序的文档ID列表。"""
    q_tokens = _tokenize(query)
    if not q_tokens:
        return []

    scores = _score_bm25(q_tokens)
    if not scores:
        return []

    # 排序：先按分数从高到低, 分数一样时按URL长度和字典序排, 保证结果稳定
    return sorted(scores.keys(), key=lambda doc_id: (scores[doc_id], -len(_doc_urls.get(doc_id, "")), _doc_urls.get(doc_id, "")), reverse=True)


def evaluate(query: str) -> list:
    """
    评测客户端调用的唯一接口。
    输入一个查询字符串，返回一个包含20个URL的列表。
    """
    global _INDEX_READY
    if not _INDEX_READY:
        _build_index()

    ranked_doc_ids = _get_ranked_doc_ids(query)

    # 按评测要求，返回URL列表
    url_list = []
    seen_urls = set()
    for doc_id in ranked_doc_ids:
        url = _doc_urls.get(doc_id)
        # 去重，并且确保URL有效
        if url and url not in seen_urls:
            seen_urls.add(url)
            url_list.append(url)
        if len(url_list) >= 20:
            break

    # 如果结果不够20个，用空字符串补齐，这是评测的要求
    if len(url_list) < 20:
        url_list.extend([""] * (20 - len(url_list)))

    return url_list


# ================== 本地测试用的代码 ==================
if __name__ == "__main__":
    _build_index()
    
    print("\n=========================================")
    print(" 欢迎使用简易搜索引擎 (本地测试版)")
    print("=========================================")
    
    while True:
        try:
            q = input("请输入查询 (直接回车退出) > ").strip()
            if not q:
                print("感谢使用，再见！")
                break
            
            ranked_doc_ids = _get_ranked_doc_ids(q)
            
            results = []
            seen = set()
            for doc_id in ranked_doc_ids:
                if doc_id in seen:
                    continue
                seen.add(doc_id)
                results.append(_get_doc_meta(doc_id))
                if len(results) >= 20:
                    break

            if not results:
                print("--> 抱歉，没有找到相关结果。")
            else:
                print(f"\n为您找到 {len(results)} 条结果：")
                for i, res in enumerate(results, 1):
                    print(f"  {i}. {res['title']}")
                    print(f"     URL: {res['url']}")
                print("-" * 20)

        except KeyboardInterrupt:
            print("\n感谢使用，再见！")
            break
        except Exception as e:
            print(f"发生了一个错误: {e}")

