#!/bin/bash
# ============================================================
# Agent P2P - 本地 Bridge 全量清理脚本
# 用法: bash local_uninstall.sh
# 幂等：即使组件不存在也不报错
# ============================================================

set -uo pipefail

log_info() { echo "[INFO] $*"; }

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_PID_FILE="$SKILL_DIR/bridge.pid"
ENV_FILE="$HOME/.openclaw/gateway.env"
STATUS_FILE="$SKILL_DIR/skill_status.json"

log_info "=== Agent P2P 本地 Bridge 卸载开始 ==="

# 1. 停止 bridge 进程
log_info "停止 bridge 进程..."
if [[ -f "$BRIDGE_PID_FILE" ]]; then
    PID=$(cat "$BRIDGE_PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        kill "$PID" && log_info "已停止 bridge (PID=$PID)"
    else
        log_info "bridge 进程已不存在 (PID=$PID)"
    fi
    rm -f "$BRIDGE_PID_FILE"
else
    # 尝试按进程名查找
    pkill -f "local/bridge.py" 2>/dev/null && log_info "已停止 bridge 进程" || log_info "未找到 bridge 进程"
fi

# 2. 删除 venv
log_info "删除 venv..."
rm -rf "$SKILL_DIR/venv"

# 3. 清理日志和状态文件
log_info "清理日志和状态文件..."
rm -f "$SKILL_DIR/bridge.log" "$SKILL_DIR/bridge.log."* "$STATUS_FILE"

# 4. 清理 gateway.env（保留文件但清空 agent-p2p 相关字段）
if [[ -f "$ENV_FILE" ]]; then
    log_info "清理 gateway.env 中的 agent-p2p 字段..."
    python3 - << PYEOF 2>/dev/null || true
lines = open("$ENV_FILE").readlines()
filtered = [l for l in lines if not any(
    l.startswith(k) for k in [
        "AGENTP2P_API_KEY=", "AGENTP2P_HUB_URL=",
        "OPENCLAW_HOOKS_TOKEN=", "OPENCLAW_GATEWAY_URL=",
        "# Agent P2P"
    ]
)]
open("$ENV_FILE", "w").writelines(filtered)
print("gateway.env 已清理")
PYEOF
fi

log_info "=== 卸载完成 ==="
echo "UNINSTALL_OK"
