/**
 * 智能信息检索系统 - 前端交互逻辑
 * 基于BM25与PageRank的混合排序算法
 */

class SearchEngine {
    constructor() {
        this.currentPage = 1;
        this.resultsPerPage = 10;
        this.currentResults = [];
        this.searchHistory = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSearchHistory();
        this.setupKeyboardShortcuts();
    }

    bindEvents() {
        // 搜索按钮点击事件
        document.getElementById('searchBtn').addEventListener('click', () => {
            this.performSearch();
        });

        // 搜索输入框事件
        const searchInput = document.getElementById('searchInput');
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.performSearch();
            }
        });

        searchInput.addEventListener('input', (e) => {
            this.handleSearchInput(e.target.value);
        });



        // 导出结果
        document.getElementById('exportBtn').addEventListener('click', () => {
            this.exportResults();
        });

        // 分享结果
        document.getElementById('shareBtn').addEventListener('click', () => {
            this.shareResults();
        });

        // 模态框关闭
        document.getElementById('modalClose').addEventListener('click', () => {
            this.closeModal();
        });

        // 点击模态框外部关闭
        document.getElementById('resultModal').addEventListener('click', (e) => {
            if (e.target.id === 'resultModal') {
                this.closeModal();
            }
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K 聚焦搜索框
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                document.getElementById('searchInput').focus();
            }
            
            // ESC 关闭模态框
            if (e.key === 'Escape') {
                this.closeModal();
            }
        });
    }

    async performSearch() {
        const query = document.getElementById('searchInput').value.trim();
        if (!query) {
            this.showNotification('请输入搜索关键词', 'error');
            return;
        }

        const startTime = performance.now();
        this.showLoading(true);
        this.hideResults();

        try {
            const response = await fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    scope: 'all',
                    sort: 'hybrid'
                })
            });

            const data = await response.json();
            const endTime = performance.now();
            const searchTime = Math.round(endTime - startTime);

            if (data.success) {
                this.currentResults = data.results;
                this.displayResults(data.query, this.currentResults, searchTime);
                this.addToSearchHistory(query);
                this.showNotification(`找到 ${this.currentResults.length} 个结果`, 'success');
            } else {
                this.showNotification(data.message || '搜索失败', 'error');
                this.showEmptyState();
            }
        } catch (error) {
            console.error('搜索错误:', error);
            this.showNotification('搜索过程中发生错误', 'error');
            this.showEmptyState();
        } finally {
            this.showLoading(false);
        }
    }

    handleSearchInput(value) {
        if (value.length > 0) {
            this.showSearchSuggestions(value);
        } else {
            this.hideSearchSuggestions();
        }
    }

    showSearchSuggestions(query) {
        const suggestions = this.generateSearchSuggestions(query);
        const suggestionsContainer = document.getElementById('searchSuggestions');
        
        if (suggestions.length > 0) {
            suggestionsContainer.innerHTML = suggestions.map(suggestion => 
                `<div class="search-suggestion-item" onclick="searchEngine.selectSuggestion('${suggestion}')">${suggestion}</div>`
            ).join('');
            suggestionsContainer.style.display = 'block';
        } else {
            this.hideSearchSuggestions();
        }
    }

    generateSearchSuggestions(query) {
        // 基于搜索历史生成建议
        const suggestions = [];
        const history = this.searchHistory.filter(item => 
            item.toLowerCase().includes(query.toLowerCase())
        );
        
        // 添加一些通用建议
        const commonSuggestions = [
            '学术研究', '学生服务', '教务管理', '科研项目', '师资力量',
            '招生信息', '就业指导', '国际交流', '校园文化', '图书馆'
        ];
        
        suggestions.push(...history.slice(0, 3));
        suggestions.push(...commonSuggestions.filter(item => 
            item.toLowerCase().includes(query.toLowerCase())
        ).slice(0, 2));
        
        return [...new Set(suggestions)].slice(0, 5);
    }

    selectSuggestion(suggestion) {
        document.getElementById('searchInput').value = suggestion;
        this.hideSearchSuggestions();
        this.performSearch();
    }

    hideSearchSuggestions() {
        document.getElementById('searchSuggestions').style.display = 'none';
    }

    displayResults(query, results, searchTime) {
        const resultsSection = document.getElementById('resultsSection');
        const resultsList = document.getElementById('resultsList');
        const resultsCount = document.getElementById('resultsCount');
        const resultsTime = document.getElementById('resultsTime');
        const queryText = document.getElementById('queryText');

        // 更新统计信息
        resultsCount.textContent = results.length;
        resultsTime.textContent = searchTime;
        queryText.textContent = query;

        // 生成结果列表
        const startIndex = (this.currentPage - 1) * this.resultsPerPage;
        const endIndex = startIndex + this.resultsPerPage;
        const pageResults = results.slice(startIndex, endIndex);

        resultsList.innerHTML = pageResults.map((url, index) => {
            const globalIndex = startIndex + index;
            return this.createResultItem(url, globalIndex + 1);
        }).join('');

        // 显示结果区域
        resultsSection.style.display = 'block';
        
        // 生成分页
        this.generatePagination(results.length);
        
        // 滚动到结果区域
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    createResultItem(result, rank) {
        const url = result.url;
        const title = result.title || this.generateTitle(url);
        const domain = result.domain || this.extractDomain(url);
        
        return `
            <div class="result-item" onclick="searchEngine.showResultDetail('${url}')">
                <div class="result-rank">#${rank}</div>
                <a href="${url}" class="result-title" target="_blank" onclick="event.stopPropagation()">
                    ${title}
                </a>
                <div class="result-url">${url}</div>
                <div class="result-meta">
                    <div class="meta-item">
                        <i class="fas fa-globe"></i>
                        <span>${domain}</span>
                    </div>
                    <div class="meta-item">
                        <i class="fas fa-external-link-alt"></i>
                        <span>点击查看</span>
                    </div>
                </div>
            </div>
        `;
    }

    extractDomain(url) {
        try {
            const urlObj = new URL(url);
            return urlObj.hostname;
        } catch {
            return url;
        }
    }

    generateTitle(url) {
        // 从URL生成标题
        const domain = this.extractDomain(url);
        const path = url.split('/').pop() || '';
        
        if (path) {
            return decodeURIComponent(path).replace(/[-_]/g, ' ').replace(/\.[^/.]+$/, '');
        }
        
        return domain;
    }



    generatePagination(totalResults) {
        const totalPages = Math.ceil(totalResults / this.resultsPerPage);
        const pagination = document.getElementById('pagination');
        
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let paginationHTML = '';
        
        // 上一页按钮
        paginationHTML += `
            <button class="pagination-btn" 
                    onclick="searchEngine.goToPage(${this.currentPage - 1})"
                    ${this.currentPage === 1 ? 'disabled' : ''}>
                <i class="fas fa-chevron-left"></i>
            </button>
        `;

        // 页码按钮
        for (let i = 1; i <= totalPages; i++) {
            if (i === 1 || i === totalPages || (i >= this.currentPage - 2 && i <= this.currentPage + 2)) {
                paginationHTML += `
                    <button class="pagination-btn ${i === this.currentPage ? 'active' : ''}"
                            onclick="searchEngine.goToPage(${i})">
                        ${i}
                    </button>
                `;
            } else if (i === this.currentPage - 3 || i === this.currentPage + 3) {
                paginationHTML += '<span class="pagination-ellipsis">...</span>';
            }
        }

        // 下一页按钮
        paginationHTML += `
            <button class="pagination-btn" 
                    onclick="searchEngine.goToPage(${this.currentPage + 1})"
                    ${this.currentPage === totalPages ? 'disabled' : ''}>
                <i class="fas fa-chevron-right"></i>
            </button>
        `;

        pagination.innerHTML = paginationHTML;
    }

    goToPage(page) {
        if (page < 1 || page > Math.ceil(this.currentResults.length / this.resultsPerPage)) {
            return;
        }

        this.currentPage = page;
        const startIndex = (page - 1) * this.resultsPerPage;
        const endIndex = startIndex + this.resultsPerPage;
        const pageResults = this.currentResults.slice(startIndex, endIndex);

        const resultsList = document.getElementById('resultsList');
        resultsList.innerHTML = pageResults.map((url, index) => {
            const globalIndex = startIndex + index;
            return this.createResultItem(url, globalIndex + 1);
        }).join('');

        this.generatePagination(this.currentResults.length);
        
        // 滚动到结果列表顶部
        document.getElementById('resultsList').scrollIntoView({ behavior: 'smooth' });
    }



    showResultDetail(url) {
        const modal = document.getElementById('resultModal');
        const modalBody = document.getElementById('modalBody');
        
        // 获取当前结果的标题
        const currentResult = this.currentResults.find(result => result.url === url);
        const title = currentResult ? currentResult.title : this.generateTitle(url);
        
        modalBody.innerHTML = `
            <div class="result-detail">
                <h4>搜索结果详情</h4>
                <div class="detail-title">
                    <strong>标题:</strong> ${title}
                </div>
                <div class="detail-url">
                    <strong>URL:</strong> <a href="${url}" target="_blank">${url}</a>
                </div>
                <div class="detail-domain">
                    <strong>域名:</strong> ${this.extractDomain(url)}
                </div>
                <div class="detail-actions">
                    <button class="btn btn-primary" onclick="window.open('${url}', '_blank')">
                        <i class="fas fa-external-link-alt"></i> 在新窗口打开
                    </button>
                    <button class="btn btn-secondary" onclick="searchEngine.copyToClipboard('${url}')">
                        <i class="fas fa-copy"></i> 复制链接
                    </button>
                </div>
            </div>
        `;
        
        modal.classList.add('show');
    }

    closeModal() {
        document.getElementById('resultModal').classList.remove('show');
    }

    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showNotification('链接已复制到剪贴板', 'success');
        } catch (err) {
            // 降级方案
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showNotification('链接已复制到剪贴板', 'success');
        }
    }

    exportResults() {
        if (this.currentResults.length === 0) {
            this.showNotification('没有可导出的搜索结果', 'info');
            return;
        }

        const query = document.getElementById('queryText').textContent;
        
        // 过滤掉摘要信息，只保留必要的字段
        const cleanResults = this.currentResults.map(result => ({
            url: result.url,
            title: result.title,
            domain: result.domain
        }));
        
        const exportData = {
            query: query,
            timestamp: new Date().toISOString(),
            totalResults: cleanResults.length,
            results: cleanResults
        };

        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `search_results_${query}_${new Date().getTime()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        this.showNotification('搜索结果已导出', 'success');
    }

    shareResults() {
        if (this.currentResults.length === 0) {
            this.showNotification('没有可分享的搜索结果', 'info');
            return;
        }

        const query = document.getElementById('queryText').textContent;
        const shareText = `我在智能信息检索系统中搜索"${query}"，找到了${this.currentResults.length}个结果。`;

        if (navigator.share) {
            navigator.share({
                title: '智能信息检索结果',
                text: shareText,
                url: window.location.href
            }).catch(err => {
                this.showNotification('分享失败', 'error');
            });
        } else {
            // 降级方案：复制到剪贴板
            this.copyToClipboard(shareText);
        }
    }

    showLoading(show) {
        const searchIcon = document.getElementById('searchIcon');
        const searchBtn = document.getElementById('searchBtn');
        
        if (show) {
            // 显示loading状态
            searchIcon.className = 'fas fa-spinner fa-spin search-icon';
            searchBtn.disabled = true;
            searchBtn.textContent = '搜索中...';
        } else {
            // 恢复正常状态
            searchIcon.className = 'fas fa-search search-icon';
            searchBtn.disabled = false;
            searchBtn.textContent = '搜索';
        }
    }

    hideResults() {
        document.getElementById('resultsSection').style.display = 'none';
        document.getElementById('emptyState').style.display = 'none';
    }

    showEmptyState() {
        document.getElementById('emptyState').style.display = 'block';
    }

    showNotification(message, type = 'info') {
        const notification = document.getElementById('notification');
        const messageElement = notification.querySelector('.notification-message');
        
        notification.className = `notification ${type}`;
        messageElement.textContent = message;
        notification.classList.add('show');
        
        setTimeout(() => {
            notification.classList.remove('show');
        }, 3000);
    }

    addToSearchHistory(query) {
        if (!this.searchHistory.includes(query)) {
            this.searchHistory.unshift(query);
            this.searchHistory = this.searchHistory.slice(0, 10); // 保留最近10条
            this.saveSearchHistory();
        }
    }

    loadSearchHistory() {
        const saved = localStorage.getItem('searchHistory');
        if (saved) {
            this.searchHistory = JSON.parse(saved);
        }
    }

    saveSearchHistory() {
        localStorage.setItem('searchHistory', JSON.stringify(this.searchHistory));
    }

    // 统计功能
    trackSearch(query, resultsCount, searchTime) {
        // 这里可以添加搜索统计功能
        console.log(`搜索统计: "${query}" -> ${resultsCount} 结果, ${searchTime}ms`);
    }

    // 推荐关键词搜索
    searchKeyword(keyword) {
        document.getElementById('searchInput').value = keyword;
        this.performSearch();
    }
}

// 初始化搜索引擎
const searchEngine = new SearchEngine();

// 页面加载完成后的初始化
document.addEventListener('DOMContentLoaded', () => {
    // 添加一些示例搜索建议
    const searchInput = document.getElementById('searchInput');
    
    // 聚焦搜索框
    searchInput.focus();
    
    // 添加搜索框焦点效果
    searchInput.addEventListener('focus', () => {
        searchInput.parentElement.style.transform = 'scale(1.02)';
    });
    
    searchInput.addEventListener('blur', () => {
        searchInput.parentElement.style.transform = 'scale(1)';
    });
});

// 添加一些CSS样式增强
const style = document.createElement('style');
style.textContent = `
    .result-rank {
        position: absolute;
        top: 20px;
        right: 20px;
        background: var(--primary-color);
        color: white;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        font-weight: 600;
    }
    
    .result-item {
        position: relative;
    }
    
    .pagination-ellipsis {
        padding: 8px 16px;
        color: var(--text-muted);
    }
    
    .btn {
        padding: 8px 16px;
        border: none;
        border-radius: var(--radius-small);
        cursor: pointer;
        font-size: 14px;
        font-weight: 500;
        transition: var(--transition-fast);
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin-right: 12px;
    }
    
    .btn-primary {
        background: var(--primary-color);
        color: white;
    }
    
    .btn-primary:hover {
        background: var(--primary-hover);
    }
    
    .btn-secondary {
        background: var(--background-tertiary);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
    }
    
    .btn-secondary:hover {
        background: var(--background-secondary);
    }
    
    .result-detail {
        line-height: 1.6;
    }
    
    .result-detail h4 {
        margin-bottom: 20px;
        color: var(--text-primary);
    }
    
    .detail-title, .detail-url, .detail-domain {
        margin-bottom: 16px;
    }
    
    .detail-url a {
        color: var(--primary-color);
        text-decoration: none;
        word-break: break-all;
    }
    
    .detail-url a:hover {
        text-decoration: underline;
    }
    
    .detail-actions {
        margin-top: 24px;
    }
`;
document.head.appendChild(style);
