"""腾讯云机器翻译服务

参考文档：https://cloud.tencent.com/document/api/551/15619
"""

import hashlib
import hmac
import json
import time
import urllib.request
from typing import Optional

from loguru import logger

from src.config import settings


class TencentTranslator:
    """
    腾讯云机器翻译 TextTranslate 接口封装。

    环境变量配置：
    - TENCENTCLOUD_SECRET_ID
    - TENCENTCLOUD_SECRET_KEY
    - TENCENTCLOUD_REGION (如 ap-guangzhou)
    - TENCENTCLOUD_PROJECT_ID (整数，默认 0)
    """

    def __init__(self) -> None:
        self.secret_id = settings.tencentcloud_secret_id
        self.secret_key = settings.tencentcloud_secret_key
        self.region = settings.tencentcloud_region
        self.project_id = settings.tencentcloud_project_id
        self.version = "2018-03-21"
        self.endpoint = "tmt.tencentcloudapi.com"
        self.enabled = bool(self.secret_id and self.secret_key)

        if not self.enabled:
            logger.warning("腾讯云翻译未配置，翻译功能不可用")

    def translate(
        self, text: str, source: str = "en", target: str = "zh"
    ) -> Optional[str]:
        """
        翻译文本

        Args:
            text: 待翻译文本
            source: 源语言（auto/en/zh 等）
            target: 目标语言（zh/en 等）

        Returns:
            翻译后的文本，失败返回 None
        """
        if not self.enabled:
            return None

        if not text or not text.strip():
            return ""

        # API 单次文本长度限制 6000 字符
        if len(text) > 6000:
            text = text[:6000]

        # 构造 TC3-HMAC-SHA256 签名
        service = "tmt"
        host = self.endpoint
        algorithm = "TC3-HMAC-SHA256"
        timestamp = int(time.time())
        date = time.gmtime(timestamp)
        date_str = time.strftime("%Y-%m-%d", date)

        canonical_uri = "/"
        canonical_querystring = ""
        payload = {
            "SourceText": text,
            "Source": source,
            "Target": target,
            "ProjectId": self.project_id,
        }
        payload_json = json.dumps(payload, separators=(",", ":"))
        hashed_payload = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        canonical_headers = f"content-type:application/json\nhost:{host}\n"
        signed_headers = "content-type;host"
        canonical_request = (
            f"POST\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
        )

        credential_scope = f"{date_str}/{service}/tc3_request"
        hashed_canonical_request = hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest()
        string_to_sign = (
            f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical_request}"
        )

        def _hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        secret_date = _hmac_sha256(
            ("TC3" + self.secret_key).encode("utf-8"), date_str
        )
        secret_service = _hmac_sha256(secret_date, service)
        secret_signing = hmac.new(
            secret_service, b"tc3_request", hashlib.sha256
        ).digest()
        signature = hmac.new(
            secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        authorization = (
            f"{algorithm} Credential={self.secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        url = f"https://{host}"
        req = urllib.request.Request(url)
        req.method = "POST"
        req.add_header("Content-Type", "application/json")
        req.add_header("Host", host)
        req.add_header("X-TC-Action", "TextTranslate")
        req.add_header("X-TC-Region", self.region)
        req.add_header("X-TC-Timestamp", str(timestamp))
        req.add_header("X-TC-Version", self.version)
        req.add_header("Authorization", authorization)
        req.data = payload_json.encode("utf-8")

        try:
            logger.debug(f"翻译请求: len={len(text)}, {source} -> {target}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode("utf-8", errors="ignore")
                obj = json.loads(data)
                resp_obj = obj.get("Response") or {}

                if "Error" in resp_obj:
                    err = resp_obj.get("Error") or {}
                    logger.error(
                        f"翻译错误: code={err.get('Code')} msg={err.get('Message')}"
                    )
                    return None

                tgt = resp_obj.get("TargetText")
                if tgt is not None:
                    logger.debug(f"翻译成功: {len(text)} -> {len(tgt)} 字符")
                    return tgt

                logger.error(f"翻译响应异常: {data}")
                return None

        except Exception as e:
            logger.error(f"翻译请求失败: {e}")
            return None

    def translate_if_english(self, text: str) -> tuple[str, Optional[str]]:
        """
        如果文本是英文，则翻译为中文

        Args:
            text: 原始文本

        Returns:
            (原文, 译文) - 如果不需要翻译或翻译失败，译文为 None
        """
        if not text or not self.enabled:
            return text, None

        # 简单判断是否主要是英文（ASCII 字符占比 > 70%）
        ascii_count = sum(1 for c in text if ord(c) < 128)
        if len(text) > 0 and ascii_count / len(text) > 0.7:
            translated = self.translate(text, source="en", target="zh")
            return text, translated

        return text, None
