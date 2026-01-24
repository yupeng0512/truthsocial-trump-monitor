"""消息构建器

工厂模式，提供统一的消息构建接口。
"""

from datetime import datetime
from typing import Optional

import pytz

from src.config import settings

from .messages import (
    BatchPostsMessage,
    DailyReportMessage,
    TrumpPostMessage,
    WeeklyReportMessage,
)
from .sections import (
    AIAnalysisSection,
    ContentSection,
    FooterSection,
    HeaderSection,
    LinkSection,
    StatsSection,
    TranslationSection,
)


def get_local_time() -> datetime:
    """获取配置时区的当前时间"""
    tz = pytz.timezone(settings.timezone)
    return datetime.now(tz)


class MessageBuilder:
    """消息构建器工厂"""

    @staticmethod
    def build_trump_post(
        content: str,
        url: str,
        posted_at: Optional[datetime] = None,
        reblogs_count: int = 0,
        favourites_count: int = 0,
        replies_count: int = 0,
        is_reblog: bool = False,
        translated_content: Optional[str] = None,
        ai_analysis: Optional[dict] = None,
    ) -> TrumpPostMessage:
        """构建 Trump 帖子消息

        Args:
            content: 帖子内容（完整，不截断）
            url: 帖子链接
            posted_at: 发布时间
            reblogs_count: 转发数
            favourites_count: 点赞数
            replies_count: 回复数
            is_reblog: 是否为转发
            translated_content: 翻译内容（完整，不截断）
            ai_analysis: AI 分析结果
        """
        now = get_local_time()
        post_type = "🔄 转发" if is_reblog else "📝 新帖"

        msg = TrumpPostMessage(
            header=HeaderSection(
                title="Trump Truth Social 动态",
                subtitle=post_type,
                emoji="🇺🇸",
            ),
            content=ContentSection(
                content=content,
                label="原文",
                emoji="📝",
            ),
            stats=StatsSection(
                reblogs_count=reblogs_count,
                favourites_count=favourites_count,
                replies_count=replies_count,
                posted_at=posted_at,
                post_type="转发" if is_reblog else "原创",
            ),
            link=LinkSection(url=url, label="查看原帖"),
            footer=FooterSection(text=f"监控时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"),
        )

        # 添加翻译
        if translated_content:
            msg.translation = TranslationSection(content=translated_content)

        # 添加 AI 分析
        if ai_analysis:
            msg.ai_analysis = AIAnalysisSection(analysis=ai_analysis)

        return msg

    @staticmethod
    def build_batch_posts(
        posts: list[dict],
        monitor_time: Optional[datetime] = None,
    ) -> BatchPostsMessage:
        """构建批量帖子消息

        Args:
            posts: 帖子列表
            monitor_time: 监控时间
        """
        if monitor_time is None:
            monitor_time = get_local_time()
        
        return BatchPostsMessage(posts=posts, monitor_time=monitor_time)

    @staticmethod
    def build_daily_report(
        date: datetime,
        posts: list[dict],
        ai_analysis: Optional[dict] = None,
        text_posts_count: int = 0,
        media_posts_count: int = 0,
    ) -> DailyReportMessage:
        """构建每日报告消息
        
        Args:
            date: 报告日期
            posts: 帖子列表
            ai_analysis: AI 分析结果
            text_posts_count: 有文本内容的帖子数
            media_posts_count: 纯媒体帖子数
        """
        now = get_local_time()
        return DailyReportMessage(
            title="Trump Truth Social 每日摘要",
            date=date.strftime("%Y年%m月%d日"),
            total_posts=len(posts),
            posts=posts,
            footer_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            ai_analysis=ai_analysis,
            text_posts_count=text_posts_count,
            media_posts_count=media_posts_count,
        )

    @staticmethod
    def build_weekly_report(
        week_start: datetime,
        week_end: datetime,
        total_posts: int,
        original_posts: int,
        reblog_posts: int,
        hot_posts: list[dict],
        ai_analysis: Optional[dict] = None,
        full_display_count: int = 10,
        summary_display_count: int = 10,
        text_posts_count: int = 0,
        media_posts_count: int = 0,
        remaining_count: int = 0,
    ) -> WeeklyReportMessage:
        """构建每周报告消息"""
        now = get_local_time()
        return WeeklyReportMessage(
            title="Trump Truth Social 每周总结",
            date_range=f"{week_start.strftime('%Y年%m月%d日')} - {week_end.strftime('%m月%d日')}",
            total_posts=total_posts,
            original_posts=original_posts,
            reblog_posts=reblog_posts,
            hot_posts=hot_posts,
            footer_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            ai_analysis=ai_analysis,
            full_display_count=full_display_count,
            summary_display_count=summary_display_count,
            text_posts_count=text_posts_count,
            media_posts_count=media_posts_count,
            remaining_count=remaining_count,
        )
