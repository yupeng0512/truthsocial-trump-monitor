"""消息区块组件

定义可复用的消息区块，支持纯文本和 Markdown 两种输出格式。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .formatters import format_ai_analysis, format_ai_analysis_markdown


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
    
    使用统一的格式化函数，支持完整 Agent 分析结果。
    """

    analysis: Optional[dict] = None
    label: str = "AI 分析"
    emoji: str = "🤖"
    style: str = "full"  # full, compact, summary

    def to_text(self) -> str:
        if not self.analysis:
            return ""
        return format_ai_analysis(
            self.analysis,
            style=self.style,
            title=f"{self.emoji} {self.label}",
        )

    def to_markdown(self) -> str:
        if not self.analysis:
            return ""
        return format_ai_analysis_markdown(
            self.analysis,
            title=f"{self.emoji} {self.label}",
        )


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

    char: str = "─"
    length: int = 30

    def to_text(self) -> str:
        return self.char * self.length

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
