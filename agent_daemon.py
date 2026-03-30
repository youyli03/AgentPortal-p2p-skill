#!/usr/bin/env python3
"""
OpenClaw Agent - Portal WebSocket 客户端（常驻）
实时接收 Portal 推送，通知用户
"""
import asyncio
import websockets
import json
import os
import sys

# 配置
PORTAL_URL = "https://agentportalp2p.com"
API_KEY = "ap2p_c-cc3wp-38P9zR5tAEnbt9Iji5ABmAjgUxslYOUNPi0"
NOTIFY_FILE = os.path.expanduser("~/.agent_p2p_realtime.json")

async def connect_and_listen():
    """连接 Portal 并监听消息"""
    ws_url = PORTAL_URL.replace('https://', 'wss://').replace('http://', 'ws://')
    ws_url = f"{ws_url}/ws/agent?api_key={API_KEY}"
    
    print(f"[Agent P2P] Connecting to {PORTAL_URL}...", flush=True)
    
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                print("[Agent P2P] ✅ Connected!", flush=True)
                
                # 发送 sync_request 获取离线消息
                await ws.send(json.dumps({"type": "sync_request"}))
                
                while True:
                    try:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        msg_type = data.get("type")
                        
                        if msg_type == "new_guest_message":
                            content = data.get('content', '')
                            print(f"[Agent P2P] 📩 New guest message: {content[:50]}...", flush=True)
                            save_notification("guest_message", content)
                            
                        elif msg_type == "new_message":
                            from_portal = data.get('from', '')
                            content = data.get('content', '')
                            print(f"[Agent P2P] 📩 New message from {from_portal}: {content[:50]}...", flush=True)
                            save_notification("message", content, from_portal)
                            
                            # 确认收到
                            msg_id = data.get('id')
                            if msg_id:
                                await ws.send(json.dumps({
                                    "type": "ack",
                                    "message_ids": [msg_id]
                                }))
                        
                        elif msg_type == "sync_response":
                            messages = data.get('messages', [])
                            if messages:
                                print(f"[Agent P2P] 📦 Synced {len(messages)} offline messages", flush=True)
                                for msg in messages:
                                    save_notification("message", msg.get('content', ''), msg.get('from', ''))
                                    
                    except websockets.exceptions.ConnectionClosed:
                        print("[Agent P2P] Connection closed, reconnecting...", flush=True)
                        break
                    except Exception as e:
                        print(f"[Agent P2P] Error: {e}", flush=True)
                        
        except Exception as e:
            print(f"[Agent P2P] Connection failed: {e}, retrying in 5s...", flush=True)
            await asyncio.sleep(5)

def save_notification(msg_type, content, sender=""):
    """保存通知到文件"""
    try:
        import time
        notification = {
            "type": msg_type,
            "content": content,
            "sender": sender,
            "timestamp": time.time()
        }
        
        notifications = []
        if os.path.exists(NOTIFY_FILE):
            try:
                with open(NOTIFY_FILE, 'r') as f:
                    notifications = json.load(f)
            except:
                notifications = []
        
        notifications.append(notification)
        notifications = notifications[-100:]
        
        with open(NOTIFY_FILE, 'w') as f:
            json.dump(notifications, f, ensure_ascii=False)
            
    except Exception as e:
        print(f"[Agent P2P] Save failed: {e}", flush=True)

if __name__ == '__main__':
    try:
        asyncio.run(connect_and_listen())
    except KeyboardInterrupt:
        print("[Agent P2P] Stopped", flush=True)
        sys.exit(0)
