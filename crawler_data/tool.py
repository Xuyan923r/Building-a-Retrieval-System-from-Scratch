import os
import shutil
import csv

# 输入文件夹（替换成你自己的路径）
INPUT_DIRS = [
    "/Users/xiexuyan/Desktop/人工智能综合设计/Day2/crawler_data_keyan",
    "/Users/xiexuyan/Desktop/人工智能综合设计/Day2/crawler_data_xsc"
]
OUTPUT_DIR = "/Users/xiexuyan/Desktop/人工智能综合设计/Day2/crawler_data"

HTML_DIR = os.path.join(OUTPUT_DIR, "html_output")
DATA_DIR = os.path.join(OUTPUT_DIR, "data_output")
LOG_FILE = os.path.join(OUTPUT_DIR, "crawled_log.csv")

# 创建输出目录
os.makedirs(HTML_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 初始化日志
with open(LOG_FILE, "w", encoding="utf-8", newline="") as log_f:
    writer = csv.writer(log_f)
    writer.writerow(["ID", "URL", "HTML_File", "JSON_File"])

count = 0

for input_dir in INPUT_DIRS:
    log_path = os.path.join(input_dir, "crawled_log.csv")
    html_path = os.path.join(input_dir, "html_output")
    data_path = os.path.join(input_dir, "data_output")

    if not os.path.exists(log_path):
        print(f"⚠️ 跳过 {input_dir}, 未找到 crawled_log.csv")
        continue

    with open(log_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # 跳过表头
        for row in reader:
            count += 1
            old_id, url, html_file, json_file = row

            # 新文件名
            new_html = f"{count}.html"
            new_json = f"{count}.json"

            # 复制 HTML
            old_html_path = os.path.join(html_path, html_file)
            if os.path.exists(old_html_path):
                shutil.copy(old_html_path, os.path.join(HTML_DIR, new_html))

            # 复制 JSON
            old_json_path = os.path.join(data_path, json_file)
            if os.path.exists(old_json_path):
                shutil.copy(old_json_path, os.path.join(DATA_DIR, new_json))

            # 写入新日志
            with open(LOG_FILE, "a", encoding="utf-8", newline="") as log_f:
                writer = csv.writer(log_f)
                writer.writerow([count, url, new_html, new_json])

print(f"✅ 合并完成，共 {count} 个页面")
print(f"合并后的日志文件: {LOG_FILE}")
