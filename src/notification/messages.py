"""消息模型

定义各种消息类型的数据结构和渲染逻辑。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .formatters import format_ai_analysis
from .sections import (
    AIAnalysisSection,
    ContentSection,
    FooterSection,
    HeaderSection,
    LinkSection,
    MessageSection,
    StatsSection,
    TranslationSection,
)


@dataclass
class TrumpPostMessage:
    """Trump 帖子消息（组合多个区块）

    可扩展设计：通过添加不同的 Section 来扩展消息内容
    """

    header: Optional[HeaderSection] = None
    content: Optional[ContentSection] = None
    translation: Optional[TranslationSection] = None
    ai_analysis: Optional[AIAnalysisSection] = None
    stats: Optional[StatsSection] = None
    link: Optional[LinkSection] = None
    footer: Optional[FooterSection] = None
    extra_sections: list[MessageSection] = field(default_factory=list)

    def to_text(self) -> str:
        """转换为纯文本格式"""
        sections = []

        if self.header:
            sections.append(self.header.to_text())

        sections.append("")  # 空行

        if self.content:
            sections.append(self.content.to_text())

        if self.translation:
            sections.append("")
            sections.append(self.translation.to_text())

        if self.ai_analysis:
            ai_text = self.ai_analysis.to_text()
            if ai_text:
                sections.append("")
                sections.append(ai_text)

        # 额外区块
        for section in self.extra_sections:
            sections.append("")
            sections.append(section.to_text())

        sections.append("")
        sections.append("─" * 30)

        if self.stats:
            sections.append(self.stats.to_text())

        if self.link:
            sections.append("")
            sections.append(self.link.to_text())

        if self.footer:
            sections.append("")
            sections.append(self.footer.to_text())

        return "\n".join(sections)

    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        sections = []

        if self.header:
            sections.append(self.header.to_markdown())

        if self.content:
            sections.append("")
            sections.append(self.content.to_markdown())

        if self.translation:
            sections.append("")
            sections.append(self.translation.to_markdown())

        if self.ai_analysis:
            ai_md = self.ai_analysis.to_markdown()
            if ai_md:
                sections.append("")
                sections.append(ai_md)

        # 额外区块
        for section in self.extra_sections:
            sections.append("")
            sections.append(section.to_markdown())

        sections.append("\n---\n")

        if self.stats:
            sections.append(self.stats.to_markdown())

        if self.link:
            sections.append("")
            sections.append(self.link.to_markdown())

        if self.footer:
            sections.append("")
            sections.append(self.footer.to_markdown())

        return "\n".join(sections)


@dataclass
class DailyReportMessage:
    """每日报告消息"""

    title: str
    date: str
    total_posts: int
    posts: list[dict]  # [{time, type, content, translation, url}, ...]
    footer_time: Optional[str] = None
    ai_analysis: Optional[dict] = None
    text_posts_count: int = 0  # 有文本内容的帖子数
    media_posts_count: int = 0  # 纯媒体帖子数（无文本）

    def to_text(self) -> str:
        lines = [
            f"📊 {self.title}",
            f"📅 {self.date}",
        ]
        
        # 统计信息拆分显示
        if self.text_posts_count > 0 or self.media_posts_count > 0:
            lines.append(f"📝 共 {self.total_posts} 条帖子（文本 {self.text_posts_count} 条，媒体 {self.media_posts_count} 条）")
        else:
            lines.append(f"📝 共 {self.total_posts} 条帖子")
        lines.append("")

        for i, post in enumerate(self.posts[:10], 1):
            time_str = post.get("time", "")
            post_type = post.get("type", "✍️ 原创")
            content = post.get("content", "")
            translation = post.get("translation", "")
            url = post.get("url", "")

            lines.append(f"{i}. [{time_str}] {post_type}")
            lines.append(f"   {content}")
            if translation:
                lines.append(f"   🌐 {translation}")
            if url:
                lines.append(f"   🔗 {url}")
            lines.append("")

        if len(self.posts) > 10:
            lines.append(f"... 还有 {len(self.posts) - 10} 条帖子")

        # 添加 AI 分析
        if self.ai_analysis:
            ai_text = format_ai_analysis(self.ai_analysis, title="🤖 AI 宏观分析:")
            if ai_text:
                lines.append("")
                lines.append(ai_text)

        if self.footer_time:
            lines.append("")
            lines.append(f"⏰ 报告生成时间: {self.footer_time}")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        return self.to_text()


@dataclass
class WeeklyReportMessage:
    """每周报告消息"""

    title: str
    date_range: str
    total_posts: int
    original_posts: int
    reblog_posts: int
    hot_posts: list[dict]  # [{content, translation, interactions, weighted_score, url}, ...]
    footer_time: Optional[str] = None
    ai_analysis: Optional[dict] = None
    full_display_count: int = 10  # 完整显示数量
    summary_display_count: int = 10  # 摘要显示数量
    text_posts_count: int = 0  # 有文本内容的帖子数
    media_posts_count: int = 0  # 纯媒体帖子数
    remaining_count: int = 0  # 剩余未显示的帖子数

    def to_text(self) -> str:
        lines = [
            f"📊 {self.title}",
            f"📅 {self.date_range}",
            "",
        ]

        # 统计信息
        lines.append("📝 统计:")
        lines.append(f"   • 总帖子数: {self.total_posts}")
        if self.text_posts_count > 0 or self.media_posts_count > 0:
            lines.append(f"   • 文本帖子: {self.text_posts_count}")
            lines.append(f"   • 媒体帖子: {self.media_posts_count}")
        lines.append(f"   • 原创帖子: {self.original_posts}")
        lines.append(f"   • 转发帖子: {self.reblog_posts}")
        lines.append("")

        # 完整显示区（Top N）
        full_posts = self.hot_posts[:self.full_display_count]
        if full_posts:
            lines.append(f"🔥 热门帖子 Top {len(full_posts)}（完整）:")
            lines.append("")

            for i, post in enumerate(full_posts, 1):
                weighted_score = post.get("weighted_score", 0)
                interactions = post.get("interactions", weighted_score)
                content = post.get("content", "")
                translation = post.get("translation", "")
                url = post.get("url", "")

                lines.append(f"{i}. 热度 {interactions:,}")
                lines.append(f"   {content}")
                if translation:
                    lines.append(f"   🌐 {translation}")
                if url:
                    lines.append(f"   🔗 {url}")
                lines.append("")

        # 摘要显示区（N+1 到 M）
        summary_posts = self.hot_posts[self.full_display_count:self.full_display_count + self.summary_display_count]
        if summary_posts:
            lines.append(f"📋 更多热门帖子（{self.full_display_count + 1}-{self.full_display_count + len(summary_posts)}）:")
            lines.append("")

            for i, post in enumerate(summary_posts, self.full_display_count + 1):
                weighted_score = post.get("weighted_score", 0)
                interactions = post.get("interactions", weighted_score)
                content = post.get("content", "")
                url = post.get("url", "")
                # 摘要显示：截断内容
                content_preview = content[:50] + "..." if len(content) > 50 else content

                lines.append(f"{i}. 热度 {interactions:,} | {content_preview}")
                if url:
                    lines.append(f"   🔗 {url}")

            lines.append("")

        # 隐藏区
        if self.remaining_count > 0:
            lines.append(f"... 还有 {self.remaining_count} 条文本帖子")
            lines.append("")

        # 添加 AI 分析
        if self.ai_analysis:
            ai_text = format_ai_analysis(self.ai_analysis, title="🤖 AI 宏观分析:")
            if ai_text:
                lines.append(ai_text)

        if self.footer_time:
            lines.append(f"⏰ 报告生成时间: {self.footer_time}")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        return self.to_text()


@dataclass
class BatchPostsMessage:
    """批量帖子消息"""

    posts: list[dict]  # [{content, url, posted_at, is_reblog, translated_content, ai_analysis}, ...]
    monitor_time: Optional[datetime] = None

    def to_text(self) -> str:
        if not self.posts:
            return ""

        lines = [
            "🇺🇸 Trump Truth Social 动态",
            f"📊 共 {len(self.posts)} 条新动态",
            "",
        ]

        for i, post in enumerate(self.posts, 1):
            posted_at = post.get("posted_at")
            if posted_at:
                if isinstance(posted_at, str):
                    time_str = posted_at
                else:
                    time_str = posted_at.strftime("%H:%M")
            else:
                time_str = "--:--"

            content = post.get("content", "")
            is_reblog = post.get("is_reblog", False)
            post_type = "🔄 转发" if is_reblog else "📝 原创"
            url = post.get("url", "")

            lines.append("─" * 30)
            lines.append(f"**{i}. {post_type} [{time_str}]**")
            lines.append("")
            lines.append("📝 原文")
            lines.append(content)

            # 翻译
            translated = post.get("translated_content")
            if translated:
                lines.append("")
                lines.append("🌐 中文翻译")
                lines.append(translated)

            # AI 分析
            ai_analysis = post.get("ai_analysis")
            if ai_analysis:
                lines.append("")
                lines.append(format_ai_analysis(ai_analysis))

            # 链接
            if url:
                lines.append("")
                lines.append(f"🔗 [查看原帖]({url})")

            lines.append("")

        lines.append("─" * 30)
        
        if self.monitor_time:
            lines.append(f"⏰ 监控时间: {self.monitor_time.strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        return self.to_text()
