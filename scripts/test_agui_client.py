#!/usr/bin/env python3
"""AG-UI 客户端测试脚本

用于测试 Trump 言论分析 Agent 的调用。

使用方法：
1. 确保 .env 中配置了 KNOT_* 相关参数
2. 运行: python scripts/test_agui_client.py
"""

import asyncio
import json
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.analyzer.agui_client import AGUIClient, TrumpPostAnalyzer, get_trump_analyzer


# 测试帖子数据
TEST_POST = {
    "content": "China has been ripping off the United States for YEARS. We are putting a 60% TARIFF on all Chinese goods. This will bring MILLIONS of jobs back to America. MAKE AMERICA GREAT AGAIN!",
    "translated_content": "中国多年来一直在占美国的便宜。我们将对所有中国商品征收60%的关税。这将为美国带回数百万个工作岗位。让美国再次伟大！",
}


async def test_config():
    """测试配置"""
    print("=" * 60)
    print("配置检查")
    print("=" * 60)
    
    print(f"KNOT_ENABLED: {settings.knot_enabled}")
    print(f"KNOT_AGENT_ID: {settings.knot_agent_id or '(未配置)'}")
    print(f"KNOT_API_TOKEN: {'***' + settings.knot_api_token[-4:] if settings.knot_api_token else '(未配置)'}")
    print(f"KNOT_AGENT_TOKEN: {'***' + settings.knot_agent_token[-4:] if settings.knot_agent_token else '(未配置)'}")
    print(f"KNOT_USERNAME: {settings.knot_username or '(未配置)'}")
    print(f"KNOT_MODEL: {settings.knot_model}")
    
    if not settings.knot_enabled:
        print("\n⚠️ KNOT_ENABLED=false，请在 .env 中启用")
        return False
    
    if not settings.knot_agent_id:
        print("\n⚠️ KNOT_AGENT_ID 未配置")
        return False
    
    if not settings.knot_api_token and not settings.knot_agent_token:
        print("\n⚠️ 需要配置 KNOT_API_TOKEN 或 KNOT_AGENT_TOKEN")
        return False
    
    print("\n✅ 配置检查通过")
    return True


async def test_client_init():
    """测试客户端初始化"""
    print("\n" + "=" * 60)
    print("客户端初始化测试")
    print("=" * 60)
    
    try:
        client = AGUIClient()
        print(f"✅ AGUIClient 初始化成功")
        print(f"   API URL: {client.api_url}")
        print(f"   Model: {client.model}")
        return client
    except Exception as e:
        print(f"❌ AGUIClient 初始化失败: {e}")
        return None


async def test_simple_chat(client: AGUIClient):
    """测试简单对话"""
    print("\n" + "=" * 60)
    print("简单对话测试")
    print("=" * 60)
    
    try:
        result = await client.chat(
            message="你好，请简单介绍一下你自己。",
            temperature=0.7,
        )
        
        if result["error"]:
            print(f"❌ 对话失败: {result['error']}")
            return False
        
        print(f"✅ 对话成功")
        print(f"   会话ID: {result['conversation_id']}")
        print(f"   消息ID: {result['message_id']}")
        print(f"   响应长度: {len(result['content'])} 字符")
        print(f"\n响应内容:\n{result['content'][:500]}...")
        return True
        
    except Exception as e:
        print(f"❌ 对话异常: {e}")
        return False


async def test_trump_analyzer():
    """测试 Trump 言论分析器"""
    print("\n" + "=" * 60)
    print("Trump 言论分析测试")
    print("=" * 60)
    
    try:
        analyzer = get_trump_analyzer()
        print("✅ TrumpPostAnalyzer 初始化成功")
        
        print(f"\n测试帖子:\n{TEST_POST['content']}")
        print(f"\n翻译:\n{TEST_POST['translated_content']}")
        
        print("\n正在分析...")
        result = await analyzer.analyze_post(
            content=TEST_POST["content"],
            translated_content=TEST_POST["translated_content"],
        )
        
        if result["status"] == "error":
            print(f"❌ 分析失败: {result['error']}")
            return False
        
        print(f"\n✅ 分析成功")
        print(f"   状态: {result['status']}")
        print(f"   分析时间: {result['analyzed_at']}")
        
        analysis = result["analysis"]
        if analysis:
            print(f"\n分析结果:")
            print(json.dumps(analysis, ensure_ascii=False, indent=2)[:2000])
            
            # 测试格式化输出
            print(f"\n飞书消息格式:")
            formatted = analyzer.format_analysis_for_feishu(analysis)
            print(formatted)
        
        return True
        
    except Exception as e:
        print(f"❌ 分析异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print("=" * 60)
    print("AG-UI 客户端测试")
    print("=" * 60)
    
    # 1. 配置检查
    if not await test_config():
        print("\n请先配置 .env 文件中的 KNOT_* 参数")
        return
    
    # 2. 客户端初始化
    client = await test_client_init()
    if not client:
        return
    
    # 3. 简单对话测试
    if not await test_simple_chat(client):
        print("\n简单对话测试失败，跳过后续测试")
        return
    
    # 4. Trump 分析测试
    await test_trump_analyzer()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
