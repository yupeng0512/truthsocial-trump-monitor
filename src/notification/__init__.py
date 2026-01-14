"""通知模块

提供消息构建和发送功能，支持飞书等多种渠道。

模块结构：
- formatters: 统一的格式化工具函数
- sections: 可复用的消息区块组件
- messages: 消息数据模型
- builder: 消息构建器工厂
- client: 飞书客户端

使用示例：
    from src.notification import FeishuClient, MessageBuilder
    
    # 发送单条帖子
    client = FeishuClient()
    await client.send_trump_post(content="...", url="...")
    
    # 发送批量帖子
    await client.send_batch_posts(posts=[...])
    
    # 发送日报
    await client.send_daily_report(posts=[...])
"""

from .builder import MessageBuilder, get_local_time
from .client import FeishuClient
from .formatters import format_ai_analysis, format_ai_analysis_markdown
from .messages import (
    BatchPostsMessage,
    DailyReportMessage,
    TrumpPostMessage,
    WeeklyReportMessage,
)
from .sections import (
    AIAnalysisSection,
    ContentSection,
    DividerSection,
    FooterSection,
    HeaderSection,
    LinkSection,
    MessageSection,
    StatsSection,
    TranslationSection,
)

__all__ = [
    # 客户端
    "FeishuClient",
    # 构建器
    "MessageBuilder",
    "get_local_time",
    # 格式化工具
    "format_ai_analysis",
    "format_ai_analysis_markdown",
    # 消息模型
    "TrumpPostMessage",
    "DailyReportMessage",
    "WeeklyReportMessage",
    "BatchPostsMessage",
    # 区块组件
    "MessageSection",
    "HeaderSection",
    "ContentSection",
    "TranslationSection",
    "AIAnalysisSection",
    "StatsSection",
    "LinkSection",
    "DividerSection",
    "FooterSection",
]
