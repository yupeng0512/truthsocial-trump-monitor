/**
 * API 服务模块
 * 
 * 封装所有与后端 API 的交互
 */

const ApiService = {
    /**
     * 获取 API 基础地址
     */
    get baseUrl() {
        return AppConfig.API_BASE;
    },

    /**
     * 通用请求方法
     * @param {string} endpoint - API 端点
     * @param {object} options - fetch 选项
     * @returns {Promise<any>} 响应数据
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        const response = await fetch(url, { ...defaultOptions, ...options });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        
        return response.json();
    },

    // ==================== 帖子相关 API ====================

    /**
     * 获取帖子列表
     * @param {object} params - 查询参数
     * @returns {Promise<{posts: Array, total: number}>}
     */
    async getPosts(params = {}) {
        const { page = 1, limit = AppConfig.apiFetchLimit, filterType, search } = params;
        let url = `/posts?page=${page}&limit=${limit}`;
        if (filterType && filterType !== 'all') {
            url += `&filter_type=${filterType}`;
        }
        if (search) {
            url += `&search=${encodeURIComponent(search)}`;
        }
        return this.request(url);
    },

    /**
     * 获取单个帖子详情
     * @param {string} postId - 帖子 ID
     * @returns {Promise<object>}
     */
    async getPost(postId) {
        return this.request(`/posts/${postId}`);
    },

    // ==================== 统计相关 API ====================

    /**
     * 获取统计信息
     * @returns {Promise<object>}
     */
    async getStats() {
        return this.request('/stats');
    },

    /**
     * 获取采集日志
     * @param {number} limit - 数量限制
     * @returns {Promise<Array>}
     */
    async getScrapeLogs(limit = 20) {
        return this.request(`/scrape-logs?limit=${limit}`);
    },

    // ==================== 设置相关 API ====================

    /**
     * 获取所有设置
     * @returns {Promise<object>}
     */
    async getSettings() {
        return this.request('/settings');
    },

    /**
     * 更新通知设置
     * @param {object} config - 通知配置
     * @returns {Promise<object>}
     */
    async updateNotificationSettings(config) {
        return this.request('/settings/notification', {
            method: 'PUT',
            body: JSON.stringify(config),
        });
    },

    /**
     * 更新采集设置
     * @param {object} config - 采集配置
     * @returns {Promise<object>}
     */
    async updateScrapeSettings(config) {
        return this.request('/settings/scrape', {
            method: 'PUT',
            body: JSON.stringify(config),
        });
    },

    /**
     * 测试通知
     * @param {string} webhookUrl - Webhook URL
     * @param {string} secret - 签名密钥
     * @returns {Promise<{success: boolean, message: string}>}
     */
    async testNotification(webhookUrl, secret) {
        return this.request('/settings/test-notification', {
            method: 'POST',
            body: JSON.stringify({ webhook_url: webhookUrl, secret: secret || null }),
        });
    },

    /**
     * 手动推送报告
     * @param {string} reportType - 报告类型 (daily/weekly/test)
     * @returns {Promise<{success: boolean, message: string}>}
     */
    async pushReport(reportType) {
        return this.request('/settings/push-report', {
            method: 'POST',
            body: JSON.stringify({ report_type: reportType }),
        });
    },

    // ==================== 健康检查 ====================

    /**
     * 健康检查
     * @returns {Promise<{status: string, timestamp: string}>}
     */
    async healthCheck() {
        return this.request('/health');
    },
};

// 导出 API 服务
window.ApiService = ApiService;
