/**
 * 帖子列表视图模块
 * 
 * 负责帖子列表的渲染和交互
 */

const PostsView = {
    /**
     * 初始化视图
     */
    init() {
        this._bindEvents();
        this._subscribeState();
    },

    /**
     * 绑定事件
     */
    _bindEvents() {
        // 筛选类型
        const filterType = document.getElementById('filter-type');
        if (filterType) {
            filterType.addEventListener('change', (e) => {
                AppState.set('filterType', e.target.value);
                AppState.set('currentPage', 1);
                this.render();
            });
        }
        
        // 搜索输入
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.addEventListener('input', Utils.debounce((e) => {
                AppState.set('searchQuery', e.target.value.toLowerCase());
                AppState.set('currentPage', 1);
                this.render();
            }, AppConfig.DEBOUNCE_DELAY));
        }
    },

    /**
     * 订阅状态变更
     */
    _subscribeState() {
        AppState.subscribe('posts', () => this.render());
    },

    /**
     * 加载数据
     */
    async loadData() {
        try {
            AppState.set('isLoading', true);
            
            const [postsRes, statsRes] = await Promise.all([
                ApiService.getPosts({ limit: AppConfig.apiFetchLimit }),
                ApiService.getStats(),
            ]);
            
            AppState.set('posts', postsRes.posts || postsRes || []);
            AppState.update('stats', {
                totalPosts: statsRes.total_posts || 0,
                todayPosts: statsRes.today_posts || 0,
                lastScrape: statsRes.last_scrape,
                nextScrape: statsRes.next_scrape,
            });
            
            this._updateStats();
            this.render();
        } catch (error) {
            console.error('Failed to load data:', error);
            this._loadDemoData();
        } finally {
            AppState.set('isLoading', false);
        }
    },

    /**
     * 加载演示数据（开发用）
     */
    _loadDemoData() {
        const demoPosts = [
            {
                id: 1,
                post_id: '114567890123456789',
                content: 'The ECONOMY is BOOMING like never before! Jobs are up, inflation is down, and America is WINNING again! Thank you to all the hardworking Americans who make this possible. MAGA!',
                posted_at: new Date().toISOString(),
                url: 'https://truthsocial.com/@realDonaldTrump/posts/114567890123456789',
                reblogs_count: 15234,
                favourites_count: 89456,
                replies_count: 3421,
                is_reblog: false,
            },
            {
                id: 2,
                post_id: '114567890123456788',
                content: 'Just had a GREAT meeting with world leaders. America First is working! Our country is respected again on the world stage.',
                posted_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
                url: 'https://truthsocial.com/@realDonaldTrump/posts/114567890123456788',
                reblogs_count: 12567,
                favourites_count: 76543,
                replies_count: 2890,
                is_reblog: false,
            },
        ];
        
        AppState.set('posts', demoPosts);
        AppState.update('stats', {
            totalPosts: 1247,
            todayPosts: 5,
            lastScrape: new Date().toISOString(),
            nextScrape: new Date(Date.now() + 45 * 60 * 1000).toISOString(),
        });
        
        this._updateStats();
        this.render();
    },

    /**
     * 更新统计信息显示
     */
    _updateStats() {
        const stats = AppState.get('stats');
        
        const totalEl = document.getElementById('stat-total');
        const todayEl = document.getElementById('stat-today');
        const lastScrapeEl = document.getElementById('stat-last-scrape');
        const nextScrapeEl = document.getElementById('stat-next-scrape');
        
        if (totalEl) totalEl.textContent = Utils.formatNumber(stats.totalPosts);
        if (todayEl) todayEl.textContent = Utils.formatNumber(stats.todayPosts);
        if (lastScrapeEl) lastScrapeEl.textContent = Utils.formatRelativeTime(stats.lastScrape);
        if (nextScrapeEl) nextScrapeEl.textContent = Utils.formatRelativeTime(stats.nextScrape);
    },

    /**
     * 渲染帖子列表
     */
    render() {
        const container = document.getElementById('posts-container');
        const loading = document.getElementById('loading-state');
        const empty = document.getElementById('empty-state');
        const pagination = document.getElementById('pagination');
        
        if (!container) return;
        
        // 隐藏加载状态
        if (loading) loading.classList.add('hidden');
        
        // 更新分页信息
        AppState.updatePagination();
        
        // 获取当前页帖子
        const filtered = AppState.getFilteredPosts();
        const pagePosts = AppState.getCurrentPagePosts();
        
        // 空状态
        if (filtered.length === 0) {
            if (empty) empty.classList.remove('hidden');
            if (pagination) pagination.classList.add('hidden');
            container.querySelectorAll('.post-item').forEach(el => el.remove());
            return;
        }
        
        if (empty) empty.classList.add('hidden');
        
        // 更新分页 UI
        this._updatePagination(filtered.length);
        
        // 清除现有帖子
        container.querySelectorAll('.post-item').forEach(el => el.remove());
        
        // 渲染帖子
        pagePosts.forEach(post => {
            const el = PostCard.create(post, (p) => PostModal.open(p));
            container.appendChild(el);
        });
    },

    /**
     * 更新分页 UI
     * @param {number} total - 总数
     */
    _updatePagination(total) {
        const pagination = document.getElementById('pagination');
        const pageSize = AppState.get('pageSize');
        const currentPage = AppState.get('currentPage');
        const totalPages = AppState.get('totalPages');
        
        const start = (currentPage - 1) * pageSize + 1;
        const end = Math.min(currentPage * pageSize, total);
        
        const pageStart = document.getElementById('page-start');
        const pageEnd = document.getElementById('page-end');
        const pageTotal = document.getElementById('page-total');
        const pageInfo = document.getElementById('page-info');
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');
        
        if (pageStart) pageStart.textContent = start;
        if (pageEnd) pageEnd.textContent = end;
        if (pageTotal) pageTotal.textContent = total;
        if (pageInfo) pageInfo.textContent = `${currentPage} / ${totalPages}`;
        if (btnPrev) btnPrev.disabled = currentPage <= 1;
        if (btnNext) btnNext.disabled = currentPage >= totalPages;
        if (pagination) pagination.classList.remove('hidden');
    },

    /**
     * 上一页
     */
    prevPage() {
        const currentPage = AppState.get('currentPage');
        if (currentPage > 1) {
            AppState.set('currentPage', currentPage - 1);
            this.render();
        }
    },

    /**
     * 下一页
     */
    nextPage() {
        const currentPage = AppState.get('currentPage');
        const totalPages = AppState.get('totalPages');
        if (currentPage < totalPages) {
            AppState.set('currentPage', currentPage + 1);
            this.render();
        }
    },

    /**
     * 刷新数据
     */
    async refresh() {
        const icon = document.getElementById('refresh-icon');
        if (icon) icon.classList.add('animate-spin');
        
        await this.loadData();
        
        if (icon) {
            setTimeout(() => icon.classList.remove('animate-spin'), 500);
        }
    },
};

// 导出视图
window.PostsView = PostsView;
