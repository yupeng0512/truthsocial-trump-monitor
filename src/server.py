"""服务启动模块

同时启动 API 服务和监控任务
"""

import asyncio
import signal
import sys
import threading

import uvicorn
from loguru import logger

from src.api import app
from src.config import settings
from src.main import TrumpMonitor

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=settings.log_level,
)
logger.add(
    "logs/server_{time:YYYY-MM-DD}.log",
    rotation="00:00",
    retention="30 days",
    level="DEBUG",
)


def run_monitor():
    """在单独的线程中运行监控任务"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    monitor = TrumpMonitor()
    
    try:
        loop.run_until_complete(monitor.start())
    except Exception as e:
        logger.error(f"监控任务异常: {e}")
    finally:
        loop.close()


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("Trump Truth Social Monitor 启动")
    logger.info("=" * 60)
    
    # 启动监控任务（后台线程）
    monitor_thread = threading.Thread(target=run_monitor, daemon=True)
    monitor_thread.start()
    logger.info("监控任务已启动（后台线程）")
    
    # 启动 API 服务（主线程）
    logger.info("API 服务启动中... http://0.0.0.0:6001")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=6001,
        log_level="info",
    )


if __name__ == "__main__":
    main()
