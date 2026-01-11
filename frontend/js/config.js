/**
 * 全局配置模块
 * 
 * 管理 API 地址、分页配置等全局设置
 */

const AppConfig = {
    // API 配置
    API_BASE: window.location.origin + '/api',
    
    // 分页配置
    DEFAULT_PAGE_SIZE: 20,
    DEFAULT_API_FETCH_LIMIT: 300,
    
    // 自动刷新间隔（毫秒）
    AUTO_REFRESH_INTERVAL: 5 * 60 * 1000,
    
    // 防抖延迟（毫秒）
    DEBOUNCE_DELAY: 300,
    
    // 动态配置（从 API 加载）
    apiFetchLimit: 300,
    
    /**
     * 从 API 加载配置
     */
    async load() {
        try {
            const res = await fetch(`${this.API_BASE}/config`);
            if (res.ok) {
                const config = await res.json();
                this.apiFetchLimit = config.api_fetch_limit || this.DEFAULT_API_FETCH_LIMIT;
            }
        } catch (e) {
            console.warn('Failed to load config, using defaults:', e);
        }
    }
};

// 导出配置
window.AppConfig = AppConfig;
