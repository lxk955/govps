#!/usr/bin/env bash
# ==============================================================================
# GoVPS - Cloudflare WARP 免费出口代理一键配置工具
# 功能：配置本地 SOCKS5 代理 (127.0.0.1:40000)，实现 Cloudflare 官方原生出口 IP，
#       有效穿透受 Cloudflare 盾保护的商家（如 VMISS/DMIT 等）。
# ==============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

PORT=40000

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}    🚀 GoVPS Cloudflare WARP 出口代理安装与配置向导        ${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# 检查 Docker 是否可用
has_docker=false
if command -v docker &> /dev/null && docker compose version &> /dev/null; then
    has_docker=true
fi

echo -e "请选择 WARP 部署模式："
echo -e "  ${GREEN}1)${NC} Docker 模式 (推荐：隔离安全，一键启停，开箱即用)"
echo -e "  ${GREEN}2)${NC} 主机原生安装 (Ubuntu/Debian 官方 cloudflare-warp)"
echo -e "  ${GREEN}3)${NC} 仅测试现有 WARP 代理 (socks5://127.0.0.1:${PORT})"
echo ""
read -p "请输入选项 [1-3] (默认 1): " choice
choice=${choice:-1}

case "$choice" in
    1)
        echo -e "\n${YELLOW}[*] 正在通过 Docker 启动 Cloudflare WARP 容器...${NC}"
        if [ "$has_docker" = false ]; then
            echo -e "${RED}[!] 未检测到 docker compose，请先安装 Docker 或选择选项 2。${NC}"
            exit 1
        fi
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
        docker compose -f "$PROJECT_ROOT/docker-compose.warp.yml" up -d
        echo -e "${GREEN}[✓] Docker WARP 容器启动成功！监听端口: 127.0.0.1:${PORT}${NC}"
        ;;
    2)
        echo -e "\n${YELLOW}[*] 正在安装 Cloudflare 官方 Linux 客户端 (cloudflare-warp)...${NC}"
        if ! command -v apt-get &> /dev/null; then
            echo -e "${RED}[!] 当前系统非 Debian/Ubuntu，请使用 Docker 模式。${NC}"
            exit 1
        fi
        
        # 添加官方源
        echo -e "${YELLOW}[*] 导入 Cloudflare 官方 GPG 密钥与源...${NC}"
        curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
        echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflare-warp.list
        
        sudo apt-get update
        sudo apt-get install -y cloudflare-warp
        
        # 配置为纯 SOCKS5 代理模式（重要：绝不接管系统全局流量或 SSH）
        echo -e "${YELLOW}[*] 配置 WARP 为纯 SOCKS5 代理模式 (端口 ${PORT})...${NC}"
        warp-cli --accept-tos registration new 2>/dev/null || warp-cli --accept-tos register 2>/dev/null || true
        warp-cli --accept-tos mode proxy 2>/dev/null || warp-cli --accept-tos set-mode proxy 2>/dev/null || true
        warp-cli --accept-tos proxy port "$PORT" 2>/dev/null || warp-cli --accept-tos set-proxy-port "$PORT" 2>/dev/null || true
        warp-cli --accept-tos connect
        
        echo -e "${GREEN}[✓] cloudflare-warp 服务已启动并在本地 127.0.0.1:${PORT} 提供 SOCKS5 代理！${NC}"
        ;;
    3)
        echo -e "\n${YELLOW}[*] 跳过安装，直接进行连通性诊断...${NC}"
        ;;
    *)
        echo -e "${RED}[!] 无效选项${NC}"
        exit 1
        ;;
esac

echo -e "\n${YELLOW}[*] 正在验证 WARP 出口连通性...${NC}"
sleep 2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/check_warp.py" "socks5://127.0.0.1:${PORT}"

echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}                 🎉 配置生效指南                           ${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "请在项目 api/.env 中添加如下环境变量："
echo -e "  ${YELLOW}WARP_PROXY=socks5://127.0.0.1:${PORT}${NC}"
echo -e "  ${YELLOW}WARP_ENABLED_MERCHANTS=vmiss${NC}  # 需走 WARP 的商家 (如 vmiss，或填 all 全量走)"
echo -e "然后重启后端服务即可自动按需分流！"
echo -e "${GREEN}============================================================${NC}"
