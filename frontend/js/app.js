/**
 * 应用主模块
 * 
 * 负责应用初始化和全局事件处理
 */

const App = {
    /**
     * 初始化应用
     */
    async init() {
        // 加载配置
        await AppConfig.load();
        
        // 初始化组件
        PostModal.init();
        PostsView.init();
        SettingsView.init();
        
        // 加载初始数据
        await PostsView.loadData();
        
        // 设置自动刷新
        this._setupAutoRefresh();
        
        console.log('Trump Monitor App initialized');
    },

    /**
     * 设置自动刷新
     */
    _setupAutoRefresh() {
        setInterval(() => {
            PostsView.loadData();
        }, AppConfig.AUTO_REFRESH_INTERVAL);
    },

    /**
     * 切换 Tab
     * @param {string} tab - Tab 名称 (posts/settings)
     */
    switchTab(tab) {
        const tabPosts = document.getElementById('tab-posts');
        const tabSettings = document.getElementById('tab-settings');
        const contentPosts = document.getElementById('content-posts');
        const contentSettings = document.getElementById('content-settings');
        
        if (tab === 'posts') {
            // 激活帖子 Tab
            if (tabPosts) {
                tabPosts.classList.add('border-primary', 'text-primary');
                tabPosts.classList.remove('border-transparent', 'text-slate-400');
            }
            if (tabSettings) {
                tabSettings.classList.remove('border-primary', 'text-primary');
                tabSettings.classList.add('border-transparent', 'text-slate-400');
            }
            if (contentPosts) contentPosts.classList.remove('hidden');
            if (contentSettings) contentSettings.classList.add('hidden');
        } else {
            // 激活设置 Tab
            if (tabSettings) {
                tabSettings.classList.add('border-primary', 'text-primary');
                tabSettings.classList.remove('border-transparent', 'text-slate-400');
            }
            if (tabPosts) {
                tabPosts.classList.remove('border-primary', 'text-primary');
                tabPosts.classList.add('border-transparent', 'text-slate-400');
            }
            if (contentSettings) contentSettings.classList.remove('hidden');
            if (contentPosts) contentPosts.classList.add('hidden');
            
            // 加载设置
            SettingsView.loadSettings();
        }
        
        AppState.set('currentTab', tab);
    },

    /**
     * 刷新数据
     */
    refreshData() {
        PostsView.refresh();
    },

    /**
     * 上一页
     */
    prevPage() {
        PostsView.prevPage();
    },

    /**
     * 下一页
     */
    nextPage() {
        PostsView.nextPage();
    },

    /**
     * 打开帖子详情弹窗
     * @param {object} post - 帖子数据
     */
    openModal(post) {
        PostModal.open(post);
    },

    /**
     * 关闭弹窗
     */
    closeModal() {
        PostModal.close();
    },

    /**
     * 切换设置项
     * @param {string} key - 设置键名
     */
    toggleSetting(key) {
        SettingsView.toggleSetting(key);
    },

    /**
     * 保存设置
     */
    saveSettings() {
        SettingsView.saveSettings();
    },

    /**
     * 测试通知
     */
    testNotification() {
        SettingsView.testNotification();
    },

    /**
     * 推送报告
     * @param {string} type - 报告类型
     */
    pushReport(type) {
        SettingsView.pushReport(type);
    },
};

// 全局函数绑定（供 HTML onclick 调用）
window.switchTab = (tab) => App.switchTab(tab);
window.refreshData = () => App.refreshData();
window.prevPage = () => App.prevPage();
window.nextPage = () => App.nextPage();
window.openModal = (post) => App.openModal(post);
window.closeModal = () => App.closeModal();
window.toggleSetting = (key) => App.toggleSetting(key);
window.saveSettings = () => App.saveSettings();
window.testNotification = () => App.testNotification();
window.pushReport = (type) => App.pushReport(type);

// DOM 加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => App.init());

// 导出应用
window.App = App;
