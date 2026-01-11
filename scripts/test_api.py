#!/usr/bin/env python3
"""测试 ScrapeCreators API

用于验证 API 响应格式，只消耗 1 个 credit。
运行前请确保 .env 中已配置 SCRAPECREATORS_API_KEY

使用方法：
    python scripts/test_api.py
"""

import asyncio
import json
import os
import sys

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


async def test_api():
    """测试 API 并打印响应结构"""
    api_key = os.getenv("SCRAPECREATORS_API_KEY")
    
    if not api_key or api_key == "your_api_key_here":
        print("❌ 错误：请先在 .env 中配置 SCRAPECREATORS_API_KEY")
        print("   获取地址：https://app.scrapecreators.com/")
        return False
    
    print(f"🔑 API Key: {api_key[:8]}...{api_key[-4:]}")
    print()
    
    import httpx
    
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }
    
    base_url = "https://api.scrapecreators.com"
    username = "realDonaldTrump"
    
    async with httpx.AsyncClient(timeout=30) as client:
        # 测试获取帖子
        print(f"📡 测试获取 @{username} 的帖子...")
        print(f"   URL: {base_url}/truthsocial/user/posts?username={username}")
        print()
        
        try:
            response = await client.get(
                f"{base_url}/truthsocial/user/posts",
                headers=headers,
                params={"username": username},
            )
            
            print(f"📊 响应状态码: {response.status_code}")
            print()
            
            if response.status_code == 200:
                data = response.json()
                
                print("📦 响应数据结构:")
                print(f"   类型: {type(data).__name__}")
                
                if isinstance(data, dict):
                    print(f"   字段: {list(data.keys())}")
                    
                    # 查找帖子数组
                    posts = None
                    for key in ["posts", "data", "statuses", "items", "results"]:
                        if key in data and isinstance(data[key], list):
                            posts = data[key]
                            print(f"   帖子字段: {key}")
                            break
                    
                    if posts:
                        print(f"   帖子数量: {len(posts)}")
                        if posts:
                            print()
                            print("📝 第一条帖子结构:")
                            first_post = posts[0]
                            print(f"   字段: {list(first_post.keys())}")
                            print()
                            print("   详细内容:")
                            print(json.dumps(first_post, indent=2, ensure_ascii=False)[:2000])
                    else:
                        print()
                        print("⚠️ 未找到帖子数组，完整响应:")
                        print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
                
                elif isinstance(data, list):
                    print(f"   帖子数量: {len(data)}")
                    if data:
                        print()
                        print("📝 第一条帖子结构:")
                        first_post = data[0]
                        print(f"   字段: {list(first_post.keys())}")
                        print()
                        print("   详细内容:")
                        print(json.dumps(first_post, indent=2, ensure_ascii=False)[:2000])
                
                print()
                print("✅ API 测试成功！")
                return True
                
            elif response.status_code == 401:
                print("❌ 认证失败：API Key 无效或已过期")
                return False
            elif response.status_code == 429:
                print("❌ 请求频率限制：请稍后再试")
                return False
            else:
                print(f"❌ 请求失败: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"❌ 请求异常: {e}")
            return False


if __name__ == "__main__":
    print("=" * 60)
    print("ScrapeCreators API 测试")
    print("=" * 60)
    print()
    print("⚠️ 注意：此测试会消耗 1 个 API credit")
    print()
    
    result = asyncio.run(test_api())
    sys.exit(0 if result else 1)
