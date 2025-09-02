# 导入所需库
import os
import time
import requests
import json
import jieba
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from url_normalize import url_normalize

# --- 1. 配置区 ---
SEED_URLS = ['http://xsc.ruc.edu.cn/']
BASE_DOMAIN = 'xsc.ruc.edu.cn'   # 只允许的域名

OUTPUT_DIR = "/Users/xiexuyan/Desktop/人工智能综合设计/Day2/crawler_data_xsc"
HTML_DIR = os.path.join(OUTPUT_DIR, "html_output")
DATA_DIR = os.path.join(OUTPUT_DIR, "data_output")
VISITED_URLS_FILE = os.path.join(OUTPUT_DIR, "visited_urls.txt")
LOG_FILE = os.path.join(OUTPUT_DIR, "crawled_log.csv")

MAX_CRAWL_COUNT = -1
WAIT_TIME = 2
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/91.0.4472.124 Safari/537.36')
}

# --- 域名过滤函数 ---
def is_allowed(u: str) -> bool:
    """只允许 xsc.ruc.edu.cn 域名下的 URL"""
    if not u:
        return False
    try:
        nu = url_normalize(u)
        parsed = urlparse(nu)
        return parsed.netloc == BASE_DOMAIN
    except:
        return False

# --- 判断是否是 HTML ---
def is_html_response(resp, url):
    content_type = resp.headers.get("Content-Type", "").lower()
    if "text/html" in content_type:
        return True
    # 补充扩展名检查（兜底）
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if ext in ["", ".html", ".htm", ".php", ".asp", ".aspx", ".jsp"]:
        return True
    return False

# --- 核心功能函数 ---
def get_html(url, headers={}, timeout=10):
    try:
        print(f"正在尝试抓取: {url}")
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        r.raise_for_status()

        if not is_html_response(r, url):
            print(f"跳过非HTML文件: {url} (Content-Type={r.headers.get('Content-Type')})")
            return None

        r.encoding = r.apparent_encoding or 'UTF-8'
        print(f"成功获取: {url}")
        return r.text
    except requests.exceptions.RequestException as e:
        print(f"抓取 {url} 时发生错误: {e}")
        return None

def crawl_all_urls(soup, base_url):
    """从页面解析所有站内URL"""
    all_links = set()
    for anchor in soup.find_all('a', href=True):
        href = anchor['href'].strip()
        if not href or href.startswith('#') or href.lower().startswith('javascript:'):
            continue
        full_url = urljoin(base_url, href)
        normalized_url = url_normalize(full_url)
        if is_allowed(normalized_url):
            all_links.add(normalized_url)
    return list(all_links)

def load_visited_urls(filepath):
    if not os.path.exists(filepath):
        return set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        print(f"加载已访问URL文件失败: {e}")
        return set()

def extract_and_process_data(html_doc, url):
    if not html_doc:
        return None
    soup = BeautifulSoup(html_doc, 'html.parser')

    title = soup.title.string.strip() if soup.title and soup.title.string else "无标题"

    # 去除非正文
    for element in soup(['script', 'style', 'head', 'title', 'meta', '[document]']):
        element.decompose()
    text = ' '.join(soup.stripped_strings)

    hyperlinks = crawl_all_urls(soup, url)

    title_segmented = list(jieba.cut_for_search(title))
    text_segmented = list(jieba.cut_for_search(text))

    extracted_data = {
        'url': url,
        'title': title,
        'title_segmented': title_segmented,
        'text': text,
        'text_segmented': text_segmented,
        'hyperlinks': hyperlinks
    }
    return extracted_data

# --- 主执行逻辑 ---
if __name__ == "__main__":
    for directory in [HTML_DIR, DATA_DIR]:
        os.makedirs(directory, exist_ok=True)

    all_urlset = load_visited_urls(VISITED_URLS_FILE)
    print(f"已加载 {len(all_urlset)} 个已访问的URL。")

    queue = []
    for url in SEED_URLS:
        normalized_url = url_normalize(url)
        if is_allowed(normalized_url) and normalized_url not in all_urlset:
            queue.append(normalized_url)
            all_urlset.add(normalized_url)
        else:
            print(f"跳过不满足域名规则或已存在的种子URL: {url}")

    count = 0
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        with open(LOG_FILE, 'w', encoding='utf-8', newline='') as log_f:
            log_f.write("ID,URL,HTML_File,JSON_File\n")

    with open(LOG_FILE, 'a', encoding='utf-8', newline='') as log_f:
        while queue and (MAX_CRAWL_COUNT == -1 or count < MAX_CRAWL_COUNT):
            current_url = queue.pop(0)

            if not is_allowed(current_url):
                print(f"跳过非允许域名URL: {current_url}")
                continue

            html_doc = get_html(current_url, headers=HEADERS)

            if html_doc:
                count += 1
                html_file_name = f"{count}.html"
                json_file_name = f"{count}.json"
                html_file_path = os.path.join(HTML_DIR, html_file_name)
                json_file_path = os.path.join(DATA_DIR, json_file_name)

                try:
                    with open(html_file_path, 'w', encoding='utf-8') as f:
                        f.write(html_doc)
                except Exception as e:
                    print(f"保存HTML失败: {e}")

                try:
                    data = extract_and_process_data(html_doc, current_url)
                    if data:
                        with open(json_file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=4)
                except Exception as e:
                    print(f"保存JSON失败: {e}")

                log_f.write(f'{count},"{current_url}","{html_file_name}","{json_file_name}"\n')

                soup = BeautifulSoup(html_doc, 'html.parser')
                new_urls = crawl_all_urls(soup, current_url)
                for new_url in new_urls:
                    if is_allowed(new_url) and new_url not in all_urlset:
                        all_urlset.add(new_url)
                        queue.append(new_url)
                        print(f"发现新URL并加入队列: {new_url}")

            print(f"--- 抓取暂停 {WAIT_TIME} 秒 ---")
            time.sleep(WAIT_TIME)

    with open(VISITED_URLS_FILE, 'w', encoding='utf-8') as f:
        for url in sorted(list(all_urlset)):
            f.write(url + '\n')

    print(f"\n本次运行共抓取了 {count} 个页面，总共发现 {len(all_urlset)} 个URL。")
