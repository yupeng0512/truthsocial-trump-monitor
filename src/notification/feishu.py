"""飞书机器人客户端（兼容层）

此文件保留向后兼容性，所有功能已迁移到独立模块：
- formatters.py: 格式化工具
- sections.py: 消息区块组件  
- messages.py: 消息数据模型
- builder.py: 消息构建器
- client.py: 飞书客户端

直接从此文件导入仍然有效，但建议使用新的模块结构。
"""

# 重新导出所有内容，保持向后兼容
from .builder import MessageBuilder, get_local_time
from .client import FeishuClient
from .formatters import (
    DIRECTION_MAP,
    IMPACT_MAP,
    SENTIMENT_MAP,
    format_ai_analysis,
    format_ai_analysis_markdown,
)
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
    "SENTIMENT_MAP",
    "IMPACT_MAP", 
    "DIRECTION_MAP",
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
