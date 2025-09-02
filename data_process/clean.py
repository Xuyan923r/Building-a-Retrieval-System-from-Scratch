# -*- coding: utf-8 -*-
"""
process_and_dedupe.py

功能:
- 读取一个已有的、可能包含重复项的爬虫数据目录。
- 应用URL去参数化逻辑，识别出唯一的页面。
- 将唯一的HTML和JSON文件复制到新的、干净的目录中，并重新编号。
- 生成一份与新目录完全对应的干净日志文件。

使用:
1. 将此脚本放置在与 OUTPUT_DIR 同级的目录中。
2. 确保下面的路径配置正确。
3. 运行 `python process_and_dedupe.py`。
"""
import os
import json
import glob
import shutil
from urllib.parse import urlparse, urlunparse
from url_normalize import url_normalize

# --- 1. 配置区 ---

# 【重要】请确保这些路径是您当前的原始数据存放路径
# 这是包含 html_output 和 data_output 的父目录
BASE_DATA_DIR = "/Users/xiexuyan/Desktop/人工智能综合设计/Project/crawler_data"

# 原始数据目录
OLD_HTML_DIR = os.path.join(BASE_DATA_DIR, "html_output")
OLD_DATA_DIR = os.path.join(BASE_DATA_DIR, "data_output")

# 【重要】处理完成后，干净的数据将存放在这里
CLEANED_OUTPUT_DIR = "/Users/xiexuyan/Desktop/人工智能综合设计/Project/crawler_data_cleaned"
NEW_HTML_DIR = os.path.join(CLEANED_OUTPUT_DIR, "html_output")
NEW_DATA_DIR = os.path.join(CLEANED_OUTPUT_DIR, "data_output")
NEW_LOG_FILE = os.path.join(CLEANED_OUTPUT_DIR, "crawled_log_cleaned.csv")


# --- 2. 核心函数 (与爬虫脚本保持一致) ---

def normalize_and_clean_url(u: str) -> str:
    """
    URL规范化函数，移除查询参数和片段标识。
    """
    try:
        normalized_url = url_normalize(u)
        parts = urlparse(normalized_url)
        cleaned_url = urlunparse((parts.scheme, parts.netloc, parts.path, '', '', ''))
        if cleaned_url.endswith('/'):
            return cleaned_url[:-1]
        return cleaned_url
    except Exception:
        return u

# --- 3. 主执行逻辑 ---

def process_data():
    """
    执行清理和去重的主要函数。
    """
    print("开始处理已爬取的数据...")
    
    # 创建新的输出目录
    for directory in [NEW_HTML_DIR, NEW_DATA_DIR]:
        os.makedirs(directory, exist_ok=True)
    print(f"已创建新的输出目录: {CLEANED_OUTPUT_DIR}")

    # 用于跟踪已经处理过的、清理后的URL，确保唯一性
    seen_clean_urls = set()
    
    # 新的文件ID计数器
    new_id_counter = 1

    # 打开新的日志文件准备写入
    with open(NEW_LOG_FILE, 'w', encoding='utf-8', newline='') as log_f:
        log_f.write("ID,URL,Original_URL,HTML_File,JSON_File\n")
        
        # 优先遍历JSON文件，因为它们包含URL信息
        # 使用glob找到所有旧的json文件，并按数字顺序排序
        old_json_files = sorted(
            glob.glob(os.path.join(OLD_DATA_DIR, "*.json")),
            key=lambda f: int(os.path.splitext(os.path.basename(f))[0])
        )

        total_files = len(old_json_files)
        print(f"发现 {total_files} 个原始json文件，开始去重处理...")

        for i, old_json_path in enumerate(old_json_files):
            print(f"正在处理: {i + 1}/{total_files} - {os.path.basename(old_json_path)}", end='\r')

            try:
                with open(old_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"\n警告: 读取文件 {old_json_path} 失败: {e}")
                continue

            original_url = data.get('url')
            if not original_url:
                print(f"\n警告: 文件 {old_json_path} 中没有找到URL。")
                continue

            # 应用与爬虫相同的清理逻辑
            clean_url = normalize_and_clean_url(original_url)

            # 如果这个清理后的URL我们已经处理过了，就跳过
            if clean_url in seen_clean_urls:
                continue
            
            # 如果是新的唯一URL，我们处理它
            seen_clean_urls.add(clean_url)

            # --- 开始复制和重命名文件 ---
            
            # 1. 找到对应的原始HTML文件
            original_id_str = os.path.splitext(os.path.basename(old_json_path))[0]
            old_html_path = os.path.join(OLD_HTML_DIR, f"{original_id_str}.html")

            if not os.path.exists(old_html_path):
                print(f"\n警告: 找不到对应的HTML文件 {old_html_path}，跳过。")
                continue

            # 2. 定义新文件的路径
            new_html_filename = f"{new_id_counter}.html"
            new_json_filename = f"{new_id_counter}.json"
            new_html_path = os.path.join(NEW_HTML_DIR, new_html_filename)
            new_json_path = os.path.join(NEW_DATA_DIR, new_json_filename)

            # 3. 复制HTML文件
            shutil.copy(old_html_path, new_html_path)

            # 4. 更新JSON内容并保存
            data['url'] = clean_url  # 将URL更新为清理后的版本
            data['original_url'] = original_url # 保留原始URL作为参考
            with open(new_json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)

            # 5. 写入新的日志记录
            log_f.write(f'{new_id_counter},"{clean_url}","{original_url}","{new_html_filename}","{new_json_filename}"\n')

            # 6. 增加新ID计数器
            new_id_counter += 1

    print("\n\n--- 处理完成 ---")
    print(f"原始文件总数: {total_files}")
    print(f"清理后的唯一文件数: {new_id_counter - 1}")
    print(f"新的干净数据已保存在: {CLEANED_OUTPUT_DIR}")

if __name__ == "__main__":
    process_data()
