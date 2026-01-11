/**
 * 帖子卡片组件
 * 
 * 负责渲染帖子列表项
 */

const PostCard = {
    /**
     * 创建帖子卡片元素
     * @param {object} post - 帖子数据
     * @param {Function} onClick - 点击回调
     * @returns {HTMLElement} 帖子卡片元素
     */
    create(post, onClick) {
        const div = document.createElement('div');
        div.className = 'post-item p-5 hover:bg-dark-bg/50 transition-colors cursor-pointer';
        div.onclick = () => onClick(post);
        
        const timeStr = Utils.formatRelativeTime(post.posted_at);
        const typeIcon = post.is_reblog 
            ? this._getIcon('reblog')
            : this._getIcon('original');
        
        // 翻译内容显示
        const translatedHtml = post.translated_content 
            ? `<p class="post-content text-slate-400 text-sm mt-2 line-clamp-2 border-l-2 border-primary/50 pl-3">🌐 ${Utils.escapeHtml(post.translated_content)}</p>`
            : '';
        
        div.innerHTML = `
            <div class="flex items-start gap-4">
                <div class="flex-shrink-0 w-10 h-10 bg-trump-red rounded-full flex items-center justify-center text-white font-heading font-bold">
                    T
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-2">
                        <span class="font-semibold">@realDonaldTrump</span>
                        ${typeIcon}
                        <span class="text-sm text-slate-400">${timeStr}</span>
                    </div>
                    <p class="post-content text-slate-200 line-clamp-3">${Utils.escapeHtml(post.content || '')}</p>
                    ${translatedHtml}
                    <div class="flex items-center gap-6 mt-3 text-sm text-slate-400">
                        <span class="flex items-center gap-1.5">
                            ${this._getIcon('reply')}
                            ${Utils.formatNumber(post.replies_count || 0)}
                        </span>
                        <span class="flex items-center gap-1.5">
                            ${this._getIcon('repost')}
                            ${Utils.formatNumber(post.reblogs_count || 0)}
                        </span>
                        <span class="flex items-center gap-1.5">
                            ${this._getIcon('like')}
                            ${Utils.formatNumber(post.favourites_count || 0)}
                        </span>
                    </div>
                </div>
            </div>
        `;
        
        return div;
    },

    /**
     * 获取图标 SVG
     * @param {string} type - 图标类型
     * @returns {string} SVG HTML
     */
    _getIcon(type) {
        const icons = {
            reblog: '<svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>',
            original: '<svg class="w-4 h-4 text-trump-blue" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg>',
            reply: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"></path></svg>',
            repost: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>',
            like: '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"></path></svg>',
        };
        return icons[type] || '';
    },
};

// 导出组件
window.PostCard = PostCard;
