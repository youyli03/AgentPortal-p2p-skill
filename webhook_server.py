#!/usr/bin/env python3
"""
Agent P2P Webhook 接收服务
接收 Portal 推送，转发给 OpenClaw
"""
import asyncio
from aiohttp import web
import json
import os

# 通知管道
NOTIFY_PIPE = "/tmp/agent_p2p_pipe"

async def handle_webhook(request):
    """接收 Portal 推送"""
    try:
        data = await request.json()
        
        # 验证 token
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return web.Response(status=401, text='Unauthorized')
        
        # 构造通知
        notification = {
            "type": data.get('type', 'message'),
            "content": data.get('content', ''),
            "portal": data.get('portal', ''),
            "timestamp": data.get('timestamp', '')
        }
        
        # 写入管道文件（触发 OpenClaw 读取）
        with open(NOTIFY_PIPE, 'a') as f:
            f.write(json.dumps(notification, ensure_ascii=False) + '\n')
        
        print(f"[Webhook] Received: {notification['content'][:50]}...", flush=True)
        
        return web.Response(status=200, text='OK')
    
    except Exception as e:
        print(f"[Webhook] Error: {e}", flush=True)
        return web.Response(status=500, text=str(e))

async def main():
    # 创建管道文件
    if not os.path.exists(NOTIFY_PIPE):
        open(NOTIFY_PIPE, 'w').close()
    
    app = web.Application()
    app.router.add_post('/webhook', handle_webhook)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 8082)
    await site.start()
    
    print("[Webhook] Server started at http://127.0.0.1:8082/webhook")
    
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
