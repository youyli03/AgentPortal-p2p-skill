#!/bin/bash
# ============================================================
# Agent P2P Portal - VPS 全量清理脚本
# 用法: bash vps_uninstall.sh [--keep-cert]
# 幂等：即使组件不存在也不报错
# ============================================================

set -uo pipefail

KEEP_CERT=0
[[ "${1:-}" == "--keep-cert" ]] && KEEP_CERT=1

INSTALL_DIR="/opt/agent-p2p"
SERVICE_NAME="agent-p2p"

log_info()  { echo "[INFO] $*"; }
log_warn()  { echo "[WARN] $*"; }

log_info "=== Agent P2P VPS 卸载开始 ==="

# 1. 停止并删除 systemd 服务
log_info "停止 systemd 服务..."
systemctl stop "$SERVICE_NAME" 2>/dev/null || true
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload 2>/dev/null || true
log_info "systemd 服务已清理"

# 2. 删除 Nginx 配置
log_info "清理 Nginx 配置..."
rm -f /etc/nginx/sites-enabled/agent-p2p
rm -f /etc/nginx/sites-available/agent-p2p
rm -f /etc/nginx/.htpasswd
# 恢复 default 站点（如果没有其他站点）
if [[ -z "$(ls /etc/nginx/sites-enabled/ 2>/dev/null)" ]]; then
    ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default 2>/dev/null || true
fi
nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true
log_info "Nginx 配置已清理"

# 3. 删除安装目录
log_info "删除安装目录 $INSTALL_DIR..."
rm -rf "$INSTALL_DIR"
log_info "安装目录已删除"

# 4. 可选：删除 certbot 证书
if [[ $KEEP_CERT -eq 0 ]]; then
    log_info "清理 certbot 证书..."
    # 读取域名（从 Nginx 配置备份中无法读取，跳过 certbot delete，只警告）
    log_warn "如需删除 SSL 证书，请手动运行: certbot delete --cert-name <DOMAIN>"
else
    log_info "保留 SSL 证书（--keep-cert）"
fi

log_info "=== 卸载完成 ==="
echo "UNINSTALL_OK"
