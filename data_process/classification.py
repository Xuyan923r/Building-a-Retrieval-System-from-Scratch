# -*- coding: utf-8 -*-
"""
classificaion.py

功能:
- 遍历所有已爬取的JSON文件，并为每个文件添加或更新页面类型标记 ('content' 或 'directory')。
- 每次运行时，都会强制刷新所有文件的标记。
- 在处理完成后，输出内容页和目录页的总数统计。
- 生成一个CSV报告，列出每个文件的ID、URL和页面类型。

"""
import os
import json
import glob
import csv
from bs4 import BeautifulSoup

# --- 配置区 ---

# 【重要】请确保路径指向您存放干净数据的目录
CLEANED_DATA_DIR = "/Users/xiexuyan/Desktop/人工智能综合设计/Project/crawler_data"
DATA_DIR = os.path.join(CLEANED_DATA_DIR, "data_output")
HTML_DIR = os.path.join(CLEANED_DATA_DIR, "html_output")

# 【新增】分类报告的输出路径
CLASSIFICATION_REPORT_PATH = os.path.join(CLEANED_DATA_DIR, "classification_report.csv")


def classify_page_type(html_content):
    """根据HTML结构判断是内容页还是目录页"""
    if not html_content:
        return 'unknown'
        
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # --- 强目录页特征 ---
    
    # 规则 1: 页面包含分页控件，几乎可以肯定是目录页
    if soup.find(class_='page_conment'):
        return 'directory'

    # 规则 2: 页面包含典型的新闻或文章列表结构
    list_containers = soup.find_all(class_=['ky', 'ResearchTrends-list', 'phone_latestStudies_list', 'slideBox'])
    for container in list_containers:
        # 检查是否是一个包含多个列表项(li)的列表(ul)
        if container.find('ul') and len(container.find_all('li')) > 2:
            return 'directory'

    # 规则 3: 检查是否存在左侧导航列表，并且右侧没有大量正文内容
    left_nav = soup.find(class_='RUC_DepartmentProfile_l')
    if left_nav and left_nav.find(class_='nav_list') and len(left_nav.find_all('li')) > 1:
         # 这是一个强烈的目录页信号，除非有强烈的反证
         content_area = soup.find(class_='text_conment')
         if not content_area or len(content_area.get_text(strip=True)) < 200:
             return 'directory'

    # --- 强内容页特征 ---
    
    # 规则 4: 页面包含一个明确的正文容器，并且该容器内有足够的文本内容
    text_container = soup.find('div', class_=['text_conment', 'content-con1', 'v_news_content'])
    if text_container and len(text_container.get_text(strip=True)) > 200: # 文本超过200个字符
        return 'content'
        
    # --- 默认行为 ---
    # 如果以上所有强特征都不匹配，根据您的要求，默认标记为内容页，以避免误删任何可能的内容
    return 'content'


def classify_files():
    """主执行函数，进行页面分类、标记并生成报告"""
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    if not json_files:
        print(f"在目录 {DATA_DIR} 中未找到任何JSON文件。")
        return

    print(f"开始为 {len(json_files)} 个文件进行页面类型分类...")
    content_count, directory_count, unknown_count = 0, 0, 0
    
    # 【新增】用于存储报告数据
    report_data = []

    for i, json_path in enumerate(json_files):
        print(f"正在处理: {i + 1}/{len(json_files)}", end='\r')
        
        try:
            file_id = os.path.splitext(os.path.basename(json_path))[0]
            html_path = os.path.join(HTML_DIR, f"{file_id}.html")
            
            if not os.path.exists(html_path):
                continue

            with open(html_path, 'r', encoding='utf-8') as html_file:
                html_content = html_file.read()
            
            # --- 进行页面分类 ---
            page_type = classify_page_type(html_content)
            
            # --- 更新JSON文件 ---
            url = ""
            with open(json_path, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                url = data.get("url", "N/A")
                data['page_type'] = page_type
                f.seek(0)
                f.truncate()
                json.dump(data, f, ensure_ascii=False, indent=4)

            # --- 统计分类结果 ---
            if page_type == 'content':
                content_count += 1
            elif page_type == 'directory':
                directory_count += 1
            else:
                unknown_count += 1

            # 【新增】将该条记录添加到报告数据中
            report_data.append([file_id, url, page_type])

        except Exception as e:
            print(f"\n处理文件 {json_path} 时出错: {e}")
            
    # --- 【新增】将报告数据写入CSV文件 ---
    print(f"\n正在生成分类报告: {CLASSIFICATION_REPORT_PATH}")
    try:
        # 按文件ID排序报告
        report_data.sort(key=lambda x: int(x[0]))
        with open(CLASSIFICATION_REPORT_PATH, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'URL', 'Page_Type']) # 写入表头
            writer.writerows(report_data)
        print("报告生成成功！")
    except Exception as e:
        print(f"生成报告时出错: {e}")


    print(f"\n--- 分类完成 ---")
    print(f"共检查了 {len(json_files)} 个文件。")
    print(f"分类统计: {content_count} 个内容页, {directory_count} 个目录页, {unknown_count} 个未知类型。")


if __name__ == "__main__":
    classify_files()

