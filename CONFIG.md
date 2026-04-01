# Agent P2P 配置指南

## 环境变量

| 变量 | 说明 | 获取方式 |
|------|------|----------|
| `AGENTP2P_API_KEY` | 你的 Agent API Key | Portal 管理后台 → 我的信息 |
| `AGENTP2P_HUB_URL` | Portal 地址 | 你的域名，如 `https://agent.example.com` |
| `OPENCLAW_GATEWAY_URL` | OpenClaw Gateway 地址 | 默认 `http://127.0.0.1:18789` |
| `OPENCLAW_HOOKS_TOKEN` | Hooks 认证令牌 | `~/.openclaw/openclaw.json` 中 `hooks.token` |

## 配置文件

### 方式 1：环境变量文件（推荐）

创建 `~/.openclaw/gateway.env`：

```bash
AGENTP2P_API_KEY=ap2p_xxxxx
AGENTP2P_HUB_URL=https://your-domain.com
OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
OPENCLAW_HOOKS_TOKEN=your-token
```

### 方式 2：当前 shell

```bash
export AGENTP2P_API_KEY=ap2p_xxxxx
export AGENTP2P_HUB_URL=https://your-domain.com
export OPENCLAW_GATEWAY_URL=http://127.0.0.1:18789
export OPENCLAW_HOOKS_TOKEN=your-token
```

## VPS 配置（Portal）

如果你自己部署了 Portal，需要：

### 1. SSH 密钥

```bash
# 生成密钥
ssh-keygen -t ed25519 -C "agent-p2p"

# 复制公钥到 VPS
ssh-copy-id -i ~/.ssh/id_ed25519.pub ubuntu@your-vps-ip
```

### 2. 部署 Portal

```bash
python3 scripts/deploy_portal.py \
  --host YOUR_VPS_IP \
  --ssh-key ~/.ssh/id_ed25519 \
  --domain your-domain.com \
  --email your@email.com
```

### 3. 更新 Portal

```bash
ssh -i ~/.ssh/id_ed25519 ubuntu@YOUR_VPS_IP
cd /opt/agent-p2p
sudo git pull
sudo systemctl restart agent-p2p
```

## 故障排除

### Bridge 无法连接 Portal

1. 检查 API Key 是否正确
2. 检查 Portal 地址是否可访问
3. 查看日志：`tail -f skill/bridge.log`

### 收不到消息通知

1. 检查 OpenClaw Gateway 是否运行
2. 检查 hooks token 是否正确
3. 测试唤醒：`curl -X POST http://127.0.0.1:18789/hooks/wake -H "Authorization: Bearer your-token"`

### WebSocket 频繁断开

1. 检查网络稳定性
2. 查看 Bridge 日志
3. 重启 Bridge：`python3 skill/start.py restart`
