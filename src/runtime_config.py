"""运行时配置管理器

支持从数据库动态加载配置，无需重启服务即可生效
"""

import json
from datetime import datetime
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.storage import get_db_manager


class NotificationConfig(BaseModel):
    """通知配置"""

    # 飞书配置
    feishu_enabled: bool = Field(default=True, description="是否启用飞书通知")
    feishu_webhook: Optional[str] = Field(default=None, description="飞书 Webhook URL")
    feishu_secret: Optional[str] = Field(default=None, description="飞书签名密钥")

    # 实时推送配置
    realtime_enabled: bool = Field(default=True, description="是否启用实时推送（有新帖立即推送）")

    # 日报配置
    daily_report_enabled: bool = Field(default=True, description="是否启用每日摘要")
    daily_report_time: str = Field(default="09:00", description="每日摘要推送时间")

    # 周报配置
    weekly_report_enabled: bool = Field(default=True, description="是否启用每周总结")
    weekly_report_time: str = Field(default="09:00", description="每周总结推送时间")
    weekly_report_day: int = Field(default=1, description="每周总结推送日（1-7，周一到周日）")

    # 报告显示配置（日报/周报通用）
    full_display_count: int = Field(default=10, ge=3, le=20, description="完整显示帖子数量")
    summary_display_count: int = Field(default=10, ge=0, le=20, description="摘要显示帖子数量（0=不显示摘要）")
    ai_analysis_limit: int = Field(default=20, ge=5, le=50, description="AI 分析帖子数量上限")

    # 互动量权重配置
    weight_replies: int = Field(default=3, ge=1, le=10, description="评论权重")
    weight_reblogs: int = Field(default=2, ge=1, le=10, description="转发权重")
    weight_favourites: int = Field(default=1, ge=1, le=10, description="点赞权重")


class ScrapeConfig(BaseModel):
    """采集配置"""

    # 基础配置
    scrape_enabled: bool = Field(default=True, description="是否启用采集")
    normal_scrape_interval: int = Field(default=3600, description="正常时段采集间隔（秒）")
    sleep_scrape_interval: int = Field(default=21600, description="睡眠时段采集间隔（秒）")
    min_scrape_gap: int = Field(default=300, description="最小采集间隔（秒）")

    # Trump 作息时间（美东时间）
    trump_sleep_start_hour: int = Field(default=0, description="Trump 睡眠开始时间（美东）")
    trump_sleep_end_hour: int = Field(default=7, description="Trump 睡眠结束时间（美东）")


class TranslateConfig(BaseModel):
    """翻译配置"""

    translate_enabled: bool = Field(default=True, description="是否启用翻译")


class RuntimeConfig(BaseModel):
    """运行时配置"""

    notification: NotificationConfig = Field(default_factory=NotificationConfig)
    scrape: ScrapeConfig = Field(default_factory=ScrapeConfig)
    translate: TranslateConfig = Field(default_factory=TranslateConfig)


class RuntimeConfigManager:
    """运行时配置管理器

    从数据库加载配置，支持热更新
    """

    CONFIG_KEY = "runtime_config"
    _instance: Optional["RuntimeConfigManager"] = None
    _config: Optional[RuntimeConfig] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._config = RuntimeConfig()

    @property
    def config(self) -> RuntimeConfig:
        """获取当前配置"""
        return self._config

    @property
    def notification(self) -> NotificationConfig:
        """获取通知配置"""
        return self._config.notification

    @property
    def scrape(self) -> ScrapeConfig:
        """获取采集配置"""
        return self._config.scrape

    @property
    def translate(self) -> TranslateConfig:
        """获取翻译配置"""
        return self._config.translate

    def load_from_db(self) -> bool:
        """从数据库加载配置

        Returns:
            是否加载成功
        """
        try:
            db = get_db_manager()
            with db.get_session() as session:
                result = session.execute(
                    text(
                        "SELECT config_value FROM system_config WHERE config_key = :key"
                    ),
                    {"key": self.CONFIG_KEY},
                )
                row = result.fetchone()

                if row:
                    config_dict = json.loads(row[0])
                    self._config = RuntimeConfig(**config_dict)
                    logger.debug("从数据库加载运行时配置成功")
                    return True
                else:
                    # 数据库没有配置，使用默认值并保存
                    self._init_from_env()
                    self.save_to_db()
                    logger.info("数据库无配置，已初始化默认配置")
                    return True

        except Exception as e:
            logger.error(f"加载运行时配置失败: {e}")
            return False

    def _init_from_env(self) -> None:
        """从环境变量初始化配置"""
        from src.config import settings

        self._config = RuntimeConfig(
            notification=NotificationConfig(
                feishu_enabled=settings.feishu_enabled,
                feishu_webhook=settings.feishu_webhook_url or None,
                feishu_secret=settings.feishu_secret or None,
                realtime_enabled=True,
                daily_report_enabled=True,
                daily_report_time="09:00",
                weekly_report_enabled=True,
                weekly_report_time="09:00",
                weekly_report_day=1,
                full_display_count=10,
                summary_display_count=10,
                ai_analysis_limit=20,
                weight_replies=3,
                weight_reblogs=2,
                weight_favourites=1,
            ),
            scrape=ScrapeConfig(
                scrape_enabled=True,
                normal_scrape_interval=settings.normal_scrape_interval,
                sleep_scrape_interval=settings.sleep_scrape_interval,
                min_scrape_gap=settings.min_scrape_gap,
                trump_sleep_start_hour=settings.trump_sleep_start_hour,
                trump_sleep_end_hour=settings.trump_sleep_end_hour,
            ),
            translate=TranslateConfig(
                translate_enabled=settings.translate_enabled,
            ),
        )

    def save_to_db(self) -> bool:
        """保存配置到数据库

        Returns:
            是否保存成功
        """
        try:
            db = get_db_manager()
            config_json = self._config.model_dump_json()

            with db.get_session() as session:
                session.execute(
                    text(
                        """
                        INSERT INTO system_config (config_key, config_value, updated_at)
                        VALUES (:key, :value, NOW())
                        ON DUPLICATE KEY UPDATE
                        config_value = :value, updated_at = NOW()
                        """
                    ),
                    {"key": self.CONFIG_KEY, "value": config_json},
                )
                session.commit()

            logger.info("运行时配置已保存到数据库")
            return True

        except Exception as e:
            logger.error(f"保存运行时配置失败: {e}")
            return False

    def update_notification(self, config: NotificationConfig) -> bool:
        """更新通知配置

        Args:
            config: 新的通知配置

        Returns:
            是否更新成功
        """
        self._config.notification = config
        return self.save_to_db()

    def update_scrape(self, config: ScrapeConfig) -> bool:
        """更新采集配置

        Args:
            config: 新的采集配置

        Returns:
            是否更新成功
        """
        self._config.scrape = config
        return self.save_to_db()

    def update_translate(self, config: TranslateConfig) -> bool:
        """更新翻译配置

        Args:
            config: 新的翻译配置

        Returns:
            是否更新成功
        """
        self._config.translate = config
        return self.save_to_db()

    def reload(self) -> bool:
        """重新加载配置

        Returns:
            是否加载成功
        """
        return self.load_from_db()


def get_runtime_config() -> RuntimeConfigManager:
    """获取运行时配置管理器单例"""
    return RuntimeConfigManager()
