# GoVPS 待办事项与路线图 (Roadmap & TODO)

## 监控探针 (Monitor Agent)

### [ ] 极致内存优化：增加 Go 语言版本 Agent

- **背景与痛点**：
  当前 Python 3 探针已实现纯标准库零第三方依赖，运行时稳定轻量。但在极端小内存环境（如 64MB / 128MB / 256MB 的超微型 NAT VPS、嵌入式容器设备），Python 解释器本身的运行时基础常驻内存 (RSS) 仍约需 10MB ~ 18MB。
- **优化目标**：
  - 开发基于 Go 语言的原生静态编译 Agent（零 CGO、静态链接无 libc 依赖）。
  - 将常驻内存占用极致压缩至 **2MB ~ 4MB** 以内，CPU 占用低于 0.1%。
- **核心实现要点**：
  1. **跨架构静态二进制构建**：
     - 利用 GitHub Actions 自动交叉编译生成各架构二进制（`linux/amd64`, `linux/arm64`, `linux/arm/v7`, `linux/386`, `linux/s390x` 等），压缩为精简 release。
  2. **协议与功能 100% 对齐**：
     - 采集逻辑：直接解析 `/proc/stat`、`/proc/meminfo`、`/proc/net/dev`、`/proc/uptime`、`/etc/os-release`，免除外部命令调用开销。
     - 三网 ICMP 探测：基于 Go 原生 raw ICMP socket 或优化的 ping 探测包，支持滑动窗口丢包率与延迟加权平均算法。
     - 完全兼容现有 `/api/monitor/report` 上报协议与数据字段结构。
  3. **平滑安装与自更新**：
     - 安装脚本 `agent.sh` 智能检测系统架构与可用资源；在缺少 Python 3 或资源极度受限的环境优先下载安装 Go 二进制。
     - 保持二进制自检测升级能力，零停机热切换。
