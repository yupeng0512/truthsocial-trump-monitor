"""API 服务模块

提供 REST API 供前端调用
"""

from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from src.config import settings
from src.storage import get_db_manager
from src.storage.models import Post, ScrapeLog
from src.runtime_config import (
    get_runtime_config,
    NotificationConfig,
    ScrapeConfig,
    TranslateConfig,
)

# 服务器时区
SERVER_TZ = ZoneInfo(settings.timezone)

# 翻译器（延迟初始化）
_translator = None

def get_translator():
    """获取翻译器实例"""
    global _translator
    if _translator is None:
        runtime_config = get_runtime_config()
        if runtime_config.translate.translate_enabled and settings.translate_enabled:
            try:
                from src.integrations.translator import TencentTranslator
                _translator = TencentTranslator()
                if not _translator.enabled:
                    _translator = None
            except Exception as e:
                logger.warning(f"翻译器初始化失败: {e}")
                _translator = None
    return _translator

def translate_post_content(post: Post, db) -> str:
    """翻译帖子内容并更新数据库
    
    Args:
        post: 帖子对象
        db: 数据库管理器
        
    Returns:
        翻译后的内容，如果翻译失败或不需要翻译则返回空字符串
    """
    # 如果已有翻译，直接返回
    if post.translated_content:
        return post.translated_content
    
    translator = get_translator()
    if not translator:
        return ""
    
    content = post.content or ""
    if not content.strip():
        logger.debug(f"帖子 {post.post_id} 内容为空（可能是视频/图片），跳过翻译")
        return ""
    
    try:
        _, translated = translator.translate_if_english(content)
        if translated:
            # 更新数据库
            db.update_translation(post.id, translated)
            logger.debug(f"帖子 {post.post_id} 翻译完成")
            return translated
    except Exception as e:
        logger.warning(f"翻译帖子 {post.post_id} 失败: {e}")
    
    return ""

# 创建 FastAPI 应用
app = FastAPI(
    title="Trump Truth Social Monitor API",
    description="Trump Truth Social 帖子监控 API",
    version="1.0.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 响应模型
class PostResponse(BaseModel):
    id: int
    post_id: str
    username: str
    content: Optional[str]
    url: Optional[str]
    reblogs_count: int
    favourites_count: int
    replies_count: int
    is_reblog: bool
    posted_at: Optional[datetime]
    created_at: datetime
    translated_content: Optional[str] = None
    translated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_posts: int
    today_posts: int
    last_scrape: Optional[datetime]
    next_scrape: Optional[datetime]
    scrape_interval: int


class ConfigResponse(BaseModel):
    api_fetch_limit: int
    scrape_interval: int
    sleep_scrape_interval: int
    normal_scrape_interval: int


class PostsListResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    page: int
    page_size: int


# API 路由
@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/config", response_model=ConfigResponse)
async def get_config():
    """获取前端配置"""
    return ConfigResponse(
        api_fetch_limit=settings.api_fetch_limit,
        scrape_interval=settings.scrape_interval,
        sleep_scrape_interval=settings.sleep_scrape_interval,
        normal_scrape_interval=settings.normal_scrape_interval,
    )


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats():
    """获取统计信息"""
    db = get_db_manager()
    
    with db.get_session() as session:
        # 总帖子数
        total_posts = session.execute(
            select(func.count(Post.id))
        ).scalar() or 0
        
        # 今日帖子数（基于帖子发布时间 posted_at，而非入库时间 created_at）
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_posts = session.execute(
            select(func.count(Post.id)).where(Post.posted_at >= today_start)
        ).scalar() or 0
        
        # 最后采集时间
        last_scrape_log = session.execute(
            select(ScrapeLog)
            .where(ScrapeLog.status == "success")
            .order_by(ScrapeLog.finished_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        
        last_scrape = last_scrape_log.finished_at if last_scrape_log else None
        
        # 计算下次采集时间
        next_scrape = None
        if last_scrape:
            next_scrape = last_scrape + timedelta(seconds=settings.scrape_interval)
    
    return StatsResponse(
        total_posts=total_posts,
        today_posts=today_posts,
        last_scrape=last_scrape,
        next_scrape=next_scrape,
        scrape_interval=settings.scrape_interval,
    )


@app.get("/api/posts", response_model=PostsListResponse)
async def get_posts(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=500, description="每页数量"),
    filter_type: Optional[str] = Query(None, description="过滤类型: original/reblog"),
    search: Optional[str] = Query(None, description="搜索关键词"),
):
    """获取帖子列表"""
    db = get_db_manager()
    
    with db.get_session() as session:
        # 构建查询
        query = select(Post).order_by(Post.posted_at.desc())
        count_query = select(func.count(Post.id))
        
        # 过滤类型
        if filter_type == "original":
            query = query.where(Post.is_reblog == False)
            count_query = count_query.where(Post.is_reblog == False)
        elif filter_type == "reblog":
            query = query.where(Post.is_reblog == True)
            count_query = count_query.where(Post.is_reblog == True)
        
        # 搜索
        if search:
            search_pattern = f"%{search}%"
            query = query.where(Post.content.like(search_pattern))
            count_query = count_query.where(Post.content.like(search_pattern))
        
        # 总数
        total = session.execute(count_query).scalar() or 0
        
        # 分页
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        posts = session.execute(query).scalars().all()
        
        # 转换为响应模型
        posts_data = [
            PostResponse(
                id=p.id,
                post_id=p.post_id,
                username=p.username,
                content=p.content,
                url=p.url,
                reblogs_count=p.reblogs_count,
                favourites_count=p.favourites_count,
                replies_count=p.replies_count,
                is_reblog=p.is_reblog,
                posted_at=p.posted_at,
                created_at=p.created_at,
                translated_content=p.translated_content,
                translated_at=p.translated_at,
            )
            for p in posts
        ]
    
    return PostsListResponse(
        posts=posts_data,
        total=total,
        page=page,
        page_size=limit,
    )


@app.get("/api/posts/{post_id}")
async def get_post(post_id: str):
    """获取单个帖子详情"""
    db = get_db_manager()
    
    post = db.get_post_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return PostResponse(
        id=post.id,
        post_id=post.post_id,
        username=post.username,
        content=post.content,
        url=post.url,
        reblogs_count=post.reblogs_count,
        favourites_count=post.favourites_count,
        replies_count=post.replies_count,
        is_reblog=post.is_reblog,
        posted_at=post.posted_at,
        created_at=post.created_at,
        translated_content=post.translated_content,
        translated_at=post.translated_at,
    )


@app.get("/api/scrape-logs")
async def get_scrape_logs(limit: int = Query(20, ge=1, le=100)):
    """获取采集日志"""
    db = get_db_manager()
    
    with db.get_session() as session:
        logs = session.execute(
            select(ScrapeLog)
            .order_by(ScrapeLog.started_at.desc())
            .limit(limit)
        ).scalars().all()
        
        return [
            {
                "id": log.id,
                "username": log.username,
                "status": log.status,
                "total_fetched": log.total_fetched,
                "new_posts": log.new_posts,
                "updated_posts": log.updated_posts,
                "error_message": log.error_message,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                "duration_seconds": log.duration_seconds,
            }
            for log in logs
        ]


# ==================== 设置 API ====================

class NotificationConfigRequest(BaseModel):
    """通知配置请求"""
    feishu_enabled: bool = True
    feishu_webhook: Optional[str] = None
    feishu_secret: Optional[str] = None
    realtime_enabled: bool = True
    daily_report_enabled: bool = True
    daily_report_time: str = "09:00"
    weekly_report_enabled: bool = True
    weekly_report_time: str = "09:00"
    weekly_report_day: int = Field(default=1, ge=1, le=7, description="1-7 对应周一到周日")
    # 报告显示配置
    full_display_count: int = Field(default=10, ge=3, le=20, description="完整显示帖子数量")
    summary_display_count: int = Field(default=10, ge=0, le=20, description="摘要显示帖子数量")
    ai_analysis_limit: int = Field(default=20, ge=5, le=50, description="AI 分析帖子数量上限")
    # 互动量权重
    weight_replies: int = Field(default=3, ge=1, le=10, description="评论权重")
    weight_reblogs: int = Field(default=2, ge=1, le=10, description="转发权重")
    weight_favourites: int = Field(default=1, ge=1, le=10, description="点赞权重")


class ScrapeConfigRequest(BaseModel):
    """采集配置请求"""
    scrape_enabled: bool = True
    normal_scrape_interval: int = Field(default=3600, ge=300, le=86400, description="正常时段采集间隔（秒）")
    sleep_scrape_interval: int = Field(default=21600, ge=3600, le=86400, description="睡眠时段采集间隔（秒）")
    min_scrape_gap: int = Field(default=300, ge=60, le=3600, description="最小采集间隔（秒）")
    trump_sleep_start_hour: int = Field(default=0, ge=0, le=23, description="Trump 睡眠开始时间（美东）")
    trump_sleep_end_hour: int = Field(default=7, ge=0, le=23, description="Trump 睡眠结束时间（美东）")


class TranslateConfigRequest(BaseModel):
    """翻译配置请求"""
    translate_enabled: bool = True


class SettingsResponse(BaseModel):
    """完整设置响应"""
    notification: NotificationConfig
    scrape: ScrapeConfig
    translate: TranslateConfig


class TestNotificationRequest(BaseModel):
    """测试通知请求"""
    webhook_url: str
    secret: Optional[str] = None


class PushReportRequest(BaseModel):
    """手动推送报告请求"""
    report_type: str = Field(..., pattern="^(daily|weekly|test)$", description="报告类型: daily/weekly/test")


@app.get("/api/settings", response_model=SettingsResponse)
async def get_settings():
    """获取所有设置"""
    config_mgr = get_runtime_config()
    config_mgr.load_from_db()
    
    return SettingsResponse(
        notification=config_mgr.notification,
        scrape=config_mgr.scrape,
        translate=config_mgr.translate,
    )


@app.get("/api/settings/notification", response_model=NotificationConfig)
async def get_notification_settings():
    """获取通知设置"""
    config_mgr = get_runtime_config()
    config_mgr.load_from_db()
    return config_mgr.notification


@app.put("/api/settings/notification", response_model=NotificationConfig)
async def update_notification_settings(config: NotificationConfigRequest):
    """更新通知设置"""
    config_mgr = get_runtime_config()
    
    new_config = NotificationConfig(**config.model_dump())
    success = config_mgr.update_notification(new_config)
    
    if not success:
        raise HTTPException(status_code=500, detail="保存配置失败")
    
    logger.info(f"通知配置已更新: realtime={config.realtime_enabled}, daily={config.daily_report_enabled}, weekly={config.weekly_report_enabled}")
    return new_config


@app.get("/api/settings/scrape", response_model=ScrapeConfig)
async def get_scrape_settings():
    """获取采集设置"""
    config_mgr = get_runtime_config()
    config_mgr.load_from_db()
    return config_mgr.scrape


@app.put("/api/settings/scrape", response_model=ScrapeConfig)
async def update_scrape_settings(config: ScrapeConfigRequest):
    """更新采集设置"""
    config_mgr = get_runtime_config()
    
    new_config = ScrapeConfig(**config.model_dump())
    success = config_mgr.update_scrape(new_config)
    
    if not success:
        raise HTTPException(status_code=500, detail="保存配置失败")
    
    logger.info(f"采集配置已更新: normal_interval={config.normal_scrape_interval}s, sleep_interval={config.sleep_scrape_interval}s")
    return new_config


@app.get("/api/settings/translate", response_model=TranslateConfig)
async def get_translate_settings():
    """获取翻译设置"""
    config_mgr = get_runtime_config()
    config_mgr.load_from_db()
    return config_mgr.translate


@app.put("/api/settings/translate", response_model=TranslateConfig)
async def update_translate_settings(config: TranslateConfigRequest):
    """更新翻译设置"""
    config_mgr = get_runtime_config()
    
    new_config = TranslateConfig(**config.model_dump())
    success = config_mgr.update_translate(new_config)
    
    if not success:
        raise HTTPException(status_code=500, detail="保存配置失败")
    
    logger.info(f"翻译配置已更新: enabled={config.translate_enabled}")
    return new_config


@app.post("/api/settings/test-notification")
async def test_notification(request: TestNotificationRequest):
    """测试飞书通知"""
    try:
        from src.notification import FeishuClient
        
        client = FeishuClient(
            webhook_url=request.webhook_url,
            secret=request.secret,
        )
        
        success = await client.send_text(
            "🔔 Trump Monitor 测试通知\n\n"
            "这是一条测试消息，用于验证推送配置是否正确。\n"
            f"如果您收到此消息，说明配置成功！\n\n"
            f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        if success:
            return {"success": True, "message": "测试消息发送成功"}
        else:
            raise HTTPException(status_code=500, detail="发送失败，请检查 Webhook URL")
            
    except Exception as e:
        logger.error(f"测试通知失败: {e}")
        raise HTTPException(status_code=500, detail=f"发送测试消息失败: {str(e)}")


@app.post("/api/settings/push-report")
async def push_report(request: PushReportRequest):
    """手动推送报告
    
    - daily: 今日帖子摘要
    - weekly: 本周帖子总结
    - test: 测试推送
    """
    config_mgr = get_runtime_config()
    config_mgr.load_from_db()
    
    notification_config = config_mgr.notification
    if not notification_config.feishu_enabled or not notification_config.feishu_webhook:
        raise HTTPException(status_code=400, detail="未配置飞书通知，请先在设置中配置 Webhook URL")
    
    try:
        from src.notification import FeishuClient
        from src.storage import get_db_manager
        from src.config import settings
        from src.analyzer import get_trump_analyzer
        from sqlalchemy import func, select, and_
        
        client = FeishuClient(
            webhook_url=notification_config.feishu_webhook,
            secret=notification_config.feishu_secret,
        )
        db = get_db_manager()
        
        # 获取 AI 分析器（如果启用）
        trump_analyzer = None
        if settings.knot_enabled:
            try:
                trump_analyzer = get_trump_analyzer()
            except Exception as e:
                logger.warning(f"AI 分析器初始化失败: {e}")
        
        if request.report_type == "test":
            success = await client.send_text(
                "🔔 Trump Monitor 手动推送测试\n\n"
                f"推送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            return {"success": success, "message": "测试推送完成" if success else "推送失败"}
        
        elif request.report_type == "daily":
            # 获取过去24小时帖子（使用服务器时区）
            now = datetime.now(SERVER_TZ)
            time_24h_ago = now - timedelta(hours=24)
            time_24h_ago_naive = time_24h_ago.replace(tzinfo=None)
            logger.info(f"日报时间范围: 过去24小时 ({time_24h_ago_naive} 至今, {settings.timezone})")
            
            def _has_text_content(post) -> bool:
                """判断帖子是否有文本内容"""
                content = post.content if hasattr(post, 'content') else post.get('content', '')
                return bool(content and content.strip())
            
            with db.get_session() as session:
                posts = session.execute(
                    select(Post)
                    .where(Post.posted_at >= time_24h_ago_naive)
                    .order_by(Post.posted_at.desc())
                ).scalars().all()
                
                if not posts:
                    return {"success": True, "message": "过去24小时暂无新帖子"}
                
                # 统计有内容和无内容的帖子
                text_posts_count = sum(1 for p in posts if _has_text_content(p))
                media_posts_count = len(posts) - text_posts_count
                logger.info(f"帖子统计: 文本 {text_posts_count} 条，媒体 {media_posts_count} 条")
                
                # 转换为字典格式，并补充翻译
                posts_data = []
                for post in posts:
                    # 如果没有翻译，尝试翻译
                    translated = post.translated_content or translate_post_content(post, db)
                    posts_data.append({
                        "content": post.content or "",
                        "translated_content": translated,
                        "posted_at": post.posted_at,
                        "is_reblog": post.is_reblog,
                        "url": post.url or "",
                    })
                
                # AI 分析（如果启用）- 只分析有文本内容的帖子
                ai_analysis = None
                if trump_analyzer and text_posts_count > 0:
                    try:
                        # 过滤出有文本内容的帖子
                        posts_for_analysis = [
                            {
                                "content": p.get("content", ""),
                                "translated_content": p.get("translated_content", ""),
                                "posted_at": p["posted_at"].isoformat() if hasattr(p.get("posted_at"), 'isoformat') else str(p.get("posted_at", "")),
                            }
                            for p in posts_data
                            if p.get("content", "").strip()  # 只分析有内容的
                        ]
                        if posts_for_analysis:
                            logger.info(f"开始 AI 分析日报 ({len(posts_for_analysis)} 条有文本帖子)...")
                            result = await trump_analyzer.analyze_batch(
                                posts=posts_for_analysis,
                                analysis_focus="daily_summary"
                            )
                            if result["status"] == "success" and result["analysis"]:
                                ai_analysis = result["analysis"]
                                logger.info("日报 AI 分析完成")
                    except Exception as e:
                        logger.warning(f"日报 AI 分析失败: {e}")
                elif text_posts_count == 0:
                    logger.info("无文本帖子，跳过 AI 分析")
                
                success = await client.send_daily_report(
                    posts_data, 
                    time_24h_ago_naive, 
                    ai_analysis=ai_analysis,
                    text_posts_count=text_posts_count,
                    media_posts_count=media_posts_count,
                )
                return {"success": success, "message": f"日报推送完成，共 {len(posts)} 条帖子（文本 {text_posts_count}，媒体 {media_posts_count}）"}
        
        elif request.report_type == "weekly":
            # 获取过去7天帖子（使用服务器时区）
            now = datetime.now(SERVER_TZ)
            time_7d_ago = now - timedelta(days=7)
            time_7d_ago_naive = time_7d_ago.replace(tzinfo=None)
            logger.info(f"周报时间范围: 过去7天 ({time_7d_ago_naive} 至今, {settings.timezone})")
            
            # 从配置获取显示和分析参数
            full_display_count = notification_config.full_display_count
            summary_display_count = notification_config.summary_display_count
            ai_analysis_limit = notification_config.ai_analysis_limit
            weight_replies = notification_config.weight_replies
            weight_reblogs = notification_config.weight_reblogs
            weight_favourites = notification_config.weight_favourites
            
            def _has_text_content(post) -> bool:
                """判断帖子是否有文本内容"""
                content = post.content if hasattr(post, 'content') else post.get('content', '')
                return bool(content and content.strip())
            
            with db.get_session() as session:
                # 获取所有帖子用于统计
                all_posts = session.execute(
                    select(Post).where(Post.posted_at >= time_7d_ago_naive)
                ).scalars().all()
                
                total_count = len(all_posts)
                if total_count == 0:
                    return {"success": True, "message": "过去7天暂无帖子"}
                
                # 统计分类
                text_posts = [p for p in all_posts if _has_text_content(p)]
                media_posts = [p for p in all_posts if not _has_text_content(p)]
                text_posts_count = len(text_posts)
                media_posts_count = len(media_posts)
                
                original_count = sum(1 for p in all_posts if not p.is_reblog)
                reblog_count = total_count - original_count
                
                logger.info(f"周报统计: 总 {total_count} 条，文本 {text_posts_count}，媒体 {media_posts_count}，原创 {original_count}，转发 {reblog_count}")
                
                # 按加权互动量排序（只统计有文本内容的帖子）
                def calc_weighted_score(post) -> int:
                    return (
                        post.replies_count * weight_replies +
                        post.reblogs_count * weight_reblogs +
                        post.favourites_count * weight_favourites
                    )
                
                sorted_text_posts = sorted(text_posts, key=calc_weighted_score, reverse=True)
                
                # 取热门帖子用于显示和分析
                hot_posts_for_display = sorted_text_posts[:full_display_count + summary_display_count]
                hot_posts_for_ai = sorted_text_posts[:ai_analysis_limit]
                
                # 转换为字典格式
                hot_posts_data = []
                for post in hot_posts_for_display:
                    translated = post.translated_content or translate_post_content(post, db)
                    hot_posts_data.append({
                        "content": post.content or "",
                        "translated_content": translated,
                        "reblogs_count": post.reblogs_count,
                        "favourites_count": post.favourites_count,
                        "replies_count": post.replies_count,
                        "weighted_score": calc_weighted_score(post),
                        "url": post.url or "",
                        "posted_at": post.posted_at.isoformat() if post.posted_at else None,
                    })
                
                # AI 分析（如果启用）- 只分析有文本内容的热门帖子
                ai_analysis = None
                if trump_analyzer and hot_posts_for_ai:
                    try:
                        logger.info(f"开始 AI 分析周报 ({len(hot_posts_for_ai)} 条有文本热门帖子)...")
                        posts_for_analysis = [
                            {
                                "content": p.content or "",
                                "translated_content": p.translated_content or "",
                                "posted_at": p.posted_at.isoformat() if p.posted_at else "",
                            }
                            for p in hot_posts_for_ai
                            if p.content and p.content.strip()
                        ]
                        if posts_for_analysis:
                            result = await trump_analyzer.analyze_batch(
                                posts=posts_for_analysis,
                                analysis_focus="weekly_summary"
                            )
                            if result["status"] == "success" and result["analysis"]:
                                ai_analysis = result["analysis"]
                                logger.info("周报 AI 分析完成")
                    except Exception as e:
                        logger.warning(f"周报 AI 分析失败: {e}")
                
                # 计算剩余帖子数
                remaining_count = max(0, text_posts_count - full_display_count - summary_display_count)
                
                success = await client.send_weekly_report(
                    week_start=time_7d_ago_naive,
                    week_end=now.replace(tzinfo=None),
                    total_posts=total_count,
                    original_posts=original_count,
                    reblog_posts=reblog_count,
                    hot_posts=hot_posts_data,
                    ai_analysis=ai_analysis,
                    full_display_count=full_display_count,
                    summary_display_count=summary_display_count,
                    text_posts_count=text_posts_count,
                    media_posts_count=media_posts_count,
                    remaining_count=remaining_count,
                )
                return {"success": success, "message": f"周报推送完成，过去7天共 {total_count} 条帖子（文本 {text_posts_count}，媒体 {media_posts_count}）"}
        
        else:
            raise HTTPException(status_code=400, detail="不支持的报告类型")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"推送报告失败: {e}")
        raise HTTPException(status_code=500, detail=f"推送报告失败: {str(e)}")


# ==================== AI 分析 API ====================


class AnalyzePostRequest(BaseModel):
    """AI 分析请求"""
    content: str = Field(..., description="帖子原文（英文）")
    translated_content: Optional[str] = Field(None, description="翻译内容（中文）")
    posted_at: Optional[str] = Field(None, description="发布时间（ISO 格式）")
    context: Optional[str] = Field(None, description="补充背景信息")


@app.post("/api/analyze")
async def analyze_post(request: AnalyzePostRequest):
    """AI 分析单条帖子
    
    使用 Trump 言论分析 Agent 分析帖子对资本市场、投资趋势、世界局势的影响。
    
    需要配置：
    - KNOT_ENABLED=true
    - KNOT_AGENT_ID=<智能体ID>
    - KNOT_API_TOKEN=<用户Token> 或 KNOT_AGENT_TOKEN + KNOT_USERNAME
    """
    from src.config import settings
    from src.analyzer import get_trump_analyzer
    
    if not settings.knot_enabled:
        raise HTTPException(
            status_code=400, 
            detail="AI 分析未启用，请在 .env 中设置 KNOT_ENABLED=true 并配置相关参数"
        )
    
    try:
        analyzer = get_trump_analyzer()
        
        # 解析发布时间
        posted_at = None
        if request.posted_at:
            try:
                posted_at = datetime.fromisoformat(request.posted_at.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        result = await analyzer.analyze_post(
            content=request.content,
            translated_content=request.translated_content,
            posted_at=posted_at,
            context=request.context,
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "success": True,
            "status": result["status"],
            "analysis": result["analysis"],
            "analyzed_at": result["analyzed_at"],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI 分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@app.post("/api/analyze/{post_id}")
async def analyze_post_by_id(post_id: int):
    """根据帖子 ID 进行 AI 分析"""
    from src.config import settings
    from src.analyzer import get_trump_analyzer
    from src.storage import get_db_manager
    
    if not settings.knot_enabled:
        raise HTTPException(
            status_code=400, 
            detail="AI 分析未启用，请在 .env 中设置 KNOT_ENABLED=true 并配置相关参数"
        )
    
    db = get_db_manager()
    
    # 获取帖子
    with db.get_session() as session:
        post = session.execute(
            select(Post).where(Post.id == post_id)
        ).scalar_one_or_none()
        
        if not post:
            raise HTTPException(status_code=404, detail="帖子不存在")
        
        content = post.content
        translated_content = post.translated_content
        posted_at = post.posted_at
    
    try:
        analyzer = get_trump_analyzer()
        
        result = await analyzer.analyze_post(
            content=content or "",
            translated_content=translated_content,
            posted_at=posted_at,
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "success": True,
            "post_id": post_id,
            "status": result["status"],
            "analysis": result["analysis"],
            "analyzed_at": result["analyzed_at"],
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI 分析帖子 {post_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


@app.get("/api/analyze/status")
async def get_analyze_status():
    """获取 AI 分析服务状态"""
    from src.config import settings
    
    status = {
        "enabled": settings.knot_enabled,
        "agent_id": settings.knot_agent_id if settings.knot_enabled else None,
        "model": settings.knot_model if settings.knot_enabled else None,
        "auth_mode": None,
    }
    
    if settings.knot_enabled:
        if settings.knot_api_token:
            status["auth_mode"] = "api_token"
        elif settings.knot_agent_token:
            status["auth_mode"] = "agent_token"
    
    return status


# 静态文件服务（前端）
# 注意：这个需要放在最后，否则会拦截 API 路由
@app.get("/")
async def serve_frontend():
    """服务前端页面"""
    return FileResponse("frontend/index.html")


# 挂载 JS 和 CSS 静态文件目录
app.mount("/js", StaticFiles(directory="frontend/js"), name="js")
app.mount("/css", StaticFiles(directory="frontend/css"), name="css")


def run_api_server():
    """运行 API 服务器"""
    import uvicorn
    
    logger.info("启动 API 服务器...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=6001,
        log_level="info",
    )


if __name__ == "__main__":
    run_api_server()
