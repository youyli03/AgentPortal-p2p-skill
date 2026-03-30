#!/usr/bin/env python3
"""
OpenClaw Agent - Portal WebSocket 客户端
主动连接 Portal，接收实时推送
"""
import asyncio
import websockets
import json
import os

# Portal 配置
PORTAL_URL = "https://agentportalp2p.com"
API_KEY = "ap2p_c-cc3wp-38P9zR5tAEnbt9Iji5ABmAjgUxslYOUNPi0"  # 使用你给 OpenClaw 的 Key

# 通知文件路径
NOTIFY_FILE = os.path.expanduser("~/.agent_p2p_notify.json")

async def connect_to_portal():
    """连接 Portal WebSocket"""
    ws_url = PORTAL_URL.replace('https://', 'wss://').replace('http://', 'ws://')
    ws_url = f"{ws_url}/ws/agent?api_key={API_KEY}"
    
    print(f"[OpenClaw Agent] Connecting to {ws_url[:60]}...")
    
    async with websockets.connect(ws_url) as websocket:
        print("[OpenClaw Agent] Connected to Portal")
        
        # 发送同步请求
        await websocket.send(json.dumps({
            "type": "sync_request"
        }))
        
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                msg_type = data.get("type")
                
                if msg_type == "pong":
                    pass  # 心跳响应
                
                elif msg_type == "new_guest_message":
                    content = data.get('content', '')
                    print(f"[OpenClaw Agent] New guest message: {content[:50]}...")
                    
                    # 保存通知
                    save_notification("guest_message", content)
                
                elif msg_type == "new_message":
                    from_portal = data.get('from', '')
                    content = data.get('content', '')
                    print(f"[OpenClaw Agent] New message from {from_portal}: {content[:50]}...")
                    
                    # 保存通知
                    save_notification("message", content, from_portal)
                    
                    # 确认收到
                    msg_id = data.get('id')
                    if msg_id:
                        await websocket.send(json.dumps({
                            "type": "ack",
                            "message_ids": [msg_id]
                        }))
                
                elif msg_type == "sync_response":
                    messages = data.get('messages', [])
                    if messages:
                        print(f"[OpenClaw Agent] Synced {len(messages)} offline messages")
                        for msg in messages:
                            save_notification("message", msg.get('content', ''), msg.get('from', ''))
                
            except Exception as e:
                print(f"[OpenClaw Agent] Error: {e}")
                await asyncio.sleep(5)

def save_notification(msg_type, content, sender=""):
    """保存通知到文件"""
    try:
        notification = {
            "type": msg_type,
            "content": content,
            "sender": sender,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        # 读取现有通知
        notifications = []
        if os.path.exists(NOTIFY_FILE):
            try:
                with open(NOTIFY_FILE, 'r') as f:
                    notifications = json.load(f)
            except:
                notifications = []
        
        # 添加新通知
        notifications.append(notification)
        notifications = notifications[-100:]
        
        # 写入文件
        with open(NOTIFY_FILE, 'w') as f:
            json.dump(notifications, f, ensure_ascii=False)
        
        print(f"[OpenClaw Agent] Notification saved: {content[:50]}...")
    except Exception as e:
        print(f"[OpenClaw Agent] Save failed: {e}")

if __name__ == '__main__':
    asyncio.run(connect_to_portal())
