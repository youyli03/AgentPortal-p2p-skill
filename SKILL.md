---
name: agent-p2p
description: "P2P Agent 消息技能。触发词:发消息/联系人/portal/p2p/send.py。使用时必须先用 read 工具读取此文件,再按文件里的指令执行。禁止自己发明步骤、禁止使用占位符参数(dummy/localhost/127.0.0.1)、禁止在未拿到真实参数前执行任何安装命令。"
---

## 第一步:检测是否已安装

```bash
[ -f ~/.openclaw/gateway.env ] && grep -q "AGENTP2P_API_KEY=ap2p_" ~/.openclaw/gateway.env \
  && echo INSTALLED || echo NEED_INSTALL
```

- 输出 `INSTALLED` → 跳到【使用】
- 输出 `NEED_INSTALL` → 继续第二步

---

## 第二步:询问用户选 A 或 B（必须等用户回答再继续）

向用户发送以下问题，**等待用户回复后再执行任何命令**：

> 请选择安装方式：
> **A) 我已有 Portal** — 请提供 API_KEY（格式 ap2p_xxx）和 PORTAL_URL（格式 https://IP:端口）
> **B) 帮我部署 VPS** — 请提供 VPS 公网 IP 和 SSH 私钥路径（例如 ~/.ssh/id_rsa）

---

## 场景 A：用户提供 API_KEY + PORTAL_URL

收到用户提供的真实 API_KEY 和 PORTAL_URL 后，执行：

```bash
cd ~/.openclaw/workspace/skills/agent-p2p
bash local_install.sh <用户提供的API_KEY> <用户提供的PORTAL_URL>
```

跳到【验证】。

---

## 场景 B：用户提供 VPS IP + SSH 私钥路径

**规则：必须完成步骤1（拿到 INSTALL_OK）才能执行步骤2。禁止并行执行。**

**步骤1：在 VPS 上安装 Portal（等待完成，可能需要 2~5 分钟）**

```bash
# 1a. 下载脚本到 VPS
ssh -i <SSH_KEY> root@<VPS_IP> \
  "curl -fsSL https://raw.githubusercontent.com/youyli03/AgentPortal-p2p-skill/master/vps_install.sh \
   -o /tmp/vps_install.sh"

# 1b. 执行安装（等待输出末尾出现 INSTALL_OK 行）
ssh -i <SSH_KEY> root@<VPS_IP> "bash /tmp/vps_install.sh <VPS_IP>"
```

从输出末尾找到这一行：
```
INSTALL_OK API_KEY=ap2p_xxxx PORTAL_URL=https://IP:PORT
```

⚠️ **未看到 INSTALL_OK 行则视为失败，不得继续执行步骤2。**  
⚠️ VPS_IP 必须是用户提供的公网 IP，禁止用 `hostname -I`。

**步骤2：本地安装 Bridge（用步骤1拿到的真实参数）**

```bash
cd ~/.openclaw/workspace/skills/agent-p2p
bash local_install.sh <步骤1输出的API_KEY> <步骤1输出的PORTAL_URL>
```

跳到【验证】。

---

## 验证

```bash
cat ~/.openclaw/workspace/skills/agent-p2p/skill_status.json
```

输出含 `"status":"connected"` 则安装成功。  
如果显示 `"status":"error"` 或连接失败，把完整 JSON 内容回报用户。

---

## 使用（已安装后）

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
