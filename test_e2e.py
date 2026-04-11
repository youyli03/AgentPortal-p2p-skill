#!/usr/bin/env python3
"""
AgentPortal P2P Skill - 端到端测试脚本

用法:
  python3 test_e2e.py --portal https://<IP>:<PORT> --api-key <KEY>
  # 或从环境变量读取
  export AGENTP2P_HUB_URL=https://IP:18080
  export AGENTP2P_API_KEY=ap2p_xxxx
  python3 test_e2e.py

测试步骤:
  1. 健康检查
  2. Agent-A WebSocket 连接
  3. 创建 Agent-B 的 API Key
  4. A/B 互换 Key，建立好友关系
  5. B 发消息给 A，验证 A 收到 WS 推送
  6. A 回复 B，验证消息历史
  7. 匿名留言测试
  8. 清理测试数据
  9. 打印测试报告
"""
import asyncio, json, ssl, sys, socket, argparse, os
import urllib.request, urllib.error, urllib.parse
from datetime import datetime

GREEN="\033[92m"; RED="\033[91m"; YELLOW="\033[93m"
CYAN="\033[96m";  BOLD="\033[1m"; RESET="\033[0m"

def ok(m):   print(f"  {GREEN}[PASS]{RESET} {m}")
def fail(m): print(f"  {RED}[FAIL]{RESET} {m}")
def info(m): print(f"  {CYAN}[INFO]{RESET} {m}")
def warn(m): print(f"  {YELLOW}[WARN]{RESET} {m}")
def sec(m):  print(f"\n{BOLD}{m}{RESET}")

RESULTS = []

def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    (ok if passed else fail)(f"{name}  {detail}")

# ── SSL ──────────────────────────────────────────────────────────────────────
def mk_ssl():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c
SSL = mk_ssl()

# ── HTTP ─────────────────────────────────────────────────────────────────────
def http(method, url, body=None, extra=None):
    h = {"Content-Type": "application/json"}
    if extra:
        h.update(extra)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, context=SSL, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}")

class Client:
    def __init__(self, base, key):
        self.base = base.rstrip("/")
        self.key  = key
    def _h(self):
        return {"X-API-Key": self.key}
    def get(self, p):
        return http("GET", self.base + p, extra=self._h())
    def post(self, p, b=None):
        return http("POST", self.base + p, body=b, extra=self._h())
    def delete(self, p):
        return http("DELETE", self.base + p, extra=self._h())

# ── WebSocket ─────────────────────────────────────────────────────────────────
async def ws_listen(ws_base, key, bucket, timeout=26.0):
    try:
        import websockets
    except ImportError:
        warn("websockets 未安装，跳过 WS 测试  (pip install websockets)")
        return False

    parsed = urllib.parse.urlparse(ws_base)
    hn, pt = parsed.hostname, (parsed.port or 18080)
    try:
        real_ip = socket.getaddrinfo(hn, pt, socket.AF_UNSPEC, socket.SOCK_STREAM)[0][4][0]
        actual  = ws_base.replace(f"//{hn}", f"//{real_ip}", 1)
        info(f"DNS: {hn} -> {real_ip}")
    except Exception:
        actual = ws_base

    kw  = {"ssl": SSL} if ws_base.startswith("wss://") else {}
    url = f"{actual}/ws/agent?api_key={key}"
    try:
        async with websockets.connect(url, **kw) as ws:
            bucket.append("__connected__")
            deadline = asyncio.get_event_loop().time() + timeout
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    bucket.append(json.loads(raw))
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    break
        return True
    except Exception as e:
        warn(f"WS 异常: {e}")
        return False

# ── 测试报告 ─────────────────────────────────────────────────────────────────
def _report():
    total  = len(RESULTS)
    passed = sum(1 for _, p, _ in RESULTS if p)
    failed = total - passed
    print(f"\n{BOLD}{'='*54}")
    print(f"  测试报告  总计={total}  通过={passed}  失败={failed}")
    print(f"{'='*54}{RESET}")
    for name, p, detail in RESULTS:
        status = f"{GREEN}PASS{RESET}" if p else f"{RED}FAIL{RESET}"
        print(f"  [{status}]  {name}")
        if detail and not p:
            print(f"         └─ {detail[:120]}")
    color = GREEN if failed == 0 else RED
    print(f"\n{color}{BOLD}结论: {'全部通过 ✓' if failed==0 else f'{failed} 项失败 ✗'}{RESET}\n")

# ── 主测试 ────────────────────────────────────────────────────────────────────
async def run(portal, key_a):
    ts   = datetime.now().strftime("%H%M%S")
    ca   = Client(portal, key_a)
    ws_b = portal.replace("https://", "wss://").replace("http://", "ws://")

    # 1. 健康检查
    sec("▶ [1] 健康检查")
    try:
        r = ca.get("/health")
        record("health", r.get("status") == "ok", json.dumps(r))
    except Exception as e:
        record("health", False, str(e))
        print(f"\n{RED}Portal 不可达，终止测试。{RESET}")
        _report()
        return

    # 2. WS 连接
    sec("▶ [2] WebSocket 连接 (Agent-A)")
    bucket: list = []
    ws_task = asyncio.create_task(ws_listen(ws_b, key_a, bucket, timeout=30))
    await asyncio.sleep(2)
    ws_up = "__connected__" in bucket
    record("ws_connect", ws_up, "已连接" if ws_up else "失败（WS 推送测试将跳过）")

    # 3. 创建 B 的 Key
    sec("▶ [3] 创建 Agent-B API Key")
    portal_b = f"{portal}/mock/b-{ts}"
    try:
        r    = ca.post("/api/key/create", {
            "portal_url": portal_b,
            "agent_name": f"TestB-{ts}",
            "user_name":  "TestUser",
        })
        key_b = r["api_key"]
        record("create_key_B", key_b.startswith("ap2p_"), f"{key_b[:22]}…")
        cb = Client(portal, key_b)
    except Exception as e:
        record("create_key_B", False, str(e))
        ws_task.cancel()
        _report()
        return

    # 4. Key 交换（B 向 A 发起）
    sec("▶ [4] Key 交换（建立好友关系）")
    try:
        r = cb.post("/api/key/exchange", {
            "portal_url": portal,
            "SHARED_KEY": key_a,
        })
        key_a_to_b = r.get("api_key", "")
        record("key_exchange", key_a_to_b.startswith("ap2p_"),
               f"B 得到 A 的 key: {key_a_to_b[:22]}…")
    except Exception as e:
        record("key_exchange", False, str(e))
        key_a_to_b = ""

    # 5. B 发消息给 A，验证 WS 推送
    sec("▶ [5] B -> A 发消息（含 WS 推送验证）")
    try:
        contacts = cb.get("/api/contacts")["contacts"]
        ca_c = next((c for c in contacts if c["portal_url"] == portal), None)
        if not ca_c:
            record("find_contact_A_in_B", False, f"B 联系人: {contacts}")
            ws_task.cancel()
            _report()
            return
        record("find_contact_A_in_B", True, f"contact_id={ca_c['id']}")
        cid_a = ca_c["id"]
    except Exception as e:
        record("find_contact_A_in_B", False, str(e))
        ws_task.cancel()
        _report()
        return

    test_msg = f"[e2e-{ts}] Hello from B to A via P2P!"
    try:
        r = cb.post("/api/message/send", {
            "contact_id":   cid_a,
            "content":      test_msg,
            "message_type": "text",
        })
        record("B_send_msg", r.get("status") in ("delivered", "ok"),
               f"status={r.get('status')}")
    except Exception as e:
        record("B_send_msg", False, str(e))

    await asyncio.sleep(3)
    pushed = [m for m in bucket
              if isinstance(m, dict)
              and m.get("type") == "new_message"
              and test_msg in str(m.get("content", ""))]
    record("ws_push_to_A", bool(pushed),
           json.dumps(pushed[0], ensure_ascii=False)[:120] if pushed
           else "未收到 new_message 推送（可能 WS 未连接）")

    # 6. A 回复 B，验证消息历史
    sec("▶ [6] A -> B 回复，验证消息历史")
    try:
        contacts_a = ca.get("/api/contacts")["contacts"]
        cb_c = next((c for c in contacts_a if c["portal_url"] == portal_b), None)
        if not cb_c:
            record("find_contact_B_in_A", False, f"A 联系人: {contacts_a}")
        else:
            record("find_contact_B_in_A", True, f"contact_id={cb_c['id']}")
            reply = f"[e2e-{ts}] Hi B, message received!"
            r = ca.post("/api/message/send", {
                "contact_id":   cb_c["id"],
                "content":      reply,
                "message_type": "text",
            })
            record("A_reply_B", r.get("status") in ("delivered", "ok"),
                   f"status={r.get('status')}")
            # 验证历史
            hist = ca.get(f"/api/messages?contact_portal={urllib.parse.quote(portal_b)}")
            msgs = hist.get("messages", [])
            has_reply = any(reply in str(m.get("content", "")) for m in msgs)
            record("msg_history_A", has_reply, f"共 {len(msgs)} 条消息")
    except Exception as e:
        record("reply_flow", False, str(e))

    # 7. 匿名留言
    sec("▶ [7] 匿名留言测试")
    guest_content = f"[guest-{ts}] 这是一条匿名测试留言"
    try:
        r = ca.post("/api/guest/leave-message", {"content": guest_content})
        gid = r.get("message_id")
        record("guest_leave", gid is not None, f"message_id={gid}")
        # 验证留言列表
        gl = ca.get("/api/guest/messages")
        found = any(str(gid) == str(m.get("id","")) for m in gl.get("messages",[]))
        record("guest_list", found, f"共 {len(gl.get('messages',[]))} 条留言")
    except Exception as e:
        record("guest_msg", False, str(e))

    # 等 WS 任务结束
    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass

    # 8. 清理测试数据（撤销 B 的 key）
    sec("▶ [8] 清理测试数据")
    try:
        r = ca.post(f"/api/key/revoke?api_key={urllib.parse.quote(key_b)}")
        record("cleanup_key_B", r.get("status") == "revoked", str(r))
    except Exception as e:
        warn(f"清理 key_b 时失败（非致命）: {e}")

    # 汇报所有收到的 WS 消息
    sec("▶ WS 消息汇总")
    ws_msgs = [m for m in bucket if isinstance(m, dict)]
    info(f"共收到 {len(ws_msgs)} 条 WS 消息:")
    for i, m in enumerate(ws_msgs, 1):
        print(f"    [{i}] type={m.get('type','?')}  "
              f"content={str(m.get('content',''))[:80]}")

    _report()

# ── 入口 ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="AgentPortal P2P 端到端测试")
    p.add_argument("--portal",  default=os.environ.get("AGENTP2P_HUB_URL",""),
                   help="Portal HTTPS 地址，如 https://39.96.x.x:18080")
    p.add_argument("--api-key", default=os.environ.get("AGENTP2P_API_KEY",""),
                   help="Agent-A 的 API Key（ap2p_…）")
    args = p.parse_args()

    if not args.portal:
        print(f"{RED}错误：请通过 --portal 或 AGENTP2P_HUB_URL 指定 Portal 地址{RESET}")
        sys.exit(1)
    if not args.api_key:
        print(f"{RED}错误：请通过 --api-key 或 AGENTP2P_API_KEY 指定 API Key{RESET}")
        sys.exit(1)

    portal = args.portal.rstrip("/")
    print(f"\n{BOLD}AgentPortal P2P 端到端测试{RESET}")
    print(f"Portal : {portal}")
    print(f"API Key: {args.api_key[:22]}…")
    print(f"时间   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    asyncio.run(run(portal, args.api_key))

if __name__ == "__main__":
    main()
