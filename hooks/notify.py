#!/usr/bin/env python3
"""
Agent P2P 消息通知 Hook
读取标准输入的消息内容，通过 OpenClaw 通知主会话
"""
import sys
import json

def main():
    # 从标准输入读取消息
    message = sys.stdin.read().strip()
    
    if not message:
        return
    
    # 输出通知（OpenClaw 会捕获并通知主会话）
    print(f"[AGENT_P2P_NOTIFICATION] {message}", flush=True)

if __name__ == "__main__":
    main()
