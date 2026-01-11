/**
 * 设置视图模块
 * 
 * 负责设置页面的渲染和交互
 */

const SettingsView = {
    /**
     * 初始化视图
     */
    init() {
        // 初始化时不加载设置，等切换到设置 Tab 时再加载
    },

    /**
     * 加载设置
     */
    async loadSettings() {
        try {
            const data = await ApiService.getSettings();
            AppState.update('settings', data);
            this.render();
        } catch (e) {
            console.error('Failed to load settings:', e);
        }
    },

    /**
     * 渲染设置 UI
     */
    render() {
        const settings = AppState.get('settings');
        const n = settings.notification;
        
        // 飞书开关
        Toggle.update('toggle-feishu', n.feishu_enabled);
        const feishuConfig = document.getElementById('feishu-config');
        if (feishuConfig) {
            feishuConfig.classList.toggle('hidden', !n.feishu_enabled);
        }
        
        // 飞书配置输入
        const webhookInput = document.getElementById('input-feishu-webhook');
        const secretInput = document.getElementById('input-feishu-secret');
        if (webhookInput) webhookInput.value = n.feishu_webhook || '';
        if (secretInput) secretInput.value = n.feishu_secret || '';
        
        // 实时推送开关
        Toggle.update('toggle-realtime', n.realtime_enabled);
        
        // 每日摘要开关
        Toggle.update('toggle-daily', n.daily_report_enabled);
        const dailyConfig = document.getElementById('daily-config');
        if (dailyConfig) {
            dailyConfig.classList.toggle('hidden', !n.daily_report_enabled);
        }
        const dailyTimeInput = document.getElementById('input-daily-time');
        if (dailyTimeInput) dailyTimeInput.value = n.daily_report_time || '09:00';
        
        // 每周总结开关
        Toggle.update('toggle-weekly', n.weekly_report_enabled);
        const weeklyConfig = document.getElementById('weekly-config');
        if (weeklyConfig) {
            weeklyConfig.classList.toggle('hidden', !n.weekly_report_enabled);
        }
        const weeklyDayInput = document.getElementById('input-weekly-day');
        const weeklyTimeInput = document.getElementById('input-weekly-time');
        const weeklyTopPostsInput = document.getElementById('input-weekly-top-posts');
        if (weeklyDayInput) weeklyDayInput.value = n.weekly_report_day || 1;
        if (weeklyTimeInput) weeklyTimeInput.value = n.weekly_report_time || '09:00';
        if (weeklyTopPostsInput) weeklyTopPostsInput.value = n.weekly_report_top_posts || 10;
    },

    /**
     * 切换设置项
     * @param {string} key - 设置键名
     */
    toggleSetting(key) {
        const settings = AppState.get('settings');
        const n = settings.notification;
        n[key] = !n[key];
        AppState.update('settings', { notification: n });
        this.render();
    },

    /**
     * 保存设置
     */
    async saveSettings() {
        const btn = document.getElementById('btn-save-settings');
        if (!btn) return;
        
        btn.disabled = true;
        btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> 保存中...';
        
        try {
            // 收集表单值
            const settings = AppState.get('settings');
            const n = settings.notification;
            
            const webhookInput = document.getElementById('input-feishu-webhook');
            const secretInput = document.getElementById('input-feishu-secret');
            const dailyTimeInput = document.getElementById('input-daily-time');
            const weeklyDayInput = document.getElementById('input-weekly-day');
            const weeklyTimeInput = document.getElementById('input-weekly-time');
            const weeklyTopPostsInput = document.getElementById('input-weekly-top-posts');
            
            if (webhookInput) n.feishu_webhook = webhookInput.value;
            if (secretInput) n.feishu_secret = secretInput.value;
            if (dailyTimeInput) n.daily_report_time = dailyTimeInput.value;
            if (weeklyDayInput) n.weekly_report_day = parseInt(weeklyDayInput.value);
            if (weeklyTimeInput) n.weekly_report_time = weeklyTimeInput.value;
            if (weeklyTopPostsInput) n.weekly_report_top_posts = parseInt(weeklyTopPostsInput.value);
            
            await ApiService.updateNotificationSettings(n);
            
            this._showSaveSuccess(btn);
        } catch (e) {
            console.error('Failed to save settings:', e);
            this._showSaveError(btn);
        }
    },

    /**
     * 显示保存成功
     * @param {HTMLElement} btn - 按钮元素
     */
    _showSaveSuccess(btn) {
        btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> 已保存';
        btn.classList.remove('bg-primary');
        btn.classList.add('bg-green-500');
        
        setTimeout(() => {
            btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> 保存设置';
            btn.classList.add('bg-primary');
            btn.classList.remove('bg-green-500');
            btn.disabled = false;
        }, 2000);
    },

    /**
     * 显示保存失败
     * @param {HTMLElement} btn - 按钮元素
     */
    _showSaveError(btn) {
        btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg> 保存失败';
        btn.classList.remove('bg-primary');
        btn.classList.add('bg-red-500');
        
        setTimeout(() => {
            btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg> 保存设置';
            btn.classList.add('bg-primary');
            btn.classList.remove('bg-red-500');
            btn.disabled = false;
        }, 2000);
    },

    /**
     * 测试通知
     */
    async testNotification() {
        const btn = document.getElementById('btn-test-notification');
        const result = document.getElementById('test-result');
        const webhookInput = document.getElementById('input-feishu-webhook');
        const secretInput = document.getElementById('input-feishu-secret');
        
        if (!webhookInput || !webhookInput.value) {
            if (result) {
                result.textContent = '请先填写 Webhook URL';
                result.className = 'text-sm text-red-400';
            }
            return;
        }
        
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> 测试中...';
        }
        if (result) result.textContent = '';
        
        try {
            const data = await ApiService.testNotification(
                webhookInput.value,
                secretInput?.value || null
            );
            
            if (result) {
                if (data.success) {
                    result.textContent = '测试成功';
                    result.className = 'text-sm text-green-400';
                } else {
                    result.textContent = data.message || '测试失败';
                    result.className = 'text-sm text-red-400';
                }
            }
        } catch (e) {
            if (result) {
                result.textContent = '测试失败: ' + e.message;
                result.className = 'text-sm text-red-400';
            }
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg> 测试推送';
            }
        }
    },

    /**
     * 推送报告
     * @param {string} type - 报告类型 (daily/weekly/test)
     */
    async pushReport(type) {
        const result = document.getElementById('push-result');
        
        if (result) {
            result.textContent = '推送中...';
            result.className = 'text-sm text-slate-400';
        }
        
        try {
            const data = await ApiService.pushReport(type);
            
            if (result) {
                if (data.success) {
                    result.textContent = data.message || '推送成功';
                    result.className = 'text-sm text-green-400';
                } else {
                    result.textContent = data.message || '推送失败';
                    result.className = 'text-sm text-red-400';
                }
            }
        } catch (e) {
            if (result) {
                result.textContent = '推送失败: ' + e.message;
                result.className = 'text-sm text-red-400';
            }
        }
        
        // 5 秒后清除结果
        setTimeout(() => {
            if (result) result.textContent = '';
        }, 5000);
    },
};

// 导出视图
window.SettingsView = SettingsView;
