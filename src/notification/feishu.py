"""飞书机器人客户端

支持两种 Webhook 类型：
1. 传统群机器人 Webhook (open.feishu.cn/open-apis/bot/v2/hook/xxx)
2. 机器人应用 Webhook 触发器 (botbuilder.feishu.cn/api/trigger/xxx)

通过 URL 自动识别类型，统一接口调用。
"""

import base64
import hashlib
import hmac
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx
import pytz
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings


def get_local_time() -> datetime:
    """获取配置时区的当前时间"""
    tz = pytz.timezone(settings.timezone)
    return datetime.now(tz)


# ==================== 消息构建器（可扩展设计）====================


class MessageSection(ABC):
    """消息区块基类（抽象）"""

    @abstractmethod
    def to_text(self) -> str:
        """转换为纯文本格式"""
        pass

    @abstractmethod
    def to_markdown(self) -> str:
        """转换为 Markdown 格式"""
        pass


@dataclass
class HeaderSection(MessageSection):
    """标题区块"""

    title: str
    subtitle: Optional[str] = None
    emoji: str = ""

    def to_text(self) -> str:
        lines = [f"{self.emoji} {self.title}" if self.emoji else self.title]
        if self.subtitle:
            lines.append(self.subtitle)
        return "\n".join(lines)

    def to_markdown(self) -> str:
        return self.to_text()


@dataclass
class ContentSection(MessageSection):
    """内容区块（帖子原文）"""

    content: str
    label: str = "原文"
    emoji: str = "📝"

    def to_text(self) -> str:
        return f"{self.emoji} {self.label}\n{self.content}"

    def to_markdown(self) -> str:
        return f"**{self.emoji} {self.label}**\n\n{self.content}"


@dataclass
class TranslationSection(MessageSection):
    """翻译区块"""

    content: str
    label: str = "中文翻译"
    emoji: str = "🌐"

    def to_text(self) -> str:
        return f"{self.emoji} {self.label}\n{self.content}"

    def to_markdown(self) -> str:
        return f"**{self.emoji} {self.label}**\n\n{self.content}"


@dataclass
class AIAnalysisSection(MessageSection):
    """AI 分析区块
    
    支持两种模式：
    1. 简单模式：使用 summary, sentiment, topics, impact 字段
    2. 完整模式：使用 full_analysis 字段（来自 Trump Post Analyst Agent）
    """

    summary: Optional[str] = None  # 内容摘要
    sentiment: Optional[str] = None  # 情感分析
    topics: Optional[list[str]] = None  # 话题标签
    impact: Optional[str] = None  # 影响分析
    custom_analysis: Optional[dict] = None  # 自定义分析结果
    full_analysis: Optional[dict] = None  # 完整 Agent 分析结果
    label: str = "AI 分析"
    emoji: str = "🤖"

    def _format_full_analysis_text(self) -> str:
        """格式化完整 Agent 分析结果（纯文本）"""
        if not self.full_analysis:
            return ""
        
        lines = [f"{self.emoji} {self.label}"]
        analysis = self.full_analysis
        
        # 核心结论
        summary = analysis.get("summary", {})
        if summary:
            if headline := summary.get("headline"):
                lines.append(f"   📌 {headline}")
            
            sentiment = summary.get("overall_sentiment", "")
            impact = summary.get("market_impact_level", "")
            urgency = summary.get("urgency", "")
            
            sentiment_map = {"bullish": "看涨📈", "bearish": "看跌📉", "neutral": "中性➡️", "mixed": "混合↔️"}
            impact_map = {"high": "高🔴", "medium": "中🟡", "low": "低🟢"}
            
            meta_parts = []
            if sentiment:
                meta_parts.append(f"情绪:{sentiment_map.get(sentiment, sentiment)}")
            if impact:
                meta_parts.append(f"影响:{impact_map.get(impact, impact)}")
            if urgency:
                meta_parts.append(f"紧迫性:{urgency}")
            
            if meta_parts:
                lines.append(f"   {' | '.join(meta_parts)}")
        
        # 投资建议（简化显示）
        recommendations = analysis.get("investment_recommendations", [])
        if recommendations:
            lines.append("")
            lines.append("   💡 投资建议:")
            for rec in recommendations[:2]:  # 最多 2 条
                category = rec.get("category", "")
                direction = rec.get("direction", "")
                confidence = rec.get("confidence", 0)
                
                direction_map = {"long": "做多📈", "short": "做空📉", "hedge": "对冲🛡️"}
                dir_text = direction_map.get(direction, direction)
                
                lines.append(f"      • {category} ({dir_text}, 置信度:{confidence}%)")
                
                targets = rec.get("specific_targets", [])
                for target in targets[:1]:  # 每类最多 1 个标的
                    name = target.get("name", "")
                    if name:
                        lines.append(f"        标的: {name}")
        
        # 风险提示
        warnings = analysis.get("risk_warnings", [])
        if warnings:
            lines.append("")
            lines.append("   ⚠️ 风险提示:")
            for w in warnings[:2]:
                lines.append(f"      • {w}")
        
        return "\n".join(lines)

    def _format_full_analysis_markdown(self) -> str:
        """格式化完整 Agent 分析结果（Markdown）"""
        if not self.full_analysis:
            return ""
        
        lines = [f"**{self.emoji} {self.label}**\n"]
        analysis = self.full_analysis
        
        # 核心结论
        summary = analysis.get("summary", {})
        if summary:
            if headline := summary.get("headline"):
                lines.append(f"📌 **{headline}**\n")
            
            sentiment = summary.get("overall_sentiment", "")
            impact = summary.get("market_impact_level", "")
            
            sentiment_map = {"bullish": "📈 看涨", "bearish": "📉 看跌", "neutral": "➡️ 中性", "mixed": "↔️ 混合"}
            impact_map = {"high": "🔴 高", "medium": "🟡 中", "low": "🟢 低"}
            
            if sentiment or impact:
                parts = []
                if sentiment:
                    parts.append(f"情绪: {sentiment_map.get(sentiment, sentiment)}")
                if impact:
                    parts.append(f"影响: {impact_map.get(impact, impact)}")
                lines.append(f"{' | '.join(parts)}\n")
        
        # 投资建议
        recommendations = analysis.get("investment_recommendations", [])
        if recommendations:
            lines.append("**💡 投资建议**\n")
            for rec in recommendations[:3]:
                category = rec.get("category", "")
                direction = rec.get("direction", "")
                confidence = rec.get("confidence", 0)
                time_horizon = rec.get("time_horizon", "")
                
                direction_map = {"long": "📈", "short": "📉", "hedge": "🛡️"}
                dir_emoji = direction_map.get(direction, "")
                
                lines.append(f"{dir_emoji} **{category}** (置信度: {confidence}%)")
                
                targets = rec.get("specific_targets", [])
                for target in targets[:2]:
                    name = target.get("name", "")
                    rationale = target.get("rationale", "")
                    if name:
                        lines.append(f"  • {name}: {rationale}")
                
                if time_horizon:
                    lines.append(f"  ⏱️ 时间窗口: {time_horizon}")
                lines.append("")
        
        # 风险提示
        warnings = analysis.get("risk_warnings", [])
        if warnings:
            lines.append("**⚠️ 风险提示**")
            for w in warnings[:3]:
                lines.append(f"• {w}")
            lines.append("")
        
        # 后续关注
        follow_up = analysis.get("follow_up_signals", [])
        if follow_up:
            lines.append("**👀 后续关注**")
            for f in follow_up[:3]:
                lines.append(f"• {f}")
        
        return "\n".join(lines)

    def to_text(self) -> str:
        # 优先使用完整分析
        if self.full_analysis:
            return self._format_full_analysis_text()
        
        if not any([self.summary, self.sentiment, self.topics, self.impact, self.custom_analysis]):
            return ""

        lines = [f"{self.emoji} {self.label}"]

        if self.summary:
            lines.append(f"   📋 摘要: {self.summary}")
        if self.sentiment:
            lines.append(f"   💭 情感: {self.sentiment}")
        if self.topics:
            lines.append(f"   🏷️ 话题: {', '.join(self.topics)}")
        if self.impact:
            lines.append(f"   📈 影响: {self.impact}")
        if self.custom_analysis:
            for key, value in self.custom_analysis.items():
                lines.append(f"   • {key}: {value}")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        # 优先使用完整分析
        if self.full_analysis:
            return self._format_full_analysis_markdown()
        
        if not any([self.summary, self.sentiment, self.topics, self.impact, self.custom_analysis]):
            return ""

        lines = [f"**{self.emoji} {self.label}**\n"]

        if self.summary:
            lines.append(f"📋 **摘要**: {self.summary}")
        if self.sentiment:
            lines.append(f"💭 **情感**: {self.sentiment}")
        if self.topics:
            lines.append(f"🏷️ **话题**: {', '.join(self.topics)}")
        if self.impact:
            lines.append(f"📈 **影响**: {self.impact}")
        if self.custom_analysis:
            for key, value in self.custom_analysis.items():
                lines.append(f"• **{key}**: {value}")

        return "\n".join(lines)


@dataclass
class StatsSection(MessageSection):
    """统计信息区块"""

    reblogs_count: int = 0
    favourites_count: int = 0
    replies_count: int = 0
    posted_at: Optional[datetime] = None
    post_type: str = "原创"
    emoji: str = "📊"

    def to_text(self) -> str:
        time_str = self.posted_at.strftime("%Y-%m-%d %H:%M:%S") if self.posted_at else "未知"
        interactions = self.reblogs_count + self.favourites_count + self.replies_count

        lines = [
            f"{self.emoji} 统计信息",
            f"   🕐 发布时间: {time_str}",
            f"   📌 类型: {self.post_type}",
            f"   🔄 转发: {self.reblogs_count:,} | ❤️ 点赞: {self.favourites_count:,} | 💬 回复: {self.replies_count:,}",
            f"   📈 总互动: {interactions:,}",
        ]
        return "\n".join(lines)

    def to_markdown(self) -> str:
        time_str = self.posted_at.strftime("%Y-%m-%d %H:%M:%S") if self.posted_at else "未知"
        interactions = self.reblogs_count + self.favourites_count + self.replies_count

        lines = [
            f"**{self.emoji} 统计信息**\n",
            f"🕐 发布时间: {time_str}",
            f"📌 类型: {self.post_type}",
            f"🔄 转发: {self.reblogs_count:,} | ❤️ 点赞: {self.favourites_count:,} | 💬 回复: {self.replies_count:,}",
            f"📈 总互动: {interactions:,}",
        ]
        return "\n".join(lines)


@dataclass
class LinkSection(MessageSection):
    """链接区块"""

    url: str
    label: str = "查看原帖"
    emoji: str = "🔗"

    def to_text(self) -> str:
        return f"{self.emoji} {self.label}: {self.url}"

    def to_markdown(self) -> str:
        return f"{self.emoji} [{self.label}]({self.url})"


@dataclass
class DividerSection(MessageSection):
    """分隔线区块"""

    def to_text(self) -> str:
        return "─" * 30

    def to_markdown(self) -> str:
        return "\n---\n"


@dataclass
class FooterSection(MessageSection):
    """页脚区块"""

    text: str
    emoji: str = "⏰"

    def to_text(self) -> str:
        return f"{self.emoji} {self.text}"

    def to_markdown(self) -> str:
        return f"*{self.emoji} {self.text}*"


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
class WeeklyReportMessage:
    """每周报告消息"""

    title: str
    date_range: str
    total_posts: int
    original_posts: int
    reblog_posts: int
    hot_posts: list[dict]  # [{content, translation, interactions, url}, ...]
    footer_time: Optional[str] = None
    ai_analysis: Optional[dict] = None  # AI 分析结果
    top_posts_count: int = 10  # 展示的热门帖子数量

    def _format_ai_analysis(self) -> str:
        """格式化 AI 分析结果"""
        if not self.ai_analysis:
            return ""
        
        lines = ["", "🤖 AI 宏观分析:", ""]
        analysis = self.ai_analysis
        
        # 核心结论
        summary = analysis.get("summary", {})
        if summary:
            if headline := summary.get("headline"):
                lines.append(f"📌 {headline}")
            
            sentiment = summary.get("overall_sentiment", "")
            impact = summary.get("market_impact_level", "")
            
            sentiment_map = {"bullish": "看涨📈", "bearish": "看跌📉", "neutral": "中性➡️", "mixed": "混合↔️"}
            impact_map = {"high": "高🔴", "medium": "中🟡", "low": "低🟢"}
            
            meta_parts = []
            if sentiment:
                meta_parts.append(f"整体情绪:{sentiment_map.get(sentiment, sentiment)}")
            if impact:
                meta_parts.append(f"市场影响:{impact_map.get(impact, impact)}")
            
            if meta_parts:
                lines.append(f"   {' | '.join(meta_parts)}")
            lines.append("")
        
        # 投资建议（简化）
        recommendations = analysis.get("investment_recommendations", [])
        if recommendations:
            lines.append("💡 本周投资建议:")
            for rec in recommendations[:3]:
                category = rec.get("category", "")
                direction = rec.get("direction", "")
                confidence = rec.get("confidence", 0)
                
                direction_map = {"long": "做多📈", "short": "做空📉", "hedge": "对冲🛡️"}
                dir_text = direction_map.get(direction, direction)
                
                lines.append(f"   • {category} ({dir_text}, 置信度:{confidence}%)")
            lines.append("")
        
        # 风险提示
        warnings = analysis.get("risk_warnings", [])
        if warnings:
            lines.append("⚠️ 风险提示:")
            for w in warnings[:3]:
                lines.append(f"   • {w}")
            lines.append("")
        
        # 后续关注
        follow_up = analysis.get("follow_up_signals", [])
        if follow_up:
            lines.append("👀 后续关注:")
            for f in follow_up[:3]:
                lines.append(f"   • {f}")
        
        return "\n".join(lines)

    def to_text(self) -> str:
        lines = [
            f"📊 {self.title}",
            f"📅 {self.date_range}",
            "",
            "📝 本周统计:",
            f"   • 总帖子数: {self.total_posts}",
            f"   • 原创帖子: {self.original_posts}",
            f"   • 转发帖子: {self.reblog_posts}",
            "",
            f"🔥 本周热门帖子 Top {self.top_posts_count}:",
            "",
        ]

        for i, post in enumerate(self.hot_posts[:self.top_posts_count], 1):
            interactions = post.get("interactions", 0)
            content = post.get("content", "")
            translation = post.get("translation", "")
            url = post.get("url", "")

            lines.append(f"{i}. 互动量 {interactions:,}")
            lines.append(f"   {content}")
            if translation:
                lines.append(f"   🌐 {translation}")
            if url:
                lines.append(f"   🔗 {url}")
            lines.append("")

        # 添加 AI 分析
        ai_text = self._format_ai_analysis()
        if ai_text:
            lines.append(ai_text)

        if self.footer_time:
            lines.append(f"⏰ 报告生成时间: {self.footer_time}")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        return self.to_text()  # 周报使用纯文本格式即可


@dataclass
class DailyReportMessage:
    """每日报告消息"""

    title: str
    date: str
    total_posts: int
    posts: list[dict]  # [{time, type, content, translation, url}, ...]
    footer_time: Optional[str] = None
    ai_analysis: Optional[dict] = None  # AI 分析结果

    def _format_ai_analysis(self) -> str:
        """格式化 AI 分析结果"""
        if not self.ai_analysis:
            return ""
        
        lines = ["", "🤖 AI 宏观分析:", ""]
        analysis = self.ai_analysis
        
        # 核心结论
        summary = analysis.get("summary", {})
        if summary:
            if headline := summary.get("headline"):
                lines.append(f"📌 {headline}")
            
            sentiment = summary.get("overall_sentiment", "")
            impact = summary.get("market_impact_level", "")
            
            sentiment_map = {"bullish": "看涨📈", "bearish": "看跌📉", "neutral": "中性➡️", "mixed": "混合↔️"}
            impact_map = {"high": "高🔴", "medium": "中🟡", "low": "低🟢"}
            
            meta_parts = []
            if sentiment:
                meta_parts.append(f"整体情绪:{sentiment_map.get(sentiment, sentiment)}")
            if impact:
                meta_parts.append(f"市场影响:{impact_map.get(impact, impact)}")
            
            if meta_parts:
                lines.append(f"   {' | '.join(meta_parts)}")
            lines.append("")
        
        # 投资建议（简化）
        recommendations = analysis.get("investment_recommendations", [])
        if recommendations:
            lines.append("💡 投资建议:")
            for rec in recommendations[:2]:
                category = rec.get("category", "")
                direction = rec.get("direction", "")
                confidence = rec.get("confidence", 0)
                
                direction_map = {"long": "做多📈", "short": "做空📉", "hedge": "对冲🛡️"}
                dir_text = direction_map.get(direction, direction)
                
                lines.append(f"   • {category} ({dir_text}, 置信度:{confidence}%)")
            lines.append("")
        
        # 风险提示
        warnings = analysis.get("risk_warnings", [])
        if warnings:
            lines.append("⚠️ 风险提示:")
            for w in warnings[:2]:
                lines.append(f"   • {w}")
        
        return "\n".join(lines)

    def to_text(self) -> str:
        lines = [
            f"📊 {self.title}",
            f"📅 {self.date}",
            f"📝 今日共 {self.total_posts} 条帖子",
            "",
        ]

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
        ai_text = self._format_ai_analysis()
        if ai_text:
            lines.append(ai_text)

        if self.footer_time:
            lines.append("")
            lines.append(f"⏰ 报告生成时间: {self.footer_time}")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        return self.to_text()


# ==================== 消息工厂 ====================


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
            ai_analysis: AI 分析结果（可选，预留扩展）
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

        # 添加翻译（如果有）
        if translated_content:
            msg.translation = TranslationSection(content=translated_content)

        # 添加 AI 分析（如果有）
        if ai_analysis:
            # 检查是否为完整 Agent 分析结果（包含 summary.headline）
            if isinstance(ai_analysis.get("summary"), dict):
                # 完整 Agent 分析结果
                msg.ai_analysis = AIAnalysisSection(full_analysis=ai_analysis)
            else:
                # 简单分析结果
                msg.ai_analysis = AIAnalysisSection(
                    summary=ai_analysis.get("summary"),
                    sentiment=ai_analysis.get("sentiment"),
                    topics=ai_analysis.get("topics"),
                    impact=ai_analysis.get("impact"),
                    custom_analysis=ai_analysis.get("custom"),
                )

        return msg

    @staticmethod
    def build_weekly_report(
        week_start: datetime,
        week_end: datetime,
        total_posts: int,
        original_posts: int,
        reblog_posts: int,
        hot_posts: list[dict],
        ai_analysis: Optional[dict] = None,
        top_posts_count: int = 10,
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
            top_posts_count=top_posts_count,
        )

    @staticmethod
    def build_daily_report(
        date: datetime,
        posts: list[dict],
        ai_analysis: Optional[dict] = None,
    ) -> DailyReportMessage:
        """构建每日报告消息"""
        now = get_local_time()
        return DailyReportMessage(
            title="Trump Truth Social 每日摘要",
            date=date.strftime("%Y年%m月%d日"),
            total_posts=len(posts),
            posts=posts,
            footer_time=now.strftime("%Y-%m-%d %H:%M:%S"),
            ai_analysis=ai_analysis,
        )


# ==================== 飞书客户端 ====================


class FeishuClient:
    """飞书机器人客户端

    支持两种 Webhook 类型：
    1. 传统群机器人 Webhook: https://open.feishu.cn/open-apis/bot/v2/hook/xxx
       - 文档：https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
       - 使用 interactive 卡片消息格式

    2. 机器人应用 Webhook 触发器: https://botbuilder.feishu.cn/api/trigger/xxx
       - 文档：https://botbuilder.feishu.cn/
       - 使用自定义参数格式
       - 参数格式：{"msg_type": "text", "content": {"total_titles": N, "timestamp": "...", "report_type": "...", "text": "..."}}
    """

    # Webhook 类型常量
    TYPE_BOT_WEBHOOK = "bot_webhook"  # 传统群机器人
    TYPE_BOT_BUILDER = "bot_builder"  # 机器人应用触发器

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        secret: Optional[str] = None,
        max_length: int = 30000,
    ):
        """初始化飞书客户端

        Args:
            webhook_url: Webhook URL
            secret: 签名密钥（传统群机器人用）
            max_length: 消息最大长度
        """
        self.webhook_url = webhook_url or settings.feishu_webhook_url
        self.secret = secret or settings.feishu_secret
        self.max_length = max_length

        if not self.webhook_url:
            raise ValueError("Feishu webhook URL is required")

        # 自动识别 Webhook 类型
        self.webhook_type = self._detect_webhook_type(self.webhook_url)
        logger.info(f"Feishu client initialized with webhook type: {self.webhook_type}")

    def _detect_webhook_type(self, url: str) -> str:
        """根据 URL 自动识别 Webhook 类型

        Bot Builder Webhook 触发器 URL 格式：
        - https://botbuilder.feishu.cn/api/trigger/xxx
        - https://www.feishu.cn/flow/api/trigger-webhook/xxx
        """
        if (
            "botbuilder.feishu.cn" in url
            or "trigger-webhook" in url
            or "/flow/api/" in url
        ):
            return self.TYPE_BOT_BUILDER
        else:
            return self.TYPE_BOT_WEBHOOK

    @staticmethod
    def _format_ai_analysis_for_batch(ai_analysis: dict) -> str:
        """格式化 AI 分析结果（用于批量推送）
        
        Args:
            ai_analysis: AI 分析结果字典
            
        Returns:
            格式化后的字符串
        """
        if not ai_analysis:
            return ""
        
        lines = ["🤖 AI 分析"]
        
        # 核心结论
        summary = ai_analysis.get("summary", {})
        if summary:
            if headline := summary.get("headline"):
                lines.append(f"   📌 {headline}")
            
            sentiment = summary.get("overall_sentiment", "")
            impact = summary.get("market_impact_level", "")
            urgency = summary.get("urgency", "")
            
            sentiment_map = {"bullish": "看涨📈", "bearish": "看跌📉", "neutral": "中性➡️", "mixed": "混合↔️"}
            impact_map = {"high": "高🔴", "medium": "中🟡", "low": "低🟢", "none": "无"}
            
            meta_parts = []
            if sentiment:
                meta_parts.append(f"情绪:{sentiment_map.get(sentiment, sentiment)}")
            if impact:
                meta_parts.append(f"影响:{impact_map.get(impact, impact)}")
            if urgency:
                meta_parts.append(f"紧迫性:{urgency}")
            
            if meta_parts:
                lines.append(f"   {' | '.join(meta_parts)}")
        
        # 投资建议（完整显示）
        recommendations = ai_analysis.get("investment_recommendations", [])
        if recommendations:
            lines.append("")
            lines.append("   💡 投资建议:")
            for rec in recommendations:
                category = rec.get("category", "")
                direction = rec.get("direction", "")
                confidence = rec.get("confidence", 0)
                ticker = rec.get("ticker", "")
                
                direction_map = {"long": "做多📈", "short": "做空📉", "hedge": "对冲🛡️", "hedge/short": "对冲/做空🛡️"}
                dir_text = direction_map.get(direction, direction)
                
                line = f"  • {category} ({dir_text}, 置信度:{confidence}%)"
                if ticker:
                    line += f"\n  标的: {ticker}"
                lines.append(line)
        
        # 风险提示（完整显示）
        warnings = ai_analysis.get("risk_warnings", [])
        if warnings:
            lines.append("")
            lines.append("   ⚠️ 风险提示:")
            for w in warnings:
                lines.append(f"  • {w}")
        
        return "\n".join(lines)

    def _gen_sign(self, timestamp: str) -> str:
        """生成签名（仅用于传统群机器人）"""
        if not self.secret:
            return ""

        string_to_sign = f"{timestamp}\n{self.secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _send(self, payload: dict) -> bool:
        """发送消息（传统群机器人格式）"""
        # 添加签名（仅传统群机器人需要）
        if self.secret and self.webhook_type == self.TYPE_BOT_WEBHOOK:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = self._gen_sign(timestamp)

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                logger.error(f"Feishu send failed: status={response.status_code}")
                return False

            result = response.json()
            # 传统群机器人返回 {"code": 0, "msg": "success"}
            # Bot Builder 触发器返回 {"code": 0, "data": {...}} 或其他格式
            if result.get("code") != 0 and result.get("StatusCode") != 0:
                logger.error(f"Feishu send failed: {result}")
                return False

            return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _send_bot_builder(
        self,
        text: str,
        report_type: str,
        total_titles: int,
    ) -> bool:
        """发送消息到 Bot Builder Webhook 触发器

        使用统一的参数格式，便于在飞书 Bot Builder 中统一处理。

        Args:
            text: 消息文本内容
            report_type: 报告类型
            total_titles: 条目数量
        """
        now = get_local_time()
        payload = {
            "msg_type": "text",
            "content": {
                "total_titles": str(total_titles),
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "report_type": report_type,
                "text": text,
            },
        }

        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                logger.error(
                    f"Feishu Bot Builder send failed: status={response.status_code}, "
                    f"body={response.text}"
                )
                return False

            # Bot Builder 可能返回不同格式，只要状态码 200 就认为成功
            logger.info(f"Feishu Bot Builder send success: {response.text[:200]}")
            return True

    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        if len(text) > self.max_length:
            text = text[: self.max_length - 3] + "..."

        payload = {
            "msg_type": "text",
            "content": {
                "text": text,
            },
        }

        return await self._send(payload)

    async def send_interactive(
        self,
        title: str,
        elements: list[dict],
        header_color: str = "blue",
    ) -> bool:
        """发送交互式卡片消息

        Args:
            title: 卡片标题
            elements: 卡片元素列表
            header_color: 标题颜色（blue/green/orange/red/...）
        """
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True,
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title,
                    },
                    "template": header_color,
                },
                "elements": elements,
            },
        }

        return await self._send(payload)

    async def send_markdown_card(
        self,
        title: str,
        content: str,
        header_color: str = "blue",
        report_type: str = "trump_post",
        total_titles: int = 1,
    ) -> bool:
        """发送 Markdown 卡片消息

        Args:
            title: 卡片标题
            content: Markdown 内容
            header_color: 标题颜色
            report_type: 报告类型（用于 Bot Builder 模式）
            total_titles: 条目数量（用于 Bot Builder 模式）
        """
        # 根据 Webhook 类型选择发送方式
        if self.webhook_type == self.TYPE_BOT_BUILDER:
            # Bot Builder 模式：使用统一格式
            text = f"{title}\n\n{content}"
            return await self._send_bot_builder(text, report_type, total_titles)
        else:
            # 传统群机器人模式：使用 interactive 卡片
            elements = [
                {
                    "tag": "markdown",
                    "content": content,
                }
            ]
            return await self.send_interactive(title, elements, header_color)

    async def send_trump_post(
        self,
        post_content: str,
        post_url: str,
        posted_at: Optional[datetime] = None,
        reblogs_count: int = 0,
        favourites_count: int = 0,
        replies_count: int = 0,
        is_reblog: bool = False,
        translated_content: Optional[str] = None,
        ai_analysis: Optional[dict] = None,
    ) -> bool:
        """发送 Trump 帖子通知

        Args:
            post_content: 帖子内容（完整，不截断）
            post_url: 帖子链接
            posted_at: 发布时间
            reblogs_count: 转发数
            favourites_count: 点赞数
            replies_count: 回复数
            is_reblog: 是否为转发
            translated_content: 翻译后的内容（完整，不截断）
            ai_analysis: AI 分析结果（可选，预留扩展）
        """
        # 使用消息构建器
        msg = MessageBuilder.build_trump_post(
            content=post_content,
            url=post_url,
            posted_at=posted_at,
            reblogs_count=reblogs_count,
            favourites_count=favourites_count,
            replies_count=replies_count,
            is_reblog=is_reblog,
            translated_content=translated_content,
            ai_analysis=ai_analysis,
        )

        # 根据 Webhook 类型选择格式
        if self.webhook_type == self.TYPE_BOT_BUILDER:
            text = msg.to_text()
            return await self._send_bot_builder(text, "trump_post", 1)
        else:
            content = msg.to_markdown()
            return await self.send_markdown_card(
                title="🇺🇸 Trump Truth Social 动态",
                content=content,
                header_color="red" if is_reblog else "blue",
                report_type="trump_post",
                total_titles=1,
            )

    async def send_batch_posts(
        self,
        posts: list[dict],
    ) -> bool:
        """批量发送帖子通知

        Args:
            posts: 帖子列表，每个帖子包含 content, url, posted_at, translated_content 等字段
        """
        if not posts:
            return True

        now = get_local_time()

        # 构建批量消息
        lines = [
            f"🇺🇸 Trump Truth Social 动态",
            f"📊 共 {len(posts)} 条新动态",
            "",
        ]

        for i, post in enumerate(posts, 1):
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

            lines.append(f"{'─' * 30}")
            lines.append(f"**{i}. {post_type} [{time_str}]**")
            lines.append("")
            lines.append(f"📝 原文")
            lines.append(content)  # 完整内容，不截断

            # 添加翻译（完整，不截断）
            translated = post.get("translated_content")
            if translated:
                lines.append("")
                lines.append(f"🌐 中文翻译")
                lines.append(translated)

            # 添加 AI 分析
            ai_analysis = post.get("ai_analysis")
            if ai_analysis:
                lines.append("")
                lines.append(self._format_ai_analysis_for_batch(ai_analysis))

            # 添加链接
            if url:
                lines.append("")
                lines.append(f"🔗 [查看原帖]({url})")

            lines.append("")

        lines.append(f"{'─' * 30}")
        lines.append(f"⏰ 监控时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        content = "\n".join(lines)

        return await self.send_markdown_card(
            title=f"🇺🇸 Trump Truth Social 动态 ({len(posts)} 条)",
            content=content,
            header_color="blue",
            report_type="trump_posts_batch",
            total_titles=len(posts),
        )

    async def send_daily_report(
        self,
        posts: list[dict],
        date: Optional[datetime] = None,
        ai_analysis: Optional[dict] = None,
    ) -> bool:
        """发送每日摘要

        Args:
            posts: 帖子列表
            date: 日期（默认今天）
            ai_analysis: AI 分析结果（可选）
        """
        if not posts:
            return True

        if date is None:
            date = get_local_time()

        # 转换帖子格式
        formatted_posts = []
        for post in posts:
            posted_at = post.get("posted_at")
            if posted_at:
                if isinstance(posted_at, datetime):
                    time_str = posted_at.strftime("%H:%M")
                else:
                    time_str = str(posted_at)
            else:
                time_str = "--:--"

            formatted_posts.append({
                "time": time_str,
                "type": "🔄 转发" if post.get("is_reblog") else "✍️ 原创",
                "content": post.get("content", ""),  # 完整内容
                "translation": post.get("translated_content", ""),  # 完整翻译
                "url": post.get("url", ""),
            })

        msg = MessageBuilder.build_daily_report(date, formatted_posts, ai_analysis=ai_analysis)
        text = msg.to_text()

        if self.webhook_type == self.TYPE_BOT_BUILDER:
            return await self._send_bot_builder(text, "daily_report", len(posts))
        else:
            return await self.send_text(text)

    async def send_weekly_report(
        self,
        week_start: datetime,
        week_end: datetime,
        total_posts: int,
        original_posts: int,
        reblog_posts: int,
        hot_posts: list[dict],
        ai_analysis: Optional[dict] = None,
        top_posts_count: int = 10,
    ) -> bool:
        """发送每周总结

        Args:
            week_start: 周开始日期
            week_end: 周结束日期
            total_posts: 总帖子数
            original_posts: 原创帖子数
            reblog_posts: 转发帖子数
            hot_posts: 热门帖子列表
            ai_analysis: AI 分析结果（可选）
            top_posts_count: 展示的热门帖子数量
        """
        # 格式化热门帖子
        formatted_hot_posts = []
        for post in hot_posts:
            interactions = (
                post.get("reblogs_count", 0)
                + post.get("favourites_count", 0)
                + post.get("replies_count", 0)
            )
            formatted_hot_posts.append({
                "content": post.get("content", ""),  # 完整内容
                "translation": post.get("translated_content", ""),  # 完整翻译
                "interactions": interactions,
                "url": post.get("url", ""),
            })

        msg = MessageBuilder.build_weekly_report(
            week_start=week_start,
            week_end=week_end,
            total_posts=total_posts,
            original_posts=original_posts,
            reblog_posts=reblog_posts,
            hot_posts=formatted_hot_posts,
            ai_analysis=ai_analysis,
            top_posts_count=top_posts_count,
        )
        text = msg.to_text()

        if self.webhook_type == self.TYPE_BOT_BUILDER:
            return await self._send_bot_builder(text, "weekly_report", total_posts)
        else:
            return await self.send_text(text)

    async def send_alert(
        self,
        title: str,
        content: str,
        level: str = "info",
    ) -> bool:
        """发送告警消息

        Args:
            title: 告警标题
            content: 告警内容
            level: 告警级别（info/warning/error）
        """
        color_map = {
            "info": "blue",
            "warning": "orange",
            "error": "red",
        }

        return await self.send_markdown_card(
            title,
            content,
            color_map.get(level, "blue"),
            report_type="alert",
            total_titles=1,
        )
