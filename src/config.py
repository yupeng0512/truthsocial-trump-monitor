"""配置管理模块"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ScrapeCreators API 配置
    scrapecreators_api_key: str = Field(default="", description="ScrapeCreators API Key")
    
    # 监控目标
    truthsocial_username: str = Field(default="realDonaldTrump", description="监控的用户名")
    
    # 采集频率（秒）
    scrape_interval: int = Field(default=3600, description="采集间隔（秒）")

    # MySQL 配置
    mysql_host: str = Field(default="mysql", description="MySQL 主机")
    mysql_port: int = Field(default=3306, description="MySQL 端口")
    mysql_user: str = Field(default="truthsocial", description="MySQL 用户名")
    mysql_password: str = Field(default="", description="MySQL 密码")
    mysql_database: str = Field(default="truthsocial_monitor", description="MySQL 数据库名")

    # 飞书配置
    feishu_webhook_url: str = Field(default="", description="飞书 Webhook URL")
    feishu_secret: str = Field(default="", description="飞书签名密钥")
    feishu_enabled: bool = Field(default=True, description="是否启用飞书通知")

    # LLM 配置（预留）
    llm_enabled: bool = Field(default=False, description="是否启用 LLM 分析")
    llm_api_key: str = Field(default="", description="LLM API Key")
    llm_api_base: str = Field(default="", description="LLM API Base URL")
    llm_model: str = Field(default="gpt-4o-mini", description="LLM 模型")

    # Knot Agent 配置（AG-UI 协议）
    # 用于调用 Trump 言论分析 Agent
    knot_enabled: bool = Field(default=False, description="是否启用 Knot Agent 分析")
    knot_agent_id: str = Field(default="", description="Knot 智能体 ID")
    knot_api_token: str = Field(default="", description="Knot 用户个人 Token（推荐）")
    knot_agent_token: str = Field(default="", description="Knot 智能体 Token")
    knot_username: str = Field(default="", description="Knot 用户名（使用智能体 Token 时需要）")
    knot_model: str = Field(default="deepseek-v3.1", description="Knot 调用的模型")

    # 腾讯云翻译配置
    tencentcloud_secret_id: str = Field(default="", description="腾讯云 SecretId")
    tencentcloud_secret_key: str = Field(default="", description="腾讯云 SecretKey")
    tencentcloud_region: str = Field(default="ap-guangzhou", description="腾讯云地域")
    tencentcloud_project_id: int = Field(default=0, description="腾讯云项目ID")
    translate_enabled: bool = Field(default=True, description="是否启用翻译")

    # 智能调度配置
    # Trump 睡眠时间（美东时间 EST/EDT）
    trump_sleep_start_hour: int = Field(default=0, description="Trump 睡眠开始时间(美东)")
    trump_sleep_end_hour: int = Field(default=7, description="Trump 睡眠结束时间(美东)")
    sleep_scrape_interval: int = Field(default=21600, description="睡眠时段采集间隔(秒)，默认6小时")
    normal_scrape_interval: int = Field(default=3600, description="正常时段采集间隔(秒)，默认1小时")
    min_scrape_gap: int = Field(default=300, description="最小采集间隔(秒)，防止频繁重启时重复采集")

    # API 配置
    api_fetch_limit: int = Field(default=300, description="前端获取帖子的默认数量限制")

    # 通用配置
    timezone: str = Field(default="Asia/Shanghai", description="服务器时区")
    log_level: str = Field(default="INFO", description="日志级别")

    @property
    def database_url(self) -> str:
        """获取数据库连接 URL"""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
