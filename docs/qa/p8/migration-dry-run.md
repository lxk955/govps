# P8 真实生产库副本迁移演练报告（migration-dry-run.md）

> 本文件记录使用**真实旧版生产数据库物理副本**（`vps-scout/api/vps_scout.db`，412 KB）执行 Alembic 自动探测、增量升降级与数据完整性校验的完整演练过程。

---

## 1. 真实生产库源数据基线

- **源文件**: `/home/kk/workspace/vps-scout/api/vps_scout.db` (412 KB)
- **迁移前结构与数据量（10 张业务表，无 alembic_version）**:
  | 表名 | 迁移前数据行数 | 关键特征 |
  |---|---|---|
  | `merchants` | **7 行** | 7 家云服务商（Bandwagon / DMIT / V.PS 等） |
  | `products` | **344 行** | 344 款套餐，含 JSON price_options 与规格参数 |
  | `price_snapshots`| **352 行** | 历史价格波动记录 |
  | `stock_snapshots`| **577 行** | 历史库存状态变迁时序 |
  | `users` | **1 行** | 历史登录用户 |
  | `watchlist` | **0 行** | 关注列表（表名确认为单数 `watchlist`） |
  | `aff_clicks` | **38 行** | 真实推广点击埋点 |
  | `email_codes` | **0 行** | 临时验证码 |
  | `notify_events` | **0 行** | 通知事件 |
  | `notify_logs` | **0 行** | 发信日志 |

---

## 2. 演练执行过程与验证

### 步骤 1：哨兵链探测旧库形态
- **执行**: `detect_current_revision(inspect(engine))`
- **结果**: 准确识别为 `0001_legacy_baseline`（通过 `view_mode`、`price_options`、`last_checked_at` 等手写 ALTER 哨兵列判定），未发生误判。

### 步骤 2：自动 Stamp 与增量升至 Head (0005)
- **执行**: `run_migrations(url="sqlite:////tmp/real_prod_dry_run.db")`
- **执行过程**:
  ```text
  Running stamp_revision -> 0001_legacy_baseline
  Running upgrade 0001_legacy_baseline -> 0002_p1_materialized_columns (物化列与索引)
  Running upgrade 0002_p1_materialized_columns -> 0003_p5_exchange_rates (汇率表与快照表)
  Running upgrade 0003_p5_exchange_rates -> 0004_p7_scheduling_notify (分级调度与发信重试列)
  Running upgrade 0004_p7_scheduling_notify -> 0005_request_rate_events (IP 限流滑动窗口表)
  ```
- **Alembic 最终版本**: `0005_request_rate_events`。

### 步骤 3：数据完整性 100% 校验
- **迁移后数据行数核验**:
  ```text
  merchants:       7 -> 7   (0 diff, 100% 保持)
  products:      344 -> 344 (0 diff, 100% 保持)
  price_snapshots: 352 -> 352 (0 diff, 100% 保持)
  stock_snapshots: 577 -> 577 (0 diff, 100% 保持)
  users:           1 -> 1   (0 diff, 100% 保持)
  watchlist:       0 -> 0   (0 diff, 100% 保持)
  aff_clicks:     38 -> 38  (0 diff, 100% 保持)
  ```
- **结论**: 存量数据 **零丢失、零截断、零外键破坏**。

### 步骤 4：存量数据物化列刷新（`refresh_derived_fields`）
- 扫描 344 款存量产品，全部成功计算 `spec_key`、`search_text`、`hot_score` 等衍生字段；
- 抽样验证：`20G KVM - PROMO` -> `spec_key=["2","20g kvm - pro",...]`, `hot_score=71.0`，物化索引直查正常。

---

## 3. 回滚能力验证

- 在真实库副本上执行 `downgrade` 至 `0001_legacy_baseline`，新增表及列干净卸载，存量 344 款产品及基础数据继续完整可用。
