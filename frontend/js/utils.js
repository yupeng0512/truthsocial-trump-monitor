/**
 * 工具函数模块
 * 
 * 提供通用的工具函数，如格式化、防抖等
 */

const Utils = {
    /**
     * 防抖函数
     * @param {Function} func - 要执行的函数
     * @param {number} wait - 等待时间（毫秒）
     * @returns {Function} 防抖后的函数
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * 格式化数字（K/M 格式）
     * @param {number} num - 数字
     * @returns {string} 格式化后的字符串
     */
    formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    },

    /**
     * 格式化相对时间
     * @param {string|Date} dateStr - 日期字符串或 Date 对象
     * @returns {string} 相对时间字符串
     */
    formatRelativeTime(dateStr) {
        if (!dateStr) return '--';
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 0) {
            // 未来时间
            const absDiff = Math.abs(diff);
            if (absDiff < 60000) return '即将';
            if (absDiff < 3600000) return Math.floor(absDiff / 60000) + '分钟后';
            if (absDiff < 86400000) return Math.floor(absDiff / 3600000) + '小时后';
            return Math.floor(absDiff / 86400000) + '天后';
        }
        
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前';
        if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前';
        if (diff < 604800000) return Math.floor(diff / 86400000) + '天前';
        return date.toLocaleDateString('zh-CN');
    },

    /**
     * 格式化完整日期时间
     * @param {string|Date} dateStr - 日期字符串或 Date 对象
     * @returns {string} 格式化后的日期时间字符串
     */
    formatDateTime(dateStr) {
        if (!dateStr) return '--';
        const date = new Date(dateStr);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    },

    /**
     * HTML 转义
     * @param {string} text - 原始文本
     * @returns {string} 转义后的文本
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * 显示 Toast 消息
     * @param {string} message - 消息内容
     * @param {string} type - 消息类型 (success/error/info)
     * @param {number} duration - 显示时长（毫秒）
     */
    showToast(message, type = 'info', duration = 3000) {
        // 创建 toast 元素
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg text-white z-50 transition-opacity duration-300 ${
            type === 'success' ? 'bg-green-500' :
            type === 'error' ? 'bg-red-500' :
            'bg-blue-500'
        }`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // 自动移除
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
};

// 导出工具函数
window.Utils = Utils;
