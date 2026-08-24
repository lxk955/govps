# P8 上线部署与配置检查清单（deployment-checklist.md）

> 本文件是 GoVPS 生产上线（P8 / P9）的**基础设施与运维配置基准**。
> 涵盖 Render 部署、Cloudflare 边缘规则、监控告警、DMIT 速率保护、邮件链路及回滚预案。

---

## 1. 架构拓扑与服务拓扑

```
                           ┌──────────────────────────────────────────────┐
                           │ Cloudflare (DNS + SSL + CDN + WAF)           │
                           │ - govps.xyz                                  │
                           │ - 代理状态：已开启 (Proxied / 橙云)          │
                           └──────────────────────┬───────────────────────┘
                                                  │
                      ┌───────────────────────────┴───────────────────────────┐
                      │                                                       │
                      ▼ (HTTPS 转发)                                          ▼ (回滚热备)
      ┌───────────────────────────────┐                       ┌───────────────────────────────┐
      │ Render Web Service: next-govps│                       │ Render Web Service: vps-scout │
      │ (Next.js App Router 独立容器) │                       │ (旧版 FastAPI + Vue 静态产物) │
      └───────────────┬───────────────┘                       └───────────────┬───────────────┘
                      │ Next.js rewrites: /api/* → API_ORIGIN                 │
                      ▼                                                       │
      ┌───────────────────────────────┐                                       │
      │ Render Web Service: api-govps │                                       │
      │ (FastAPI 后端，唯一 DB 所有者)│◀──────────────────────────────────────┘
      └───────────────┬───────────────┘
                      │ SQLAlchemy 2.0 (postgresql+psycopg)
                      ▼
      ┌───────────────────────────────┐
      │ Render Managed PostgreSQL     │
      │ (共享数据库，Alembic 版本化)  │
      └───────────────────────────────┘
```

---

## 2. Render 环境变量与服务配置清单

### 2.1 Next.js 前端服务 (`next-govps`)
- **Runtime**: Docker (standalone build)
- **Dockerfile**: 仓库根目录 `Dockerfile`
- **环境变量**:
  | 变量名 | 推荐值 / 来源 | 说明 |
  |---|---|---|
  | `NODE_ENV` | `production` | 生产模式 |
  | `PORT` | `3000` | 监听端口 |
  | `API_ORIGIN` | `http://api-govps:8000` 或内网 Service URL | Next.js 服务端同域转发 FastAPI 的目标源地址 |

### 2.2 FastAPI 后端服务 (`api-govps` / `vps-scout-api`)
- **Runtime**: Python 3.12 (`uvicorn app.main:app --host 0.0.0.0 --port 8000`)
- **Root Directory**: `api`
- **环境变量**:
  | 变量名 | 推荐值 / 来源 | 安全级别 | 说明 |
  |---|---|---|---|
  | `DATABASE_URL` | `postgresql+psycopg://user:pass@host/db` | **机密** | Render Postgres 连接串（已规范化为 psycopg3 协议） |
  | `TASK_TOKEN` | 随机生成 64 位字符串（如 `openssl rand -hex 32`） | **机密** | 用于 cron-job.org 触发 `/api/tasks/*` 鉴权 |
  | `RESEND_API_KEY` | `re_xxxxxxxxxxxx` | **机密** | Resend 官方发信 API Key |
  | `MAIL_FROM` | `GoVPS <notify@govps.xyz>` | 公开 | 邮件发信人（需与 Resend 验证域名一致） |
  | `PUBLIC_API_URL` | `https://govps.xyz` | 公开 | /go 跳转与邮件购买链接生成的根域名 |
  | `CORS_ORIGINS` | `https://govps.xyz` | 公开 | 允许的跨域来源（同域架构下零 CORS，供备用） |
  | `SKIP_STARTUP_SCAN` | `true` | 开关 | 生产环境设为 true：启动时禁全量扫描，避免阻塞就绪；扫描交由 cron |
  | `NOTIFY_WORKER_ENABLED`| `true` | 开关 | 开启后台 `notify-worker` 线程消费异步待发邮件 |
  | `CRAWL_INTERVAL_MINUTES`| `15` | 配置 | 全局兜底抓取间隔（各商家优先走各自配置） |
  | `EXCHANGE_RATE_MAX_DEVIATION` | `0.5` | 守卫 | 汇率单日漂移超过 50% 自动阻断写入 |

---

## 3. DMIT 抓取频率与防封保护配置

> [!IMPORTANT]
> **DMIT 速率与合规性说明**：
> - DMIT 爬虫适配器（`api/app/crawler/dmit.py`）采用**第三方监控源主备聚合**机制（主源 `monitor.vpszk.com` JSON API + 备源 `vpsoso.com` HTML + 内置兜底 presets），不向 `dmit.io` 官网发起高频请求，无直接封禁风险；
> - 为节约上游请求资源并遵循 AGENTS.md Crawl Scheduling 条款，生产推荐将 DMIT 抓取间隔配置为 **20–30 分钟**；
> - 运维覆盖方式：通过数据库执行 `UPDATE merchants SET crawl_interval_minutes = 20 WHERE slug = 'dmit';` 即可实时生效，无需重启服务或改动代码。

---

## 4. Cloudflare 边缘缓存与安全规则

| 优先级 | 匹配路径 | 动作 / 规则 | 缓存级别 | 边缘 TTL | 浏览器 TTL | 理由 |
|---|---|---|---|---|---|---|
| 1 | `govps.xyz/api/*` | Bypass Cache | 绕过缓存 | 0s | 0s (no-store) | 动态 API、登录、关注与价格时效性 |
| 2 | `govps.xyz/go/*` | Bypass Cache | 绕过缓存 | 0s | 0s | 返利跳转、缺货插页与点击埋点 |
| 3 | `govps.xyz/_next/static/*`| Cache Everything | 强缓存 | 1 年 | 1 年 (immutable) | Next.js 静态 chunk 含哈希，永久有效 |
| 4 | `govps.xyz/static/*` | Cache Everything | 强缓存 | 30 天 | 7 天 | 图标、静态资产与字体 |
| 5 | `govps.xyz/*` (页面 HTML) | Respect Header | 遵循源站 | 遵循 `Cache-Control` | max-age=0, must-revalidate | RSC 服务端动态渲染，保证库存一致性 |

**安全设置**：
- SSL/TLS 加密模式：`Full (Strict)`
- Minimum TLS Version: `TLS 1.2`
- Always Use HTTPS: `ON`
- Automatic HTTPS Rewrites: `ON`

---

## 5. 监控与可观察性指标

1. **健康检查端点**：
   - URL: `https://govps.xyz/api/health`
   - 预期响应: `{"ok": true}`（HTTP 200）
   - Render Health Check Path 配置为 `/api/health`，失败 3 次自动重启实例。
2. **定时任务监控**：
   - `cron-job.org` 配置 2 个周期调用：
     - `POST /api/tasks/scan`（Header: `X-Task-Token: <TASK_TOKEN>`）每 5 分钟调用一次；
     - `POST /api/tasks/update-rates`（Header: `X-Task-Token: <TASK_TOKEN>`）每日 04:00 UTC 调用一次。
3. **异步邮件告警观察**：
   - 查询滞留与失败邮件：`SELECT count(*) FROM notify_logs WHERE status = 'failed' OR (status = 'processing' AND sent_at < NOW() - INTERVAL '10 minutes');`

---

## 6. 真实邮件链路接入与冒烟指引

1. **Resend 域名认证**：在 Resend 控制台添加 `govps.xyz`，按要求在 Cloudflare DNS 中配置 SPF（TXT）、DKIM（CNAME）与 DMARC 记录；
2. **冒烟脚本验证**：
   在部署环境中执行一次性发信测试：
   ```bash
   curl -X POST https://govps.xyz/api/auth/request-code \
        -H "Content-Type: application/json" \
        -d '{"email": "your-test-email@example.com"}'
   ```
   检查目标邮箱是否收到 6 位验证码邮件。
3. **关注补货通知验证**：
   登录后关注测试产品，通过 `api/scripts/crawl_live_check.py` 触发状态同步，观察 `notify_logs` 状态由 `pending` 变为 `sent`。

---

## 7. 生产回滚预案（零停机与 0 DB 损伤）

若上线后遇到不可预期的前端或渲染严重故障，按以下步骤 2 分钟内完成回滚：

1. **DNS / 路由回切**：
   在 Cloudflare 中将 `govps.xyz` 的 CNAME 解析由 `next-govps.onrender.com` 切回旧版 `vps-scout.onrender.com`（旧版始终热备在线）；
2. **数据库无缝兼容**：
   无需执行 Alembic downgrade。P1–P7 所有增量变更均为可空列、独立表（`exchange_rates`, `request_rate_events` 等），旧代码天然忽略新字段，旧版功能 100% 正常读取旧字段；
3. **清除 Cloudflare 缓存**：
   在 Cloudflare 控制台点击 `Purge Everything`，清除边缘残留的 HTML 缓存。
