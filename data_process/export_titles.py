import os
import json
import csv

def analyze_and_export_data_from_json(json_dir, output_csv_path):
    """
    遍历JSON目录，直接从文件内提取编号、URL、标题和page_type，
    按编号排序后，输出到CSV文件。

    Args:
        json_dir (str): 存放JSON文件的根目录路径。
        output_csv_path (str): 输出CSV文件的路径。
    """
    print(f"正在从目录 '{json_dir}' 提取详细信息...")
    
    extracted_data = []
    files_processed = 0

    for root, _, files in os.walk(json_dir):
        for filename in files:
            if filename.endswith('.json'):
                files_processed += 1
                file_path = os.path.join(root, filename)
                
                # 编号依然来自文件名
                item_id = os.path.splitext(filename)[0]
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 1. 提取URL和标题
                    url = data.get('url', '（URL未找到）')
                    title = data.get('title', '（标题未找到）')
                    
                    # 2. 【核心改动】直接读取 page_type 字段并进行转换
                    raw_page_type = data.get('page_type') # 获取原始值
                    
                    if raw_page_type == 'content':
                        page_type = '内容页'
                    else:
                        page_type = '目录页' # 处理空值或其他意外值
                    
                    # 将所有信息添加到列表
                    extracted_data.append([item_id, url, title, page_type])

                except Exception as e:
                    print(f"[错误] 处理文件 '{file_path}' 时发生意外: {e}")
                    extracted_data.append([item_id, 'N/A', f'（读取错误: {e}）', 'N/A'])

    if not extracted_data:
        print("未找到任何JSON文件或未能提取任何数据。")
        return

    # 3. 对数据按编号进行数字排序
    def sort_key(item):
        try:
            return int(item[0])
        except (ValueError, TypeError):
            return item[0]

    print("\n正在对数据进行排序...")
    extracted_data.sort(key=sort_key)
    print("排序完成。")

    # 4. 将排序后的结果写入CSV文件
    try:
        with open(output_csv_path, 'w', newline='', encoding='utf-8-sig') as csv_file:
            writer = csv.writer(csv_file)
            
            # 写入表头
            writer.writerow(['原始编号', 'URL', '标题', '目录页/内容页'])
            
            # 写入所有行数据
            writer.writerows(extracted_data)
        
        print("\n" + "="*30)
        print("处理完成！")
        print(f"总共处理了 {files_processed} 个JSON文件。")
        print(f"数据已成功排序并导出到: {output_csv_path}")
        print("="*30)

    except Exception as e:
        print(f"\n[严重错误] 写入CSV文件时失败: {e}")


if __name__ == "__main__":
    # --- 请在这里配置您的文件夹和输出文件名 ---
    
    # 存放JSON文件的根目录
    JSON_ROOT_DIRECTORY = '/Users/xiexuyan/Desktop/人工智能综合设计/IR_System/crawler_data/data_output'
    
    # 您希望生成的CSV文件名
    OUTPUT_CSV_FILE = 'full_summary_final.csv'
    
    # -----------------------------------------

    if not os.path.isdir(JSON_ROOT_DIRECTORY):
        print(f"错误：JSON目录 '{JSON_ROOT_DIRECTORY}' 不存在，请检查路径。")
    else:
        analyze_and_export_data_from_json(JSON_ROOT_DIRECTORY, OUTPUT_CSV_FILE)