"""
search_engine.py

功能：
- 构建面向 keyan.ruc.edu.cn 与 xsc.ruc.edu.cn 的站内检索索引（惰性初始化）
- 【优化】引入“最长连续短语”奖励
- 【优化】对被标记为“目录页”的链接施加一个轻微的“降权惩罚”
- 使用 BM25 作为主排序，PageRank 作为次级排序的混合模型进行检索
- 对给定单条查询，返回 Top-20 原始 URL 列表


依赖：
- jieba
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
except Exception as _:
    raise RuntimeError("需要安装 jieba：pip install jieba")

# ===================== 配置区 =====================

# 允许域（仅索引这些域名下的文档）
ALLOWED_PREFIXES = (
    "http://keyan.ruc.edu.cn/",
    "http://xsc.ruc.edu.cn/",
)

# 默认 JSON 文档目录（按你的项目结构调整）
DEFAULT_JSON_DIRS = [
    # 你的 Project 路径
    "/Users/xiexuyan/Desktop/人工智能综合设计/IR_System/crawler_data/data_output"
]

# 标题 token 的加权方式（简单复制倍数）
TITLE_TOKEN_DUP = 3 

# BM25 参数
K1 = 1.5
B = 0.75

# 为匹配了短语的文档设置一个奖励乘数
PHRASE_BONUS_WEIGHT = 0.5

# 【新增】为目录页设置一个惩罚系数（乘以这个值）
DIRECTORY_PAGE_PENALTY = 0.8 # 可以微调这个值，越小惩罚越重

# 【优化】停用词表 (与您的搜索引擎保持一致)
# 根据高频词分析，添加了大量针对此数据集的、低信息量的词汇
STOPWORDS = {
    # 原始停用词
    "的", "了", "和", "是", "在", "与", "及", "或", "与否", "并", "为", "而", "对", "以",
    "与及", "以及", "等", "各", "其", "也", "都", "更", "再", "很", "着", "于", "中",
    "你", "我", "他", "她", "它", "他们", "我们", "你们","……", "中", "在", "的", "地", "得",
    "是", "了", "和", "与", "或", "也", "都",

    # --- 新增停用词 ---
    # 1. 绝对安全的网站结构与功能词
    "首页", "通知", "公告", "附件", "下载", "链接", "简介", "版权", "版权所有",
    "友情链接", "微信", "官网", "网站", "搜索", "登陆", "通讯录",

    # 2. 极高频且低信息量的通用词
    "我校", "学校", "相关", "情况", "进行", "开展", "关于", "要求", "提供", "组织",
    
    # 3. 分词错误产生的碎片
    "京市", "公室", "国人",
    
    # 4. 无意义的符号或代码
    "cn", "edu", "ruc", "http", "Copyright", "..."
}


# ==================================================

# ---------- 全局索引（惰性构建） ----------
_INDEX_READY = False
_DOCID_TO_URL: Dict[int, str] = {}
# 【新增】存储每个文档的页面类型
_DOCID_TO_PAGE_TYPE: Dict[int, str] = {}
# 倒排列表现在存储 (doc_id, [positions...])
_POSTINGS: Dict[str, List[Tuple[int, List[int]]]] = defaultdict(list)
_DF: Dict[str, int] = {}
_DOC_LEN: Dict[int, int] = {}
_PAGERANK_SCORES: Dict[int, float] = {} 
_AVG_DL: float = 1.0
_NUM_DOCS: int = 0


def _discover_json_dirs() -> List[str]:
    env = os.environ.get("CRAWL_JSON_DIRS", "").strip()
    dirs = []
    if env:
        for p in env.split(":"):
            p = p.strip()
            if p and os.path.isdir(p):
                if glob.glob(os.path.join(p, "*.json")): dirs.append(p)
    if not dirs:
        for p in DEFAULT_JSON_DIRS:
            if os.path.isdir(p) and glob.glob(os.path.join(p, "*.json")): dirs.append(p)
    if not dirs:
        raise FileNotFoundError("未找到任何含 .json 的数据目录。")
    return dirs


def _is_allowed_url(u: str) -> bool:
    if not u: return False
    return any(u.startswith(pref) for pref in ALLOWED_PREFIXES)


_PUNCT_RE = re.compile(r"[\s\u3000，。、“”‘’：；？！《》—\-—_,.;:!?()（）\[\]【】{}<>~`@#$%^&*+=|\\/]+")


def _tokenize(text: str) -> List[str]:
    if not text: return []
    cleaned = _PUNCT_RE.sub(" ", text.strip())
    tokens = [t.strip().lower() for t in jieba.cut_for_search(cleaned) if t.strip()]
    return [t for t in tokens if t not in STOPWORDS]


def _iter_docs(json_dirs: List[str]):
    for d in json_dirs:
        files = sorted(
            glob.glob(os.path.join(d, "*.json")),
            key=lambda f: int(os.path.splitext(os.path.basename(f))[0])
        )
        for fp in files:
            try:
                with open(fp, "r", encoding="utf-8") as f: data = json.load(f)
            except Exception: continue
            url = data.get("url", "") or ""
            if not _is_allowed_url(url): continue
            title_tokens = _tokenize(data.get("title", ""))
            text_tokens = _tokenize(data.get("text", ""))
            hyperlinks = data.get("hyperlinks", [])
            # 【修改】读取页面类型
            page_type = data.get("page_type", "content") # 默认为content
            yield url, title_tokens, text_tokens, hyperlinks, page_type


def _calculate_pagerank_optimized(link_graph: Dict[int, List[int]], num_docs: int, damping=0.85, max_iter=100) -> Dict[int, float]:
    if num_docs == 0: return {}
    ranks = {i: 1.0 / num_docs for i in range(num_docs)}
    out_degrees = {i: len(links) for i, links in link_graph.items()}
    in_links = defaultdict(list)
    for from_id, to_ids in link_graph.items():
        for to_id in to_ids: in_links[to_id].append(from_id)
    for _ in range(max_iter):
        new_ranks = {}
        for i in range(num_docs):
            rank_sum = sum(ranks[j] / out_degrees.get(j, 1) for j in in_links.get(i, []))
            new_ranks[i] = (1 - damping) / num_docs + damping * rank_sum
        if all(abs(new_ranks[i] - ranks[i]) < 1e-6 for i in range(num_docs)): break
        ranks = new_ranks
    return ranks


def _build_index():
    global _INDEX_READY, _DOCID_TO_URL, _POSTINGS, _DF, _DOC_LEN, _AVG_DL, _NUM_DOCS, _PAGERANK_SCORES, _DOCID_TO_PAGE_TYPE
    print("首次运行，正在构建索引(包含位置和页面类型信息)...")
    json_dirs = _discover_json_dirs()

    doc_id, total_len = 0, 0
    url_to_docid, docid_to_hyperlinks = {}, {}

    for url, title_tokens, text_tokens, hyperlinks, page_type in _iter_docs(json_dirs):
        url_to_docid[url] = doc_id
        docid_to_hyperlinks[doc_id] = hyperlinks
        _DOCID_TO_URL[doc_id] = url
        _DOCID_TO_PAGE_TYPE[doc_id] = page_type # 存储页面类型
        
        tokens = text_tokens + title_tokens * TITLE_TOKEN_DUP
        _DOC_LEN[doc_id] = len(tokens)
        total_len += len(tokens)

        term_positions = defaultdict(list)
        for i, term in enumerate(tokens):
            term_positions[term].append(i)
        
        for term, positions in term_positions.items():
            _POSTINGS[term].append((doc_id, positions))
        
        doc_id += 1

    _NUM_DOCS = doc_id
    _AVG_DL = (total_len / _NUM_DOCS) if _NUM_DOCS > 0 else 1.0
    _DF = {term: len(postings) for term, postings in _POSTINGS.items()}

    print("正在构建链接图并计算PageRank...")
    link_graph = {
        from_id: [url_to_docid[link] for link in links if link in url_to_docid]
        for from_id, links in docid_to_hyperlinks.items()
    }
    _PAGERANK_SCORES = _calculate_pagerank_optimized(link_graph, _NUM_DOCS)
    
    _INDEX_READY = True
    print(f"索引构建完成，共索引 {doc_id} 个文档。")


def _bm25_idf(df: int, N: int) -> float:
    return math.log((N - df + 0.5) / (df + 0.5) + 1.0)


def _score_bm25(query_terms: List[str]) -> Dict[int, float]:
    scores = defaultdict(float)
    if not query_terms or _NUM_DOCS == 0: return scores
    
    q_tf_counter = Counter([t for t in query_terms if t in _POSTINGS])
    for term, qf in q_tf_counter.items():
        postings = _POSTINGS.get(term, [])
        df = _DF.get(term, 0)
        if df == 0: continue
        
        idf = _bm25_idf(df, _NUM_DOCS)
        for doc_id, positions in postings:
            tf = len(positions)
            dl = _DOC_LEN.get(doc_id, 0)
            if _AVG_DL == 0: continue
            
            denom = tf + K1 * (1 - B + B * (dl / _AVG_DL))
            contrib = idf * (tf * (K1 + 1)) / (denom + 1e-12)
            scores[doc_id] += contrib
            
    return scores


def _extract_key_terms(query: str) -> List[str]:
    # 对于短查询，我们直接使用分词结果以保留所有信息
    if len(query) < 10:
        return _tokenize(query)
    key_terms = jieba.analyse.extract_tags(query, topK=5, withWeight=False)
    return key_terms if key_terms else _tokenize(query)


def evaluate(query: str) -> list:
    global _INDEX_READY
    if not _INDEX_READY:
        _build_index()

    q_tokens = _extract_key_terms(query)
    if not q_tokens: return [""] * 20

    scores = _score_bm25(q_tokens)
    if not scores: return [""] * 20

    final_scores = scores.copy()

    # --- 【优化】最长连续短语奖励 ---
    if len(q_tokens) > 1:
        postings_map = defaultdict(dict)
        for term in q_tokens:
            for doc_id, positions in _POSTINGS.get(term, []):
                if doc_id in scores:
                    postings_map[doc_id][term] = set(positions)
        
        for doc_id in scores:
            doc_positions = postings_map.get(doc_id)
            if not doc_positions or len(doc_positions) < len(q_tokens):
                continue
            
            max_phrase_len = 0
            for start_pos in doc_positions.get(q_tokens[0], set()):
                current_len = 1
                for i in range(1, len(q_tokens)):
                    next_pos = start_pos + i
                    if next_pos in doc_positions.get(q_tokens[i], set()):
                        current_len += 1
                    else:
                        break
                if current_len > max_phrase_len:
                    max_phrase_len = current_len
            
            if max_phrase_len > 1:
                bonus = 1 + PHRASE_BONUS_WEIGHT * (max_phrase_len ** 2)
                final_scores[doc_id] *= bonus

    # 【新增】目录页惩罚
    for doc_id in final_scores:
        if _DOCID_TO_PAGE_TYPE.get(doc_id) == 'directory':
            final_scores[doc_id] *= DIRECTORY_PAGE_PENALTY
            
    # 最终排序：(综合分数, PageRank分数)
    ranked_doc_ids = sorted(
        final_scores.keys(), 
        key=lambda doc_id: (final_scores.get(doc_id, 0), _PAGERANK_SCORES.get(doc_id, 0)),
        reverse=True
    )

    urls = []
    seen = set()
    for doc_id in ranked_doc_ids:
        u = _DOCID_TO_URL.get(doc_id)
        if u and u not in seen:
            seen.add(u)
            urls.append(u)
        
        if len(urls) >= 20: break
    
    urls.extend([""] * (20 - len(urls)))
    return urls

