# -*- coding: utf-8 -*-
"""
continue_crawler.py

功能:
- 智能地从一个已经清理过的、干净的数据目录继续爬取。
- 它会读取所有已存在的JSON文件，从中发现新的、尚未爬取的URL作为线索。
- 在整个续爬过程中，始终使用URL去参数化逻辑，保证数据质量。

使用:
1. 确保下面的 CLEANED_DATA_DIR 路径正确。
2. 运行 `python continue_crawler.py` 即可开始续爬。
"""
import os
import time
import requests
import json
import jieba
import glob
import csv
from urllib.parse import urlparse, urljoin, urlunparse
from bs4 import BeautifulSoup
from url_normalize import url_normalize

# --- 1. 配置区 ---

# 【重要】请将此路径设置为您存放干净数据的目录
CLEANED_DATA_DIR = "/Users/xiexuyan/Desktop/人工智能综合设计/Project/crawler_data"

# 种子URL和允许的域名
SEED_URLS = ['http://keyan.ruc.edu.cn/', 'http://xsc.ruc.edu.cn/']
ALLOWED_DOMAINS = {'keyan.ruc.edu.cn', 'xsc.ruc.edu.cn'}

# 从主目录衍生出其他路径
HTML_DIR = os.path.join(CLEANED_DATA_DIR, "html_output")
DATA_DIR = os.path.join(CLEANED_DATA_DIR, "data_output")
# 【注意】我们会读取日志文件来生成已访问列表
LOG_FILE = os.path.join(CLEANED_DATA_DIR, "crawled_log.csv")
# 【新增】定义新的visited_urls.txt路径，程序运行后会自动生成
VISITED_URLS_FILE = os.path.join(CLEANED_DATA_DIR, "visited_urls.txt")


MAX_CRAWL_COUNT_THIS_RUN = -1 # 本次运行最多抓取的新页面数 (-1为不限制)
WAIT_TIME = 1
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/91.0.4472.124 Safari/537.36')
}

# --- 2. 核心函数 (与清理脚本和新爬虫保持一致) ---

def normalize_and_clean_url(u: str) -> str:
    try:
        normalized_url = url_normalize(u)
        parts = urlparse(normalized_url)
        cleaned_url = urlunparse((parts.scheme, parts.netloc, parts.path, '', '', ''))
        return cleaned_url.rstrip('/')
    except Exception:
        return u.rstrip('/')

def is_allowed(u: str) -> bool:
    if not u: return False
    try:
        parsed = urlparse(url_normalize(u))
        return parsed.netloc in ALLOWED_DOMAINS
    except:
        return False

def is_html_response(resp, url):
    content_type = resp.headers.get("Content-Type", "").lower()
    if "text/html" in content_type: return True
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    if ext in ["", ".html", ".htm", ".php", ".asp", ".aspx", ".jsp"]: return True
    return False

def get_html(url, headers={}, timeout=10):
    try:
        print(f"正在尝试抓取: {url}")
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        r.raise_for_status()
        if not is_html_response(r, url):
            print(f"跳过非HTML文件: {url}")
            return None
        r.encoding = r.apparent_encoding or 'UTF-8'
        print(f"成功获取: {url}")
        return r.text
    except requests.exceptions.RequestException as e:
        print(f"抓取 {url} 时发生错误: {e}")
        return None

def crawl_all_urls(soup, base_url):
    all_links = set()
    for anchor in soup.find_all('a', href=True):
        href = anchor['href'].strip()
        if not href or href.startswith('#') or href.lower().startswith('javascript:'):
            continue
        full_url = urljoin(base_url, href)
        if is_allowed(full_url):
            cleaned_url = normalize_and_clean_url(full_url)
            all_links.add(cleaned_url)
    return list(all_links)

# --- 【重要修改】 ---
def load_visited_urls_from_log(log_filepath):
    """
    从CSV日志文件读取第二列的URL来构建已访问集合。
    """
    visited = set()
    if not os.path.exists(log_filepath):
        return visited
    
    try:
        with open(log_filepath, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            next(reader) # 跳过表头
            for row in reader:
                if len(row) > 1 and row[1]:
                    # 假设第二列(index 1)是清理后的URL
                    visited.add(row[1].strip())
        print(f"成功从日志文件 {os.path.basename(log_filepath)} 加载了 {len(visited)} 个URL。")
    except Exception as e:
        print(f"从日志文件加载URL失败: {e}")
        
    return visited


def extract_and_process_data(html_doc, url):
    if not html_doc: return None
    soup = BeautifulSoup(html_doc, 'html.parser')
    title = soup.title.string.strip() if soup.title and soup.title.string else "无标题"
    for element in soup(['script', 'style', 'head', 'title', 'meta', '[document]']):
        element.decompose()
    text = ' '.join(soup.stripped_strings)
    hyperlinks = crawl_all_urls(soup, url)
    title_segmented = list(jieba.cut_for_search(title))
    text_segmented = list(jieba.cut_for_search(text))
    return {
        'url': url, 'title': title, 'title_segmented': title_segmented,
        'text': text, 'text_segmented': text_segmented, 'hyperlinks': hyperlinks
    }

def get_start_id(data_dir: str) -> int:
    if not os.path.isdir(data_dir): return 1
    files = glob.glob(os.path.join(data_dir, "*.json"))
    if not files: return 1
    max_id = 0
    for f in files:
        try:
            num = int(os.path.splitext(os.path.basename(f))[0])
            if num > max_id: max_id = num
        except ValueError: continue
    print(f"发现已有最大文件ID为 {max_id}，将从 {max_id + 1} 开始继续编号。")
    return max_id + 1

# --- 3. 主执行逻辑 ---

if __name__ == "__main__":
    # 确保目录存在
    for directory in [HTML_DIR, DATA_DIR]:
        os.makedirs(directory, exist_ok=True)

    # 1. 【修改】从日志文件加载所有已经访问过的URL
    all_urlset = load_visited_urls_from_log(LOG_FILE)
    if not all_urlset:
        print("警告: 未找到日志文件或文件为空。将从种子URL开始。")

    # 2. 智能构建待爬取队列
    queue = []
    
    # 首先，将种子URL作为备选
    for url in SEED_URLS:
        cleaned_url = normalize_and_clean_url(url)
        if cleaned_url not in all_urlset:
            if cleaned_url not in queue:
                queue.append(cleaned_url)

    # 其次，从已有的JSON文件中发现新大陆
    print("正在从现有文件中扫描新的URL线索...")
    existing_json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    for json_file in existing_json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for link in data.get('hyperlinks', []):
                    # 确保链接也被清理，并检查是否是全新的
                    cleaned_link = normalize_and_clean_url(link)
                    if cleaned_link and cleaned_link not in all_urlset and cleaned_link not in queue:
                        queue.append(cleaned_link)
        except Exception:
            continue
    
    print(f"扫描完成！发现 {len(queue)} 个新的URL待爬取。")
    if not queue:
        print("看起来所有能发现的页面都已爬取完毕。程序退出。")
        # 在退出前，确保visited_urls.txt是最新的
        with open(VISITED_URLS_FILE, 'w', encoding='utf-8') as f:
            for url in sorted(list(all_urlset)):
                f.write(url + '\n')
        exit()

    # 3. 开始续爬循环
    count = get_start_id(DATA_DIR)
    crawled_this_run = 0

    with open(LOG_FILE, 'a', encoding='utf-8', newline='') as log_f:
        while queue and (MAX_CRAWL_COUNT_THIS_RUN == -1 or crawled_this_run < MAX_CRAWL_COUNT_THIS_RUN):
            current_url = queue.pop(0)
            
            # 双重保险，再次检查是否已访问
            if current_url in all_urlset:
                continue

            html_doc = get_html(current_url, headers=HEADERS)

            if html_doc:
                all_urlset.add(current_url) # 抓取成功后才正式标记为已访问
                
                html_file_name = f"{count}.html"
                json_file_name = f"{count}.json"
                html_file_path = os.path.join(HTML_DIR, html_file_name)
                json_file_path = os.path.join(DATA_DIR, json_file_name)

                data = extract_and_process_data(html_doc, current_url)
                if data:
                    try:
                        with open(html_file_path, 'w', encoding='utf-8') as f: f.write(html_doc)
                        with open(json_file_path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
                        
                        # 日志记录的是清理后的URL，Original_URL列留空
                        log_f.write(f'{count},"{current_url}","","{html_file_name}","{json_file_name}"\n')
                        
                        count += 1
                        crawled_this_run += 1
                        
                        new_urls = data.get('hyperlinks', [])
                        for new_url in new_urls:
                            if new_url not in all_urlset and new_url not in queue:
                                queue.append(new_url)
                                print(f"发现新URL并加入队列: {new_url}")

                    except Exception as e:
                        print(f"保存文件时发生错误: {e}")

            print(f"--- 抓取暂停 {WAIT_TIME} 秒 ---")
            time.sleep(WAIT_TIME)

    # 4. 结束前，更新总的已访问URL列表文件
    with open(VISITED_URLS_FILE, 'w', encoding='utf-8') as f:
        for url in sorted(list(all_urlset)):
            f.write(url + '\n')

    print(f"\n--- 续爬完成 ---")
    print(f"本次运行共抓取了 {crawled_this_run} 个新页面。")
    print(f"数据目录中总文件数应为 {count - 1}。")
    print(f"总共发现 {len(all_urlset)} 个URL。")

