#!/usr/bin/env python3
"""
Agent P2P Skill 启动脚本
管理 bridge 进程的启动、停止和状态查看
"""

import subprocess
import sys
import os
import json
import signal
import time
from pathlib import Path

PID_FILE = Path(__file__).parent / 'bridge.pid'
LOG_FILE = Path(__file__).parent / 'bridge.log'

def get_pid():
    """获取进程 ID"""
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except:
            return None
    return None

def is_running(pid):
    """检查进程是否运行中"""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def start():
    """启动 bridge"""
    pid = get_pid()
    if pid and is_running(pid):
        print(f'Bridge 已在运行 (PID: {pid})')
        return
    
    print('启动 Agent P2P Skill Bridge...')
    
    # 加载环境变量
    env_file = Path.home() / '.openclaw' / 'gateway.env'
    env = os.environ.copy()
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env[key.strip()] = value.strip()
    
    # 使用 nohup 启动
    bridge_py = Path(__file__).parent / 'bridge.py'
    
    with open(LOG_FILE, 'a') as log:
        process = subprocess.Popen(
            [sys.executable, str(bridge_py)],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env
        )
    
    PID_FILE.write_text(str(process.pid))
    print(f'Bridge 已启动 (PID: {process.pid})')
    print(f'日志: {LOG_FILE}')
    
    # 等待几秒检查状态
    time.sleep(2)
    if is_running(process.pid):
        print('✅ 启动成功')
    else:
        print('❌ 启动失败，请查看日志')
        sys.exit(1)

def stop():
    """停止 bridge"""
    pid = get_pid()
    if not pid:
        print('Bridge 未运行')
        return
    
    if not is_running(pid):
        print('Bridge 进程已不存在')
        PID_FILE.unlink(missing_ok=True)
        return
    
    print(f'停止 Bridge (PID: {pid})...')
    try:
        os.kill(pid, signal.SIGTERM)
        # 等待进程结束
        for _ in range(10):
            if not is_running(pid):
                break
            time.sleep(0.5)
        
        if is_running(pid):
            print('强制终止...')
            os.kill(pid, signal.SIGKILL)
        
        PID_FILE.unlink(missing_ok=True)
        print('✅ 已停止')
    except Exception as e:
        print(f'停止失败: {e}')

def status():
    """查看状态"""
    pid = get_pid()
    
    if pid and is_running(pid):
        print(f'✅ Bridge 运行中 (PID: {pid})')
    else:
        print('❌ Bridge 未运行')
    
    # 显示状态文件
    status_file = Path(__file__).parent.parent / 'skill_status.json'
    if status_file.exists():
        try:
            data = json.loads(status_file.read_text())
            print(f'状态: {data.get("status")}')
            print(f'消息: {data.get("message")}')
            print(f'时间: {data.get("timestamp")}')
        except:
            pass
    
    # 显示最近日志
    if LOG_FILE.exists():
        print(f'\n最近日志 (最后5行):')
        lines = LOG_FILE.read_text().split('\n')[-6:-1]
        for line in lines:
            if line.strip():
                print(f'  {line}')

def restart():
    """重启 bridge"""
    stop()
    time.sleep(1)
    start()

def main():
    if len(sys.argv) < 2:
        print(f'用法: {sys.argv[0]} <start|stop|restart|status>')
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == 'start':
        start()
    elif command == 'stop':
        stop()
    elif command == 'restart':
        restart()
    elif command == 'status':
        status()
    else:
        print(f'未知命令: {command}')
        print(f'用法: {sys.argv[0]} <start|stop|restart|status>')
        sys.exit(1)

if __name__ == '__main__':
    main()
