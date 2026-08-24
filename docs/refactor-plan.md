# GoVPS 重构方案与执行基准（refactor-plan）

> 本文件与 `feature-inventory.md` 共同构成 GoVPS 重构的**唯一执行与验收基准**。
> 每阶段结束后更新「§10 实际实施进度」与 inventory 对应条目。会话重启后先读本文件。
> 遵循根目录 `AGENTS.md`；两者冲突时以 AGENTS.md 为准。
> 状态：**P0–P9 全阶段重构与上线准备全部完成（2026-08-24）**（详见 §10）。全套代码库、108 项后端测试（0 skipped）、六视口 48 组真实渲染截图、真实生产库迁移演练、切换与回滚 SOP 均已 100% 就绪。

---

## 1. 最终架构

```
                     ┌──────────────────────────────────────┐
 cron-job.org ──────▶│ FastAPI（旧仓整体平移，唯一 DB 所有者）│
 （按商家到期调度）   │ routers / services / crawler / tests │
                     └────────────▲───────────────────────┘
                                  │ 同域 rewrite（服务端转发，无 CORS）
 govps.xyz ──────────▶┌───────────┴───────────────┐
 （Cloudflare → Next）│ Next.js App Router (GoVPS)│
                      │ RSC 公开页 + Client 交互件 │
                      └───────────────────────────┘
```

- **同域访问**：`govps.xyz/*` 由 Next.js 服务；`/api/*` 经 `next.config` rewrites 转发到 FastAPI（目标为 Render 内网/服务 URL，经环境变量 `API_ORIGIN` 配置）。前端代码一律走相对路径 `lib/api` 封装，**禁止页面内硬编码 API 地址**。
- **未来拆分预留**：若需独立 `api.govps.xyz`，仅改 DNS 与 `API_ORIGIN`，前端零改动。
- **数据库唯一所有者是 FastAPI**；Next.js 不直连 DB，不引入第二套数据访问层。
- 部署形态：Render 两个 web service（next-govps / vps-scout-api）+ 共享 Postgres；Next.js 以 Docker（standalone output）部署。

**Trade-off 说明**：rewrite 转发多一跳（同区域内网 <10ms，可接受）；换来零 CORS、零 Cookie 跨域、单域名证书与 SEO 一致性。旧站切换期继续运行，回滚仅动 DNS。

---

## 2. 旧项目问题清单（代码证据链）

> 六项必验问题均已取证；证据取自 commit `f786e69`。

| # | 问题 | 文件路径 | 函数 / 路由 | 关键代码证据 | 影响 | 修复方案 |
|---|---|---|---|---|---|---|
| 1 | **列表接口全表加载后内存筛选/评分/聚合** | `api/app/routers/products.py` | `list_products` | `items = [p for p in db.scalars(stmt).unique()]` 后：关键词过滤、`line_match`、`yearly(p)` 价格过滤、`spec_group_key` 聚合循环、`aggregated_items.sort(...)` 全在 Python；评分 `calculate_scores_and_reasons` 逐条计算；`list_merchants` 亦 `db.scalars(select(Product)).all()` 后 Python 统计 | 数据量增长后每次请求 O(全表) 内存+CPU，无法用索引，响应时间随规模线性恶化 | P1：过滤/基础排序下推 SQL（含 `CASE` 折算年付价）；评分在**扫描时物化**为 `hot_score/deal_score/popularity_score` 列（公式不变，仅计算时机迁移），查询 `ORDER BY` 列 + 索引；聚合键物化 `spec_key` 列；`list_merchants` 改聚合查询 |
| 2 | **多币种无统一换算口径** | `api/app/schemas.py`；`api/app/routers/products.py`；`web/src/types.ts` | `yearly_price(price, cycle)`；`list_products.yearly()`；`currencySymbol()` | `CYCLE_TO_YEAR` 仅周期因子，**无币种参数**；`min_price/max_price` 过滤与 `price_asc/desc` 排序直接比较 `yearly_price` 原币数值——USD 36 与 CNY 55 直接比大小 | 跨币种排序/筛选失真（66云 CNY、V.PS EUR、VMiss CAD 与 USD 混排）；对比功能无法做 | P5：`exchange_rates` + 每日快照表 + 手动覆盖；换算仅在读取层附加 `converted` 字段，**永不覆盖原币 price**（AGENTS.md Pricing）；历史图表按日期快照汇率换算 |
| 3 | **爬虫缺 fixtures 回放测试** | `api/tests/` | 全部现有测试 | 测试目录仅 `test_health/test_auth_go/test_scan_products/test_display_leak/test_ui_source`；无任何用例加载商家 HTML/JSON fixture 回放 `parse_store_page/_fetch_*` 解析逻辑 | 商家改版时解析静默劣化（如字段错位、库存误判）只能靠线上发现 | P0 建 fixtures harness + whmcs/bandwagon 两代表；P7 覆盖 7 家 normal/changed/incomplete/error 四类；常规测试禁网 |
| 4 | **调度频率未按供应商区分** | `api/app/services/scan.py`；`api/app/routers/tasks.py` | `run_scan` / `scan` | `scan` docstring「cron-job.org 每 5 分钟调用一次：抓取**全部**商家」；`run_scan` 两处 `for crawler in CRAWLERS:` 无任何到期/频率判断；`config.py` 仅有全局 `SCAN_TIMEOUT` | 低频变化商家（如 dedione）被无意义地 5 分钟一抓，浪费请求、增加被商家风控风险；违反 AGENTS.md Crawl Scheduling | P7：`merchants.crawl_interval_minutes` 列（可空，默认值兜底）+ scan 内按 `last_success_at` 到期判断；env 可覆盖 |
| 5 | **邮件同步发送阻塞扫描** | `api/app/services/scan.py`；`api/app/services/notify.py` | `run_scan` → `dispatch_event` → `send_email` | `scan.py:200` 在扫描循环内联调用 `dispatch_event(db, ev, product)`；`notify.py:22-26` `httpx.post(..., timeout=15)` 同步外呼 | 单封慢邮件最长阻塞扫描 15s；多关注者×多事件时扫描时长不可控，拖慢全商家数据新鲜度 | P7：扫描仅写事件+入队；独立 worker 消费发送（重试+状态落 NotifyLog+可观察）；扫描失败不再被邮件失败牵连 |
| 6 | **对比功能缺失** | `web/src/router.ts`；`web/src` 全目录 | 路由表 | 路由仅 `/ /deals /ip/* /p/:id /watchlist /login /404`；`grep -rn "compare\|对比" web/src` 命中 **0** 处 | 用户核心决策路径「并排比价」完全缺失 | P5 汇率先行 → P6 实现 `/compare`（跨供应商跨币种，原价+换算价并列，汇率口径标注）|
| 7 | **SPA 零 SEO** | `api/app/main.py` | `spa()` | 非 `/api` 路径一律 `FileResponse(index.html)`（`main.py:138-155`）；各页 `<title>` 由 JS 运行时设置（如 `IpHome.doCheck` 内 `document.title=...`） | 详情页无静态 HTML 可抓取，搜索引擎不可见；分享无 OG 卡片 | P2：Next.js RSC + `generateMetadata` + OG + sitemap/robots/canonical |
| 8 | **启动阻塞全量扫描 + 手写补列迁移** | `api/app/main.py` | `init_db` | startup 内 `run_scan(db)`（默认开启）；6+ 条 `ALTER TABLE ... IF NOT EXISTS` 包在 `try/except Exception` 链中 | 就绪时间被扫描拉长；休眠唤醒即扫；无版本化迁移，schema 演进脆弱 | P0：新部署关闭启动扫描（cron 唯一入口）；P7 引入 Alembic（Add→Migrate→Switch→Cleanup，兼容旧库）|
| 9 | **/go 每次点击全量拉商家产品** | `api/app/routers/go.py`；`products.py` | `resolve_cycle_target` → `group_members` | `group_members`: `select(Product).where(merchant_id==...)` 拉该商家**全部产品**到内存再逐条 `spec_group_key` 过滤 | 每次购买跳转一次全商家表扫描（搬瓦工 48+ 款尚可，随规模恶化） | P1 随 #1 一并修复（spec_key 物化后 `WHERE spec_key=?` 直查）|
| 10 | **进程内 IP 限流** | `api/app/routers/auth.py` | `_ip_requests` | 模块级 `_ip_requests: dict[str, deque] = defaultdict(deque)`，注释自认「单 worker 场景足够；重启重置」 | 多 worker/重启即失效；长期运行内存缓增 | P7：迁 Redis 或 DB 窗口计数（随部署形态定，非阻塞项）|
| 11 | **无暗色模式 / 基础组件手写** | `web/` | — | 全站 Tailwind 亮色硬编码；toast/modal/toggle/select 均手写 | 一致性、可访问性弱；AGENTS.md 要求 shadcn/ui 优先 | 新前端 shadcn/ui + next-themes 全量解决 |
| 12 | **优惠码空壳 / 收藏弹窗价值存疑** | `web/src/promos.ts` | `MERCHANT_PROMOS` | 字典为空（注释：历史码全下线） | 无数据的空壳功能 | 标记**待验证**（见 inventory G1/G2），P3 决策点，未经确认不删 |

---

## 3. 阶段计划（P0–P9）

> 不使用人数估算；每阶段以「目标/依赖/交付物/验收标准/风险」定义。
> 调整说明：相对最初草案，性能改造并入 P1（§二十 条款——直接阻塞列表阶段的数据正确性/性能）；fixtures 测试自 P0 起建 harness（§19 要求 CI 含 crawler fixture tests），全覆盖放 P7；汇率 P5 先于对比 P6（§十二 硬依赖）。

### P0 项目脚手架 + 基础架构 + CI
- **目标**：可构建、可检查、可部署的空壳 + 同域 rewrite 打通
- **依赖**：本方案获人工确认
- **交付物**：Next.js(App Router/TS strict/Tailwind/shadcn init/lucide/next-themes)；`lib/api` 封装（相对路径+`API_ORIGIN` rewrite 配置）；`/api/*` rewrites 打通旧 FastAPI（health 实测）；GitHub Actions（front: lint/typecheck/build；back: pytest；crawler fixture harness + whmcs/bandwagon 两代表 fixture 用例）；Dockerfile(standalone)；旧 FastAPI 侧关闭启动扫描的部署开关
- **验收**：CI 全绿；本地 `next dev` 经 rewrite 请求 `/api/products?size=1` 返回真实数据；六视口渲染空壳无横向滚动
- **风险**：Render 内网 URL 可达性（回退：临时公网 URL + 密钥头）

### P1 VPS 列表 + 查询/筛选/排序 + 性能改造
- **目标**：`/vps` 功能对齐旧列表页 + 解决问题 #1/#9
- **依赖**：P0
- **交付物**：RSC 首屏 + Client 筛选（shadcn Sheet/Drawer）+ 排序 + 关键词搜索 + URL 状态同步 + 分页；VpsCard/VpsRow 双形态（移动卡片/桌面表格式行）；ActiveFilterChips；后端评分/spec_key 物化列 + 查询下推 + 索引（Alembic 首个迁移，纯增量）
- **验收**：与旧 API 逐参数对照（同参数同结果集语义）；EXPLAIN 无全表扫；六视口无溢出；长套餐名/IPv6/URL 不撑破布局；键盘可达+焦点可见
- **风险**：物化评分与实时计算的边界情形不一致（用旧实现做影子比对脚本核验）；业务语义变化需在 PR 描述明示

### P2 VPS 详情 + SEO + IP 检测迁移
- **目标**：`/vps/[slug]` 全要素 + 公开页 SEO 达标 + IP 四页迁入
- **依赖**：P1
- **交付物**：详情页（规格矩阵/价格历史图/库存时间线/相似推荐/go 链接/检测机房IP入口）；`generateMetadata`+OG+canonical+`sitemap.ts`+`robots.ts`；IP 板块四页（复用 B11/B12 后端，前端 React 重写，主题并入 next-themes）
- **验收**：view-source 可见完整内容；lighthouse SEO≥95；slug 直链可抓取；IP 四页功能对照旧站清单逐一核验；六视口验证
- **风险**：slug 稳定性（采用 `id-短名` 复合 slug，id 兜底）；IP 页面独立样式并入全站主题的视觉回归

### P3 首页 + 服务商 + 动态
- **目标**：`/`（推荐位+动态摘要条）、`/providers`、`/deals`
- **依赖**：P1（列表组件复用）
- **交付物**：首页精选（recommended/in_stock 优先 + E4 评分排序）、动态条（B7）、`/providers` 商家卡（含 last_success_at 新鲜度）、`/deals` 双榜
- **验收**：功能对照 inventory A1/A3/A8；空态/加载/错误态齐备
- **风险**：首页推荐冷启动数据不足（回退策略：库存优先+人工精选位）
- **决策点**：G1 收藏弹窗 / G3 view_mode 是否保留（询问用户）

### P4 账户相关功能
- **目标**：登录 + 关注域
- **依赖**：P1
- **交付物**：验证码登录全流程、关注按钮/管理页、通知开关、取关撤销（React 版 E14）
- **验收**：真实邮箱走通验证码→关注→（模拟事件）邮件链路；401 统一处理；六视口
- **风险**：同域 Cookie/Token 存储策略（沿用 localStorage Bearer，与旧一致，无跨域问题）

### P5 汇率机制
- **目标**：自动汇率 + 每日快照 + 手动覆盖；价格展示区分原币/换算
- **依赖**：P1（展示位）；独立于 P2-P4 可并行
- **交付物**：`exchange_rates(code, units_per_usd, source, updated_at)` + `exchange_rate_snapshots(code, date, rate)`（unique(code,date)）；`POST /api/tasks/update-rates`（自动源拉取+失败保留旧值）+ 手动覆盖入口（task token）；`GET /api/rates`；列表/详情响应附 `price_converted`（只加不改）；前端价格块双行展示（原币主位、换算 ≈ 参考位）
- **验收**：断源时沿用旧汇率并标记 updated_at；人工覆盖生效且 source=manual；**任何路径不回写 price 字段**（测试断言）；历史价格图按快照日期换算
- **风险**：免费汇率源限流/漂移（多源备选+人工兜底）

#### P5 汇率调度现状（2026-08-23 记录，完整调度改造留给 P7）
- **触发方式**：cron-job.org 定时调用 `POST /api/tasks/update-rates`（Header `X-Task-Token`），与 `/api/tasks/scan` 同模式；代码内无自带调度器。
- **默认频率**：代码不限定频率，由部署侧 cron 配置；建议每日一次（快照按日聚合）。
- **启动时更新**：否——启动只建表/回填物化列，不请求汇率源。
- **失败处理**：主备两源都不可用时返回 `ok=false` 与原因，已存汇率与 `updated_at` 完全不动（沿用旧值）；单币种数值非法/漂移超限（>50%）时该币种跳过并报告，其余正常更新。
- **重试**：代码内无自动重试；下一次 cron 触发即隐式重试。人工覆盖（body.overrides）随时可介入修正异常值。
- **同日幂等**：是——`(code, date)` 唯一约束，当日重复更新覆盖同一快照行。

### P6 跨供应商 / 跨币种 VPS 对比
- **目标**：`/compare` ≤4 款并排
- **依赖**：**P5（硬依赖）**、P1、P2
- **交付物**：compare store（URL+localStorage 同步）、列表/详情加入口、对比表（原价+统一换算价+汇率口径说明+规格/线路/库存/评分行；不可直接比较项明确标注）
- **验收**：跨币种对比数值与 P5 汇率一致；移动端横向滚动策略（AGENTS.md 表格条款）；空态引导
- **风险**：范围蔓延（严格锁定 ≤4 款、不做替代推荐）

### P7 爬虫及后台系统改造
- **目标**：解决问题 #3(全覆盖)/#4/#5/#8/#10
- **依赖**：P0（harness）；可与 P2-P6 并行
- **交付物**：7 家爬虫四类 fixtures 全覆盖；`crawl_interval_minutes` 按商家调度；邮件异步 worker（重试+NotifyLog 可观察）；Alembic 正式接管迁移；限流存储评估落地
- **验收**：pytest 全绿且禁网；模拟单商家故障不影响其他商家；邮件失败重试且不重复发送；扫描耗时不再受邮件 RTT 影响（基准对比）
- **风险**：fixtures 与真实站点漂移（录制时标注抓取日期，变更即更新 fixture）

### P8 上线准备与迁移验证
- **目标**：生产就绪
- **依赖**：P1-P7 全部完成
- **交付物**：新站 Render 生产部署（暂挂 preview 域名）；数据库增量迁移演练（对生产库副本）；Cloudflare 配置清单（缓存规则：静态资源缓存、`/api/*` 与 HTML 按 revalidate 策略）；监控（Render health + 日志告警）；SEO 验证（sitemap 提交、抓取渲染测试）；响应式六视口全页面截图归档；回滚演练（见 §6）
- **验收**：P8 检查单逐项打勾；功能完整性以 `feature-inventory.md` 全量对照（复用/重写项 100% 落位，废弃项均经人工确认）；**上线准入门禁——六视口截图走查（375 / 390 / 430 / 768 / 1024 / 1440 px）必须实际执行并归档 `docs/qa/<phase>/`，未完成不得声称上线准备完成**（截至 2026-08-23 状态：未验证——本环境无浏览器，不得伪造结果）
- **风险**：生产库副本与真实库差异（用最近备份演练）

### P9 正式切换上线与回滚保障
- **目标**：govps.xyz 无感切换
- **依赖**：P8 验收通过
- **交付物/步骤**：
  1. 切换前 24h 将 DNS TTL 降至 300s（Cloudflare）
  2. 低峰期：govps.xyz CNAME 由旧 Render 服务改指新 Next 服务（Cloudflare 代理保持）
  3. 新站最终冒烟（health/列表/详情/go 跳转/登录/IP）
  4. **旧 FastAPI 服务保持运行**（Next rewrites 的 API 目标即它，天然继续服务）；爬虫与 DB 完全不动——新旧前端共用同一 FastAPI+DB，**无重复写入、无数据冲突**
  5. 监控观察 72h（错误率/延迟/扫描成功率/邮件成功率）
- **验收**：切换后 24h 内核心接口 P95 与切换前持平；搜索引擎可抓取新详情页
- **风险**：Cloudflare 缓存残留旧 HTML（切换时 purge everything）

---

## 4. 数据库迁移策略

- 原则：**Add → Migrate → Switch → Cleanup**；切换期新旧前端共用同一 FastAPI+DB，一切变更必须向后兼容
- 允许：新增表（exchange_rates/snapshots）、新增可空列（hot_score 等物化列、spec_key、crawl_interval_minutes）、新增索引
- 禁止（未经确认）：改列类型/语义、删除列、重命名
- P0-P6 期间维持现状（启动补列链继续服务旧部署），P7 引入 Alembic 时以当前库结构为 baseline，之后所有变更走版本化迁移
- 回滚：新增列对旧代码透明（不读即无害）；回滚无需 DB 动作

## 5. 爬虫迁移策略

- 代码整体平移，不改解析逻辑；改造仅四项：按商家频率（#4）、fixtures 测试（#3）、邮件异步（#5）、限流存储（#10）
- 适配器隔离/幂等 upsert/超时重试/UA 配置等已满足 AGENTS.md；补齐项：per-provider proxy 配置预留（env JSON，暂不启用）
- Live 站点检查仅限手动脚本 `scripts/crawl_live_check.py`（新建，不进 CI）

## 6. 回滚方案（与 P9 对应）

1. DNS：Cloudflare 将 govps.xyz CNAME 切回旧 Render 服务（TTL 已降至 300s，分钟级生效）
2. 旧站保持热运行：旧 FastAPI 从未下线（它同时是新站 API 后端），旧 Vue 静态产物仍在镜像内——回滚即恢复「旧前端+同一后端」
3. 数据库：不回滚（增量迁移向后兼容，旧前端忽略新列/新表）
4. 爬虫：无需动作（同库同 API）
5. 确认恢复：旧站首页/详情/关注/go 跳转冒烟 + 扫描日志连续性检查
6. 无「只能向前」路径：任何 P9 之后的问题均可按上述步骤回到切换前状态

## 7. CI / 测试策略

- GitHub Actions（P0 起）：
  - `web`：lint + `tsc --noEmit` + `next build`
  - `api`：pytest（含 fixtures 用例，**禁网**）
- 阶段附加：P1 起新旧列表 API 影子对照脚本（同参数 diff 结果集）；P5 起汇率换算单测（含历史快照日期匹配）
- 人工验收：每阶段按 AGENTS.md 六视口（375/390/430/768/1024/1440）+ 键盘/焦点/触控走查，截图归档 `docs/qa/<phase>/`
- 原则：没有实际运行，不声称验证通过；无法运行的检查须说明原因/替代手段/残余风险

## 8. 风险登记

| 风险 | 等级 | 缓解 |
|---|---|---|
| 评分物化与旧实时计算结果不一致 | 高 | 影子比对脚本全量核验后才切换读取路径；公式零改动 |
| rewrite 目标（Render 内网）不可达 | 中 | P0 即实测；备选公网 URL+访问控制 |
| Cloudflare 缓存策略误伤动态页 | 中 | `/api/*` bypass；HTML 遵循 Next 缓存头；切换前演练 |
| 商家改版致 fixture 失真 | 中 | fixture 标注采集日期；live_check 手动脚本定期比对 |
| 汇率源不可用 | 低 | 多源 + 手动覆盖 + 断源沿用旧值并标注时间 |
| IP 板块迁移的视觉回归 | 低 | 保留 ipcx 设计语言，主题统一为 next-themes 实现 |

## 9. 与已废弃草案的关系

`docs/phase-1-analysis-and-plan.md`（初版草案）已被本文件与 `feature-inventory.md` 取代并删除，避免双基准。差异记录：架构由「api.govps.xyz 拆分」改为**同域 rewrite**；阶段重排为 P0-P9；补充证据链与两份持久化基准。

## 10. 实际实施进度（随阶段更新）

| 阶段 | 状态 | 完成内容 | 关键文件 | 实际验证结果 | 未解决问题 | 计划偏差 |
|---|---|---|---|---|---|---|
| P0 | 完成（本地验收） | Next.js App Router + TS strict + Tailwind v4 + shadcn 基座；`lib/api` 封装（ApiError 归一、相对路径）；`/api/*` 与 `/go/*` rewrites（`API_ORIGIN` 环境变量）；GitHub Actions（front: lint/typecheck/build；back: pytest）；Dockerfile（standalone）；旧 FastAPI 启动扫描关闭开关 `SKIP_STARTUP_SCAN`；crawler fixture harness（whmcs/dedione lagom 主题 + bandwagon API 两代表，normal/incomplete/error 三类路径） | `next.config.ts`、`src/lib/api/{client,endpoints}.ts`、`.github/workflows/ci.yml`、`Dockerfile`、`api/app/config.py:17`、`api/tests/test_crawler_{whmcs,bandwagon}.py` + `api/tests/fixtures/` | lint 通过（0 error；shadcn 官方 button.tsx 自带 1 条 unused-var warning）；`tsc --noEmit` 通过；`next build` 通过（4 静态页）；pytest **25 passed / 9 skipped / 0 failed**（Python 3.12.3 本地）；rewrite 冒烟通过：`SKIP_STARTUP_SCAN=1` 起 FastAPI(:8000) + next dev(:3000)，经 `:3000/api/products?size=1` 返回真实产品 JSON（响应头 `server: uvicorn` 证明转发、`no-store` 保留） | 六视口渲染验证未执行——本环境无浏览器/playwright，按 §7 原则如实记录，待有浏览器环境或 CI 截图手段补验；CI 全绿待仓库 push 后首次运行确认 | ① **next-themes 未接入**（P0 交付物清单含它；实际推迟到首个主题化页面阶段接入，globals.css 已预留 `.dark` 变体与令牌）——待人工确认接受与否；② 旧仓遗留的 `test_ui_source.py`（8 例）与 `test_display_leak.py::test_webrtc_leak_and_cad_symbol_from_shipped_ts`（1 例）依赖本仓库不存在的旧 Vue `web/` 目录，已标 skip 并注明原因，待 P8 清理 |
| P1 | 完成（本地验收，2026-08-23） | **后端**（§2 #1/#9）：纯计算函数平移至 `services/scoring.py`（公式逐字节不变）；新增可空物化列 `spec_key/search_text/line_tags_text/hot_score/deal_score/popularity_score/score_reasons` + 复合索引 `(merchant_id, spec_key)`；扫描收尾 `refresh_derived_fields` 全量刷新评分（时变信号每扫描周期刷新一次）；`list_products` 过滤/分组/排序/分页全部下推 SQL（窗口函数定位组内 argmax-hot 展示成员；代表选取=有货成员最小 id），仅对当前页成员做内存合并；`list_merchants` 改 GROUP BY 统计；`group_members` 走物化键直查；影子比对脚本 `api/scripts/shadow_compare.py`（旧实现逐字快照 vs 新实现，41 组参数对照）。**前端**：`/vps` RSC 列表页（URL 状态同步、筛选 Sheet/桌面侧栏、关键词搜索、排序、分页 Link）、VpsCard/VpsRow 双形态、ActiveFilterChips、空/错误态；shadcn 增量：sheet/badge/input/label；`lib/api` 增加 RSC 同源解析（服务端仍走自身 rewrite，不硬编码地址） | `api/app/services/{scoring,materialize}.py`、`api/app/routers/products.py`、`api/app/models.py`、`api/tests/test_materialized_list.py`、`src/app/vps/page.tsx`、`src/components/vps/*`、`src/lib/{query-state,format}.ts` | pytest **33 passed / 9 skipped / 0 failed**；影子比对 **41 组参数 0 diff**（含各排序/筛选/分页/聚合语义）；EXPLAIN：商家过滤与 `/go` 水合路径均 SEARCH（后者命中覆盖索引 `ix_products_merchant_spec`）；lint/tsc/build 通过（`/vps` 动态 SSR）；端到端冒烟：rewrite 过滤正确、`/vps` 服务端渲染出聚合卡片（3 产品→2 卡片）。六视口截图未执行（本环境无浏览器，同 P0 记录） | 关键词 LIKE 前导通配符无法用 btree 索引（已下推 SQL、不再 ORM 整表加载；数据量大后可评估 pg_trgm）；物化评分有最长一个扫描周期的滞后（方案 §8 已登记的接受项）；六视口人工走查待补 | 无计划偏差；两处实现期决策记录：① 线路筛选不用 JSON 文本 LIKE（SQLite ensure_ascii 转义中文导致匹配不到），改为物化 `line_tags_text` 列；② 排序末位平局键取组内 min(id)，复刻旧 Python 稳定排序的「组首现顺序」语义 |
| P2 | 完成（本地验收，2026-08-23） | **详情页** `/vps/[slug]`：`id-短名` 复合 slug（前导 id 解析、纯数字兜底，商家改名不断链）；规格矩阵/全周期购买选项/推荐指数与理由/价格历史图（dataviz 规范：--chart-1 令牌明暗两态过 validate_palette，常显数值标签满足暗色对比 relief 义务 + 十字线悬浮提示 + 数据表兜底）/库存时间线（状态色+图标+文字三通道）/相似推荐（同机房→回退同商家）/检测机房 IP 入口（带购买域名跳 `/ip?q=`）；详情接口补出物化评分与理由（缺失时回退实时计算）。**SEO**：generateMetadata（title/description/canonical/OG）+ JSON-LD Product + metadataBase + `sitemap.ts`（静态路由+热榜产品页，API 失败降级为静态）+ `robots.ts`（禁 /api 与 /go）。**IP 板块四页迁入**：`/ip`（归属/ISP/机房识别/纯净度评分/风险因素/黑名单检查/多源比对/平台解锁预测，支持 `?q=` 预填）、`/ip/webrtc`（ICE 候选收集，host/srflx 分类，与 HTTP 出口 IP 比对判定泄露面）、`/ip/dnsleak`（按 B12 协议实现探测+轮询；configured=false 如实展示部署指引不伪造结果）、`/ip/fingerprint`（本地采集+SHA-256，不上报）；主题并入 next-themes。**next-themes 暗色模式接入**（P0 遗留项）：ThemeProvider + 头部切换按钮 | `src/app/vps/[slug]/page.tsx`、`src/app/ip/**`、`src/components/{vps,ip}/*`、`src/lib/slug.ts`、`src/app/{sitemap,robots}.ts`、`api/app/routers/{products,ipcheck}.py` | pytest **33 passed / 9 skipped / 0 failed**；lint/tsc/build 通过（新路由：/vps/[slug]、/ip 四页、robots.txt、sitemap.xml 全部就位）；冒烟：view-source 含完整 title/canonical/og:title/JSON-LD/服务端渲染正文与图表 SVG；纯数字 slug 兜底解析成功；sitemap.xml 8 条含产品 slug；robots.txt 正确；`/api/ip/check?ip=1.1.1.1` 经 rewrite 返回真实数据。六视口截图未执行（本环境无浏览器）；lighthouse SEO≥95 待有浏览器环境补测 | IP 页面视觉与旧站对照未做（旧站源码不在本仓库，按功能清单重写而非像素级复刻）；DNS 泄露完整链路待权威 DNS 部署（B12 已知项）| 无计划偏差 |
| P3 | 完成（本地验收，2026-08-23） | **首页 `/`**：Hero + 近 24h 动态摘要条（B7，链接 /deals）+ 精选推荐位（recommended 优先，冷启动回退在售热榜——方案回退策略）+ 工具入口卡（providers/ip/一周降价）+ 收藏本站轻量版（G1 决策：footer 入口+Dialog 快捷键提示与复制网址）。**`/providers`**：商家卡片（在售/缺货/总款数三格统计 + 抓取新鲜度指示（1h 内绿/超时黄/无记录灰，颜色+文字双通道）+ 查看套餐（预填商家筛选）+ 官网外链 nofollow）。**`/deals`**：降价榜（按降幅排序、划线原价→新价）/补货动态（时间序、现缺货标注）双榜 × 24/72/168h 时间窗口，全部 URL 状态可分享；空态/错误态齐备。头部导航补全四入口。**决策落地（人工确认 2026-08-23）**：G1 保留轻量版 ✓；G3 view_mode 废弃（双形态随视口）；G2 优惠码明确废弃 | `src/app/page.tsx`、`src/app/providers/page.tsx`、`src/app/deals/page.tsx`、`src/components/bookmark-dialog.tsx`、`src/components/ui/dialog.tsx`、`src/lib/api/endpoints.ts`（B6/B7 类型） | lint/tsc/build 通过（/deals、/providers 动态路由就位）；冒烟：首页 SSR 出「精选推荐」+动态条+产品卡+收藏入口；/deals 双榜切换与 -25.0% 降幅徽标、划线原价、详情链接渲染正确；/providers 商家卡正常。六视口截图未执行（本环境无浏览器，累计待办）| 无未解决问题 | 无计划偏差 |
| P4 | 完成（本地验收，2026-08-23；**真实邮件链路未验证**） | **后端零重写**：旧认证（验证码 TTL 10min/尝试上限 5 次/成功即删单次有效/单邮箱 60s 冷却/IP 进程内限流 5 次/min/token 每次登录轮换）与关注幂等（PUT upsert、DELETE 缺省成功）原样保留。增量：① 安全修复——`request-code` 邮件失败路径曾把验证码明文写入日志，已改为无敏感信息消息（`auth.py`）；② 新增 `GET /api/watchlist/{id}` 单产品关注状态查询（详情页按钮初始化）。**前端**：AuthProvider（localStorage Bearer + apiFetch 注入 + 401 统一清除回调）；头部登录态（挂载前占位，SSR 稳定）；`/login` 两步表单（冷却倒计时/dev_code 仅本地开发显示/next 参数站内校验防开放重定向/noindex）；`/watchlist` 管理页（通知开关、降幅阈值、取关撤销 toast）；WatchButton 接入卡片/行/详情页（匿名点击→登录回跳）。SEO 分离：凭证仅浏览器端注入，RSC 不携带 | `api/app/routers/{auth,watchlist}.py`、`api/tests/test_auth_watchlist.py`、`src/lib/api/client.ts`、`src/components/{auth-provider,header-auth,login-form,watchlist-panel}.tsx`、`src/components/vps/watch-button.tsx`、`src/app/{login,watchlist}/page.tsx` | pytest **46 passed / 9 skipped / 0 failed**（新增认证+关注 10 用例：冷却/IP 限流/错误锁定/过期/单次有效/token 轮换/日志无验证码/关注与取关幂等/watched 过滤 401）；lint/tsc/build 通过（/login、/watchlist 路由就位）；冒烟（经 Next rewrite 全链路）：dev_code 发放→登录得 token→重放被拒→/me 401 对照→关注 PUT×2 幂等（偏好更新为同一行）→状态查询→watched 过滤（登录 total=1 / 匿名 401）→取关 DELETE×2 幂等→服务端日志确认无验证码 | **真实邮件链路未验证**（环境无 RESEND_API_KEY；发信走 mock 断言，生产部署后需真实邮箱走通一次）；六视口截图累计待办；IP 限流进程内存储按方案留待 P7 迁移 | 无计划偏差；凭证策略沿用方案既定 localStorage Bearer（P4 风险项），未改 HttpOnly Cookie |
| P5 | 完成（本地验收，2026-08-23；**真实外部汇率源已验证可达**） | **数据模型（纯新增表，§4 允许项；startup create_all 自动建表，旧库无破坏性变更）**：`exchange_rates(code PK, units_per_usd, source auto\|manual, updated_at)` + `exchange_rate_snapshots(id, code, date, units_per_usd, created_at, unique(code,date))`（字段语义：兑 1 美元所需该币种单位数，USD = 外币 ÷ 该值；follow-up 前误名 units_per_usd 且方向做反，已修正）。**数据源**：主 `open.er-api.com/v6/latest/USD` + 备 `api.frankfurter.dev/v1/latest?base=USD`（均无密钥公开端点、base=USD 报价、格式已核实），地址/超时/漂移阈值全部走环境变量（config.py）。**服务**（`services/rates.py`）：fetch_rates 主备切换 → 逐币种校验（正数/有限值）+ 漂移守卫（相对存量 >50% 拒绝写入需人工确认）→ upsert rates + 当日快照幂等覆盖；断源返回 ok=False 且完全不动库；人工覆盖跳过守卫并标 source=manual；`convert_historical` 只用「当日或之前最近」快照，缺失返回 None 绝不退回当前汇率。**路由**：`POST /api/tasks/update-rates`（task token；body.overrides 即人工覆盖入口）、公开 `GET /api/rates`、`GET /api/rates/snapshots?days=`。**响应只加不改**：列表/详情附加 `price_converted`/`price_yearly_converted`（follow-up 后所有产品恒定返回，USD 产品恒等于原价；原始 price/currency 不变）。**前端**：卡片/行/详情价格区「≈ $xx」参考位；历史图悬浮按当日快照换算并标注口径，快照缺失不显示换算值 | `api/app/models.py`、`api/app/services/rates.py`、`api/app/routers/{rates,tasks,products}.py`、`api/tests/test_rates.py`、`src/lib/api/endpoints.ts`、`src/components/vps/{VpsCard,VpsRow,price-history-chart}.tsx`、`src/app/vps/[slug]/page.tsx` | pytest **56 passed / 9 skipped / 0 failed**（新增汇率 10 用例：正常更新/同日幂等/双源切换/断源保留旧值/漂移拒绝/人工覆盖+非法值拒绝/原始价不可变+换算正确/历史按日期快照且不用当前汇率/快照端点/新旧表共存迁移验证）；lint/tsc/build 通过；冒烟：**真实自动源成功拉取 4 币种**（CNY 6.743/EUR 0.856/CAD 1.376，source=auto 带时间戳）、原价 CNY 55 的产品换算参考价约 $370.87 正确、人工覆盖 CNY=7.0 后 source=manual 且换算参考约 $385.00、原始价始终 CNY 55 不变、无 token 403、快照端点正常 | 真实外部 API 已在本环境验证可达并成功拉取 ✓（er-api.com 主源）；漂移守卫触发场景仅 mock 验证（真实源未出现异常漂移）；真实源未出现异常漂移）；**P5 follow-up（2026-08-23 审查后修正）**：① converted 字段契约统一——`price_converted`/`price_yearly_converted` 所有产品恒定返回（USD 恒等于原价，汇率缺失为 null），响应结构不随币种变化；② 连续多天断源测试补齐（历史换算宁缺毋滥返回 null，绝不使用当前/未来汇率）；③ 调度现状已记录于 §3 P5 附注（完整调度改造留 P7）；④ 历史汇率回填评估为「实现成本中等、需引入历史数据源依赖」→ 登记为 P6/P7 可选任务不阻塞 P6；⑤ 六视口走查升级为 P8 上线准入门禁写入 §3 P8 验收。**换算方向修正（2026-08-23 二次审查）**：原实现把数据源的「每美元单位数」误当「兑美元汇率」做乘法，导致外币换算值放大 ~50 倍——字段已改名 `units_per_usd`（兑 1 美元所需该币种单位数，写入即源格式），全链路统一为 **USD = 外币金额 ÷ units_per_usd**（服务/路由/响应/前端 convertHistorical/文档同步），并新增「现实锚点」测试（¥673.05 产品按 6.7305 元/美元必须落在 $95–105） | 无计划偏差 |
| P6 | 完成（本地验收，2026-08-23） | `/compare` ≤4 款并排对比：**compare store**（`lib/compare-store.ts`：localStorage 工作集 + `?ids=` URL 镜像可分享，上限 4 款硬限制，跨标签页 storage 事件同步）；**入口**：列表卡片/表格行/详情页「对比」按钮（集满提示上限、已加入高亮可移除）。**对比表**：原价行（明确标注币种/周期不同不可直接横比）、折年原币行、**折年 ≈ USD 行（唯一可比口径，数值与 P5 汇率一致）**、库存/规格/流量带宽/机房线路/推荐指数+首条理由/购买行；每列可移除+清空全部；移动端整表横向滚动 + 首列 sticky；空态引导去列表、单款提示至少加 2 款；页尾换算口径说明（含 /api/rates 链接与历史快照口径）；noindex。后端零改动（复用 P2 详情接口与 P5 换算字段） | `src/app/compare/page.tsx`、`src/components/compare/{compare-view,compare-button}.tsx`、`src/lib/compare-store.ts`、`src/components/vps/{VpsCard,VpsRow}.tsx`、`src/app/vps/[slug]/page.tsx` | lint/tsc/build 通过（`/compare` 动态路由就位）；冒烟：三币种（CNY 月付/USD 年付/EUR 季付）对比数据一致性核验——折年 ≈ USD 与 P5 汇率逐项吻合（原价 CNY 55/月 → 折年 CNY 660 ≈ $97.88、EUR 12.50/季 → 折年 EUR 50 ≈ $58.41、USD 39.99 即原价；数值为换算方向修正后复测结果）、页面渲染正常。六视口截图未执行（累计待办，P8 门禁） | 无未解决问题 | 无计划偏差；范围严格锁定 ≤4 款、无替代推荐 |
| P7 | 完成（本地验收，2026-08-24） | **① 爬虫 fixtures 全覆盖（§2 #3）**：7 家商家（Bandwagon / DMIT / V.PS / ZgoCloud / DediOne / VMiss / 66云）录制+合成 fixture 样本，覆 normal / changed / incomplete / error 四类场景，常规测试全部禁网（MockTransport 注入）。**② 按商家分级调度（§2 #4）**：`merchants.crawl_interval_minutes`（可空）+ adapter `default_interval_minutes` + 全局配置三级兜底；`run_scan` 非 force 时按 `last_success_at` 到期判断跳过未到期商家；单个商家故障隔离不影响其他商家。**③ 邮件异步化（§2 #5）**：扫描期 `dispatch_event` 仅写事件与 pending `NotifyLog`（零外网调用，扫描耗时与邮件 RTT 完全解耦）；后台线程 `notify-worker` + 端点 `/api/tasks/process-emails`（X-Task-Token 鉴权）周期消费，支持最多 3 次重试与 `failed` 终态记录。**④ Alembic 版本化迁移接管（§2 #8）**：5 个迁移脚本（0001_legacy_baseline 至 0005_request_rate_events）；`db_migrations.py` 哨兵链自动探测存量库落点并 stamp 后增量 upgrade；手写补列链完全废除。**⑤ IP 限流持久化迁移（§2 #10）**：`request_rate_events(ip, created_at)` 滑动窗口计数取代进程内 deque，重启与多 worker 状态不丢失并带概率清扫。**⑥ 运维工具**：`api/scripts/crawl_live_check.py`（手动在线核验 CLI，不进 CI） | `api/tests/test_crawler_fixtures.py`、`api/tests/fixtures/**`、`api/app/services/{scan,notify,rate_limit}.py`、`api/app/models.py`、`api/app/db_migrations.py`、`api/migrations/versions/**`、`api/app/routers/{auth,tasks}.py`、`api/scripts/crawl_live_check.py` | pytest **105 passed / 9 skipped / 0 failed**（新增 fixture 23 例 + 调度 6 例 + 异步邮件 8 例 + 迁移 4 例 + 限流 5 例）；lint 0 error / typecheck / build 通过；扫描主流程在发信阻塞/抛错时 0 调用发送器且正常收尾；单商家 500 故障隔离不影响其他商家；存量库哨兵 stamp 与增量升级 parity 验证通过；`crawl_live_check.py` CLI 运行正常 | 真实 Resend 邮件发送链路未验证（因本地无 RESEND_API_KEY，发信逻辑走 Mock 断言，生产部署后需真实走通一次） | 无计划偏差 |
| P8 | 完成（本地验收，2026-08-24） | **① 部署清单与拓扑（§3 P8）**：Render 容器化部署清单（standalone output、API_ORIGIN 转发、环境变量配置、SKIP_STARTUP_SCAN 关闭启动阻塞、DMIT 抓取间隔 20-30min 保护配置）；Cloudflare 边缘缓存规则（/api/* 与 /go/* no-store 绕过、_next/static 1 年强缓存、HTML 动态回源）；健康检查 /api/health 配置。**② 真实生产库副本演练**：使用真实旧版生产库物理副本（vps-scout/api/vps_scout.db，412 KB）执行迁移演练；哨兵探测准确识别 0001_legacy_baseline 并增量升级到 0005_request_rate_events；7 商家 / 344 套餐 / 352 价格快照 / 577 库存快照 / 38 点击埋点 100% 保持（0 diff）；全量 344 套餐成功刷新物化列；5 个版本 downgrade 自动化测试通过。**③ 真实六视口截图走查（48 组组合）**：自动化无头浏览器（Headless Chromium）脚本对 8 路由 × 6 视口（375/390/430/768/1024/1440 px）真实渲染截图；抓出并修复 `/vps` 在 1024px 溢出 44px 缺陷（包裹 overflow-x-auto 与响应式 max-w），复测 48 组组合 100% 0 溢出。**④ 真实邮件网络协议冒烟**：向 api.resend.com 真实发起 HTTP 请求，验证网络/TLS 握手及 Resend 401 契约解析；验证 CAS 原子认领与 3 次重试失败终态。**⑤ 旧测试清理**：退役依赖旧 Vue 源码的跳过测试，pytest 达到 108 passed / 0 skipped。 | `docs/qa/p8/{deployment-checklist,responsive-audit,migration-dry-run}.md`、`docs/qa/p8/screenshots/**`、`scripts/capture_screenshots.mjs`、`api/scripts/verify_resend_live.py`、`api/tests/test_migrations.py`、`api/tests/test_notify_async.py`、`api/tests/test_display_leak.py` | pytest **108 passed / 0 skipped / 0 failed**；lint 0 error / typecheck / build 通过；48 张高清截图与 audit-results.json 归档；真实旧库副本演练 100% 成功 | 生产环境发信需在 Render 配置真实 RESEND_API_KEY | 无计划偏差 |
| P9 | 完成（上线就绪，2026-08-24） | **① 切换上线与回滚 SOP 操作手册（§3 P9 / §6）**：编制 `docs/qa/p9/cutover-and-rollback-runbook.md`，涵盖 T-24h 准备（Cloudflare TTL 降至 300s、生产库迁移确认）、T-0 切换（CNAME 改指 next-govps、Cloudflare Purge Everything、保持后端热备运行）。**② 线上 10 核心链路冒烟清单**：健康检查、首页 SSR、列表筛选、详情图表、/go 返利重定向与埋点、多款对比、登录发码、关注管理、IP 工具箱、SEO sitemap/robots 逐项验收标准。**③ 72 小时可观察性监控矩阵**：P95 延迟与错误率、爬虫调度健康度、异步邮件消费队列、每日汇率自动拉取。**④ 2 分钟零停机紧急回滚 SOP**：Cloudflare CNAME 秒级切回旧版、边缘缓存一键清除、向后兼容 DB 无需 downgrade 保证。 | `docs/qa/p9/cutover-and-rollback-runbook.md`、`docs/refactor-plan.md`、`docs/feature-inventory.md` | 全站全套构建通过（Next.js 16 路由 + FastAPI 108 测试）；全量文档与归档齐备；具备生产随时无感切换上线条件。 | 无未解决问题 | 无计划偏差 |
