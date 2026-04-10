#!/bin/bash
# ============================================================
# Agent P2P - 本地 Bridge 一键安装脚本
# 用法: bash local_install.sh <API_KEY> <PORTAL_URL>
#
# 输出规范（AI 可 grep）：
#   成功: LOCAL_OK BRIDGE_PID=<pid>
#   失败: LOCAL_FAILED STEP=xxx ERROR=<msg>
# ============================================================

set -euo pipefail

API_KEY="${1:-}"
PORTAL_URL="${2:-}"

log_info()  { echo "[INFO] $*"; }
log_error() { echo "[ERROR] $*"; }

fail() {
    local step="$1"; local error="$2"
    log_error "步骤 $step 失败: $error"
    echo "LOCAL_FAILED STEP=$step ERROR=$error"
    exit 1
}

# ── 参数校验 ─────────────────────────────────────────────────
if [[ -z "$API_KEY" || -z "$PORTAL_URL" ]]; then
    echo "用法: bash local_install.sh <API_KEY> <PORTAL_URL>"
    echo "LOCAL_FAILED STEP=params ERROR=missing_api_key_or_portal_url"
    exit 1
fi

# 脚本所在目录（即 skill 根目录）
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SKILL_DIR/venv"
ENV_FILE="$HOME/.openclaw/gateway.env"
OPENCLAW_CONFIG="$HOME/.openclaw/openclaw.json"
BRIDGE_PID_FILE="$SKILL_DIR/bridge.pid"
BRIDGE_LOG="$SKILL_DIR/bridge.log"

log_info "Skill 目录: $SKILL_DIR"

# ── step_01: 创建 Python venv ──────────────────────────────
step_01_venv() {
    log_info "=== step_01: 创建 Python venv ==="
    if [[ ! -d "$VENV" ]]; then
        python3 -m venv "$VENV" || fail "step_01" "venv_create_failed"
        log_info "venv 已创建"
    else
        log_info "venv 已存在，跳过创建"
    fi
}

# ── step_02: 安装 Python 依赖 ─────────────────────────────
step_02_pip() {
    log_info "=== step_02: 安装依赖 ==="
    "$VENV/bin/pip" install --upgrade pip -q
    "$VENV/bin/pip" install -q websockets requests \
        || fail "step_02" "pip_install_failed"
    log_info "依赖安装完成"
}

# ── step_03: 读取 hooks token ─────────────────────────────
step_03_read_hooks_token() {
    log_info "=== step_03: 读取 hooks token ==="
    HOOKS_TOKEN=""

    # 优先从 openclaw.json 读取
    if [[ -f "$OPENCLAW_CONFIG" ]] && command -v python3 &>/dev/null; then
        HOOKS_TOKEN=$(python3 -c "
import json, sys
try:
    d = json.load(open('$OPENCLAW_CONFIG'))
    print(d.get('hooks', {}).get('token', ''))
except:
    print('')
" 2>/dev/null || echo "")
    fi

    # 其次从 gateway.env 读取
    if [[ -z "$HOOKS_TOKEN" && -f "$ENV_FILE" ]]; then
        HOOKS_TOKEN=$(grep "^OPENCLAW_HOOKS_TOKEN=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "")
    fi

    # 如果都没有，生成一个新 token
    if [[ -z "$HOOKS_TOKEN" ]]; then
        HOOKS_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        log_info "已生成新 hooks token"

        # 写入 openclaw.json
        if [[ -f "$OPENCLAW_CONFIG" ]]; then
            python3 - << PYEOF
import json
path = "$OPENCLAW_CONFIG"
try:
    d = json.load(open(path))
except:
    d = {}
if 'hooks' not in d:
    d['hooks'] = {}
if not d['hooks'].get('token'):
    d['hooks']['token'] = "$HOOKS_TOKEN"
    d['hooks']['enabled'] = True
    d['hooks']['path'] = '/hooks'
    open(path, 'w').write(json.dumps(d, indent=2))
    print("已写入 openclaw.json")
PYEOF
        fi
    fi

    log_info "hooks token 已就绪"
    export HOOKS_TOKEN
}

# ── step_04: 写入 gateway.env ─────────────────────────────
step_04_write_env() {
    log_info "=== step_04: 写入 gateway.env ==="
    mkdir -p "$(dirname "$ENV_FILE")"

    # 读取当前 gateway URL（默认 openclaw 的端口）
    GATEWAY_URL="http://127.0.0.1:18789"
    if [[ -f "$ENV_FILE" ]]; then
        existing=$(grep "^OPENCLAW_GATEWAY_URL=" "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "")
        [[ -n "$existing" ]] && GATEWAY_URL="$existing"
    fi

    # 生成 env 文件（统一字段名 AGENTP2P_API_KEY）
    cat > "$ENV_FILE" << ENVEOF
# Agent P2P 配置 - 由 local_install.sh 自动生成
AGENTP2P_API_KEY=$API_KEY
AGENTP2P_HUB_URL=$PORTAL_URL
OPENCLAW_GATEWAY_URL=$GATEWAY_URL
OPENCLAW_HOOKS_TOKEN=$HOOKS_TOKEN
ENVEOF

    log_info "gateway.env 已写入: $ENV_FILE"
}

# ── step_05: 停止旧 bridge 进程 ───────────────────────────
step_05_stop_old_bridge() {
    log_info "=== step_05: 停止旧 bridge 进程（如有）==="
    if [[ -f "$BRIDGE_PID_FILE" ]]; then
        OLD_PID=$(cat "$BRIDGE_PID_FILE")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            kill "$OLD_PID" && log_info "已停止旧 bridge (PID=$OLD_PID)"
            sleep 2
        fi
        rm -f "$BRIDGE_PID_FILE"
    fi
}

# ── step_06: 启动 bridge ──────────────────────────────────
step_06_start_bridge() {
    log_info "=== step_06: 启动 bridge ==="
    BRIDGE_SCRIPT="$SKILL_DIR/local/bridge.py"
    if [[ ! -f "$BRIDGE_SCRIPT" ]]; then
        fail "step_06" "bridge_script_not_found:$BRIDGE_SCRIPT"
    fi

    # 加载 env 并后台启动
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a

    nohup "$VENV/bin/python3" "$BRIDGE_SCRIPT" > "$BRIDGE_LOG" 2>&1 &
    BRIDGE_PID=$!
    echo "$BRIDGE_PID" > "$BRIDGE_PID_FILE"
    log_info "bridge 已启动 PID=$BRIDGE_PID"
}

# ── step_07: 验证 ─────────────────────────────────────────
step_07_verify() {
    log_info "=== step_07: 验证 bridge ==="
    sleep 3

    BRIDGE_PID=$(cat "$BRIDGE_PID_FILE" 2>/dev/null || echo "")
    if [[ -z "$BRIDGE_PID" ]] || ! ps -p "$BRIDGE_PID" > /dev/null 2>&1; then
        log_error "bridge 进程未运行，最近日志:"
        tail -20 "$BRIDGE_LOG" 2>/dev/null || true
        fail "step_07" "bridge_not_running"
    fi

    log_info "bridge 运行正常 (PID=$BRIDGE_PID)"

    # 检查 skill_status.json
    STATUS_FILE="$SKILL_DIR/skill_status.json"
    if [[ -f "$STATUS_FILE" ]]; then
        log_info "skill_status: $(cat "$STATUS_FILE")"
    fi

    echo "LOCAL_OK BRIDGE_PID=$BRIDGE_PID"
}

# ── 主流程 ────────────────────────────────────────────────
main() {
    log_info "=== Agent P2P 本地 Bridge 安装 ==="
    log_info "API_KEY  : ${API_KEY:0:20}..."
    log_info "Portal   : $PORTAL_URL"

    step_01_venv
    step_02_pip
    step_03_read_hooks_token
    step_04_write_env
    step_05_stop_old_bridge
    step_06_start_bridge
    step_07_verify
}

main "$@"
