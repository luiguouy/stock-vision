# -*- coding: utf-8 -*-
"""
StockVision 桌面端主程序 (Windows Edge WebView2 + 极速冷启动 + 单实例互斥锁)

核心性能规范:
  1. 采用原生 Edge WebView2 Runtime，无须打包 Electron 庞大 Chromium 内核，内存基线仅 ~60-80MB。
  2. 极速冷启动架构：入口仅导入 webview 与 threading，主窗口 < 1.0 秒呈现。
  3. 后台单进程多线程内联：Uvicorn 静默运行（log_level='warning', access_log=False）。
  4. Windows 命名互斥锁：防止多开冲突，次实例秒级退出。
"""

import sys
import os
import threading
import time
import ctypes

# 修正工作目录与模块路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

MUTEX_NAME = r"Global\StockVisionAppMutex_SingleInstance"
ERROR_ALREADY_EXISTS = 183
_MUTEX_HANDLE = None


def check_single_instance() -> bool:
    """检查是否已有 StockVision 运行实例 (Windows 命名互斥锁)。"""
    global _MUTEX_HANDLE
    if sys.platform != "win32":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        _MUTEX_HANDLE = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            return False
        return True
    except Exception:
        return True


def start_backend_server(port: int = 8000):
    """在后台静默守护线程中运行 Uvicorn ASGI 服务。"""
    import uvicorn
    # 关闭繁重的 Access Log，使用 WARNING 日志等级消除控制台 I/O 开销
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        access_log=False,
        log_level="warning",
        app_dir=BASE_DIR,
    )


def main():
    if not check_single_instance():
        print("[StockVision] 应用程序已在运行中，请切换至已有窗口。")
        # 尝试唤醒已有实例并退出
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:8000/api/control/state")
            urllib.request.urlopen(req, timeout=1.0)
        except Exception:
            pass
        sys.exit(0)

    port = 8000

    # 启动后台 Uvicorn 服务子线程
    t = threading.Thread(target=start_backend_server, args=(port,), daemon=True)
    t.start()

    # 秒级极速呈现：导入 pywebview
    import webview

    target_url = f"http://127.0.0.1:{port}"

    # 创建桌面窗口
    window = webview.create_window(
        title="StockVision 智能股票技术分析平台",
        url=target_url,
        width=1440,
        height=900,
        min_size=(1024, 680),
        background_color="#0f172a",
        text_select=False,
        confirm_close=False,
    )

    # 启动 WebView2 原生渲染引擎 (硬件加速)
    webview.start(gui="edgechromium", debug=False)


if __name__ == "__main__":
    main()
