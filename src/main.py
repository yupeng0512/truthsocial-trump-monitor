"""Truth Social Trump Monitor 主程序

功能：
1. 定时采集 Trump 的 Truth Social 帖子
2. 存储到 MySQL 数据库
3. 新帖子通过飞书推送通知
4. 可选翻译服务（腾讯云）
5. 智能调度（Trump 睡眠时间减少采集频率）
6. 定时报告（每日摘要、每周总结）
"""

import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from src.analyzer import LLMAnalyzer, get_trump_analyzer
from src.config import settings
from src.notification import FeishuClient
from src.scraper import ScrapeCreatorsClient
from src.scraper.scrapecreators import parse_post_data
from src.storage import DatabaseManager, get_db_manager
from src.runtime_config import get_runtime_config


# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level,
)
logger.add(
    "logs/monitor_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG",
)


class TrumpMonitor:
    """Trump Truth Social 监控器"""

    # 美东时区
    TRUMP_TZ = ZoneInfo("America/New_York")
    SERVER_TZ = ZoneInfo(settings.timezone)

    def __init__(self):
        """初始化监控器"""
        self.db: Optional[DatabaseManager] = None
        self.scraper: Optional[ScrapeCreatorsClient] = None
        self.feishu: Optional[FeishuClient] = None
        self.llm: Optional[LLMAnalyzer] = None
        self.trump_analyzer = None  # Trump 言论分析 Agent
        self.translator = None  # 延迟初始化
        self.scheduler: Optional[AsyncIOScheduler] = None
        self.running = False
        self.is_first_run = True  # 标记是否首次运行
        self.current_interval = settings.normal_scrape_interval
        self.runtime_config = get_runtime_config()

    def is_trump_sleeping(self) -> bool:
        """
        判断当前是否是 Trump 的睡眠时间

        Trump 通常在美东时间 0:00-7:00 睡觉
        """
        now_est = datetime.now(self.TRUMP_TZ)
        hour = now_est.hour
        scrape_config = self.runtime_config.scrape
        return scrape_config.trump_sleep_start_hour <= hour < scrape_config.trump_sleep_end_hour

    def get_current_interval(self) -> int:
        """根据 Trump 作息时间获取当前采集间隔"""
        scrape_config = self.runtime_config.scrape
        if self.is_trump_sleeping():
            return scrape_config.sleep_scrape_interval
        return scrape_config.normal_scrape_interval

    def should_skip_scrape(self) -> bool:
        """
        判断是否应该跳过本次采集

        如果距离上次采集时间小于 min_scrape_gap，则跳过
        避免频繁重启时重复调用 API
        """
        if not self.db:
            return False

        last_scrape = self.db.get_last_scrape_time()
        if not last_scrape:
            return False

        # 确保时区一致
        now = datetime.now()
        if last_scrape.tzinfo:
            now = datetime.now(last_scrape.tzinfo)

        gap = (now - last_scrape).total_seconds()
        scrape_config = self.runtime_config.scrape
        if gap < scrape_config.min_scrape_gap:
            logger.info(
                f"距离上次采集仅 {int(gap)} 秒，小于最小间隔 {scrape_config.min_scrape_gap} 秒，跳过本次采集"
            )
            return True
        return False

    async def init(self) -> None:
        """初始化各组件"""
        logger.info("初始化 Trump Monitor...")

        # 初始化数据库
        self.db = get_db_manager()
        self.db.init_db()
        logger.info("数据库初始化完成")

        # 加载运行时配置
        self.runtime_config.load_from_db()
        logger.info("运行时配置加载完成")

        # 初始化 ScrapeCreators 客户端
        if settings.scrapecreators_api_key:
            self.scraper = ScrapeCreatorsClient()
            logger.info("ScrapeCreators 客户端初始化完成")
        else:
            logger.warning("未配置 ScrapeCreators API Key，采集功能不可用")

        # 初始化飞书客户端（从运行时配置读取）
        notification_config = self.runtime_config.notification
        if notification_config.feishu_enabled and notification_config.feishu_webhook:
            self.feishu = FeishuClient(
                webhook_url=notification_config.feishu_webhook,
                secret=notification_config.feishu_secret,
            )
            logger.info("飞书客户端初始化完成")
        elif settings.feishu_enabled and settings.feishu_webhook_url:
            # 回退到环境变量配置
            self.feishu = FeishuClient()
            logger.info("飞书客户端初始化完成（使用环境变量配置）")
        else:
            logger.warning("飞书通知未启用或未配置")

        # 初始化 LLM 分析器
        if settings.llm_enabled:
            self.llm = LLMAnalyzer()
            logger.info("LLM 分析器初始化完成")
        else:
            logger.info("LLM 分析未启用")

        # 初始化 Trump 言论分析 Agent（Knot AG-UI）
        if settings.knot_enabled:
            try:
                self.trump_analyzer = get_trump_analyzer()
                logger.info("Trump 言论分析 Agent 初始化完成")
            except Exception as e:
                logger.warning(f"Trump 言论分析 Agent 初始化失败: {e}")
                self.trump_analyzer = None
        else:
            logger.info("Trump 言论分析 Agent 未启用")

        # 初始化翻译器
        translate_config = self.runtime_config.translate
        if translate_config.translate_enabled and settings.translate_enabled:
            try:
                from src.integrations.translator import TencentTranslator
                self.translator = TencentTranslator()
                if self.translator.enabled:
                    logger.info("腾讯云翻译初始化完成")
                else:
                    logger.info("翻译服务未配置密钥，翻译功能不可用")
            except Exception as e:
                logger.warning(f"翻译服务初始化失败: {e}")
                self.translator = None

        # 初始化调度器
        self.scheduler = AsyncIOScheduler()

    async def scrape_and_notify(self) -> None:
        """执行一次采集和通知任务"""
        if not self.scraper:
            logger.error("ScrapeCreators 客户端未初始化")
            return

        # 检查是否需要跳过（防止频繁重启时重复调用 API）
        if self.should_skip_scrape():
            # 首次运行但数据库已有数据，标记为非首次运行
            if self.is_first_run and self.db:
                post_count = self.db.get_post_count()
                if post_count > 0:
                    logger.info(f"数据库已有 {post_count} 条帖子，跳过首次采集")
                    self.is_first_run = False
            return

        # 动态调整采集间隔
        new_interval = self.get_current_interval()
        if new_interval != self.current_interval:
            self.current_interval = new_interval
            self._reschedule_job()
            now_est = datetime.now(self.TRUMP_TZ)
            logger.info(
                f"采集间隔调整为 {new_interval // 3600}h "
                f"(美东时间: {now_est.strftime('%H:%M')}, "
                f"{'睡眠时段' if self.is_trump_sleeping() else '活跃时段'})"
            )

        username = settings.truthsocial_username
        started_at = datetime.now()
        logger.info(f"开始采集 @{username} 的帖子...")

        try:
            # 获取最新帖子
            raw_posts = await self.scraper.fetch_latest_posts(
                username=username,
                max_posts=20,  # 每次最多获取 20 条
            )

            if not raw_posts:
                logger.info("未获取到新帖子")
                self.db.log_scrape(
                    username=username,
                    status="success",
                    total_fetched=0,
                    new_posts=0,
                    updated_posts=0,
                    started_at=started_at,
                )
                return

            # 解析帖子数据
            posts_data = []
            for raw_post in raw_posts:
                parsed = parse_post_data(raw_post)
                parsed["username"] = username

                # 解析发布时间
                created_at_str = parsed.get("created_at", "")
                if created_at_str:
                    try:
                        # 尝试多种时间格式
                        for fmt in [
                            "%Y-%m-%dT%H:%M:%S.%fZ",
                            "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%d %H:%M:%S",
                        ]:
                            try:
                                parsed["posted_at"] = datetime.strptime(
                                    created_at_str, fmt
                                )
                                break
                            except ValueError:
                                continue
                    except Exception as e:
                        logger.warning(f"解析时间失败: {created_at_str}, {e}")

                posts_data.append(parsed)

            # 保存到数据库
            new_count, updated_count = self.db.save_posts_batch(posts_data)

            logger.info(
                f"采集完成: 获取 {len(raw_posts)} 条, "
                f"新增 {new_count}, 更新 {updated_count}"
            )

            # 记录采集日志
            self.db.log_scrape(
                username=username,
                status="success",
                total_fetched=len(raw_posts),
                new_posts=new_count,
                updated_posts=updated_count,
                started_at=started_at,
            )

            # 发送通知（仅新帖子，且非首次运行）
            # 首次运行时只存储数据，不发送通知，避免一次性发送大量历史帖子
            notification_config = self.runtime_config.notification
            if new_count > 0 and self.feishu and notification_config.realtime_enabled:
                if self.is_first_run:
                    logger.info(f"首次运行，跳过通知 {new_count} 条历史帖子，已标记为已通知")
                    # 首次运行时直接标记所有帖子为已通知
                    self.db.mark_all_posts_notified()
                else:
                    await self.send_notifications()
            elif new_count > 0 and not notification_config.realtime_enabled:
                logger.info(f"实时推送已禁用，跳过 {new_count} 条新帖子通知")
                # 标记为已通知，避免后续重复处理
                self.db.mark_all_posts_notified()

            # LLM 分析（如果启用）
            if self.llm and settings.llm_enabled:
                await self.run_llm_analysis()

        except Exception as e:
            logger.error(f"采集任务失败: {e}")
            self.db.log_scrape(
                username=username,
                status="failed",
                error_message=str(e),
                started_at=started_at,
            )

    def translate_post(self, post: "Post") -> Optional[str]:
        """翻译帖子内容并更新数据库

        Args:
            post: 帖子对象

        Returns:
            翻译后的内容，如果翻译失败或不需要翻译则返回 None
        """
        if not self.translator or not self.translator.enabled:
            return None

        # 如果已有翻译，直接返回
        if post.translated_content:
            return post.translated_content

        content = post.content or ""
        if not content.strip():
            logger.debug(f"帖子 {post.post_id} 内容为空（可能是视频/图片），跳过翻译")
            return None

        try:
            _, translated = self.translator.translate_if_english(content)
            if translated:
                # 更新数据库
                self.db.update_translation(post.id, translated)
                logger.debug(f"帖子 {post.post_id} 翻译完成")
                return translated
        except Exception as e:
            logger.warning(f"翻译帖子 {post.post_id} 失败: {e}")

        return None

    async def send_notifications(self) -> None:
        """发送未通知的帖子"""
        if not self.feishu:
            return

        try:
            # 获取未通知的帖子
            unnotified = self.db.get_unnotified_posts(limit=10)
            if not unnotified:
                return

            logger.info(f"发送 {len(unnotified)} 条帖子通知...")

            # 批量发送或逐条发送
            if len(unnotified) == 1:
                # 单条帖子
                post = unnotified[0]

                # 翻译并更新数据库
                translated = self.translate_post(post)

                # AI 分析（如果启用）
                ai_analysis = await self._analyze_post(post, translated)

                success = await self.feishu.send_trump_post(
                    post_content=post.content or "",
                    post_url=post.url or "",
                    posted_at=post.posted_at,
                    reblogs_count=post.reblogs_count,
                    favourites_count=post.favourites_count,
                    is_reblog=post.is_reblog,
                    translated_content=translated,
                    ai_analysis=ai_analysis,
                )
            else:
                # 多条帖子批量发送
                posts_data = []
                for p in unnotified:
                    # 翻译并更新数据库
                    translated = self.translate_post(p)
                    
                    # AI 分析（如果启用）
                    ai_analysis = await self._analyze_post(p, translated)

                    post_dict = {
                        "content": p.content,
                        "url": p.url,
                        "posted_at": p.posted_at,
                        "is_reblog": p.is_reblog,
                        "translated_content": translated,
                        "ai_analysis": ai_analysis,
                    }
                    posts_data.append(post_dict)

                success = await self.feishu.send_batch_posts(posts_data)

            if success:
                # 标记为已通知
                post_ids = [p.id for p in unnotified]
                self.db.mark_posts_notified(post_ids)
                logger.info(f"通知发送成功，已标记 {len(post_ids)} 条帖子")
            else:
                logger.error("通知发送失败")

        except Exception as e:
            logger.error(f"发送通知失败: {e}")

    async def _analyze_post(self, post, translated_content: Optional[str] = None) -> Optional[dict]:
        """使用 Trump 言论分析 Agent 分析帖子
        
        Args:
            post: 帖子对象
            translated_content: 翻译后的内容
            
        Returns:
            分析结果字典，如果分析失败或未启用则返回 None
        """
        if not self.trump_analyzer or not settings.knot_enabled:
            return None
        
        try:
            logger.info(f"开始 AI 分析帖子 {post.post_id}...")
            
            result = await self.trump_analyzer.analyze_post(
                content=post.content or "",
                translated_content=translated_content,
                posted_at=post.posted_at,
            )
            
            if result["status"] == "success" and result["analysis"]:
                logger.info(f"帖子 {post.post_id} AI 分析完成")
                return result["analysis"]
            else:
                if result["error"]:
                    logger.warning(f"帖子 {post.post_id} AI 分析失败: {result['error']}")
                return None
                
        except Exception as e:
            logger.warning(f"帖子 {post.post_id} AI 分析异常: {e}")
            return None

    async def _analyze_posts_batch(
        self, 
        posts: list[dict], 
        analysis_focus: Optional[str] = None
    ) -> Optional[dict]:
        """批量分析帖子（用于日报/周报）
        
        Args:
            posts: 帖子列表，每个帖子包含 content, translated_content, posted_at 等字段
            analysis_focus: 分析重点，如 "daily_summary" 或 "weekly_summary"
            
        Returns:
            分析结果字典，如果分析失败或未启用则返回 None
        """
        if not self.trump_analyzer or not settings.knot_enabled:
            return None
        
        if not posts:
            return None
        
        try:
            logger.info(f"开始批量 AI 分析 {len(posts)} 条帖子...")
            
            # 准备帖子数据（只保留必要字段）
            posts_for_analysis = []
            for p in posts:
                post_data = {
                    "content": p.get("content", ""),
                }
                if p.get("translated_content"):
                    post_data["translated_content"] = p["translated_content"]
                if p.get("posted_at"):
                    # 处理 datetime 对象
                    posted_at = p["posted_at"]
                    if hasattr(posted_at, 'isoformat'):
                        post_data["posted_at"] = posted_at.isoformat()
                    else:
                        post_data["posted_at"] = str(posted_at)
                posts_for_analysis.append(post_data)
            
            result = await self.trump_analyzer.analyze_batch(
                posts=posts_for_analysis,
                analysis_focus=analysis_focus,
            )
            
            if result["status"] == "success" and result["analysis"]:
                logger.info(f"批量 AI 分析完成")
                return result["analysis"]
            else:
                if result["error"]:
                    logger.warning(f"批量 AI 分析失败: {result['error']}")
                return None
                
        except Exception as e:
            logger.warning(f"批量 AI 分析异常: {e}")
            return None

    async def run_llm_analysis(self) -> None:
        """运行 LLM 分析（预留）"""
        if not self.llm or not settings.llm_enabled:
            return

        try:
            # 获取未分析的帖子
            unanalyzed = self.db.get_unanalyzed_posts(limit=10)
            if not unanalyzed:
                return

            logger.info(f"开始 LLM 分析 {len(unanalyzed)} 条帖子...")

            for post in unanalyzed:
                try:
                    analysis = await self.llm.analyze_post(
                        content=post.content or "",
                        context={"post_id": post.post_id},
                    )
                    self.db.update_llm_analysis(post.id, analysis)
                    logger.debug(f"帖子 {post.post_id} 分析完成")
                except Exception as e:
                    logger.error(f"分析帖子 {post.post_id} 失败: {e}")

        except Exception as e:
            logger.error(f"LLM 分析任务失败: {e}")

    def _reschedule_job(self) -> None:
        """重新调度采集任务（当间隔变化时）"""
        if not self.scheduler:
            return

        try:
            self.scheduler.reschedule_job(
                "scrape_job",
                trigger=IntervalTrigger(seconds=self.current_interval),
            )
            logger.debug(f"采集任务已重新调度，间隔: {self.current_interval} 秒")
        except Exception as e:
            logger.error(f"重新调度失败: {e}")

    def _setup_report_jobs(self) -> None:
        """设置定时报告任务"""
        notification_config = self.runtime_config.notification

        # 每日摘要
        if notification_config.daily_report_enabled:
            try:
                hour, minute = map(int, notification_config.daily_report_time.split(":"))
                self.scheduler.add_job(
                    self.send_daily_report,
                    trigger=CronTrigger(hour=hour, minute=minute, timezone=self.SERVER_TZ),
                    id="daily_report_job",
                    name="每日摘要推送",
                    replace_existing=True,
                )
                logger.info(f"每日摘要任务已设置: 每天 {notification_config.daily_report_time} ({settings.timezone})")
            except Exception as e:
                logger.error(f"设置每日摘要任务失败: {e}")

        # 每周总结
        if notification_config.weekly_report_enabled:
            try:
                hour, minute = map(int, notification_config.weekly_report_time.split(":"))
                # APScheduler 的 day_of_week: 0=周一, 6=周日
                day_of_week = notification_config.weekly_report_day - 1
                self.scheduler.add_job(
                    self.send_weekly_report,
                    trigger=CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute, timezone=self.SERVER_TZ),
                    id="weekly_report_job",
                    name="每周总结推送",
                    replace_existing=True,
                )
                day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
                logger.info(
                    f"每周总结任务已设置: 每{day_names[day_of_week]} {notification_config.weekly_report_time} ({settings.timezone})"
                )
            except Exception as e:
                logger.error(f"设置每周总结任务失败: {e}")

        # 定期重新加载配置（每 5 分钟）
        self.scheduler.add_job(
            self._reload_config,
            trigger=IntervalTrigger(minutes=5),
            id="config_reload_job",
            name="配置重载",
            replace_existing=True,
        )

    async def _reload_config(self) -> None:
        """重新加载运行时配置"""
        try:
            old_config = self.runtime_config.config.model_copy()
            self.runtime_config.reload()
            new_config = self.runtime_config.config

            # 检查采集间隔是否变化
            if (
                old_config.scrape.normal_scrape_interval != new_config.scrape.normal_scrape_interval
                or old_config.scrape.sleep_scrape_interval != new_config.scrape.sleep_scrape_interval
            ):
                new_interval = self.get_current_interval()
                if new_interval != self.current_interval:
                    self.current_interval = new_interval
                    self._reschedule_job()
                    logger.info(f"采集间隔已更新为 {new_interval} 秒")

            # 检查飞书配置是否变化
            if (
                old_config.notification.feishu_webhook != new_config.notification.feishu_webhook
                or old_config.notification.feishu_secret != new_config.notification.feishu_secret
            ):
                if new_config.notification.feishu_enabled and new_config.notification.feishu_webhook:
                    self.feishu = FeishuClient(
                        webhook_url=new_config.notification.feishu_webhook,
                        secret=new_config.notification.feishu_secret,
                    )
                    logger.info("飞书客户端配置已更新")

            logger.debug("配置重载完成")
        except Exception as e:
            logger.error(f"配置重载失败: {e}")

    async def send_daily_report(self) -> None:
        """发送每日摘要"""
        notification_config = self.runtime_config.notification
        if not notification_config.feishu_enabled or not self.feishu:
            logger.debug("飞书未启用，跳过每日摘要")
            return

        try:
            from sqlalchemy import select

            # 使用服务器时区获取今天的开始时间
            now = datetime.now(self.SERVER_TZ)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            # 转换为无时区的 datetime 用于数据库查询（数据库存储的是本地时间）
            today_start_naive = today_start.replace(tzinfo=None)
            logger.info(f"每日摘要时间范围: {today_start_naive} 至今 ({settings.timezone})")

            with self.db.get_session() as session:
                from src.storage.models import Post

                posts = session.execute(
                    select(Post)
                    .where(Post.posted_at >= today_start_naive)
                    .order_by(Post.posted_at.desc())
                ).scalars().all()

                if not posts:
                    logger.info("今日无新帖子，跳过每日摘要")
                    return

                # 转换为字典格式，并补充翻译
                posts_data = []
                for post in posts:
                    # 如果没有翻译，尝试翻译
                    translated = post.translated_content
                    if not translated and self.translator and self.translator.enabled:
                        translated = self.translate_post(post)
                    
                    posts_data.append({
                        "content": post.content or "",
                        "translated_content": translated or "",
                        "posted_at": post.posted_at,
                        "is_reblog": post.is_reblog,
                        "url": post.url or "",
                    })

                # AI 分析（如果启用）
                ai_analysis = await self._analyze_posts_batch(
                    posts_data, 
                    analysis_focus="daily_summary"
                )

                success = await self.feishu.send_daily_report(
                    posts_data, 
                    today_start,
                    ai_analysis=ai_analysis,
                )
                if success:
                    logger.info(f"每日摘要推送成功，共 {len(posts)} 条帖子")
                else:
                    logger.error("每日摘要推送失败")

        except Exception as e:
            logger.error(f"发送每日摘要失败: {e}")

    async def send_weekly_report(self) -> None:
        """发送每周总结"""
        notification_config = self.runtime_config.notification
        if not notification_config.feishu_enabled or not self.feishu:
            logger.debug("飞书未启用，跳过每周总结")
            return

        try:
            from sqlalchemy import select, func, and_

            # 使用服务器时区获取本周的开始时间
            now = datetime.now(self.SERVER_TZ)
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            # 转换为无时区的 datetime 用于数据库查询
            week_start_naive = week_start.replace(tzinfo=None)
            logger.info(f"每周总结时间范围: {week_start_naive} 至今 ({settings.timezone})")

            with self.db.get_session() as session:
                from src.storage.models import Post

                # 统计数据
                total_count = session.execute(
                    select(func.count(Post.id)).where(Post.posted_at >= week_start_naive)
                ).scalar() or 0

                original_count = session.execute(
                    select(func.count(Post.id)).where(
                        and_(Post.posted_at >= week_start_naive, Post.is_reblog == False)
                    )
                ).scalar() or 0

                reblog_count = total_count - original_count

                # 从配置获取热门帖子数量
                top_posts_limit = notification_config.weekly_report_top_posts

                # 获取热门帖子
                hot_posts = session.execute(
                    select(Post)
                    .where(Post.posted_at >= week_start_naive)
                    .order_by(
                        (Post.reblogs_count + Post.favourites_count + Post.replies_count).desc()
                    )
                    .limit(top_posts_limit)
                ).scalars().all()

                if total_count == 0:
                    logger.info("本周无帖子，跳过每周总结")
                    return

                # 转换为字典格式，并补充翻译
                hot_posts_data = []
                for post in hot_posts:
                    # 如果没有翻译，尝试翻译
                    translated = post.translated_content
                    if not translated and self.translator and self.translator.enabled:
                        translated = self.translate_post(post)
                    
                    hot_posts_data.append({
                        "content": post.content or "",
                        "translated_content": translated or "",
                        "reblogs_count": post.reblogs_count,
                        "favourites_count": post.favourites_count,
                        "replies_count": post.replies_count,
                        "url": post.url or "",
                        "posted_at": post.posted_at.isoformat() if post.posted_at else None,
                    })

                # AI 分析（如果启用）- 分析热门帖子
                ai_analysis = await self._analyze_posts_batch(
                    hot_posts_data,
                    analysis_focus="weekly_summary"
                )

                success = await self.feishu.send_weekly_report(
                    week_start=week_start_naive,
                    week_end=now.replace(tzinfo=None),
                    total_posts=total_count,
                    original_posts=original_count,
                    reblog_posts=reblog_count,
                    hot_posts=hot_posts_data,
                    ai_analysis=ai_analysis,
                    top_posts_count=top_posts_limit,
                )
                if success:
                    logger.info(f"每周总结推送成功，本周共 {total_count} 条帖子")
                else:
                    logger.error("每周总结推送失败")

        except Exception as e:
            logger.error(f"发送每周总结失败: {e}")

    async def start(self) -> None:
        """启动监控器"""
        await self.init()

        self.running = True

        # 根据当前时间确定初始采集间隔
        self.current_interval = self.get_current_interval()
        now_est = datetime.now(self.TRUMP_TZ)
        logger.info(
            f"Trump Monitor 启动 (美东时间: {now_est.strftime('%Y-%m-%d %H:%M')})"
        )
        logger.info(
            f"当前{'睡眠' if self.is_trump_sleeping() else '活跃'}时段，"
            f"采集间隔: {self.current_interval // 3600}h"
        )

        # 添加采集任务
        scrape_config = self.runtime_config.scrape
        if scrape_config.scrape_enabled:
            self.scheduler.add_job(
                self.scrape_and_notify,
                trigger=IntervalTrigger(seconds=self.current_interval),
                id="scrape_job",
                name="Truth Social 采集任务",
                replace_existing=True,
            )
        else:
            logger.warning("采集功能已禁用")

        # 设置定时报告任务
        self._setup_report_jobs()

        # 启动调度器
        self.scheduler.start()

        # 检查是否需要立即执行采集
        should_scrape_now = True
        if self.db and scrape_config.scrape_enabled:
            last_scrape = self.db.get_last_scrape_time()
            if last_scrape:
                now = datetime.now()
                if last_scrape.tzinfo:
                    now = datetime.now(last_scrape.tzinfo)
                gap = (now - last_scrape).total_seconds()
                if gap < scrape_config.min_scrape_gap:
                    should_scrape_now = False
                    logger.info(
                        f"距离上次采集 {int(gap)} 秒，跳过首次采集"
                    )
                    # 检查数据库是否有数据，有则标记为非首次运行
                    post_count = self.db.get_post_count()
                    if post_count > 0:
                        self.is_first_run = False
                        logger.info(f"数据库已有 {post_count} 条帖子")

        if should_scrape_now and scrape_config.scrape_enabled:
            logger.info("执行首次采集...")
            await self.scrape_and_notify()
            self.is_first_run = False

        # 保持运行
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("收到停止信号")

    async def stop(self) -> None:
        """停止监控器"""
        logger.info("正在停止 Trump Monitor...")
        self.running = False

        if self.scheduler:
            self.scheduler.shutdown(wait=False)

        logger.info("Trump Monitor 已停止")


async def main():
    """主函数"""
    monitor = TrumpMonitor()

    # 设置信号处理
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("收到终止信号，正在停止...")
        asyncio.create_task(monitor.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)

    try:
        await monitor.start()
    except Exception as e:
        logger.error(f"监控器异常: {e}")
    finally:
        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
