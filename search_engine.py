"""
search_engine.py

功能:
- 搜索引擎函数
- 排序采用“BM25（含短语奖励与目录降权） + PageRank 线性融合”。
- 短语奖励支持“有序 + 小窗口”匹配，鲁棒容错分词噪声。
- PageRank 做了实用优化：预计算入链、悬挂节点(dangling)质量回流、每轮归一化、早停。
- 索引惰性加载：首次查询时自动构建。

使用:
- 与评测客户端 client.py 放置在同一目录。
- 直接运行 client.py 即可。
"""
import os
import re
import json
import math
import glob
from bisect import bisect_right
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
import jieba
import jieba.analyse


# ===================== 配置区 =====================

# 数据源目录，爬取的数据应存放于此
DEFAULT_JSON_DIRS = [
    "/Users/xiexuyan/Desktop/人工智能综合设计/IR_System/crawler_data/data_output"
]

ALLOWED_PREFIXES = (
    "http://keyan.ruc.edu.cn/",  "https://keyan.ruc.edu.cn/",
    "http://xsc.ruc.edu.cn/",    "https://xsc.ruc.edu.cn/",
)


# --- 模型参数 ---

# 提高标题中词的权重，通过增加其在文档中的计数实现
TITLE_TOKEN_DUP = 3

# BM25 的标准经验参数
K1 = 1.5
B = 0.75

# 为匹配了连续查询短语的文档设置奖励乘数
PHRASE_BONUS_WEIGHT = 0.5

# 短语有序匹配的窗口大小（2 表示允许相邻或中间隔 1 个词）
PHRASE_WINDOW = 2

# 目录页降权
DIRECTORY_PAGE_PENALTY = 0.8

# BM25 与 PageRank 线性融合权重（BM25为主）
ALPHA = 0.95

# 自定义停用词表
STOPWORDS = {
    # 通用停用词
    "的", "了", "和", "是", "在", "与", "及", "或", "并", "为", "而", "对", "以",
    "以及", "等", "各", "其", "也", "都", "更", "再", "很", "着", "于", "中",
    "你", "我", "他", "她", "它", "他们", "我们", "你们","……", "地", "得",
    # 网站结构与功能词
    "首页", "通知", "公告", "附件", "下载", "链接", "简介", "版权", "版权所有",
    "友情链接", "微信", "官网", "网站", "搜索", "登陆", "通讯录",
    # 高频低信息量词
    "我校", "学校", "相关", "情况", "进行", "开展", "关于", "要求", "提供", "组织",
    # 分词错误残留
    "京市", "公室", "国人",
    # 无意义符号
    "cn", "edu", "ruc", "http", "Copyright", "..."
}

# ==================================================

# 全局变量，用于存储索引。使用惰性加载，仅在首次查询时构建。
_INDEX_READY = False
_DOCID_TO_URL: Dict[int, str] = {}
_DOCID_TO_PAGE_TYPE: Dict[int, str] = {}
# 倒排列表: term -> List[(doc_id, positions)]
_POSTINGS: Dict[str, List[Tuple[int, List[int]]]] = defaultdict(list)
_DF: Dict[str, int] = {}
_DOC_LEN: Dict[int, int] = {}
_PAGERANK_SCORES: Dict[int, float] = {}
_AVG_DL: float = 1.0
_NUM_DOCS: int = 0

# 用于清洗文本中的标点符号和空白字符
_PUNCT_RE = re.compile(r"[\s\u3000，。、“”‘’：；？！《》—\-—_,.;:!?()（）\[\]【】{}<>~`@#$%^&*+=|\\/]+")


def _discover_json_dirs() -> List[str]:
    """发现并验证包含 JSON 数据文件的目录列表。"""
    # 优先使用环境变量 CRAWL_JSON_DIRS，其次使用默认配置
    env = os.environ.get("CRAWL_JSON_DIRS", "").strip()
    dirs = [p.strip() for p in env.split(":") if p.strip() and os.path.isdir(p)]
    if not dirs:
        dirs = [p for p in DEFAULT_JSON_DIRS if os.path.isdir(p)]

    # 确保返回的目录中确实存在 JSON 文件
    valid_dirs = [d for d in dirs if glob.glob(os.path.join(d, "*.json"))]
    if not valid_dirs:
        raise FileNotFoundError("未能定位到任何包含 .json 文件的数据目录。")
    return valid_dirs


def _is_allowed_url(u: str) -> bool:
    """检查 URL 是否属于允许的域名。"""
    if not u:
        return False
    return any(u.startswith(pref) for pref in ALLOWED_PREFIXES)


def _tokenize(text: str) -> List[str]:
    """对文本进行清洗、分词和去停用词处理。"""
    if not text:
        return []
    cleaned = _PUNCT_RE.sub(" ", text.strip())
    tokens = [t.strip().lower() for t in jieba.cut_for_search(cleaned) if t.strip()]
    return [t for t in tokens if t not in STOPWORDS]


def _iter_docs(json_dirs: List[str]):
    """迭代器，用于逐一读取和解析所有合法的 JSON 文档。"""
    for d in json_dirs:
        # 按文件名中的数字排序，确保每次索引构建的 doc_id 是确定的
        files = sorted(
            glob.glob(os.path.join(d, "*.json")),
            key=lambda f: int(os.path.splitext(os.path.basename(f))[0])
        )
        for fp in files:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                # 跳过损坏或格式错误的 JSON 文件
                continue

            url = data.get("url", "")
            if not _is_allowed_url(url):
                continue

            title_tokens = _tokenize(data.get("title", ""))
            text_tokens = _tokenize(data.get("text", ""))
            hyperlinks = data.get("hyperlinks", [])
            # 默认为 'content'，以兼容没有 page_type 字段的旧数据
            page_type = data.get("page_type", "content")

            yield url, title_tokens, text_tokens, hyperlinks, page_type


def _calculate_pagerank_optimized(
    link_graph: Dict[int, List[int]],
    num_docs: int,
    damping: float = 0.85,
    max_iter: int = 100
) -> Dict[int, float]:
    """
    PageRank（优化版）：
    - 预计算入链 in_links；
    - 显式处理悬挂节点（出度=0）的质量回流；
    - 每轮做一次归一化（sum=1），数值更稳；
    - 收敛阈值早停。
    """
    if num_docs == 0:
        return {}

    # 初值均匀分配
    ranks = {i: 1.0 / num_docs for i in range(num_docs)}
    # 出度
    out_degrees = {i: len(link_graph.get(i, [])) for i in range(num_docs)}

    # 预计算入链
    in_links = defaultdict(list)
    for from_id, to_ids in link_graph.items():
        for to_id in to_ids:
            in_links[to_id].append(from_id)

    for _ in range(max_iter):
        new_ranks: Dict[int, float] = {}
        delta = 0.0

        # 悬挂节点（出度=0）的总质量
        dangling_sum = sum(ranks[j] for j in range(num_docs) if out_degrees.get(j, 0) == 0)

        base = (1.0 - damping) / num_docs                     # 随机跳转的均匀注入
        leak = damping * dangling_sum / num_docs              # 悬挂质量回流给全体

        # 更新每个节点的 rank
        for i in range(num_docs):
            rank_sum = 0.0
            for j in in_links.get(i, []):
                deg = out_degrees.get(j, 1) or 1  # 防除零
                rank_sum += ranks[j] / deg
            new_val = base + leak + damping * rank_sum
            new_ranks[i] = new_val
            delta += abs(new_val - ranks[i])

        # 归一化（可选但推荐）：让总和=1，提升数值稳定
        s = sum(new_ranks.values()) or 1.0
        for i in range(num_docs):
            new_ranks[i] /= s

        ranks = new_ranks
        if delta < 1e-6:
            break

    return ranks


def _build_index():
    """执行索引构建全流程，包括倒排索引、PageRank 等。"""
    global _INDEX_READY, _DOCID_TO_URL, _POSTINGS, _DF, _DOC_LEN, _AVG_DL, _NUM_DOCS, _PAGERANK_SCORES, _DOCID_TO_PAGE_TYPE

    print("首次查询，正在构建索引...")
    json_dirs = _discover_json_dirs()

    doc_id, total_len = 0, 0
    url_to_docid, docid_to_hyperlinks = {}, {}

    # 第一次遍历：构建基础索引和元数据
    for url, title_tokens, text_tokens, hyperlinks, page_type in _iter_docs(json_dirs):
        url_to_docid[url] = doc_id
        docid_to_hyperlinks[doc_id] = hyperlinks
        _DOCID_TO_URL[doc_id] = url
        _DOCID_TO_PAGE_TYPE[doc_id] = page_type

        tokens = text_tokens + title_tokens * TITLE_TOKEN_DUP
        _DOC_LEN[doc_id] = len(tokens)
        total_len += len(tokens)

        term_positions = defaultdict(list)
        for i, term in enumerate(tokens):
            term_positions[term].append(i)

        for term, positions in term_positions.items():
            _POSTINGS[term].append((doc_id, positions))

        doc_id += 1

    # 计算全局统计量
    _NUM_DOCS = doc_id
    _AVG_DL = (total_len / _NUM_DOCS) if _NUM_DOCS > 0 else 1.0
    _DF = {term: len(postings) for term, postings in _POSTINGS.items()}

    # 构建链接图并计算 PageRank
    print("正在计算 PageRank...")
    link_graph = {
        from_id: [url_to_docid[link] for link in links if link in url_to_docid]
        for from_id, links in docid_to_hyperlinks.items()
    }
    _PAGERANK_SCORES = _calculate_pagerank_optimized(link_graph, _NUM_DOCS)

    _INDEX_READY = True    # 惰性加载完成
    print(f"索引构建完成，共索引 {doc_id} 个文档。")


def _bm25_idf(df: int, N: int) -> float:
    """计算 BM25 的 IDF 部分。"""
    return math.log((N - df + 0.5) / (df + 0.5) + 1.0)


def _score_bm25(query_terms: List[str]) -> Dict[int, float]:
    """根据给定的查询词，计算所有相关文档的 BM25 分数。"""
    scores = defaultdict(float)
    if not query_terms or _NUM_DOCS == 0:
        return scores

    q_tf_counter = Counter([t for t in query_terms if t in _POSTINGS])
    for term, _ in q_tf_counter.items():
        postings = _POSTINGS.get(term, [])
        df = _DF.get(term, 0)
        if df == 0:
            continue

        idf = _bm25_idf(df, _NUM_DOCS)
        for doc_id, positions in postings:
            tf = len(positions)
            dl = _DOC_LEN.get(doc_id, 0)

            # BM25 核心评分公式
            denom = tf + K1 * (1 - B + B * (dl / _AVG_DL))
            contrib = idf * (tf * (K1 + 1)) / (denom + 1e-12)  # 加 epsilon 避免除零
            scores[doc_id] += contrib

    return scores


def _extract_key_terms(query: str) -> List[str]:
    """
    根据查询长度智能选择分词策略。
    短查询使用全分词，长查询提取关键词以提高信噪比。
    """
    if len(query) < 10:
        return _tokenize(query)

    key_terms = jieba.analyse.extract_tags(query, topK=5, withWeight=False)
    # 若无法提取关键词（如查询全由停用词组成），则回退到普通分词
    return key_terms if key_terms else _tokenize(query)


def _max_windowed_phrase_len(doc_positions: Dict[str, List[int]], q_tokens: List[str], window: int) -> int:
    """
    计算窗口有序匹配下的最长“短语”长度。
    规则：保持查询词的顺序；从前到后，后一个词的位置需在 (prev_pos, prev_pos + window] 区间内。
    贪心：选取满足条件的“最早可用位置”，通常能留出更多空间给后续词。
    """
    # 若缺词，直接 0
    if any(t not in doc_positions or not doc_positions[t] for t in q_tokens):
        return 0

    # 预先排序，便于二分查找
    sorted_pos = {t: sorted(doc_positions[t]) for t in q_tokens}
    first_positions = sorted_pos[q_tokens[0]]

    max_len = 0
    for start in first_positions:
        prev = start
        length = 1
        # 依次扩展 q_tokens[1:]
        for i in range(1, len(q_tokens)):
            cur_list = sorted_pos[q_tokens[i]]
            # 在 cur_list 中二分找 > prev 的最小位置
            idx = bisect_right(cur_list, prev)
            if idx < len(cur_list) and cur_list[idx] <= prev + window:
                prev = cur_list[idx]
                length += 1
            else:
                break
        if length > max_len:
            max_len = length

        # 已达最大可能值，可提前退出
        if max_len == len(q_tokens):
            break

    return max_len


def evaluate(query: str) -> list:
    """
    搜索引擎的评测主入口。
    """
    if not _INDEX_READY:
        _build_index()

    q_tokens = _extract_key_terms(query)
    if not q_tokens:
        return [""] * 20

    # 1) 基础 BM25 分数
    scores = _score_bm25(q_tokens)
    if not scores:
        return [""] * 20

    final_scores = scores.copy()

    # 2) 窗口有序短语奖励
    if len(q_tokens) > 1:
        postings_map = defaultdict(dict)
        for term in q_tokens:
            for doc_id, positions in _POSTINGS.get(term, []):
                if doc_id in scores:
                    postings_map[doc_id][term] = list(positions)

        for doc_id in scores:
            doc_positions = postings_map.get(doc_id)
            if not doc_positions or len(doc_positions) < len(q_tokens):
                continue

            # 计算窗口有序匹配下的最长长度
            max_phrase_len = _max_windowed_phrase_len(doc_positions, q_tokens, PHRASE_WINDOW)

            # 奖励大小与匹配长度的平方成正比
            if max_phrase_len > 1:
                bonus = 1 + PHRASE_BONUS_WEIGHT * (max_phrase_len ** 2)
                final_scores[doc_id] *= bonus

    # 3) 目录页降权
    for doc_id in final_scores:
        if _DOCID_TO_PAGE_TYPE.get(doc_id) == 'directory':
            final_scores[doc_id] *= DIRECTORY_PAGE_PENALTY

    # 4) 线性融合排序：ALPHA * normalized(final_scores) + (1-ALPHA) * normalized(PageRank)
    # 归一化，防止量纲差异导致某一方“碾压”
    max_f = max(final_scores.values()) if final_scores else 1.0
    max_p = max(_PAGERANK_SCORES.values(), default=0.0)
    if not max_p or max_p <= 0.0:
        max_p = 1.0  # 避免除零或图无边导致的全 0

    def _combined(d: int) -> float:
        f = final_scores.get(d, 0.0) / max_f
        p = _PAGERANK_SCORES.get(d, 0.0) / max_p
        return ALPHA * f + (1.0 - ALPHA) * p

    ranked_doc_ids = sorted(final_scores.keys(), key=_combined, reverse=True)

    # 5) 组织返回（Top-20，不足补空串）
    urls = [_DOCID_TO_URL.get(doc_id) for doc_id in ranked_doc_ids]
    urls = [u for u in urls if u][:20]
    urls.extend([""] * (20 - len(urls)))
    return urls
