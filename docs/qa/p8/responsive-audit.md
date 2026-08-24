# P8 六视口 Headless 真实截图走查与可访问性审查报告（responsive-audit.md）

> 依据根目录 `AGENTS.md` 响应式与可访问性规范，通过 Headless Chromium（`scripts/capture_screenshots.mjs`）在真实渲染环境下对全站 8 个核心路由模板、在 6 大基准视口下执行全量渲染、截图归档与物理宽度防溢出测量。
> 视口基准：**375px（iPhone SE）/ 390px（iPhone 12/13/14）/ 430px（iPhone 14/15 Pro Max）/ 768px（iPad 竖屏）/ 1024px（小桌面/横屏）/ 1440px（宽屏桌面）**

---

## 1. 真实视口截图与物理防溢出测量矩阵（8 路由 × 6 视口 = 48 组组合）

| 页面 / 路由 | 375px (Mobile) | 390px (Mobile) | 430px (Mobile) | 768px (Tablet) | 1024px (Desktop) | 1440px (Wide) | 溢出检测 | 截图存档 |
|---|---|---|---|---|---|---|---|---|
| **首页 `/`** | 375/375px | 390/390px | 430/430px | 768/768px | 1024/1024px | 1440/1440px | **0 溢出** | `home_{w}px.png` (6张) |
| **VPS 列表 `/vps`** | 375/375px | 390/390px | 430/430px | 768/768px | 1024/1024px | 1440/1440px | **0 溢出** (已修复 1024px 溢出) | `vps-list_{w}px.png` (6张) |
| **套餐详情 `/vps/[slug]`** | 375/375px | 390/390px | 430/430px | 768/768px | 1024/1024px | 1440/1440px | **0 溢出** | `vps-detail_{w}px.png` (6张) |
| **套餐对比 `/compare`** | 375/375px | 390/390px | 430/430px | 768/768px | 1024/1024px | 1440/1440px | **0 溢出** (横向滚动 + sticky 首列) | `compare_{w}px.png` (6张) |
| **优惠动态 `/deals`** | 375/375px | 390/390px | 430/430px | 768/768px | 1024/1024px | 1440/1440px | **0 溢出** | `deals_{w}px.png` (6张) |
| **服务商 `/providers`** | 375/375px | 390/390px | 430/430px | 768/768px | 1024/1024px | 1440/1440px | **0 溢出** | `providers_{w}px.png` (6张) |
| **账户登录 `/login`** | 375/375px | 390/390px | 430/430px | 768/768px | 1024/1024px | 1440/1440px | **0 溢出** | `login_{w}px.png` (6张) |
| **IP 检测 `/ip`** | 375/375px | 390/390px | 430/430px | 768/768px | 1024/1024px | 1440/1440px | **0 溢出** | `ip_{w}px.png` (6张) |

> 截图产物已完整归档在 `docs/qa/p8/screenshots/` 目录下（共 48 张高清全页面截图与 `audit-results.json` 测量快照）。

---

## 2. 真实走查抓到的问题与修复记录

### 缺陷发现：`/vps` 列表页在 1024px 视口下产生 44px 横向溢出（1068px > 1024px）
- **现象**：在 1024px 断点（`lg`），侧边筛选栏（`w-64 shrink-0`）展开，右侧表格因列内容固定宽度（产品名 `max-w-[26rem]` 与价格 `whitespace-nowrap`）导致表格固有宽度达到 1066px，超出父容器可用宽度（704px），导致整页横向被撑开至 1068px。
- **修复**：
  1. 在 `src/app/vps/page.tsx` 中为桌面表格外层包裹 `<div className="hidden lg:block overflow-x-auto rounded-xl border">`，落实 AGENTS.md 大表格条款；
  2. 在 `src/components/vps/VpsRow.tsx` 中将产品名最大宽度调整为响应式 `max-w-[16rem] xl:max-w-[24rem]`；
- **复测验证**：重新执行 `scripts/capture_screenshots.mjs`，1024px 下 `scrollWidth=1024px / clientWidth=1024px`，**溢出清零，48 组组合 100% 达标**。

---

## 3. 可访问性（a11y）与交互规范核查

- [x] **移动端表单字号**：所有 `<input>` 使用 `text-base`（16px），避免 iOS Safari 聚焦时页面放大；
- [x] **视口高度**：全屏高度容器使用 `min-h-dvh` / `h-dvh`；
- [x] **防溢出约束**：所有 Flex / Grid 子容器显式设置 `min-w-0`，长字符串设置 `break-words`；
- [x] **大表格交互**：`/compare` 对比页在移动端支持平滑横向滚动，首列参数名 `sticky left-0` 冻结；
- [x] **无障碍与焦点**：所有纯图标按钮具备 `aria-label`，焦点态保持 `focus-visible:ring-2`；
- [x] **多通道反馈**：库存状态采用「色彩 + 圆点/图标 + 文字」三通道，图表配备数据表兜底。
