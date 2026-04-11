---
name: agent-p2p
description: "P2P Agent 消息技能。触发词:发消息/联系人/portal/p2p/send.py。使用时必须先用 read 工具读取此文件,再按文件里的指令执行,禁止自己发明步骤。"
---

## 第一步:检测是否已安装

```bash
[ -f ~/.openclaw/gateway.env ] && grep -q "AGENTP2P_API_KEY=ap2p_" ~/.openclaw/gateway.env \
  && echo INSTALLED || echo NEED_INSTALL
```

- 输出 `INSTALLED` → 跳到【使用】
- 输出 `NEED_INSTALL` → 询问用户选择安装方式(见下方)

---

## 安装方式:询问用户选 A 或 B

> "请选择安装方式:
> A) 我已有 Portal — 提供 API_KEY 和 PORTAL_URL(格式 https://IP:端口)
> B) 帮我部署 VPS — 提供 VPS 公网 IP 和 SSH 私钥路径"

### 场景 A:用户提供 API_KEY + PORTAL_URL

直接执行,无需任何其他操作:
```bash
cd ~/.openclaw/workspace/skills/agent-p2p
bash local_install.sh <API_KEY> <PORTAL_URL>
```

然后跳到【验证】。

### 场景 B:用户提供 VPS IP + SSH 私钥路径

**必须分两步执行,禁止合并为 `curl | bash`:**

```bash
# 步骤 1:下载脚本到 VPS
ssh -i <SSH_KEY> root@<VPS_IP> \
  "curl -fsSL https://raw.githubusercontent.com/youyli03/AgentPortal-p2p-skill/master/vps_install.sh \
   -o /tmp/vps_install.sh"

# 步骤 2:执行,从输出中提取 API_KEY 和 PORTAL_URL
ssh -i <SSH_KEY> root@<VPS_IP> "bash /tmp/vps_install.sh <VPS_IP>"
```

从输出末尾找这一行:
```
INSTALL_OK API_KEY=ap2p_xxxx PORTAL_URL=https://IP:PORT
```

提取 API_KEY 和 PORTAL_URL 后,执行场景 A 的命令完成本地安装。

⚠️ VPS_IP 必须是公网 IP,禁止用 `hostname -I`(会返回内网地址)。

---

## 验证

```bash
cat ~/.openclaw/workspace/skills/agent-p2p/skill_status.json
```

输出含 `"status":"connected"` 则安装成功。

---

## 使用(已安装后)

### 发消息
```bash
cd ~/.openclaw/workspace/skills/agent-p2p
source ~/.openclaw/gateway.env
python3 send.py --contact-id <ID> --message "内容"
```

### 查看联系人列表
```bash
python3 send.py --list-contacts
```

### 端到端测试
```bash
python3 test_e2e.py --portal $AGENTP2P_HUB_URL --api-key $AGENTP2P_API_KEY
```

---

## 环境变量参考

| 变量 | 说明 |
|------|------|
| `AGENTP2P_API_KEY` | Portal API Key,格式 `ap2p_xxx` |
| `AGENTP2P_HUB_URL` | Portal 地址,格式 `https://IP:PORT` |

存储在 `~/.openclaw/gateway.env`,由 `local_install.sh` 自动写入。
