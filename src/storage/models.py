"""数据库模型定义"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 基类"""

    pass


class Post(Base):
    """帖子表

    存储 Truth Social 帖子数据
    """

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 帖子基本信息
    post_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="Truth Social 帖子 ID"
    )
    username: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="发帖用户名"
    )
    content: Mapped[Optional[str]] = mapped_column(Text, comment="帖子内容")
    url: Mapped[Optional[str]] = mapped_column(String(512), comment="帖子链接")

    # 互动数据
    reblogs_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="转发数"
    )
    favourites_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="点赞数"
    )
    replies_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="回复数"
    )

    # 转发相关
    is_reblog: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否为转发"
    )
    reblog_content: Mapped[Optional[str]] = mapped_column(
        Text, comment="转发的原帖内容"
    )

    # 媒体附件（JSON 存储）
    media_attachments: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="媒体附件"
    )

    # 原始数据（用于调试和 LLM 分析）
    raw_data: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="API 返回的原始数据"
    )

    # LLM 分析结果（预留）
    llm_analysis: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="LLM 分析结果"
    )
    llm_analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="LLM 分析时间"
    )

    # 翻译内容
    translated_content: Mapped[Optional[str]] = mapped_column(
        Text, comment="翻译后的内容（中文）"
    )
    translated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="翻译时间"
    )

    # 时间戳
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="帖子发布时间"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), comment="记录创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), comment="记录更新时间"
    )

    # 通知状态
    notified: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已发送通知"
    )
    notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="通知发送时间"
    )

    # 索引
    __table_args__ = (
        Index("idx_post_id", "post_id"),
        Index("idx_username", "username"),
        Index("idx_posted_at", "posted_at"),
        Index("idx_notified", "notified"),
        Index("idx_llm_analyzed", "llm_analyzed_at"),
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, post_id={self.post_id}, username={self.username})>"


class ScrapeLog(Base):
    """采集日志表

    记录每次采集的状态和统计信息
    """

    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 采集信息
    username: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="采集的用户名"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="采集状态: success/failed/partial"
    )

    # 统计信息
    total_fetched: Mapped[int] = mapped_column(
        Integer, default=0, comment="获取的帖子总数"
    )
    new_posts: Mapped[int] = mapped_column(
        Integer, default=0, comment="新增帖子数"
    )
    updated_posts: Mapped[int] = mapped_column(
        Integer, default=0, comment="更新帖子数"
    )

    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, comment="错误信息"
    )

    # 时间
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), comment="开始时间"
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, comment="结束时间"
    )
    duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float, comment="耗时（秒）"
    )

    # 索引
    __table_args__ = (
        Index("idx_scrape_username", "username"),
        Index("idx_scrape_status", "status"),
        Index("idx_scrape_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<ScrapeLog(id={self.id}, username={self.username}, status={self.status})>"


class SystemConfig(Base):
    """系统配置表

    存储运行时配置，支持热更新
    """

    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 配置键值
    config_key: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="配置键名"
    )
    config_value: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="配置值（JSON 格式）"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255), comment="配置描述"
    )

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    # 索引
    __table_args__ = (
        Index("idx_config_key", "config_key"),
    )

    def __repr__(self) -> str:
        return f"<SystemConfig(id={self.id}, key={self.config_key})>"
