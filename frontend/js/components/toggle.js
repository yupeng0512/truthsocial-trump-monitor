/**
 * 开关按钮组件
 * 
 * 提供统一的开关按钮 UI 更新方法
 */

const Toggle = {
    /**
     * 更新开关按钮 UI
     * @param {string} id - 按钮 ID
     * @param {boolean} enabled - 是否启用
     */
    update(id, enabled) {
        const btn = document.getElementById(id);
        if (!btn) return;
        
        const span = btn.querySelector('span');
        if (!span) return;
        
        if (enabled) {
            btn.classList.remove('bg-dark-border');
            btn.classList.add('bg-primary');
            span.classList.remove('translate-x-1');
            span.classList.add('translate-x-6');
        } else {
            btn.classList.add('bg-dark-border');
            btn.classList.remove('bg-primary');
            span.classList.add('translate-x-1');
            span.classList.remove('translate-x-6');
        }
    },

    /**
     * 创建开关按钮
     * @param {string} id - 按钮 ID
     * @param {boolean} enabled - 初始状态
     * @param {Function} onChange - 变更回调
     * @returns {string} HTML 字符串
     */
    create(id, enabled, onChange) {
        const bgClass = enabled ? 'bg-primary' : 'bg-dark-border';
        const translateClass = enabled ? 'translate-x-6' : 'translate-x-1';
        
        return `
            <button id="${id}" class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${bgClass}">
                <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${translateClass}"></span>
            </button>
        `;
    },
};

// 导出组件
window.Toggle = Toggle;
