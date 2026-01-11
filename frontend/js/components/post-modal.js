/**
 * 帖子详情弹窗组件
 * 
 * 负责显示帖子详情
 */

const PostModal = {
    /**
     * 打开弹窗
     * @param {object} post - 帖子数据
     */
    open(post) {
        const modal = document.getElementById('post-modal');
        const content = document.getElementById('modal-content');
        
        const timeStr = Utils.formatDateTime(post.posted_at);
        
        // 翻译内容区块
        const translatedSection = post.translated_content 
            ? `<div class="bg-dark-bg/50 rounded-lg p-4 mb-6 border-l-4 border-primary">
                <p class="text-sm text-primary mb-2 font-semibold">🌐 中文翻译</p>
                <div class="text-slate-300 leading-relaxed">${Utils.escapeHtml(post.translated_content)}</div>
               </div>`
            : '';
        
        content.innerHTML = `
            <div class="flex items-center gap-4 mb-6">
                <div class="w-14 h-14 bg-trump-red rounded-full flex items-center justify-center text-white font-heading font-bold text-xl">
                    T
                </div>
                <div>
                    <p class="font-heading font-semibold text-lg">Donald J. Trump</p>
                    <p class="text-slate-400">@realDonaldTrump</p>
                </div>
            </div>
            
            <div class="post-content text-lg leading-relaxed mb-6">
                ${Utils.escapeHtml(post.content || '')}
            </div>
            
            ${translatedSection}
            
            <div class="flex items-center gap-8 py-4 border-y border-dark-border text-slate-400">
                <div class="text-center">
                    <p class="text-2xl font-heading font-semibold text-slate-100">${Utils.formatNumber(post.replies_count || 0)}</p>
                    <p class="text-sm">回复</p>
                </div>
                <div class="text-center">
                    <p class="text-2xl font-heading font-semibold text-slate-100">${Utils.formatNumber(post.reblogs_count || 0)}</p>
                    <p class="text-sm">转发</p>
                </div>
                <div class="text-center">
                    <p class="text-2xl font-heading font-semibold text-slate-100">${Utils.formatNumber(post.favourites_count || 0)}</p>
                    <p class="text-sm">点赞</p>
                </div>
            </div>
            
            <div class="mt-6 space-y-3 text-sm text-slate-400">
                <p><span class="text-slate-500">发布时间：</span>${timeStr}</p>
                <p><span class="text-slate-500">帖子 ID：</span>${post.post_id}</p>
                <p><span class="text-slate-500">类型：</span>${post.is_reblog ? '转发' : '原创'}</p>
            </div>
            
            <div class="mt-6">
                <a href="${post.url}" target="_blank" rel="noopener noreferrer" 
                    class="inline-flex items-center gap-2 px-4 py-2 bg-trump-red hover:bg-trump-red/90 rounded-lg transition-colors cursor-pointer">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path>
                    </svg>
                    查看原帖
                </a>
            </div>
        `;
        
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        
        // 保存到状态
        AppState.set('modalPost', post);
    },

    /**
     * 关闭弹窗
     */
    close() {
        document.getElementById('post-modal').classList.add('hidden');
        document.body.style.overflow = '';
        AppState.set('modalPost', null);
    },

    /**
     * 初始化事件监听
     */
    init() {
        // ESC 键关闭弹窗
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.close();
            }
        });
    },
};

// 导出组件
window.PostModal = PostModal;
