# 🦅 Trump Truth Social Monitor

> 实时监控 Trump 的 Truth Social 动态，AI 驱动的宏观分析与投资洞察

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## ✨ 项目亮点

### 🤖 AI 驱动的宏观分析
- **智能解读**：基于 AG-UI 协议对接 AI Agent，自动分析 Trump 言论的市场影响
- **投资建议**：生成具体的投资方向建议，包含置信度评估
- **风险提示**：自动识别潜在风险因素，提供后续关注点

### 📊 多维度报告系统
- **实时推送**：新帖子秒级推送到飞书群
- **每日总结**：自动生成每日帖子统计与 AI 分析
- **每周报告**：Top N 热门帖子综合分析（可配置 3-20 条）

### ⚡ 运行时动态配置
- **无需重启**：所有配置项支持 API 热更新
- **Web 管理面板**：可视化配置监控参数、推送设置
- **灵活调度**：自定义采集频率、报告推送时间

### 🎯 生产级架构
- **Docker 一键部署**：开箱即用的容器化方案
- **MySQL 持久化**：可靠的数据存储
- **完善的日志**：结构化日志便于问题排查

## 🖼️ 功能预览

### 飞书推送效果

**实时帖子通知：**
```
🔔 Trump 发布了新帖子

📝 内容:
The United States of America is the Hottest and most 
Successful Country anywhere in the WORLD!!!

🤖 AI 宏观分析:
📌 Trump 强调美国经济地位，释放积极信号
   整体情绪:积极📈 | 市场影响:中🟡

💡 投资建议:
   • 美股大盘指数（做多） 置信度:65%
```

**每周报告：**
```
📊 Trump Truth Social 每周总结
📅 2026年01月05日 - 01月11日

📝 本周统计:
   • 总帖子数: 20
   • 原创帖子: 20

🔥 本周热门帖子 Top 10:
...

🤖 AI 宏观分析:
📌 聚焦地缘政治，中东紧张与拉美缓和并存

💡 本周投资建议:
   • 能源/石油（做多） 置信度:70%
   • 军工/国防（做多） 置信度:72%
```

## 🚀 快速开始

### 环境要求
- Docker & Docker Compose
- Python 3.11+（本地开发）

### 1. 克隆项目
```bash
git clone https://github.com/yupeng0512/truthsocial-trump-monitor.git
cd truthsocial-trump-monitor
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 填写必要配置
```

**必填配置：**
| 配置项 | 说明 | 获取方式 |
|--------|------|----------|
| `SCRAPECREATORS_API_KEY` | 数据采集 API | [ScrapeCreators](https://app.scrapecreators.com/) |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook | 飞书群设置 → 群机器人 |
| `KNOT_AGENT_ID` | AI 分析智能体 ID | [Knot 平台](https://knot.woa.com/) |
| `KNOT_API_TOKEN` | Knot API Token | Knot 设置 → Token |

### 3. 启动服务
```bash
docker-compose up -d
```

### 4. 访问管理面板
```
http://localhost:6001
```

## 📁 项目结构

```
truthsocial-trump-monitor/
├── src/
│   ├── main.py              # 主程序入口
│   ├── api.py               # REST API 接口
│   ├── config.py            # 静态配置
│   ├── runtime_config.py    # 运行时配置管理
│   ├── analyzer/            # AI 分析模块
│   │   ├── agui_client.py   # AG-UI 协议客户端
│   │   └── llm.py           # LLM 接口封装
│   ├── notification/        # 通知模块
│   │   └── feishu.py        # 飞书消息构建器
│   ├── scraper/             # 数据采集
│   │   └── scrapecreators.py
│   └── storage/             # 数据存储
│       ├── database.py      # 数据库操作
│       └── models.py        # 数据模型
├── frontend/                # Web 管理面板
│   ├── index.html
│   └── js/
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 🔧 API 接口

### 配置管理
```bash
# 获取通知配置
GET /api/settings/notification

# 更新通知配置
PUT /api/settings/notification
{
  "feishu_enabled": true,
  "realtime_enabled": true,
  "daily_report_enabled": true,
  "weekly_report_enabled": true,
  "weekly_report_top_posts": 10
}

# 手动触发报告推送
POST /api/settings/push-report
{"report_type": "daily"}  # 或 "weekly"
```

### 数据查询
```bash
# 获取帖子列表
GET /api/posts?page=1&page_size=20

# 获取统计数据
GET /api/stats
```

## ⚙️ 配置说明

### 采集配置
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `scrape_interval` | 3600 | 采集间隔（秒） |
| `max_posts_per_scrape` | 20 | 单次最大采集数 |

### 通知配置
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `realtime_enabled` | true | 实时推送开关 |
| `daily_report_enabled` | true | 每日报告开关 |
| `daily_report_time` | 09:00 | 每日报告时间 |
| `weekly_report_enabled` | true | 每周报告开关 |
| `weekly_report_day` | 1 | 周报推送日（1=周一） |
| `weekly_report_top_posts` | 10 | 周报热门帖子数量 |

### AI 分析配置
| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ai_enabled` | true | AI 分析开关 |
| `ai_timeout` | 60 | 分析超时（秒） |

## 🛠️ 本地开发

```bash
# 创建虚拟环境
uv venv
source .venv/bin/activate

# 安装依赖
uv pip install -r requirements.txt

# 启动服务
python -m src.server
```

## 📝 更新日志

### v1.0.0 (2026-01-11)
- ✅ 实时帖子监控与采集
- ✅ AI 宏观分析与投资建议
- ✅ 飞书实时/日报/周报推送
- ✅ Web 管理面板
- ✅ 运行时动态配置
- ✅ Docker 一键部署

## 📄 License

MIT License

## 🙏 致谢

- [ScrapeCreators](https://app.scrapecreators.com/) - Truth Social 数据采集
- [Knot](https://knot.woa.com/) - AI Agent 平台
- [飞书开放平台](https://open.feishu.cn/) - 消息推送
