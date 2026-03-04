# Truth Social Trump Monitor 已知问题

## 项目状态：健康

容器运行 4 周，总计仅 8 次 ERROR，核心功能正常。

## 间歇性错误（非阻塞）

### ScrapeCreators API 偶发失败

- **频率**: 4 周内 8 次（极低）
- **错误类型**: 502 Bad Gateway / 500 Internal Server Error
- **原因**: 上游 ScrapeCreators 服务不稳定、代理节点 DNS 解析失败 (`getaddrinfo ENOTFOUND core-residential.evomi.com`)
- **影响**: 单次采集失败，已有 tenacity 重试机制
- **状态**: 无需修复，属于上游问题

### 恶意扫描请求

- **现象**: 大量 `WARNING: Invalid HTTP request received` + Struts2 OGNL 注入尝试
- **影响**: 无（FastAPI 正确返回 405 Method Not Allowed）
- **建议**: 可在前置 nginx 层添加 IP 黑名单或 rate limit，但不影响功能

## 运维信息

- 采集频率：每小时 1 次
- 日报推送：每天 12:00
- API credits 余额：23861（充足）
- 数据存储：SQLite 本地文件
