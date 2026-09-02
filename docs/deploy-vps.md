# GoVPS 硅谷 VPS 自动化部署与运维指南

本指南指导如何将 GoVPS 全栈服务（FastAPI 后端 + Next.js 前端 + Caddy 网关 + SQLite WAL 数据库）部署到硅谷独立 VPS，并开启 **GitHub Actions 提交代码自动发布（CI/CD）**。

---

## 架构拓扑

```
[ 访客浏览器 / 手机端 ]
           │
           ▼ (HTTPS / HTTP3)
┌─────────────────────────────────────────────────────────┐
│ Cloudflare 边缘节点 (DNS 灰云或黄云 CDN + WAF 防护)     │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│ 硅谷 VPS (独立公网 IP / 离上游机房近 / 零休眠)          │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Caddy 反代网关 (端口 80 / 443，自动化 HTTPS)       │  │
│  └─────────────────────────┬─────────────────────────┘  │
│                            │ 内部转发                   │
│                            ▼                            │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Next.js 前端容器 (端口 3000，SSR 渲染)            │  │
│  └─────────────────────────┬─────────────────────────┘  │
│                            │ /api/* 内部直连            │
│                            ▼                            │
│  ┌───────────────────────────────────────────────────┐  │
│  │ FastAPI 后端容器 (端口 8000，0 延迟内网通信)      │  │
│  └─────────────────────────┬─────────────────────────┘  │
│                            │ 毫秒级文件读写             │
│                            ▼                            │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 挂载目录: ./data/govps.db (SQLite WAL 极速高并发)  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 第一步：VPS 基础环境准备（仅需 1 分钟）

在全新的硅谷 VPS 上执行以下命令安装 Docker 与 Docker Compose：

```bash
# 1. 更新系统并一键安装 Docker
curl -fsSL https://get.docker.com | sh

# 2. 创建部署工作目录
sudo mkdir -p /opt/govps/data
sudo chown -R $USER:$USER /opt/govps
```

---

## 第二步：配置 GitHub Secrets（开启提交自动发布）

在 GitHub 仓库页面进入 **Settings -> Secrets and variables -> Actions**，点击 **New repository secret** 添加以下密钥：

| Secret 名称 | 说明 | 示例值 |
| :--- | :--- | :--- |
| **`VPS_HOST`** | VPS 的公网 IP 地址 | `192.0.2.1` |
| **`VPS_USERNAME`** | VPS 的 SSH 登录用户名 | `root` 或 `ubuntu` |
| **`VPS_SSH_KEY`** | 本地或 CI 连接 VPS 的 **SSH 私钥** | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| **`VPS_PORT`** | SSH 端口（可选，默认 22） | `22` |
| **`VPS_DEPLOY_PATH`**| 部署目录（可选，默认 `/opt/govps`） | `/opt/govps` |

> 💡 **如何生成专属部署密钥（如果还没有）：**
> ```bash
> # 在本地生成一对不带密码的专用密钥
> ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/govps_deploy
> 
> # 将公钥 (~/.ssh/govps_deploy.pub) 内容追加到 VPS 的 ~/.ssh/authorized_keys 中
> # 将私钥 (~/.ssh/govps_deploy) 全部内容填入 GitHub Secrets 的 VPS_SSH_KEY
> ```

---

## 第三步：首次部署与环境变量配置

你可以直接 `git push` 触发 GitHub Actions 自动首次发布，也可以在 VPS 上手动初始化一次：

```bash
cd /opt/govps

# 1. 拉取代码
git clone https://github.com/lxk955/govps.git .

# 2. 配置生产环境变量
cp .env.example .env
nano .env
```

在 `.env` 中按需修改：
```ini
SITE_DOMAIN=govps.xyz           # 你的域名
SITE_URL=https://govps.xyz       # 站点完整 URL
TASK_TOKEN=生成一个随机安全密钥     # 定时任务鉴权
RESEND_API_KEY=re_xxxx          # Resend 邮件发送 API Key（若未配置登录显示临时调试码）
```

启动容器：
```bash
docker compose up -d --build
```

---

## 第四步：域名与 Cloudflare 解析

1. 打开 Cloudflare 控制台，添加一条 **A 记录**：
   - **名称**：`@`（或 `vps`）
   - **内容**：你的 VPS 公网 IP
   - **代理状态**：点亮（Proxied 灰云或黄云均可）
2. 在 Cloudflare 的 **SSL/TLS** 设置中：
   - 加密模式建议选择 **Full**（或 Full Strict）。Caddy 会全自动为你申请 Let's Encrypt 证书并完成 HTTPS 终结。

---

## 第五步：定时任务配置（商家抓取与汇率同步）

在硅谷 VPS 上配置系统 crontab，全自动触发后台定时任务（无需依赖外部第三方）：

```bash
crontab -e
```
追加以下两行（将其中的 `YOUR_TASK_TOKEN` 替换为你的 `.env` 中的 `TASK_TOKEN`）：

```bash
# 每 5 分钟抓取各商家最新库存与价格（本地内网调用，0 外部网络开销）
*/5 * * * * curl -s -X POST http://127.0.0.1:8000/api/tasks/scan -H "X-Task-Token: YOUR_TASK_TOKEN" > /dev/null

# 每天中午 12:00 (UTC 04:00) 自动同步多币种汇率
0 12 * * * curl -s -X POST http://127.0.0.1:8000/api/tasks/update-rates -H "X-Task-Token: YOUR_TASK_TOKEN" > /dev/null
```

---

## 常用运维命令

```bash
# 查看容器运行状态
docker compose ps

# 查看实时日志
docker compose logs -f api     # 后端日志
docker compose logs -f web     # 前端日志
docker compose logs -f caddy   # 网关日志

# 重启全部服务
docker compose restart

# 备份数据库（直接备份单个 SQLite 文件即可）
cp /opt/govps/data/govps.db /backup/govps_$(date +%F).db
```
