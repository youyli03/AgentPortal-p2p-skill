#!/usr/bin/env python3
"""
Agent P2P Client - WebSocket + 轮询双机制
"""
import asyncio
import websockets
import json
import time
import os
import sys
import threading
from datetime import datetime
from config import get_portal_url, get_api_key

# 通知文件路径
NOTIFY_FILE = os.path.expanduser("~/.agent_p2p_notify.json")
STATE_FILE = os.path.expanduser("~/.agent_p2p_state.json")

class PortalClient:
    def __init__(self):
        self.portal_url = None
        self.api_key = None
        self.ws = None
        self.running = False
        self.reconnect_delay = 5
        self.last_poll_time = 0
        self.poll_interval = 300  # 轮询间隔：5分钟
        
    def load_config(self):
        """加载配置"""
        self.portal_url = get_portal_url()
        self.api_key = get_api_key()
        return bool(self.portal_url and self.api_key)
    
    def get_ws_url(self):
        """获取 WebSocket URL"""
        ws_url = self.portal_url.replace('https://', 'wss://').replace('http://', 'ws://')
        return f"{ws_url}/ws/agent?api_key={self.api_key}"
    
    def _load_state(self):
        """加载状态"""
        try:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[Agent P2P] 加载状态失败: {e}")
        return {}
    
    def _save_state(self, state):
        """保存状态"""
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            print(f"[Agent P2P] 保存状态失败: {e}")
    
    def _notify(self, msg_type, content, sender=""):
        """写入通知文件"""
        try:
            notification = {
                "type": msg_type,
                "content": content,
                "sender": sender,
                "timestamp": datetime.now().isoformat()
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
            
            # 只保留最近100条
            notifications = notifications[-100:]
            
            # 写入文件
            with open(NOTIFY_FILE, 'w') as f:
                json.dump(notifications, f, ensure_ascii=False)
                
            print(f"[Agent P2P] 通知已记录: {msg_type}")
        except Exception as e:
            print(f"[Agent P2P] 通知记录失败: {e}")
    
    async def poll_messages(self):
        """轮询消息（备份机制）"""
        while self.running:
            try:
                now = time.time()
                if now - self.last_poll_time >= self.poll_interval:
                    print(f"[Agent P2P] 执行轮询检查...")
                    await self._check_messages_via_api()
                    self.last_poll_time = now
                await asyncio.sleep(10)  # 每10秒检查一次是否需要轮询
            except Exception as e:
                print(f"[Agent P2P] 轮询错误: {e}")
                await asyncio.sleep(10)
    
    async def _check_messages_via_api(self):
        """通过 API 检查消息"""
        try:
            import httpx
            
            # 获取联系人列表
            async with httpx.AsyncClient(timeout=30.0) as client:
                contacts_res = await client.get(
                    f"{self.portal_url}/api/contacts"
                )
                contacts = contacts_res.json().get('contacts', [])
                
                # 检查每个联系人的消息
                for contact in contacts:
                    portal = contact.get('portal_url')
                    if not portal:
                        continue
                    
                    # 获取消息历史
                    messages_res = await client.get(
                        f"{self.portal_url}/api/messages/history",
                        params={"contact_portal": portal}
                    )
                    messages = messages_res.json().get('messages', [])
                    
                    # 检查未读消息（简化处理，实际应该记录 last_read_id）
                    for msg in messages:
                        if msg.get('type') == 'received':
                            # 检查是否已经通知过
                            if not self._is_notified(msg.get('id')):
                                self._notify(
                                    "new_message",
                                    f"来自 {contact.get('display_name', portal)}: {msg.get('content', '')}",
                                    portal
                                )
                                self._mark_notified(msg.get('id'))
                                
        except Exception as e:
            print(f"[Agent P2P] API 检查失败: {e}")
    
    def _is_notified(self, msg_id):
        """检查消息是否已通知"""
        if not msg_id:
            return False
        state = self._load_state()
        notified_ids = state.get('notified_ids', [])
        return msg_id in notified_ids
    
    def _mark_notified(self, msg_id):
        """标记消息已通知"""
        if not msg_id:
            return
        state = self._load_state()
        notified_ids = state.get('notified_ids', [])
        if msg_id not in notified_ids:
            notified_ids.append(msg_id)
            # 只保留最近1000条
            state['notified_ids'] = notified_ids[-1000:]
            self._save_state(state)
    
    async def connect(self):
        """连接 WebSocket"""
        if not self.load_config():
            print("[Agent P2P] 未配置，请先配置门户地址和 API Key")
            return False
        
        try:
            ws_url = self.get_ws_url()
            print(f"[Agent P2P] 正在连接: {ws_url[:60]}...")
            
            self.ws = await websockets.connect(ws_url)
            self.running = True
            
            print(f"[Agent P2P] 已连接到门户: {self.portal_url}")
            
            # 发送同步请求
            await self._send_sync_request()
            
            return True
        except Exception as e:
            print(f"[Agent P2P] 连接失败: {e}")
            return False
    
    async def _send_sync_request(self):
        """发送同步请求"""
        state = self._load_state()
        last_sync = state.get("last_sync")
        
        await self.ws.send(json.dumps({
            "type": "sync_request",
            "last_sync": last_sync
        }))
        print(f"[Agent P2P] 请求同步消息 (last_sync: {last_sync})")
    
    async def _send_ack(self, message_ids):
        """发送消息确认"""
        if not message_ids or not self.ws:
            return
        
        try:
            await self.ws.send(json.dumps({
                "type": "ack",
                "message_ids": message_ids
            }))
            print(f"[Agent P2P] 确认收到 {len(message_ids)} 条消息")
        except Exception as e:
            print(f"[Agent P2P] 发送确认失败: {e}")
    
    async def handle_messages(self):
        """处理 WebSocket 消息"""
        while self.running and self.ws:
            try:
                message = await self.ws.recv()
                data = json.loads(message)
                
                msg_type = data.get("type")
                
                if msg_type == "pong":
                    pass  # 心跳响应
                
                elif msg_type == "new_message":
                    msg_id = data.get("id")
                    from_portal = data.get('from')
                    content = data.get('content')
                    
                    print(f"[Agent P2P] 📩 新消息来自 {from_portal}: {content[:50]}...")
                    
                    # 记录通知
                    self._notify("new_message", content, from_portal)
                    
                    # 立即确认收到
                    if msg_id:
                        await self._send_ack([msg_id])
                        self._mark_notified(msg_id)
                
                elif msg_type == "new_guest_message":
                    content = data.get('content')
                    print(f"[Agent P2P] 💬 新留言: {content[:50]}...")
                    self._notify("new_guest_message", content)
                
                elif msg_type == "sync_response":
                    messages = data.get('messages', [])
                    if messages:
                        print(f"[Agent P2P] 📦 同步到 {len(messages)} 条离线消息")
                        
                        ack_ids = []
                        for msg in messages:
                            msg_id = msg.get("id")
                            content = msg.get("content")
                            from_portal = msg.get("from")
                            
                            print(f"[Agent P2P] 📩 [离线消息] 来自 {from_portal}: {content[:50]}...")
                            
                            # 记录通知
                            if not self._is_notified(msg_id):
                                self._notify("new_message", content, from_portal)
                                self._mark_notified(msg_id)
                            
                            if msg_id:
                                ack_ids.append(msg_id)
                        
                        # 批量确认
                        if ack_ids:
                            await self._send_ack(ack_ids)
                    else:
                        print("[Agent P2P] 没有离线消息")
                    
                    # 更新最后同步时间
                    state = self._load_state()
                    state["last_sync"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    self._save_state(state)
                
            except websockets.exceptions.ConnectionClosed:
                print("[Agent P2P] 连接已关闭")
                self.running = False
                break
            except Exception as e:
                print(f"[Agent P2P] 消息处理错误: {e}")
    
    async def run(self):
        """运行客户端（WebSocket + 轮询）"""
        while True:
            if await self.connect():
                # 同时启动 WebSocket 处理和轮询
                await asyncio.gather(
                    self.handle_messages(),
                    self.poll_messages(),
                    return_exceptions=True
                )
            
            # 断线后等待重连
            print(f"[Agent P2P] {self.reconnect_delay}秒后重连...")
            await asyncio.sleep(self.reconnect_delay)

# 全局客户端实例
_client = None

def get_client():
    """获取客户端实例"""
    global _client
    if _client is None:
        _client = PortalClient()
    return _client

if __name__ == "__main__":
    client = get_client()
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\n[Agent P2P] 客户端已停止")
