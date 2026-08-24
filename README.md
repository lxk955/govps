# GoVPS

VPS 雷达的重构版：多商家 VPS 套餐聚合、库存与降价监控。以 **Next.js App Router 前端全新构建 + FastAPI 后端整体复用** 为架构（详见 `docs/refactor-plan.md`，功能基准见 `docs/feature-inventory.md`）。工程规范遵循根目录 `AGENTS.md`。

## 结构

```
src/          Next.js App Router（页面/UI/RSC）
api/          FastAPI 后端（自旧项目平移：routers/services/crawler/tests）
docs/         重构方案与阶段文档
```

## 本地开发

```bash
# 前端
npm install
npm run dev            # http://localhost:3000，/api/* 与 /go/* 经 rewrite 转发

# 后端（另开终端；SKIP_STARTUP_SCAN 避免启动即全量抓取）
cd api && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env   # 按需修改
SKIP_STARTUP_SCAN=true uvicorn app.main:app --port 8000
```

环境变量 `API_ORIGIN` 控制 rewrite 目标（默认 `http://localhost:8000`），未来 API 独立域名时仅改此值。

## 检查命令

```bash
npm run lint        # ESLint
npm run typecheck   # tsc --noEmit
npm run build       # 生产构建
cd api && python -m pytest tests/ -q   # 后端测试（禁网 fixtures 回放）
```

CI（GitHub Actions）在每次 push/PR 时运行以上全部检查。

## 数据库迁移（Alembic）

后端启动时自动执行「检测落点 → stamp → upgrade head」（`api/app/db_migrations.py`），
存量旧库无需手工干预。手工操作：

```bash
cd api && alembic upgrade head        # 手动升级到最新
alembic revision --autogenerate -m "..."   # 生成增量迁移（模型变更后）
ALEMBIC_DATABASE_URL=... alembic upgrade head   # 对隔离库演练迁移
```
