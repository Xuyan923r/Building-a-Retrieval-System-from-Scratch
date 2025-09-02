import os
import json
from bs4 import BeautifulSoup

def fix_json_titles_from_html_folders(json_dir, html_dir):
    """
    遍历JSON目录，找到标题错误的JSON文件，
    然后从对应的HTML目录中找到同名HTML文件，提取正确标题并修复JSON。

    Args:
        json_dir (str): 存放JSON文件的根目录路径。
        html_dir (str): 存放对应HTML文件的根目录路径。
    """
    print(f"JSON目录: {json_dir}")
    print(f"HTML目录: {html_dir}")
    print("-" * 30)

    wrong_title = "中国人民大学科研处"
    files_processed = 0
    files_fixed = 0

    # 递归遍历JSON目录
    for root, _, files in os.walk(json_dir):
        for filename in files:
            if filename.endswith('.json'):
                json_path = os.path.join(root, filename)
                files_processed += 1

                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    # 检查标题是否是需要修复的错误标题
                    if data.get('title') and data['title'].strip() == wrong_title:
                        
                        # --- 核心改动：根据JSON路径推断出对应的HTML路径 ---
                        # 1. 获取JSON文件的基础名 (例如 '12345')
                        base_name = os.path.splitext(filename)[0]
                        
                        # 2. 获取JSON文件相对于其根目录的相对路径 (例如 'subfolder/')
                        relative_dir = os.path.relpath(root, json_dir)
                        
                        # 3. 构造对应的HTML文件路径
                        #    如果JSON在'./json_files/subfolder/12345.json'
                        #    则HTML会在'./html_files/subfolder/12345.html'
                        html_path = os.path.join(html_dir, relative_dir, f"{base_name}.html")
                        
                        # ----------------------------------------------------

                        if not os.path.exists(html_path):
                            print(f"[警告] 找到需修复的JSON '{json_path}'")
                            print(f"  -> 但未找到对应的HTML文件: '{html_path}'，已跳过。\n")
                            continue

                        # 读取对应的HTML文件内容
                        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                            html_content = f.read()

                        soup = BeautifulSoup(html_content, 'lxml')
                        new_title = None

                        # 优先策略：从 meta 标签提取
                        meta_tag = soup.find('meta', attrs={'name': 'ArticleTitle'})
                        if meta_tag and meta_tag.get('content'):
                            new_title = meta_tag['content'].strip()

                        # 备用策略：如果 meta 标签找不到，从 h3 标签提取
                        if not new_title:
                            h3_tag = soup.find('h3', class_='xs_tile')
                            if h3_tag:
                                new_title = h3_tag.get_text(strip=True)

                        if new_title and new_title != wrong_title:
                            old_title = data['title']
                            data['title'] = new_title
                            
                            with open(json_path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=4)
                            
                            print(f"[成功] 文件: {filename}")
                            print(f"  - 旧标题: {old_title}")
                            print(f"  + 新标题: {new_title}\n")
                            files_fixed += 1
                        else:
                            print(f"[失败] 文件 '{filename}' 标题错误，但在 '{html_path}' 中未能提取到新标题。\n")

                except Exception as e:
                    print(f"[错误] 处理文件 '{json_path}' 时发生意外: {e}")

    print("=" * 30)
    print("全部处理完成！")
    print(f"总共检查JSON文件数: {files_processed}")
    print(f"成功修复JSON文件数: {files_fixed}")
    print("=" * 30)


if __name__ == "__main__":
    # --- 请在这里配置您的两个文件夹路径 ---
    # 存放JSON文件的根目录
    JSON_ROOT_DIRECTORY = '/Users/xiexuyan/Desktop/人工智能综合设计/IR_System/crawler_data/data_output'  
    # 存放对应HTML文件的根目录
    HTML_ROOT_DIRECTORY = '/Users/xiexuyan/Desktop/人工智能综合设计/IR_System/crawler_data/html_output' 
    # ------------------------------------

    if not os.path.isdir(JSON_ROOT_DIRECTORY):
        print(f"错误：JSON目录 '{JSON_ROOT_DIRECTORY}' 不存在，请检查路径。")
    elif not os.path.isdir(HTML_ROOT_DIRECTORY):
        print(f"错误：HTML目录 '{HTML_ROOT_DIRECTORY}' 不存在，请检查路径。")
    else:
        fix_json_titles_from_html_folders(JSON_ROOT_DIRECTORY, HTML_ROOT_DIRECTORY)