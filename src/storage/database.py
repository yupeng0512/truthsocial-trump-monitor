"""数据库管理模块"""

from datetime import datetime
from functools import lru_cache
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

from .models import Base, Post, ScrapeLog


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, database_url: Optional[str] = None):
        """初始化数据库连接

        Args:
            database_url: 数据库连接 URL，默认从配置读取
        """
        self.database_url = database_url or settings.database_url
        self.engine = create_engine(
            self.database_url,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
            echo=False,
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )

    def init_db(self) -> None:
        """初始化数据库表"""
        logger.info("初始化数据库表...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("数据库表初始化完成")

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()

    # Post 模型允许的字段列表
    POST_ALLOWED_FIELDS = {
        "post_id", "username", "content", "url",
        "reblogs_count", "favourites_count", "replies_count",
        "is_reblog", "reblog_content", "media_attachments",
        "raw_data", "llm_analysis", "llm_analyzed_at",
        "posted_at", "notified", "notified_at",
    }

    def _filter_post_data(self, post_data: dict) -> dict:
        """过滤帖子数据，只保留模型允许的字段
        
        Args:
            post_data: 原始帖子数据
            
        Returns:
            过滤后的数据
        """
        return {k: v for k, v in post_data.items() if k in self.POST_ALLOWED_FIELDS}

    def save_post(self, post_data: dict) -> tuple[Post, bool]:
        """保存帖子数据

        Args:
            post_data: 帖子数据字典

        Returns:
            (Post 对象, 是否为新帖子)
        """
        # 过滤无效字段
        filtered_data = self._filter_post_data(post_data)
        
        with self.get_session() as session:
            # 检查是否已存在
            existing = session.execute(
                select(Post).where(Post.post_id == filtered_data.get("post_id"))
            ).scalar_one_or_none()

            if existing:
                # 更新现有记录
                for key, value in filtered_data.items():
                    if key != "post_id" and hasattr(existing, key):
                        setattr(existing, key, value)
                session.commit()
                session.refresh(existing)
                return existing, False
            else:
                # 创建新记录
                post = Post(**filtered_data)
                session.add(post)
                session.commit()
                session.refresh(post)
                return post, True

    def save_posts_batch(
        self,
        posts_data: list[dict],
    ) -> tuple[int, int]:
        """批量保存帖子

        Args:
            posts_data: 帖子数据列表

        Returns:
            (新增数量, 更新数量)
        """
        new_count = 0
        updated_count = 0

        with self.get_session() as session:
            for post_data in posts_data:
                # 过滤无效字段，防止传入模型不存在的字段
                filtered_data = self._filter_post_data(post_data)
                
                existing = session.execute(
                    select(Post).where(Post.post_id == filtered_data.get("post_id"))
                ).scalar_one_or_none()

                if existing:
                    # 更新
                    for key, value in filtered_data.items():
                        if key != "post_id" and hasattr(existing, key):
                            setattr(existing, key, value)
                    updated_count += 1
                else:
                    # 新增
                    post = Post(**filtered_data)
                    session.add(post)
                    new_count += 1

            session.commit()

        logger.info(f"批量保存完成: 新增 {new_count}, 更新 {updated_count}")
        return new_count, updated_count

    def get_unnotified_posts(self, limit: int = 50) -> list[Post]:
        """获取未通知的帖子

        Args:
            limit: 最大数量

        Returns:
            未通知的帖子列表
        """
        with self.get_session() as session:
            posts = session.execute(
                select(Post)
                .where(Post.notified == False)
                .order_by(Post.posted_at.desc())
                .limit(limit)
            ).scalars().all()
            # 确保在会话关闭前加载所有数据
            return [self._detach_post(p) for p in posts]

    def _detach_post(self, post: Post) -> Post:
        """分离 Post 对象，使其可在会话外使用"""
        # 创建一个新的 Post 对象副本
        detached = Post(
            id=post.id,
            post_id=post.post_id,
            username=post.username,
            content=post.content,
            url=post.url,
            reblogs_count=post.reblogs_count,
            favourites_count=post.favourites_count,
            replies_count=post.replies_count,
            is_reblog=post.is_reblog,
            reblog_content=post.reblog_content,
            media_attachments=post.media_attachments,
            raw_data=post.raw_data,
            llm_analysis=post.llm_analysis,
            llm_analyzed_at=post.llm_analyzed_at,
            translated_content=post.translated_content,
            translated_at=post.translated_at,
            posted_at=post.posted_at,
            created_at=post.created_at,
            updated_at=post.updated_at,
            notified=post.notified,
            notified_at=post.notified_at,
        )
        return detached

    def update_translation(self, post_id: int, translated_content: str) -> bool:
        """更新帖子的翻译内容

        Args:
            post_id: 帖子数据库 ID
            translated_content: 翻译后的内容

        Returns:
            是否更新成功
        """
        with self.get_session() as session:
            result = session.execute(
                Post.__table__.update()
                .where(Post.id == post_id)
                .values(
                    translated_content=translated_content,
                    translated_at=datetime.now()
                )
            )
            session.commit()
            return result.rowcount > 0

    def mark_posts_notified(self, post_ids: list[int]) -> None:
        """标记帖子为已通知

        Args:
            post_ids: 帖子 ID 列表
        """
        with self.get_session() as session:
            session.execute(
                Post.__table__.update()
                .where(Post.id.in_(post_ids))
                .values(notified=True, notified_at=datetime.now())
            )
            session.commit()

    def mark_all_posts_notified(self) -> int:
        """标记所有未通知的帖子为已通知
        
        用于首次运行时，避免发送大量历史帖子通知
        
        Returns:
            标记的帖子数量
        """
        with self.get_session() as session:
            result = session.execute(
                Post.__table__.update()
                .where(Post.notified == False)
                .values(notified=True, notified_at=datetime.now())
            )
            session.commit()
            count = result.rowcount
            logger.info(f"已标记 {count} 条帖子为已通知")
            return count

    def get_unanalyzed_posts(self, limit: int = 50) -> list[Post]:
        """获取未进行 LLM 分析的帖子

        Args:
            limit: 最大数量

        Returns:
            未分析的帖子列表
        """
        with self.get_session() as session:
            posts = session.execute(
                select(Post)
                .where(Post.llm_analyzed_at == None)
                .order_by(Post.posted_at.desc())
                .limit(limit)
            ).scalars().all()
            return [self._detach_post(p) for p in posts]

    def update_llm_analysis(
        self,
        post_id: int,
        analysis: dict,
    ) -> None:
        """更新帖子的 LLM 分析结果

        Args:
            post_id: 帖子 ID
            analysis: 分析结果
        """
        with self.get_session() as session:
            session.execute(
                Post.__table__.update()
                .where(Post.id == post_id)
                .values(
                    llm_analysis=analysis,
                    llm_analyzed_at=datetime.now(),
                )
            )
            session.commit()

    def log_scrape(
        self,
        username: str,
        status: str,
        total_fetched: int = 0,
        new_posts: int = 0,
        updated_posts: int = 0,
        error_message: Optional[str] = None,
        started_at: Optional[datetime] = None,
    ) -> ScrapeLog:
        """记录采集日志

        Args:
            username: 采集的用户名
            status: 状态
            total_fetched: 获取总数
            new_posts: 新增数
            updated_posts: 更新数
            error_message: 错误信息
            started_at: 开始时间

        Returns:
            ScrapeLog 对象
        """
        with self.get_session() as session:
            now = datetime.now()
            duration = None
            if started_at:
                duration = (now - started_at).total_seconds()

            log = ScrapeLog(
                username=username,
                status=status,
                total_fetched=total_fetched,
                new_posts=new_posts,
                updated_posts=updated_posts,
                error_message=error_message,
                started_at=started_at or now,
                finished_at=now,
                duration_seconds=duration,
            )
            session.add(log)
            session.commit()
            session.refresh(log)
            return log

    def get_post_by_id(self, post_id: str) -> Optional[Post]:
        """根据帖子 ID 获取帖子

        Args:
            post_id: Truth Social 帖子 ID

        Returns:
            Post 对象或 None
        """
        with self.get_session() as session:
            post = session.execute(
                select(Post).where(Post.post_id == post_id)
            ).scalar_one_or_none()
            if post:
                return self._detach_post(post)
            return None

    def get_latest_posts(
        self,
        username: str,
        limit: int = 20,
    ) -> list[Post]:
        """获取用户最新帖子

        Args:
            username: 用户名
            limit: 数量限制

        Returns:
            帖子列表
        """
        with self.get_session() as session:
            posts = session.execute(
                select(Post)
                .where(Post.username == username)
                .order_by(Post.posted_at.desc())
                .limit(limit)
            ).scalars().all()
            return [self._detach_post(p) for p in posts]

    def get_last_scrape_time(self) -> Optional[datetime]:
        """获取上次成功采集的时间

        Returns:
            上次采集时间，如果没有记录则返回 None
        """
        with self.get_session() as session:
            log = session.execute(
                select(ScrapeLog)
                .where(ScrapeLog.status == "success")
                .order_by(ScrapeLog.finished_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if log:
                return log.finished_at
            return None

    def get_post_count(self) -> int:
        """获取帖子总数

        Returns:
            帖子总数
        """
        with self.get_session() as session:
            count = session.execute(
                select(func.count(Post.id))
            ).scalar()
            return count or 0


@lru_cache
def get_db_manager() -> DatabaseManager:
    """获取数据库管理器单例"""
    return DatabaseManager()
