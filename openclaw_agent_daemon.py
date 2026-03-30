#!/usr/bin/env python3
"""
OpenClaw Agent - Portal WebSocket 客户端
常驻后台，接收 Portal 实时推送
"""
import asyncio
import websockets
import json
import os
import time

# 配置
PORTAL_URL = "https://agentportalp2p.com"
API_KEY = "ap2p_c-cc3wp-38P9zR5tAEnbt9Iji5ABmAjgUxslYOUNPi0"

# 通知文件
NOTIFY_FILE = os.path.expanduser("~/.agent_p2p_notify.json")

async def connect_and_listen():
    """连接 Portal 并监听消息"""
    ws_url = PORTAL_URL.replace('https://', 'wss://').replace('http://', 'ws://')
    ws_url = f"{ws_url}/ws/agent?api_key={API_KEY}"
    
    print(f"[{time.strftime('%H:%M:%S')}] [Agent] Connecting to Portal...")
    
    async with websockets.connect(ws_url) as ws:
        print(f"[{time.strftime('%H:%M:%S')}] [Agent] Connected!")
        
        # 发送 sync_request 获取离线消息
        await ws.send(json.dumps({"type": "sync_request"}))
        
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(msg)
                msg_type = data.get("type")
                
                if msg_type == "pong":
                    pass
                
                elif msg_type == "new_guest_message":
                    content = data.get('content', '')
                    print(f"[{time.strftime('%H:%M:%S')}] [Agent] New guest message: {content[:50]}...")
                    save_notification("guest_message", content)
                
                elif msg_type == "new_message":
                    from_portal = data.get('from', '')
                    content = data.get('content', '')
                    print(f"[{time.strftime('%H:%M:%S')}] [Agent] New message from {from_portal}: {content[:50]}...")
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
                        print(f"[{time.strftime('%H:%M:%S')}] [Agent] Synced {len(messages)} offline messages")
                        for msg in messages:
                            save_notification("message", msg.get('content', ''), msg.get('from', ''))
                
            except asyncio.TimeoutError:
                # 发送 ping 保持连接
                await ws.send(json.dumps({"type": "ping"}))
            
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] [Agent] Error: {e}")
                break

def save_notification(msg_type, content, sender=""):
    """保存通知到文件"""
    try:
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
        print(f"[{time.strftime('%H:%M:%S')}] [Agent] Save failed: {e}")

async def main():
    """主循环 - 断线重连"""
    while True:
        try:
            await connect_and_listen()
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] [Agent] Connection failed: {e}")
        
        print(f"[{time.strftime('%H:%M:%S')}] [Agent] Reconnecting in 5 seconds...")
        await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(main())
