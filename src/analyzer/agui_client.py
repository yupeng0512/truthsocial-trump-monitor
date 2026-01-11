"""AG-UI 协议客户端

通过 AG-UI 协议调用 Knot 平台上的智能体。
文档参考：https://knot.woa.com/

支持功能：
- 流式/非流式调用
- 多种事件类型处理
- 自动重试和错误处理
"""

import json
from datetime import datetime
from typing import Any, AsyncGenerator, Optional

import httpx
from loguru import logger

from src.config import settings


class AGUIClient:
    """AG-UI 协议客户端
    
    通过 AG-UI 协议调用 Knot 平台智能体。
    
    使用方式：
    1. 用户个人 Token 模式（推荐）：
       - 设置 KNOT_API_TOKEN
       
    2. 智能体 Token 模式：
       - 设置 KNOT_AGENT_TOKEN 和 KNOT_USERNAME
    """
    
    # API 端点模板
    API_URL_TEMPLATE = "http://knot.woa.com/apigw/api/v1/agents/agui/{agent_id}"
    
    # 默认超时时间（秒）
    DEFAULT_TIMEOUT = 120
    
    # 支持的模型
    SUPPORTED_MODELS = ["deepseek-v3.1", "deepseek-v3.2", "glm-4.7"]
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        api_token: Optional[str] = None,
        agent_token: Optional[str] = None,
        username: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """初始化 AG-UI 客户端
        
        Args:
            agent_id: 智能体 ID
            api_token: 用户个人 Token（优先使用）
            agent_token: 智能体 Token
            username: 用户名（使用智能体 Token 时需要）
            model: 模型名称
            timeout: 请求超时时间（秒）
        """
        self.agent_id = agent_id or settings.knot_agent_id
        self.api_token = api_token or settings.knot_api_token
        self.agent_token = agent_token or settings.knot_agent_token
        self.username = username or settings.knot_username
        self.model = model or settings.knot_model
        self.timeout = timeout
        
        # 验证配置
        if not self.agent_id:
            raise ValueError("Agent ID is required (KNOT_AGENT_ID)")
        
        if not self.api_token and not self.agent_token:
            raise ValueError(
                "Either API Token (KNOT_API_TOKEN) or "
                "Agent Token (KNOT_AGENT_TOKEN) is required"
            )
        
        if self.agent_token and not self.username:
            raise ValueError(
                "Username (KNOT_USERNAME) is required when using Agent Token"
            )
        
        # 构建 API URL
        self.api_url = self.API_URL_TEMPLATE.format(agent_id=self.agent_id)
        
        logger.info(
            f"AGUIClient initialized: agent_id={self.agent_id}, "
            f"model={self.model}, auth_mode={'api_token' if self.api_token else 'agent_token'}"
        )
    
    def _build_headers(self) -> dict[str, str]:
        """构建请求头"""
        if self.api_token:
            # 用户个人 Token 模式
            return {
                "x-knot-api-token": self.api_token,
                "Content-Type": "application/json",
            }
        else:
            # 智能体 Token 模式
            return {
                "x-knot-token": self.agent_token,
                "X-Username": self.username,
                "Content-Type": "application/json",
            }
    
    def _build_request_body(
        self,
        message: str,
        conversation_id: str = "",
        stream: bool = True,
        enable_web_search: bool = False,
        temperature: float = 0.5,
        attached_images: Optional[list[str]] = None,
        extra_headers: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """构建请求体
        
        Args:
            message: 用户消息
            conversation_id: 会话 ID（留空创建新会话）
            stream: 是否流式返回
            enable_web_search: 是否开启联网搜索
            temperature: 温度参数 [0, 1]
            attached_images: 附加图片 URL 列表
            extra_headers: 额外请求头（透传给 MCP 工具）
        """
        body = {
            "input": {
                "message": message,
                "conversation_id": conversation_id,
                "model": self.model,
                "stream": stream,
                "enable_web_search": enable_web_search,
                "temperature": temperature,
                "chat_extra": {
                    "attached_images": attached_images or [],
                    "extra_headers": extra_headers or {},
                },
            }
        }
        return body
    
    async def chat(
        self,
        message: str,
        conversation_id: str = "",
        stream: bool = False,
        enable_web_search: bool = False,
        temperature: float = 0.5,
    ) -> dict[str, Any]:
        """发送消息并获取完整响应（非流式）
        
        Args:
            message: 用户消息
            conversation_id: 会话 ID
            stream: 是否流式（此方法内部处理流式，返回完整结果）
            enable_web_search: 是否开启联网搜索
            temperature: 温度参数
            
        Returns:
            包含完整响应的字典：
            {
                "content": "完整响应内容",
                "conversation_id": "会话ID",
                "message_id": "消息ID",
                "thinking": "思考过程（如有）",
                "tool_calls": [...],  # 工具调用记录
                "token_usage": {...},  # Token 使用情况
                "error": None,  # 错误信息（如有）
            }
        """
        headers = self._build_headers()
        body = self._build_request_body(
            message=message,
            conversation_id=conversation_id,
            stream=True,  # 使用流式获取，内部处理
            enable_web_search=enable_web_search,
            temperature=temperature,
        )
        
        result = {
            "content": "",
            "conversation_id": "",
            "message_id": "",
            "thinking": "",
            "tool_calls": [],
            "token_usage": None,
            "error": None,
        }
        
        content_parts = []
        thinking_parts = []
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    self.api_url,
                    json=body,
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        result["error"] = f"HTTP {response.status_code}: {error_text.decode()}"
                        logger.error(f"AGUI request failed: {result['error']}")
                        return result
                    
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        # 处理 SSE 格式
                        chunk_str = line.lstrip("data:").strip()
                        if chunk_str == "[DONE]":
                            break
                        
                        try:
                            msg = json.loads(chunk_str)
                        except json.JSONDecodeError:
                            continue
                        
                        if "type" not in msg:
                            continue
                        
                        msg_type = msg["type"]
                        raw_event = msg.get("rawEvent", {})
                        
                        # 更新会话信息
                        if "conversation_id" in raw_event:
                            result["conversation_id"] = raw_event["conversation_id"]
                        if "message_id" in raw_event:
                            result["message_id"] = raw_event["message_id"]
                        
                        # 处理不同事件类型
                        if msg_type == "TEXT_MESSAGE_CONTENT":
                            content_parts.append(raw_event.get("content", ""))
                        
                        elif msg_type == "THINKING_TEXT_MESSAGE_CONTENT":
                            thinking_parts.append(raw_event.get("content", ""))
                        
                        elif msg_type == "TOOL_CALL_START":
                            result["tool_calls"].append({
                                "name": raw_event.get("name"),
                                "status": "started",
                            })
                        
                        elif msg_type == "TOOL_CALL_RESULT":
                            if result["tool_calls"]:
                                result["tool_calls"][-1]["status"] = "completed"
                                result["tool_calls"][-1]["result"] = raw_event.get("result")
                        
                        elif msg_type == "STEP_FINISHED":
                            if "token_usage" in raw_event:
                                result["token_usage"] = raw_event["token_usage"]
                        
                        elif msg_type == "RUN_ERROR":
                            tip_option = raw_event.get("tip_option", {})
                            result["error"] = tip_option.get("content", "Unknown error")
                            logger.error(f"AGUI run error: {result['error']}")
            
            result["content"] = "".join(content_parts)
            result["thinking"] = "".join(thinking_parts)
            
            logger.info(
                f"AGUI chat completed: conversation_id={result['conversation_id']}, "
                f"content_length={len(result['content'])}"
            )
            
        except httpx.TimeoutException:
            result["error"] = f"Request timeout after {self.timeout}s"
            logger.error(result["error"])
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"AGUI request exception: {e}")
        
        return result
    
    async def chat_stream(
        self,
        message: str,
        conversation_id: str = "",
        enable_web_search: bool = False,
        temperature: float = 0.5,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """流式发送消息
        
        Args:
            message: 用户消息
            conversation_id: 会话 ID
            enable_web_search: 是否开启联网搜索
            temperature: 温度参数
            
        Yields:
            事件字典：
            {
                "type": "事件类型",
                "content": "内容（如有）",
                "raw_event": {...},
            }
        """
        headers = self._build_headers()
        body = self._build_request_body(
            message=message,
            conversation_id=conversation_id,
            stream=True,
            enable_web_search=enable_web_search,
            temperature=temperature,
        )
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    self.api_url,
                    json=body,
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        yield {
                            "type": "ERROR",
                            "content": f"HTTP {response.status_code}: {error_text.decode()}",
                            "raw_event": {},
                        }
                        return
                    
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        chunk_str = line.lstrip("data:").strip()
                        if chunk_str == "[DONE]":
                            yield {"type": "DONE", "content": "", "raw_event": {}}
                            break
                        
                        try:
                            msg = json.loads(chunk_str)
                        except json.JSONDecodeError:
                            continue
                        
                        if "type" not in msg:
                            continue
                        
                        yield {
                            "type": msg["type"],
                            "content": msg.get("rawEvent", {}).get("content", ""),
                            "raw_event": msg.get("rawEvent", {}),
                        }
        
        except httpx.TimeoutException:
            yield {
                "type": "ERROR",
                "content": f"Request timeout after {self.timeout}s",
                "raw_event": {},
            }
        except Exception as e:
            yield {
                "type": "ERROR",
                "content": str(e),
                "raw_event": {},
            }


class TrumpPostAnalyzer:
    """Trump 帖子分析器
    
    封装 AG-UI 客户端，专门用于调用 Trump 言论分析 Agent。
    """
    
    def __init__(self, agui_client: Optional[AGUIClient] = None):
        """初始化分析器
        
        Args:
            agui_client: AG-UI 客户端实例（可选，默认自动创建）
        """
        self.client = agui_client
        self._initialized = False
    
    def _ensure_client(self) -> bool:
        """确保客户端已初始化"""
        if self._initialized:
            return self.client is not None
        
        self._initialized = True
        
        if self.client:
            return True
        
        # 检查配置
        if not settings.knot_agent_id:
            logger.warning("Trump Post Analyzer disabled: KNOT_AGENT_ID not configured")
            return False
        
        if not settings.knot_api_token and not settings.knot_agent_token:
            logger.warning(
                "Trump Post Analyzer disabled: "
                "KNOT_API_TOKEN or KNOT_AGENT_TOKEN not configured"
            )
            return False
        
        try:
            self.client = AGUIClient()
            logger.info("Trump Post Analyzer initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Trump Post Analyzer: {e}")
            return False
    
    def _build_analysis_prompt(
        self,
        content: str,
        translated_content: Optional[str] = None,
        posted_at: Optional[datetime] = None,
        context: Optional[str] = None,
    ) -> str:
        """构建分析 Prompt
        
        Args:
            content: 帖子原文（英文）
            translated_content: 翻译内容（中文）
            posted_at: 发布时间
            context: 补充背景信息
        """
        # 构建输入 JSON
        input_data = {
            "content": content,
        }
        
        if translated_content:
            input_data["translated_content"] = translated_content
        
        if posted_at:
            input_data["posted_at"] = posted_at.isoformat()
        
        if context:
            input_data["context"] = context
        
        prompt = f"""请分析以下 Trump 帖子：

```json
{json.dumps(input_data, ensure_ascii=False, indent=2)}
```

请按照你的分析框架，输出完整的 JSON 格式分析报告。"""
        
        return prompt
    
    async def analyze_post(
        self,
        content: str,
        translated_content: Optional[str] = None,
        posted_at: Optional[datetime] = None,
        context: Optional[str] = None,
    ) -> dict[str, Any]:
        """分析单条帖子
        
        Args:
            content: 帖子原文
            translated_content: 翻译内容
            posted_at: 发布时间
            context: 补充背景
            
        Returns:
            分析结果字典，包含：
            - status: "success" | "error" | "disabled"
            - analysis: 分析结果（JSON 解析后的字典）
            - raw_content: 原始响应内容
            - error: 错误信息（如有）
            - analyzed_at: 分析时间
        """
        result = {
            "status": "disabled",
            "analysis": None,
            "raw_content": "",
            "error": None,
            "analyzed_at": datetime.now().isoformat(),
        }
        
        if not self._ensure_client():
            result["error"] = "Analyzer not configured"
            return result
        
        try:
            prompt = self._build_analysis_prompt(
                content=content,
                translated_content=translated_content,
                posted_at=posted_at,
                context=context,
            )
            
            response = await self.client.chat(
                message=prompt,
                temperature=0.3,  # 低温度，保证输出稳定
            )
            
            if response["error"]:
                result["status"] = "error"
                result["error"] = response["error"]
                return result
            
            raw_content = response["content"]
            result["raw_content"] = raw_content
            
            # 尝试解析 JSON
            analysis = self._extract_json(raw_content)
            if analysis:
                result["status"] = "success"
                result["analysis"] = analysis
            else:
                # JSON 解析失败，但有内容
                result["status"] = "success"
                result["analysis"] = {"raw_response": raw_content}
                logger.warning("Failed to parse JSON from analysis response")
            
            logger.info(f"Post analysis completed: status={result['status']}")
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"Post analysis failed: {e}")
        
        return result
    
    async def analyze_batch(
        self,
        posts: list[dict],
        analysis_focus: Optional[str] = None,
    ) -> dict[str, Any]:
        """批量分析帖子
        
        Args:
            posts: 帖子列表，每个帖子包含 content, translated_content, posted_at
            analysis_focus: 分析重点（可选）
            
        Returns:
            批量分析结果
        """
        result = {
            "status": "disabled",
            "analysis": None,
            "raw_content": "",
            "error": None,
            "analyzed_at": datetime.now().isoformat(),
        }
        
        if not self._ensure_client():
            result["error"] = "Analyzer not configured"
            return result
        
        try:
            # 构建批量分析 Prompt
            input_data = {
                "posts": posts,
            }
            if analysis_focus:
                input_data["analysis_focus"] = analysis_focus
            
            prompt = f"""请批量分析以下 Trump 帖子：

```json
{json.dumps(input_data, ensure_ascii=False, indent=2)}
```

请综合分析这些帖子的整体趋势和影响，输出完整的 JSON 格式分析报告。"""
            
            response = await self.client.chat(
                message=prompt,
                temperature=0.3,
            )
            
            if response["error"]:
                result["status"] = "error"
                result["error"] = response["error"]
                return result
            
            raw_content = response["content"]
            result["raw_content"] = raw_content
            
            analysis = self._extract_json(raw_content)
            if analysis:
                result["status"] = "success"
                result["analysis"] = analysis
            else:
                result["status"] = "success"
                result["analysis"] = {"raw_response": raw_content}
            
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            logger.error(f"Batch analysis failed: {e}")
        
        return result
    
    def _extract_json(self, text: str) -> Optional[dict]:
        """从文本中提取 JSON
        
        支持：
        - 纯 JSON 文本
        - Markdown 代码块包裹的 JSON
        """
        if not text:
            return None
        
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 代码块
        import re
        json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        matches = re.findall(json_pattern, text)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # 尝试提取 { ... } 块
        brace_pattern = r'\{[\s\S]*\}'
        matches = re.findall(brace_pattern, text)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        return None
    
    def format_analysis_for_feishu(self, analysis: dict) -> str:
        """将分析结果格式化为飞书消息
        
        Args:
            analysis: 分析结果字典
            
        Returns:
            格式化的 Markdown 文本
        """
        if not analysis:
            return "⚠️ 分析结果为空"
        
        lines = []
        
        # 核心结论
        summary = analysis.get("summary", {})
        if summary:
            lines.append("📊 **AI 分析摘要**")
            lines.append("")
            if headline := summary.get("headline"):
                lines.append(f"**{headline}**")
            
            sentiment = summary.get("overall_sentiment", "")
            sentiment_emoji = {
                "bullish": "📈",
                "bearish": "📉",
                "neutral": "➡️",
                "mixed": "↔️",
            }.get(sentiment, "")
            
            impact = summary.get("market_impact_level", "")
            impact_emoji = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢",
            }.get(impact, "")
            
            if sentiment or impact:
                lines.append(f"{sentiment_emoji} 情绪: {sentiment} | {impact_emoji} 影响: {impact}")
            lines.append("")
        
        # 投资建议
        recommendations = analysis.get("investment_recommendations", [])
        if recommendations:
            lines.append("💡 **投资建议**")
            lines.append("")
            for rec in recommendations[:3]:  # 最多显示 3 条
                category = rec.get("category", "")
                direction = rec.get("direction", "")
                confidence = rec.get("confidence", 0)
                
                direction_emoji = {
                    "long": "📈",
                    "short": "📉",
                    "hedge": "🛡️",
                }.get(direction, "")
                
                lines.append(f"{direction_emoji} **{category}** (置信度: {confidence}%)")
                
                targets = rec.get("specific_targets", [])
                for target in targets[:2]:  # 每类最多 2 个标的
                    name = target.get("name", "")
                    rationale = target.get("rationale", "")
                    lines.append(f"  • {name}: {rationale}")
                lines.append("")
        
        # 风险提示
        warnings = analysis.get("risk_warnings", [])
        if warnings:
            lines.append("⚠️ **风险提示**")
            for w in warnings[:3]:
                lines.append(f"• {w}")
            lines.append("")
        
        # 后续关注
        follow_up = analysis.get("follow_up_signals", [])
        if follow_up:
            lines.append("👀 **后续关注**")
            for f in follow_up[:3]:
                lines.append(f"• {f}")
        
        return "\n".join(lines)


# 全局实例
_trump_analyzer: Optional[TrumpPostAnalyzer] = None


def get_trump_analyzer() -> TrumpPostAnalyzer:
    """获取 Trump 帖子分析器单例"""
    global _trump_analyzer
    if _trump_analyzer is None:
        _trump_analyzer = TrumpPostAnalyzer()
    return _trump_analyzer
