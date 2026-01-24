"""飞书客户端

负责与飞书 API 通信，支持多种 Webhook 类型。
"""

import base64
import hashlib
import hmac
import time
from datetime import datetime
from typing import Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings

from .builder import MessageBuilder, get_local_time


class FeishuClient:
    """飞书机器人客户端

    支持两种 Webhook 类型：
    1. 传统群机器人 Webhook: https://open.feishu.cn/open-apis/bot/v2/hook/xxx
    2. 机器人应用 Webhook 触发器: https://botbuilder.feishu.cn/api/trigger/xxx
    """

    # Webhook 类型常量
    TYPE_BOT_WEBHOOK = "bot_webhook"
    TYPE_BOT_BUILDER = "bot_builder"

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

        self.webhook_type = self._detect_webhook_type(self.webhook_url)
        logger.info(f"Feishu client initialized with webhook type: {self.webhook_type}")

    def _detect_webhook_type(self, url: str) -> str:
        """根据 URL 自动识别 Webhook 类型"""
        if (
            "botbuilder.feishu.cn" in url
            or "trigger-webhook" in url
            or "/flow/api/" in url
        ):
            return self.TYPE_BOT_BUILDER
        return self.TYPE_BOT_WEBHOOK

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
        """发送消息到 Bot Builder Webhook 触发器"""
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

            logger.info(f"Feishu Bot Builder send success: {response.text[:200]}")
            return True

    async def send_text(self, text: str) -> bool:
        """发送文本消息"""
        if len(text) > self.max_length:
            text = text[: self.max_length - 3] + "..."

        payload = {"msg_type": "text", "content": {"text": text}}
        return await self._send(payload)

    async def send_interactive(
        self,
        title: str,
        elements: list[dict],
        header_color: str = "blue",
    ) -> bool:
        """发送交互式卡片消息"""
        payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": title},
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
        """发送 Markdown 卡片消息"""
        if self.webhook_type == self.TYPE_BOT_BUILDER:
            text = f"{title}\n\n{content}"
            return await self._send_bot_builder(text, report_type, total_titles)
        else:
            elements = [{"tag": "markdown", "content": content}]
            return await self.send_interactive(title, elements, header_color)

    # ==================== 业务方法 ====================

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
        """发送 Trump 帖子通知"""
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

    async def send_batch_posts(self, posts: list[dict]) -> bool:
        """批量发送帖子通知"""
        if not posts:
            return True

        msg = MessageBuilder.build_batch_posts(posts)
        content = msg.to_text()

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
        text_posts_count: int = 0,
        media_posts_count: int = 0,
    ) -> bool:
        """发送每日摘要
        
        Args:
            posts: 帖子列表
            date: 报告日期
            ai_analysis: AI 分析结果
            text_posts_count: 有文本内容的帖子数
            media_posts_count: 纯媒体帖子数
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
                "content": post.get("content", ""),
                "translation": post.get("translated_content", ""),
                "url": post.get("url", ""),
            })

        msg = MessageBuilder.build_daily_report(
            date, 
            formatted_posts, 
            ai_analysis=ai_analysis,
            text_posts_count=text_posts_count,
            media_posts_count=media_posts_count,
        )
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
        """发送每周总结"""
        # 格式化热门帖子
        formatted_hot_posts = []
        for post in hot_posts:
            interactions = (
                post.get("reblogs_count", 0)
                + post.get("favourites_count", 0)
                + post.get("replies_count", 0)
            )
            formatted_hot_posts.append({
                "content": post.get("content", ""),
                "translation": post.get("translated_content", ""),
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
        """发送告警消息"""
        color_map = {"info": "blue", "warning": "orange", "error": "red"}
        return await self.send_markdown_card(
            title,
            content,
            color_map.get(level, "blue"),
            report_type="alert",
            total_titles=1,
        )
