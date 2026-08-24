# 旧项目功能与 API 完整清单（GoVPS 验收基准）

> 来源：`~/workspace/vps-scout` @ commit `f786e69`（2026-08-23 核验）
> 本文件是 GoVPS 重构的**功能完整性验收基准**。每个阶段结束后必须更新本文件中对应条目的状态。
>
> 状态标记：`复用`（后端原样沿用）/ `重写`（功能保留、实现以 Next.js/shadcn 重做）/ `新增`（旧项目没有）
> / `明确废弃`（附理由，**未经人工确认不得删除**）/ `待验证`（证据不足，禁止下结论）

---

## A. 页面与路由

| # | 旧路由 | 功能 | GoVPS 去向 | 状态 |
|---|---|---|---|---|
| A1 | `/` | 产品列表（筛选/搜索/排序/聚合卡片/分页）| `/vps`（首页独立拆分）| 重写 |
| A2 | `/p/:id` | 产品详情（规格/价格历史/库存时间线/相似推荐/检测机房IP入口）| `/vps/[slug]` | **重写完成（2026-08-23）**：全要素落地 + generateMetadata/OG/JSON-LD；旧 `/p/:id` 链接如需兼容跳转可在 P8 前加 redirect |
| A3 | `/deals` | 降价榜 + 补货动态（24h/72h/168h）| `/deals` | **重写完成（2026-08-23）**：双榜 Tab + 时间窗口 URL 状态；降价按降幅排序、补货按时间序 |
| A4 | `/watchlist` | 关注管理 + 通知开关 + 取关撤销 | `/watchlist` | **重写完成（2026-08-23）**：通知开关/降幅阈值即改即存、取关 6s 内可撤销（含原偏好恢复）、未登录引导 |
| A5 | `/login` | 邮箱验证码登录/注册合一 | `/login` | **重写完成（2026-08-23）**：两步表单+冷却倒计时+next 站内回跳；真实邮件链路未验证（环境无发信密钥，mock 测试通过）|
| A6 | `/ip` `/ip/webrtc` `/ip/dnsleak` `/ip/fingerprint` | IP 检测板块（独立明暗主题系统）| 同路径迁入新站 | **重写完成（2026-08-23）**：四页全量落地，主题并入全站 next-themes（不再维护独立主题系统）；DNS 泄露页按 B12 协议实现，权威侧未部署前如实展示部署指引 |
| A7 | `/*` SPA 兜底回 index.html | 单页应用托管 | 由 Next.js 文件路由天然取代 | 明确废弃 —— 理由：SPA 兜底是旧架构产物，Next.js 服务端路由取代之；SEO 缺失正是本次重构动因 |
| A8 | （无）| 首页推荐位/服务商页/对比页 | `/`（首页）、`/providers`、`/compare` | **P6 完成（2026-08-23）**：首页推荐位+动态摘要条 ✓、`/providers` ✓、`/compare` ≤4 款对比页 ✓（原价+折年 ≈USD 双口径、不可横比标注、移动端横向滚动、空态引导）|

## B. API 清单（FastAPI，全部随旧仓平移至 GoVPS 的 api 部分）

| # | 方法与路径 | 用途 | 后端处置 | 前端消费 |
|---|---|---|---|---|
| B1 | GET `/api/products` | 列表：多维筛选+关键词+排序+聚合+分页+三评分+理由 | **P1 完成（2026-08-23）**：评分/spec_key/search_text 物化 + 过滤/分组/排序/分页下推 SQL，API 形状不变；影子比对 41 组 0 diff | `/vps` RSC+Client（已上线 P1 版本）|
| B2 | GET `/api/products/merchants` | 服务商列表+聚合口径在售数/总数+最近抓取时间 | **P1 完成**：GROUP BY 统计，卡片口径与列表一致 | `/providers`、筛选面板（`/vps` 已消费）|
| B3 | GET `/api/products/{id}` | 详情+price_snapshots+stock_snapshots | 复用 | 详情页 |
| B4 | POST `/api/products/{id}/click` | 购买点击埋点 | 复用 | 卡片/详情 |
| B5 | PUT `/api/products/{id}/recommend` | 精选开关（X-Task-Token）| 复用 | 运维工具（无 UI）|
| B6 | GET `/api/events?type&hours&limit` | RESTOCK/PRICE_DROP 事件流 | 复用 | `/deals`（P2 已消费）|
| B7 | GET `/api/events/summary?hours` | 事件计数聚合 | 复用 | 首页动态条（P2 已消费）|
| B8 | GET/PUT/DELETE `/api/watchlist[/{pid}]` | 关注 CRUD | **复用 + P4 增量**：新增 GET `/api/watchlist/{pid}` 单产品状态查询；幂等语义经测试锁定 | `/watchlist`、关注按钮（P2 已消费）|
| B9 | POST `/api/auth/request-code` · `/verify` · GET me · PUT preferences | 验证码登录、视图偏好 | 复用（安全修复：验证码不再入日志）；view_mode 随 G3 废弃不再建 UI，接口保留向后兼容 | `/login`（P4 已消费）、导航 |
| B10 | GET `/go/{pid}?src&cycle` | 购买跳转（302/缺货插页/ZgoCloud POST 页）+AffClick 埋点+OOS 口径 | 复用 | 全站购买按钮 |
| B11 | GET `/api/ip/check?ip=` | IP 归属/威胁/纯净度情报 | 复用 | IP 板块 |
| B12 | GET `/api/ip/dns-leak/results` | DNS 泄露回收桩 | 复用（待权威侧部署）| IP-DNS 页 |
| B13 | POST `/api/tasks/scan` | 手动触发全量扫描 | 复用；P7 改造为按商家到期调度 | cron-job.org / 运维 |
| B14 | GET `/api/rates` · GET `/api/rates/snapshots?days=` | 当前汇率与每日快照 | **新增（P5 完成，2026-08-23）**：独立汇率存储，source 区分 auto/manual | 价格换算展示、P6 对比页 |
| B15 | POST `/api/tasks/update-rates`（body.overrides 即人工覆盖） | 自动拉取+当日快照；断源保留旧值；人工覆盖标 manual | **新增（P5 完成）**：漂移守卫拒绝异常自动值；真实源已验证可达 | cron-job.org / 运维 |
| B16 | （响应字段）列表/详情 `price_converted` · `price_yearly_converted` | USD 换算价附加字段 | **新增（P5 完成；契约 2026-08-23 follow-up 统一）**：所有产品**恒定返回**两字段（USD 产品值恒等于原价；汇率缺失为 null），响应结构不随币种变化，禁止以字段缺席判断币种；只加不改——原始 price/currency 永不回写（测试断言）；历史价格换算按「对应日期」快照，缺失返回 null 不显示换算值 | 前端价格参考位、历史图悬浮 |
| B17 | （数据表）`exchange_rates` · `exchange_rate_snapshots(unique(code,date))` | 汇率与每日快照独立存储 | **新增（P5 完成）**：纯增量建表向后兼容，旧库 startup 自动创建 | — |
| B14 | GET `/api/health` | 健康 | 复用 | 监控 |
| B15 | GET `/api/rates` + POST `/api/tasks/update-rates` | 汇率查询/更新（含手动覆盖） | **新增**（P5）| 价格换算展示、对比页 |

## C. 定时任务与后台任务

| # | 任务 | 现状 | GoVPS 去向 | 状态 |
|---|---|---|---|---|
| C1 | cron-job.org 每 5 分钟 POST scan（兼保活）| 全商家统一频率 | cron 保留入口；频率判断下沉到 scan 内部按商家到期执行 | **重写完成（P7，2026-08-24）**：商家列 `crawl_interval_minutes` + adapter 默认值 + 全局配置三级兜底；非 force 仅抓取到期者 |
| C2 | 应用启动时全量扫描 + 补列迁移 | 默认开启（SKIP_STARTUP_SCAN 可关）| 移除启动扫描；迁移改 Alembic | 明确废弃 —— 理由：启动阻塞就绪、休眠唤醒即扫；已由显式 cron 与 Alembic 版本化迁移取代（P0/P7 实施完成）|
| C3 | 邮件同步发送（dispatch_event 内联于扫描）| httpx timeout=15 同步调用 | 扫描入队、独立 worker 发送+重试+状态记录 | **重写完成（P7，2026-08-24）**：扫描期仅入队 pending NotifyLog，后台线程与 `/api/tasks/process-emails` 消费，支持 3 次重试 |

## D. 爬虫（provider adapters，全部整体平移）

| # | slug | 数据源 | 特有逻辑 | 状态 |
|---|---|---|---|---|
| D1 | bandwagon | 官方 JSON get-data | 多周期 price_options、aff=83019 加购规范 | 复用 |
| D2 | dmit | vpszk JSON+vpsoso HTML 双源合并+预置兜底 | 字段级合并、预置 from_preset | 复用 |
| D3 | vps | HostBill 分类页+预置兜底 | EUR 计价 | 复用 |
| D4 | zgocloud | WHMCS 定制模板 | 加购须 POST（B10 特判）、全周期 option 解析 | 复用 |
| D5 | dedione | WHMCS lagom 通用解析 | — | 复用 |
| D6 | vmiss | 分组页（CF 盾常拦）+CAD 预置 | CAD 计价 | 复用 |
| D7 | 66yun | cart.php?gid+CNY 预置 | CMI/软银专有线路标签 | 复用 |
| D8 | 公共层 base.py | 规格正则 parse_specs、线路七档归一+CMI/软银保留、机房中文归一、UA/Cookie 头 | — | 复用 |
| D9 | whmcs.py | WHMCS 通用卡片解析（悲观默认缺货、流量文案不当周期） | — | 复用 |
| D10 | 爬虫测试 | 现无 fixtures 回放测试 | 按 AGENTS.md 新增 normal/changed/incomplete/error 四类 fixture | **新增完成（P7，2026-08-24）**：7 家商家四类场景 23 用例全覆盖，常规测试 100% 禁网 |

## E. 重要业务逻辑

| # | 逻辑 | 说明 | 状态 |
|---|---|---|---|
| E1 | upsert_product 规则 | 悲观默认缺货；价格≤0 不入库不产生事件；规格非空才覆盖；新品独立收口 | 复用 |
| E2 | 消失标缺货 + 完整性门槛 | 仅官方源计入门槛 max(3, 存量×0.5)；预置目录不参与 | 复用 |
| E3 | SKU 聚合 | merchant+规范化名称+机房+线路+规格 聚合不同周期；有货代表替换；spec_group_key/group_members 已抽函数 | 复用（P1 评估 SQL 化）|
| E4 | 三评分+推荐理由 | Deal×0.7+Popularity×0.3，可解释 reasons≤4 条；冷启动探索加成 | 复用（P1 物化为列，公式不变）|
| E5 | 史低价判定 | 对比 PriceSnapshot 历史最低，区别于较上次降价 | 复用 |
| E6 | 关键词搜索 | 分词 AND 匹配名称/商家别名/机房别名/规格/流量 | 复用（P1 下推 LIKE/索引）|
| E7 | 年付价折算 yearly_price | 周期分隔符归一化；**不含币种换算**（见 refactor-plan 问题#2）| 复用 + P5 叠加汇率层 |
| E8 | go 跳转返利 | bandwagon aff=83019 官方规范、模板 {url}/{pid}、_safe_http_url 白名单、缺货插页、ZgoCloud 自动 POST、OOS 点击 `_oos` 口径 | 复用 |
| E9 | 通知事件去重 | 同产品同类型 30 分钟窗口 | 复用 |
| E10 | 邮件限额 | 每用户每日 sent ≤10，skipped 记录 | 复用 |
| E11 | 验证码安全 | secrets 生成、60s 冷却、attempts≤5、配置发信后失败 503 且不下发 dev_code | 复用 |
| E12 | 数据新鲜度 | last_checked_at（每次有效抓取刷新）/merchant.last_success_at·last_error | 复用（UI 必须展示）|
| E13 | API no-store | /api/* 响应禁缓存防陈旧库存 | 复用 |
| E14 | 取关撤销/乐观更新模式 | watch.ts 全局 store+失败回滚+vs:watch-changed 事件 | 重写（React 版同等能力）|
| E15 | 商家测试 IP 映射 merchants.ts | 详情页一键检测机房 IP | 重写 |

## F. IP 检测板块（A6 详细展开）

| # | 能力 | 状态 |
|---|---|---|
| F1 | 双源情报（ip-api+ipwho.is）中文运营商归一化、主机商品牌识别、欺诈分模型、解锁预测、多源对照 | 复用（后端 B11/B12 原样）|
| F2 | WebRTC 泄露检测（5 台公开 STUN、STUN=出口不算泄漏判定）| 重写（webrtcLeak.ts 逻辑移植 React，P2/P3）|
| F3 | DNS 泄露基座（随机子域探测流程+回收接口+部署指引）| 重写（P2/P3）|
| F4 | 浏览器指纹（15 项信号 SHA-256 本地计算）| 重写（P2/P3）|
| F5 | ip.cx 风格四页面框架+三态主题 | 重写 |

## G. 其他

| # | 项 | 现状 | 状态 |
|---|---|---|---|
| G1 | 收藏本站弹窗 BookmarkModal | 引导+复制链接 | **保留轻量版（2026-08-23 人工确认）**：首页 footer 入口 + Dialog（快捷键提示+复制网址） |
| G2 | 优惠码机制 promos.ts | 机制在、字典为空（历史码全部失效已清理）| **明确废弃（2026-08-23 人工确认）**：无数据的空壳功能不迁入新前端；后端无对应接口，无需清理 |
| G3 | view_mode 用户偏好 | card/list 存服务端 | **明确废弃（2026-08-23 人工确认）**：新版列表为移动卡片/桌面表格双形态随视口自适应，不做手动切换偏好 |
| G4 | 全球延迟测速 | IpHome 内嵌增值模块 | 重写（随 F 迁移）|
| G5 | pytest 套件 25 用例 | 库存准确性/认证跳转/UI 结构断言 | 复用扩展 |
