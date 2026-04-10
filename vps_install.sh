#!/bin/bash
# ============================================================
# Agent P2P Portal - VPS 一键安装脚本
# 用法: bash vps_install.sh <DOMAIN> <EMAIL> [REPO_URL]
#
# 输出规范（AI 可 grep）：
#   成功: INSTALL_OK API_KEY=ap2p_xxx PORTAL_URL=https://domain.com
#   失败: INSTALL_FAILED STEP=xxx ERROR=<msg>
#
# 检查点文件: /opt/agent-p2p/.install_state.json
# 支持断点续装：重跑时已完成步骤自动跳过
# ============================================================

set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
REPO_URL="${3:-https://github.com/yananli199307-dev/AgentPortal-p2p-skill.git}"
INSTALL_DIR="/opt/agent-p2p"
STATE_FILE="$INSTALL_DIR/.install_state.json"
VENV="$INSTALL_DIR/venv"
PORT=8080

log_info()  { echo "[INFO] $*"; }
log_warn()  { echo "[WARN] $*"; }
log_error() { echo "[ERROR] $*"; }

# ── 参数校验 ─────────────────────────────────────────────────
if [[ -z "$DOMAIN" || -z "$EMAIL" ]]; then
    echo "用法: bash vps_install.sh <DOMAIN> <EMAIL> [REPO_URL]"
    echo "INSTALL_FAILED STEP=params ERROR=missing_domain_or_email"
    exit 1
fi

# ── 检查点工具 ───────────────────────────────────────────────
checkpoint_done() {
    local step="$1"
    mkdir -p "$INSTALL_DIR"
    local tmp
    if [[ -f "$STATE_FILE" ]]; then
        tmp=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
except:
    d = {}
d['$step'] = 'done'
print(json.dumps(d))
")
    else
        tmp="{\"$step\":\"done\"}"
    fi
    echo "$tmp" > "$STATE_FILE"
    log_info "步骤 $step 完成"
}

checkpoint_skip() {
    local step="$1"
    [[ ! -f "$STATE_FILE" ]] && return 1
    local status
    status=$(python3 -c "
import json
try:
    d = json.load(open('$STATE_FILE'))
    print(d.get('$step',''))
except:
    print('')
" 2>/dev/null || echo "")
    [[ "$status" == "done" ]]
}

fail() {
    local step="$1"
    local error="$2"
    log_error "步骤 $step 失败: $error"
    echo "INSTALL_FAILED STEP=$step ERROR=$error"
    exit 1
}

# ── step_01: 安装系统依赖 ─────────────────────────────────────
step_01_install_deps() {
    checkpoint_skip "step_01" && { log_info "跳过 step_01"; return 0; }
    log_info "=== step_01: 安装系统依赖 ==="
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq || fail "step_01" "apt_update_failed"
    apt-get install -y -qq \
        git curl wget python3 python3-venv python3-pip \
        nginx certbot python3-certbot-nginx \
        sqlite3 ufw apache2-utils \
        || fail "step_01" "apt_install_failed"
    checkpoint_done "step_01"
}

# ── step_02: 克隆/更新仓库 ───────────────────────────────────
step_02_clone_repo() {
    checkpoint_skip "step_02" && { log_info "跳过 step_02"; return 0; }
    log_info "=== step_02: 克隆仓库 ==="
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        log_info "仓库已存在，执行 git pull"
        git -C "$INSTALL_DIR" pull --ff-only || fail "step_02" "git_pull_failed"
    else
        rm -rf "$INSTALL_DIR"
        git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" || fail "step_02" "git_clone_failed"
    fi
    chown -R "$(whoami):$(whoami)" "$INSTALL_DIR"
    checkpoint_done "step_02"
}

# ── step_03: Python venv ──────────────────────────────────────
step_03_python_venv() {
    checkpoint_skip "step_03" && { log_info "跳过 step_03"; return 0; }
    log_info "=== step_03: Python venv + 依赖 ==="
    python3 -m venv "$VENV" || fail "step_03" "venv_create_failed"
    "$VENV/bin/pip" install --upgrade pip -q
    "$VENV/bin/pip" install -q \
        fastapi uvicorn "python-jose[cryptography]" \
        python-multipart websockets pytz requests \
        || fail "step_03" "pip_install_failed"
    checkpoint_done "step_03"
}

# ── step_04: Nginx + SSL ──────────────────────────────────────
step_04_nginx_ssl() {
    checkpoint_skip "step_04" && { log_info "跳过 step_04"; return 0; }
    log_info "=== step_04: 配置 Nginx + 申请 SSL ==="

    ADMIN_PASS=$(openssl rand -base64 9 | tr -d '/+=' | head -c 12)
    htpasswd -cb /etc/nginx/.htpasswd admin "$ADMIN_PASS"
    printf 'ADMIN_USER=admin\nADMIN_PASS=%s\n' "$ADMIN_PASS" > "$INSTALL_DIR/.admin_creds"
    chmod 600 "$INSTALL_DIR/.admin_creds"

    cat > /etc/nginx/sites-available/agent-p2p << NGINXEOF
server {
    listen 80;
    server_name $DOMAIN;

    location = /static/admin.html {
        auth_basic "Agent P2P Admin";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static/ {
        auth_basic "Agent P2P Admin";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINXEOF

    ln -sf /etc/nginx/sites-available/agent-p2p /etc/nginx/sites-enabled/agent-p2p
    rm -f /etc/nginx/sites-enabled/default
    nginx -t || fail "step_04" "nginx_config_invalid"
    systemctl restart nginx || fail "step_04" "nginx_restart_failed"

    certbot --nginx -d "$DOMAIN" \
        --non-interactive --agree-tos -m "$EMAIL" \
        || fail "step_04" "certbot_failed"

    systemctl enable certbot.timer 2>/dev/null || true
    systemctl restart nginx

    checkpoint_done "step_04"
}

# ── step_05: 初始化数据库 + 生成 API Key ──────────────────────
step_05_init_db() {
    checkpoint_skip "step_05" && { log_info "跳过 step_05"; return 0; }
    log_info "=== step_05: 初始化数据库 + 生成 API Key ==="

    mkdir -p "$INSTALL_DIR/data"

    "$VENV/bin/python3" - << PYEOF
import sqlite3, secrets, os

db_path = "$INSTALL_DIR/data/portal.db"
os.makedirs(os.path.dirname(db_path), exist_ok=True)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.executescript("""
CREATE TABLE IF NOT EXISTS api_keys (
    key_id TEXT PRIMARY KEY,
    portal_url TEXT NOT NULL,
    agent_name TEXT,
    user_name TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS guest_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portal_url TEXT NOT NULL UNIQUE,
    DISPLAY_NAME TEXT,
    SHARED_KEY TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT NOT NULL,
    contact_portal TEXT,
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE
);
""")

# 生成或复用 API Key
cur.execute("SELECT key_id FROM api_keys WHERE is_active=1 LIMIT 1")
row = cur.fetchone()
if row:
    api_key = row[0]
    print(f"EXISTING_API_KEY={api_key}")
else:
    api_key = "ap2p_" + secrets.token_urlsafe(32)
    cur.execute(
        "INSERT INTO api_keys (key_id, portal_url, agent_name, user_name, description) VALUES (?,?,?,?,?)",
        (api_key, "https://$DOMAIN", "default_agent", "admin", "Auto-generated by vps_install.sh")
    )
    print(f"NEW_API_KEY={api_key}")

conn.commit()
conn.close()
PYEOF

    # 从 Python 输出中提取 API Key 并保存
    API_KEY_LINE=$("$VENV/bin/python3" - << PYEOF2
import sqlite3
conn = sqlite3.connect("$INSTALL_DIR/data/portal.db")
cur = conn.cursor()
cur.execute("SELECT key_id FROM api_keys WHERE is_active=1 LIMIT 1")
row = cur.fetchone()
print(row[0] if row else "")
conn.close()
PYEOF2
)

    if [[ -z "$API_KEY_LINE" ]]; then
        fail "step_05" "api_key_not_found_in_db"
    fi

    echo "API_KEY=$API_KEY_LINE" > "$INSTALL_DIR/.api_key"
    chmod 600 "$INSTALL_DIR/.api_key"
    log_info "API Key 已保存到 $INSTALL_DIR/.api_key"

    checkpoint_done "step_05"
}

# ── step_06: systemd 服务 ──────────────────────────────────────
step_06_systemd() {
    # 检查点只保护"写 service 文件"这一步。
    # 但每次运行都无条件执行 restart，确保代码更新后新版本生效。
    log_info "=== step_06: 配置并重启 systemd 服务 ==="

    if ! checkpoint_skip "step_06"; then
        # 首次安装：写 service 文件
        cat > /etc/systemd/system/agent-p2p.service << SVCEOF
[Unit]
Description=Agent P2P Portal
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$INSTALL_DIR
Environment=PORTAL_URL=https://$DOMAIN
Environment=DATABASE_PATH=$INSTALL_DIR/data/portal.db
ExecStart=$VENV/bin/uvicorn vps.main:app --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

        systemctl daemon-reload
        systemctl enable agent-p2p
        checkpoint_done "step_06"
        log_info "service 文件已创建并 enable"
    else
        log_info "service 文件已存在（跳过写入），执行 daemon-reload"
        systemctl daemon-reload
    fi

    # 无论是否首次安装，都执行 restart（保证代码更新后新版本生效）
    log_info "重启 agent-p2p 服务..."
    systemctl restart agent-p2p || fail "step_06" "service_start_failed"

    # 等待服务就绪（最多 20 秒）
    for i in $(seq 1 20); do
        sleep 1
        if systemctl is-active --quiet agent-p2p; then
            log_info "服务已启动 (等待 ${i}s)"
            break
        fi
        if [[ $i -eq 20 ]]; then
            journalctl -u agent-p2p -n 30 --no-pager || true
            fail "step_06" "service_not_active_after_20s"
        fi
    done
}

# ── step_07: 验证 ──────────────────────────────────────────────
step_07_verify() {
    checkpoint_skip "step_07" && { log_info "跳过 step_07"; return 0; }
    log_info "=== step_07: 验证部署 ==="

    # 检查本地 HTTP 健康
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$PORT/ 2>/dev/null || echo "000")
    if [[ "$http_code" != "200" ]]; then
        fail "step_07" "local_http_not_200_got_$http_code"
    fi
    log_info "本地服务健康 (HTTP $http_code)"

    # 检查 HTTPS（允许证书不可信，仅验证端口通）
    local https_code
    https_code=$(curl -sk -o /dev/null -w "%{http_code}" "https://localhost/" 2>/dev/null || echo "000")
    log_info "HTTPS 状态码: $https_code"

    checkpoint_done "step_07"
}

# ── 主流程 ──────────────────────────────────────────────────────
main() {
    log_info "============================================"
    log_info "Agent P2P Portal 安装开始"
    log_info "DOMAIN=$DOMAIN  EMAIL=$EMAIL"
    log_info "INSTALL_DIR=$INSTALL_DIR"
    log_info "============================================"

    step_01_install_deps
    step_02_clone_repo
    step_03_python_venv
    step_04_nginx_ssl
    step_05_init_db
    step_06_systemd
    step_07_verify

    # 读取 API Key
    if [[ ! -f "$INSTALL_DIR/.api_key" ]]; then
        fail "final" "api_key_file_missing"
    fi
    local api_key
    api_key=$(grep "^API_KEY=" "$INSTALL_DIR/.api_key" | cut -d= -f2)
    if [[ -z "$api_key" ]]; then
        fail "final" "api_key_empty"
    fi

    # 读取管理后台密码
    local admin_pass
    admin_pass=$(grep "^ADMIN_PASS=" "$INSTALL_DIR/.admin_creds" 2>/dev/null | cut -d= -f2 || echo "unknown")

    log_info "============================================"
    log_info "安装完成!"
    log_info "Portal URL : https://$DOMAIN"
    log_info "Admin URL  : https://$DOMAIN/static/admin.html"
    log_info "Admin Pass : admin / $admin_pass"
    log_info "============================================"

    # 标准化输出（AI grep 用）
    echo "INSTALL_OK API_KEY=$api_key PORTAL_URL=https://$DOMAIN ADMIN_PASS=$admin_pass"
}

main "$@"
