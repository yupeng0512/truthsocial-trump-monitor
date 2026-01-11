"""ScrapeCreators API 客户端

API 文档: https://app.scrapecreators.com/playground
支持的端点:
- 用户资料: /truthsocial/user/profile
- 用户帖子: /truthsocial/user/posts
- 单帖详情: /truthsocial/post/details
"""

from datetime import datetime
from typing import Any, Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings


class ScrapeCreatorsClient:
    """ScrapeCreators Truth Social API 客户端"""

    BASE_URL = "https://api.scrapecreators.com"

    def __init__(self, api_key: Optional[str] = None):
        """初始化客户端

        Args:
            api_key: ScrapeCreators API Key，默认从配置读取
        """
        self.api_key = api_key or settings.scrapecreators_api_key
        if not self.api_key:
            raise ValueError("ScrapeCreators API Key is required")

        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _request(
        self,
        endpoint: str,
        params: Optional[dict] = None,
    ) -> dict[str, Any]:
        """发送 API 请求

        Args:
            endpoint: API 端点
            params: 查询参数

        Returns:
            API 响应数据
        """
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                url,
                headers=self.headers,
                params=params,
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                logger.error("ScrapeCreators API 认证失败，请检查 API Key")
                raise ValueError("Invalid API Key")
            elif response.status_code == 429:
                logger.warning("ScrapeCreators API 请求频率限制")
                raise Exception("Rate limit exceeded")
            else:
                logger.error(
                    f"ScrapeCreators API 请求失败: status={response.status_code}, "
                    f"body={response.text[:500]}"
                )
                raise Exception(f"API request failed: {response.status_code}")

    async def get_user_profile(self, username: str) -> dict[str, Any]:
        """获取用户资料

        Args:
            username: Truth Social 用户名

        Returns:
            用户资料数据
        """
        logger.info(f"获取用户资料: {username}")
        return await self._request(
            "/truthsocial/user/profile",
            params={"username": username},
        )

    async def get_user_posts(
        self,
        username: str,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """获取用户帖子列表

        ScrapeCreators API 说明：
        - 每次请求消耗 1 个 credit
        - 默认返回最新的帖子（数量取决于 API）
        - 支持 cursor 分页获取更多历史帖子

        Args:
            username: Truth Social 用户名
            cursor: 分页游标（用于获取更多帖子）
            limit: 每页数量（默认 20，API 可能有自己的限制）

        Returns:
            帖子列表数据，结构可能为：
            - 直接返回帖子数组
            - 或 {"posts": [...], "next_cursor": "...", "has_more": true/false}
        """
        logger.info(f"获取用户帖子: {username}, cursor={cursor}")

        params = {"handle": username}
        if cursor:
            params["cursor"] = cursor
        if limit:
            params["limit"] = str(limit)

        result = await self._request("/truthsocial/user/posts", params=params)
        
        # 记录 API 响应结构，便于调试
        logger.debug(f"API 响应类型: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        
        return result

    async def get_post_details(self, post_id: str) -> dict[str, Any]:
        """获取单帖详情

        Args:
            post_id: 帖子 ID

        Returns:
            帖子详情数据
        """
        logger.info(f"获取帖子详情: {post_id}")
        return await self._request(
            "/truthsocial/post/details",
            params={"post_id": post_id},
        )

    async def fetch_latest_posts(
        self,
        username: str,
        max_posts: int = 20,
    ) -> list[dict[str, Any]]:
        """获取用户最新帖子

        注意：
        - 每次 API 调用消耗 1 个 credit
        - 为节省 credit，默认只获取一次（不分页）
        - 1小时采集一次，通常一次请求足够获取新帖

        Args:
            username: Truth Social 用户名
            max_posts: 最大获取数量（默认 20，通常一次请求足够）

        Returns:
            帖子列表
        """
        try:
            result = await self.get_user_posts(
                username=username,
                limit=max_posts,
            )

            # 处理不同的 API 响应格式
            posts = []
            
            if isinstance(result, list):
                # 直接返回帖子数组
                posts = result
            elif isinstance(result, dict):
                # 返回包装对象
                # 尝试多种可能的字段名
                for key in ["posts", "data", "statuses", "items", "results"]:
                    if key in result and isinstance(result[key], list):
                        posts = result[key]
                        break
                
                # 如果没找到数组字段，可能整个 result 就是单个帖子
                if not posts and "id" in result:
                    posts = [result]
            
            logger.info(f"获取到 {len(posts)} 条帖子")
            return posts[:max_posts]

        except Exception as e:
            logger.error(f"获取帖子失败: {e}")
            return []


def parse_post_data(raw_post: dict) -> dict[str, Any]:
    """解析帖子原始数据为统一格式

    ScrapeCreators 返回的 Truth Social 帖子数据结构
    可能与 Mastodon API 类似（Truth Social 基于 Mastodon）

    Args:
        raw_post: API 返回的原始帖子数据

    Returns:
        标准化的帖子数据
    """
    # 提取帖子 ID（尝试多种字段名）
    post_id = (
        raw_post.get("id") or 
        raw_post.get("post_id") or 
        raw_post.get("status_id") or
        ""
    )
    
    # 提取内容（Truth Social 可能使用 content 或 text）
    content = (
        raw_post.get("content") or 
        raw_post.get("text") or 
        raw_post.get("body") or
        ""
    )
    
    # 清理 HTML 标签（如果内容包含 HTML）
    if content and "<" in content:
        import re
        content = re.sub(r"<[^>]+>", "", content)
    
    # 提取 URL
    url = raw_post.get("url") or raw_post.get("uri") or ""
    if not url and post_id:
        # 构造 URL
        username = raw_post.get("account", {}).get("username", "realDonaldTrump")
        url = f"https://truthsocial.com/@{username}/posts/{post_id}"
    
    return {
        "post_id": str(post_id),
        "content": content,
        "created_at": raw_post.get("created_at", ""),
        "url": url,
        "reblogs_count": int(raw_post.get("reblogs_count", 0) or 0),
        "favourites_count": int(raw_post.get("favourites_count", 0) or raw_post.get("likes_count", 0) or 0),
        "replies_count": int(raw_post.get("replies_count", 0) or 0),
        "media_attachments": raw_post.get("media_attachments", []),
        "is_reblog": raw_post.get("reblog") is not None,
        "reblog_content": (
            raw_post.get("reblog", {}).get("content", "")
            if raw_post.get("reblog")
            else None
        ),
        "raw_data": raw_post,  # 保留原始数据用于调试
    }
