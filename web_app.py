from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import sys
import time
import json
from datetime import datetime

# 导入现有的搜索引擎功能
from search_engine import evaluate

app = Flask(__name__)

# 配置
app.config['JSON_AS_ASCII'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

@app.route('/')
def index():
    """主页 - 搜索界面"""
    return render_template("index.html")

@app.route('/search', methods=['POST'])
def search():
    """处理搜索请求"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': '无效的请求数据'
            })
        
        query = data.get('query', '').strip()
        scope = data.get('scope', 'all')
        sort_method = data.get('sort', 'hybrid')
        
        if not query:
            return jsonify({
                'success': False,
                'message': '请输入搜索关键词'
            })
        
        # 记录搜索开始时间
        start_time = time.time()
        
        # 调用现有的搜索引擎
        results = evaluate(query)
        
        # 计算搜索时间
        search_time = round((time.time() - start_time) * 1000, 2)
        
        # 过滤空结果并获取详细信息
        detailed_results = []
        for url in results:
            if url and url.strip():
                # 获取URL对应的详细信息
                details = get_url_details(url)
                detailed_results.append({
                    'url': url,
                    'title': details.get('title', ''),
                    'domain': extract_domain(url)
                })
        
        # 记录搜索日志
        log_search(query, len(detailed_results), search_time, scope, sort_method)
        
        return jsonify({
            'success': True,
            'query': query,
            'results': detailed_results,
            'count': len(detailed_results),
            'search_time': search_time,
            'scope': scope,
            'sort_method': sort_method,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        app.logger.error(f'搜索错误: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'搜索出错: {str(e)}'
        }), 500

@app.route('/api/search', methods=['GET'])
def api_search():
    """API接口 - 用于调试和外部调用"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'error': '请提供查询参数 q'})
    
    try:
        start_time = time.time()
        results = evaluate(query)
        search_time = round((time.time() - start_time) * 1000, 2)
        
        filtered_results = [url for url in results if url and url.strip()]
        
        return jsonify({
            'query': query,
            'results': filtered_results,
            'count': len(filtered_results),
            'search_time': search_time,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        app.logger.error(f'API搜索错误: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取系统统计信息"""
    try:
        # 这里可以添加更多统计信息
        stats = {
            'total_searches': get_total_searches(),
            'popular_queries': get_popular_queries(),
            'system_status': 'running',
            'last_updated': datetime.now().isoformat()
        }
        return jsonify(stats)
    except Exception as e:
        app.logger.error(f'获取统计信息错误: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/suggestions', methods=['GET'])
def get_suggestions():
    """获取搜索建议"""
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'suggestions': []})
    
    try:
        # 这里可以实现更智能的搜索建议算法
        suggestions = generate_suggestions(query)
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        app.logger.error(f'获取搜索建议错误: {str(e)}')
        return jsonify({'suggestions': []})

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/favicon.ico')
def favicon():
    """网站图标"""
    return send_from_directory('static', 'favicon.ico')

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({
        'error': '页面未找到',
        'message': '请求的资源不存在'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return jsonify({
        'error': '服务器内部错误',
        'message': '服务器处理请求时发生错误'
    }), 500

@app.errorhandler(413)
def too_large(error):
    """文件过大错误处理"""
    return jsonify({
        'error': '请求过大',
        'message': '请求的数据超过了服务器允许的大小限制'
    }), 413

def log_search(query, results_count, search_time, scope, sort_method):
    """记录搜索日志"""
    try:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'query': query,
            'results_count': results_count,
            'search_time': search_time,
            'scope': scope,
            'sort_method': sort_method,
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        }
        
        # 这里可以将日志写入文件或数据库
        app.logger.info(f'搜索日志: {json.dumps(log_entry, ensure_ascii=False)}')
        
    except Exception as e:
        app.logger.error(f'记录搜索日志失败: {str(e)}')

def get_total_searches():
    """获取总搜索次数（示例实现）"""
    # 这里可以实现真实的统计逻辑
    return 0

def get_popular_queries():
    """获取热门搜索词（示例实现）"""
    # 这里可以实现真实的统计逻辑
    return []

def generate_suggestions(query):
    """生成搜索建议（示例实现）"""
    # 这里可以实现更智能的搜索建议算法
    common_suggestions = [
        '学术研究', '学生服务', '教务管理', '科研项目', '师资力量',
        '招生信息', '就业指导', '国际交流', '校园文化', '图书馆'
    ]
    
    suggestions = []
    query_lower = query.lower()
    
    for suggestion in common_suggestions:
        if query_lower in suggestion.lower() or suggestion.lower() in query_lower:
            suggestions.append(suggestion)
    
    return suggestions[:5]

def extract_domain(url):
    """从URL提取域名"""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except:
        return url

def get_url_details(url):
    """根据URL获取详细信息（标题和摘要）"""
    try:
        # 从crawler_data/data_output目录中查找对应的JSON文件
        import glob
        import json
        
        # 查找包含该URL的JSON文件
        json_files = glob.glob("crawler_data/data_output/*.json")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('url') == url:
                        # 提取标题
                        title = data.get('title', '')
                        if not title:
                            # 如果没有标题，从URL生成
                            title = generate_title_from_url(url)
                        
                        # 提取摘要
                        text = data.get('text', '')
                        snippet = generate_snippet_from_text(text, 150)  # 150字符摘要
                        
                        return {
                            'title': title,
                            'snippet': snippet
                        }
            except Exception as e:
                continue
        
        # 如果没找到对应的JSON文件，返回默认值
        return {
            'title': generate_title_from_url(url),
            'snippet': '暂无摘要信息'
        }
        
    except Exception as e:
        app.logger.error(f"获取URL详情失败: {e}")
        return {
            'title': generate_title_from_url(url),
            'snippet': '暂无摘要信息'
        }

def generate_title_from_url(url):
    """从URL生成标题"""
    try:
        # 从URL路径中提取有意义的标题
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path
        
        if path and path != '/':
            # 移除文件扩展名和多余字符
            title = path.split('/')[-1]
            title = title.replace('-', ' ').replace('_', ' ')
            title = title.replace('.html', '').replace('.htm', '').replace('.php', '')
            
            if title:
                return title.title()
        
        # 如果路径为空，返回域名
        return parsed.netloc
        
    except:
        return url

def generate_snippet_from_text(text, max_length=150):
    """从文本生成摘要"""
    if not text:
        return "暂无内容"
    
    # 清理文本
    text = text.strip()
    
    # 如果文本长度小于最大长度，直接返回
    if len(text) <= max_length:
        return text
    
    # 截取前max_length个字符，并确保在句子边界截断
    snippet = text[:max_length]
    
    # 尝试在句子边界截断
    last_period = snippet.rfind('。')
    last_exclamation = snippet.rfind('！')
    last_question = snippet.rfind('？')
    
    # 找到最后一个句子结束符号
    last_sentence_end = max(last_period, last_exclamation, last_question)
    
    if last_sentence_end > max_length * 0.7:  # 如果句子结束位置在70%之后
        snippet = snippet[:last_sentence_end + 1]
    
    return snippet + "..."

if __name__ == '__main__':
    # 设置日志
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 启动智能信息检索系统...")
    print("📖 基于BM25与PageRank的混合排序算法")
    print("🌐 访问地址: http://localhost:8080")
    print("🔍 API文档: http://localhost:8080/api/search?q=关键词")
    
    app.run(
        debug=True, 
        host='0.0.0.0', 
        port=8080,
        threaded=True
    )
