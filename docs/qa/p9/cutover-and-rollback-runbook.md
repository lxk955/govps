# P9 正式切换上线与回滚保障操作手册（cutover-and-rollback-runbook.md）

> 本文件为 GoVPS 生产域名（`govps.xyz`）从旧版（FastAPI+Vue）正式切换至新版（Next.js App Router + FastAPI）的**标准作业程序（SOP）与回滚操作手册**。

---

## 1. 切换总体时间轴与阶段规划

```
 [T-24h 准备期]              [T-0 切换期 (低峰 02:00 UTC)]      [T+5m 冒烟核验]         [T+72h 观察期]
 ─────────────────────────▶ ───────────────────────────────▶ ──────────────────────▶ ─────────────────────
 1. Cloudflare TTL 降至 300s 1. CNAME 改指 next-govps        1. 线上 10 核心链路冒烟  1. 核心接口 P95 监控
 2. 生产库增量迁移生效      2. Cloudflare Purge Everything  2. 搜索引擎与爬虫收录   2. 爬虫周期调度监测
 3. Next.js 生产容器预热                                    3. 观察错误日志与告警   3. 邮件 Worker 队列观察
```

---

## 2. 详细切换执行步骤（Cutover SOP）

### 2.1 切换前准备（T-24h 至 T-1h）
1. **Cloudflare DNS 准备**：
   - 登录 Cloudflare 控制台，进入 `govps.xyz` DNS 配置；
   - 将根域名与 `www` 的 TTL 设置为 **300 秒（5 分钟）**，确保切换时全球 DNS 快速收敛；
   - 保持代理状态为 **Proxied（橙云）**。
2. **生产数据库迁移就绪**：
   - 确保 Render Postgres 已自动或手动执行 `alembic upgrade head`，版本确认停留在 `0005_request_rate_events`；
   - 确认 344+ 款存量产品物化列已由扫描任务或 `refresh_derived_fields` 全量回填。
3. **服务状态核验**：
   - Next.js 前端服务（`next-govps.onrender.com`）：健康状态正常；
   - FastAPI 后端服务（`api-govps.onrender.com`）：`/api/health` 返回 `{"ok": true}`。

### 2.2 切换执行（T-0，推荐业务低峰期 02:00–04:00 UTC）
1. **CNAME 目标切换**：
   - 在 Cloudflare DNS 将 `govps.xyz` 的 CNAME 目标由 `vps-scout.onrender.com`（旧版）修改为 `next-govps.onrender.com`（新版）；
2. **清除边缘缓存**：
   - 在 Cloudflare 控制台 -> 缓存（Caching）-> 配置（Configuration）-> 点击 **「清除所有内容」（Purge Everything）**，清除边缘残留的旧版 HTML；
3. **保持后端热备**：
   - **严禁停止旧版 FastAPI 容器**。因为新版 Next.js 服务端所有 `/api/*` 请求均同域反代至 FastAPI 容器，后端是唯一数据所有者。

---

## 3. 上线后 10 项核心用户链路冒烟清单（T+5m 至 T+30m）

上线后按以下顺序在生产域名 `https://govps.xyz` 执行实测：

| # | 检查项 | 验证路径 / 操作 | 预期行为 | 状态 |
|---|---|---|---|---|
| 1 | **健康检查** | `curl -i https://govps.xyz/api/health` | HTTP 200 `{"ok": true}` | [ ] |
| 2 | **首页 SSR 渲染** | 访问 `https://govps.xyz/` 查看网页源代码 | 首屏包含精选推荐卡片、24h 动态条与工具入口；SSR HTML 正文完整 | [ ] |
| 3 | **VPS 列表与筛选** | 访问 `/vps`，按商家「DMIT」、线路「CN2 GIA」筛选并搜索 | URL 查询参数同步更新，卡片即时响应，分页器正常 | [ ] |
| 4 | **套餐详情与图表** | 访问任意详情页（如 `/vps/1-dmit-pvm-lax-pro-wee`） | 规格矩阵展示清晰；SVG 价格历史图正常渲染；库存时间线正常 | [ ] |
| 5 | **返利跳转与埋点** | 点击购买按钮跳转 `/go/1?src=detail` | 触发 302 临时重定向至商家官网；数据库 `aff_clicks` 正常记录点击 | [ ] |
| 6 | **多款对比页** | 将 2–3 款产品加入对比，访问 `/compare?ids=1,2,3` | 横向表格整齐并排；折年 ≈ USD 数值一致；移动端首列 sticky 固定 | [ ] |
| 7 | **账户与验证码** | 访问 `/login`，输入真实邮箱获取验证码 | 收到 6 位验证码邮件；输入后成功登录并持久化 token | [ ] |
| 8 | **关注管理与推送** | 登录后关注 1 款产品并修改阈值，访问 `/watchlist` | 关注列表展示该套餐；支持实时修改降幅阈值与通知开关 | [ ] |
| 9 | **IP 工具箱** | 访问 `/ip`，测试 `?q=1.1.1.1` 与 WebRTC 泄露检测 | 纯净度评分正常计算，WebRTC 正确收集本地与公共候选 | [ ] |
| 10| **SEO 与爬虫协议** | 访问 `/sitemap.xml` 与 `/robots.txt` | robots 禁止 /api 与 /go；sitemap 包含全部公开套餐与路由 | [ ] |

---

## 4. 72 小时可观察性监控矩阵（T+1h 至 T+72h）

1. **服务可用性与延迟（Render Metrics）**：
   - 目标：Next.js 与 FastAPI P95 响应时间 ≤ 300ms，HTTP 5xx 错误率 ≤ 0.01%；
2. **爬虫调度与抓取健康度**：
   - 通过 `SELECT slug, last_success_at, last_error FROM merchants;` 监控 7 家爬虫抓取状态，确保无持续超时或解析崩溃；
3. **异步邮件投递队列**：
   - 监控 `SELECT status, count(*) FROM notify_logs GROUP BY status;`，确保 `pending` 能够被及时清空，`failed` 比例正常；
4. **汇率自动拉取状态**：
   - 每日 04:00 UTC 观察 `exchange_rates` 表的 `updated_at` 时间戳是否正常更新。

---

## 5. 零停机紧急回滚 SOP（Rollback Runbook）

若切换后发现不可预期的严重渲染故障、核心阻塞性 Bug 或第三方不可抗力，**2 分钟内按以下步骤无损回滚**：

### 步骤 1：DNS 秒级切回
- 在 Cloudflare 控制台中，将 `govps.xyz` 的 CNAME 目标改回 `vps-scout.onrender.com`（旧版）；
- 耗时：约 30 秒生效。

### 步骤 2：全量清除边缘缓存
- 在 Cloudflare 控制台点击 **「Purge Everything」**；
- 耗时：立即生效。

### 步骤 3：数据库状态保证
- **无需执行数据库 downgrade**；
- 原因：重构期间所有数据库变更均为**可空新增列、新表与新索引**。旧版 FastAPI 与 Vue 静态产物在架构上天然忽略这些新增字段，旧版本在当前数据库上可 100% 正常运行，数据零丢失。

### 步骤 4：回滚后冒烟核验
- 访问 `https://govps.xyz/`，确认已恢复为旧版 Vue SPA 界面；
- 测试旧版产品列表、详情与跳转链接，确认业务完全恢复。
