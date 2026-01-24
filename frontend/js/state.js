/**
 * 状态管理模块
 * 
 * 管理应用的全局状态，支持状态变更通知
 */

const AppState = {
    // 私有状态
    _state: {
        // 帖子数据
        posts: [],
        
        // 分页状态
        currentPage: 1,
        totalPages: 1,
        pageSize: 20,
        
        // 筛选状态
        filterType: 'all',
        searchQuery: '',
        
        // 统计数据
        stats: {
            totalPosts: 0,
            todayPosts: 0,
            lastScrape: null,
            nextScrape: null,
        },
        
        // 设置数据
        settings: {
            notification: {
                feishu_enabled: false,
                feishu_webhook: '',
                feishu_secret: '',
                realtime_enabled: true,
                daily_report_enabled: true,
                daily_report_time: '09:00',
                weekly_report_enabled: true,
                weekly_report_time: '09:00',
                weekly_report_day: 1,
                // 报告显示配置
                full_display_count: 10,
                summary_display_count: 10,
                ai_analysis_limit: 20,
                // 互动量权重
                weight_replies: 3,
                weight_reblogs: 2,
                weight_favourites: 1,
            },
        },
        
        // UI 状态
        currentTab: 'posts',
        isLoading: false,
        modalPost: null,
    },
    
    // 订阅者列表
    _subscribers: {},

    /**
     * 获取状态
     * @param {string} key - 状态键名
     * @returns {any} 状态值
     */
    get(key) {
        return this._state[key];
    },

    /**
     * 设置状态
     * @param {string} key - 状态键名
     * @param {any} value - 状态值
     */
    set(key, value) {
        const oldValue = this._state[key];
        this._state[key] = value;
        this._notify(key, value, oldValue);
    },

    /**
     * 更新状态（合并对象）
     * @param {string} key - 状态键名
     * @param {object} updates - 要合并的对象
     */
    update(key, updates) {
        const oldValue = this._state[key];
        this._state[key] = { ...oldValue, ...updates };
        this._notify(key, this._state[key], oldValue);
    },

    /**
     * 订阅状态变更
     * @param {string} key - 状态键名
     * @param {Function} callback - 回调函数
     * @returns {Function} 取消订阅函数
     */
    subscribe(key, callback) {
        if (!this._subscribers[key]) {
            this._subscribers[key] = [];
        }
        this._subscribers[key].push(callback);
        
        // 返回取消订阅函数
        return () => {
            const index = this._subscribers[key].indexOf(callback);
            if (index > -1) {
                this._subscribers[key].splice(index, 1);
            }
        };
    },

    /**
     * 通知订阅者
     * @param {string} key - 状态键名
     * @param {any} newValue - 新值
     * @param {any} oldValue - 旧值
     */
    _notify(key, newValue, oldValue) {
        const subscribers = this._subscribers[key] || [];
        subscribers.forEach(callback => {
            try {
                callback(newValue, oldValue);
            } catch (e) {
                console.error('State subscriber error:', e);
            }
        });
    },

    /**
     * 重置状态
     */
    reset() {
        this._state.posts = [];
        this._state.currentPage = 1;
        this._state.totalPages = 1;
        this._state.filterType = 'all';
        this._state.searchQuery = '';
    },

    /**
     * 获取筛选后的帖子
     * @returns {Array} 筛选后的帖子列表
     */
    getFilteredPosts() {
        let filtered = this._state.posts;
        
        // 类型筛选
        if (this._state.filterType === 'original') {
            filtered = filtered.filter(post => !post.is_reblog);
        } else if (this._state.filterType === 'reblog') {
            filtered = filtered.filter(post => post.is_reblog);
        }
        
        // 搜索筛选
        if (this._state.searchQuery) {
            const query = this._state.searchQuery.toLowerCase();
            filtered = filtered.filter(post => 
                post.content?.toLowerCase().includes(query)
            );
        }
        
        return filtered;
    },

    /**
     * 获取当前页的帖子
     * @returns {Array} 当前页帖子列表
     */
    getCurrentPagePosts() {
        const filtered = this.getFilteredPosts();
        const start = (this._state.currentPage - 1) * this._state.pageSize;
        const end = start + this._state.pageSize;
        return filtered.slice(start, end);
    },

    /**
     * 更新分页信息
     */
    updatePagination() {
        const filtered = this.getFilteredPosts();
        this._state.totalPages = Math.ceil(filtered.length / this._state.pageSize) || 1;
        
        // 确保当前页在有效范围内
        if (this._state.currentPage > this._state.totalPages) {
            this._state.currentPage = this._state.totalPages;
        }
    },
};

// 导出状态管理
window.AppState = AppState;
