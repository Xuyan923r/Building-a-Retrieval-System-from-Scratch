# -*- coding: utf-8 -*-
"""
word_frequency_analyzer.py

功能:
- 遍历所有已爬取的JSON文件。
- 统计所有分词后的文本和标题中的词频。
- 将所有词及其频率输出到一个CSV文件中。
"""
import os
import json
import glob
import csv
from collections import Counter

# --- 配置区 ---

# 【重要】请确保此路径指向您存放JSON文件的目录
DATA_DIR = "/Users/xiexuyan/Desktop/人工智能综合设计/Project/crawler_data/data_output"

# 【重要】输出的CSV报告将保存在DATA_DIR的上一级目录
OUTPUT_CSV_PATH = os.path.join(os.path.dirname(DATA_DIR), "word_frequency_report.csv")


# 停用词表 (与您的搜索引擎保持一致)
STOPWORDS = {
    # 原始停用词
    "的", "了", "和", "是", "在", "与", "及", "或", "与否", "并", "为", "而", "对", "以",
    "与及", "以及", "等", "各", "其", "也", "都", "更", "再", "很", "着", "于", "中",
    "你", "我", "他", "她", "它", "他们", "我们", "你们","……", "中", "在", "的", "地", "得",
    "是", "了", "和", "与", "或", "也", "都",

}

def analyze_word_frequency():
    """主分析函数"""
    if not os.path.isdir(DATA_DIR):
        print(f"错误: 目录不存在 -> {DATA_DIR}")
        return

    all_words = []
    json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
    
    if not json_files:
        print("错误: 在指定目录中未找到任何.json文件。")
        return

    print(f"开始分析 {len(json_files)} 个文件...")

    for i, filepath in enumerate(json_files):
        print(f"正在处理: {i + 1}/{len(json_files)}", end='\r')
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 合并标题和正文中的所有分词
                words = data.get("title_segmented", []) + data.get("text_segmented", [])
                # 过滤掉停用词和单个字符的词（通常是标点符号残留）
                filtered_words = [word for word in words if word not in STOPWORDS and len(word) > 1]
                all_words.extend(filtered_words)
        except Exception as e:
            print(f"\n处理文件 {filepath} 时出错: {e}")
    
    print("\n词频统计完成！")

    # 使用Counter进行计数
    word_counts = Counter(all_words)

    # 【修改】将结果写入CSV文件
    print(f"\n正在将词频统计结果保存到: {OUTPUT_CSV_PATH}")
    try:
        with open(OUTPUT_CSV_PATH, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.writer(csvfile)
            # 写入表头
            writer.writerow(['Word', 'Frequency'])
            # 写入所有词和对应的词频，按频率从高到低排序
            for word, count in word_counts.most_common():
                writer.writerow([word, count])
        print("CSV文件保存成功！")
    except Exception as e:
        print(f"\n保存CSV文件时出错: {e}")


if __name__ == "__main__":
    analyze_word_frequency()

