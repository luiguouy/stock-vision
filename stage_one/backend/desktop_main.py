# -*- coding: utf-8 -*-
"""
StockVision 桌面端主程序 (Windows Edge WebView2 + 极速冷启动 + 单实例互斥锁)
"""

import sys
import os
import threading
import time
import ctypes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 兼容 PyInstaller 打包后的资源根目录 (_MEIPASS)
ROOT_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
ICON_PATH = os.path.join(ROOT_DIR, "assets", "app.ico")
if not os.path.exists(ICON_PATH):
    ICON_PATH = os.path.join(BASE_DIR, "assets", "app.ico")

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

MUTEX_NAME = r"Global\StockVisionAppMutex_SingleInstance"
ERROR_ALREADY_EXISTS = 183
_MUTEX_HANDLE = None

LOG_DIR = os.path.join(BASE_DIR, "logs")
MIN_SPLASH_DURATION = 3.2


def _console_available() -> bool:
    try:
        if sys.stdout is None or sys.stderr is None:
            return False
        sys.stdout.write("")
        sys.stderr.write("")
        return True
    except Exception:
        return False


def setup_logging():
    if _console_available():
        return
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        path = os.path.join(LOG_DIR, "desktop.log")
        stream = open(path, "a", encoding="utf-8", buffering=1)
        sys.stdout = stream
        sys.stderr = stream
        print(f"\n===== StockVision 启动 {time.strftime('%Y-%m-%d %H:%M:%S')} =====")
    except Exception:
        pass


def check_single_instance() -> bool:
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
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        access_log=False,
        log_level="warning",
        app_dir=BASE_DIR,
    )


def wait_for_backend(port: int, timeout: float = 30.0) -> bool:
    import socket
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False


SPLASH_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  :root {
    --cream-bg: #FAF8F3;
    --emerald: #10B981;
    --coral: #F43F5E;
    --openai: #10A37F;
    --claude: #D97757;
    --gold: #F59E0B;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: 100%; height: 100%;
    background: var(--cream-bg);
    overflow: hidden;
    user-select: none;
  }

  .stage {
    position: relative;
    width: 100%; height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: opacity 0.45s cubic-bezier(0.22, 1, 0.36, 1),
                transform 0.48s cubic-bezier(0.22, 1, 0.36, 1);
  }
  .stage.exit-active {
    opacity: 0;
    transform: scale(1.04);
  }

  .paper-dots {
    position: absolute;
    inset: 0;
    background-image: radial-gradient(rgba(120, 113, 108, 0.14) 1px, transparent 1px);
    background-size: 28px 28px;
    mask-image: radial-gradient(circle at 50% 50%, black 25%, transparent 72%);
    -webkit-mask-image: radial-gradient(circle at 50% 50%, black 25%, transparent 72%);
    pointer-events: none;
  }

  .warm-aura {
    position: absolute;
    width: 680px; height: 380px;
    background: radial-gradient(ellipse at center, rgba(16, 185, 129, 0.08) 0%, rgba(217, 119, 87, 0.07) 48%, transparent 75%);
    filter: blur(32px);
    pointer-events: none;
  }

  .canvas-wrap {
    position: relative;
    width: 780px;
    max-width: 94vw;
    height: 390px;
    cursor: pointer;
  }
  svg {
    width: 100%;
    height: 100%;
    overflow: visible;
  }

  .node-inner {
    opacity: 0;
    transform-box: fill-box;
    transform-origin: center;
    transform: scale(0.25) translateY(8px);
    transition: opacity 0.28s ease, transform 0.52s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .node-inner.lit {
    opacity: 1;
    transform: scale(1) translateY(0);
  }

  .openai-rot {
    transform-box: fill-box;
    transform-origin: center;
    animation: spin-slow 12s linear infinite;
  }
  .claude-breathe {
    transform-box: fill-box;
    transform-origin: center;
    animation: spark-pulse 1.6s ease-in-out infinite alternate;
  }
  @keyframes spin-slow { to { transform: rotate(360deg); } }
  @keyframes spark-pulse {
    0% { transform: scale(0.92) rotate(-6deg); }
    100% { transform: scale(1.1) rotate(6deg); }
  }

  /* 小牛奔跑腿部交替摆动 */
  .leg-front {
    transform-box: fill-box;
    transform-origin: top center;
    animation: leg-swing-a 0.24s ease-in-out infinite alternate;
  }
  .leg-back {
    transform-box: fill-box;
    transform-origin: top center;
    animation: leg-swing-b 0.24s ease-in-out infinite alternate;
  }
  .bull-tail {
    transform-box: fill-box;
    transform-origin: right center;
    animation: tail-wag 0.35s ease-in-out infinite alternate;
  }
  @keyframes leg-swing-a {
    from { transform: rotate(-22deg); }
    to { transform: rotate(22deg); }
  }
  @keyframes leg-swing-b {
    from { transform: rotate(22deg); }
    to { transform: rotate(-22deg); }
  }
  @keyframes tail-wag {
    from { transform: rotate(-14deg); }
    to { transform: rotate(18deg); }
  }

  .bounce-ring {
    transform-box: fill-box;
    transform-origin: center;
    opacity: 0;
  }
  .bounce-ring.pop {
    animation: ring-expand 0.75s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }
  @keyframes ring-expand {
    0% { transform: scale(0.5); opacity: 0.85; }
    100% { transform: scale(2.4); opacity: 0; }
  }

  .sweat-drop {
    opacity: 0;
    transform-box: fill-box;
    transform-origin: top center;
    transform: scale(0);
    transition: all 0.24s cubic-bezier(0.34, 1.56, 0.64, 1);
  }
  .sweat-drop.show {
    opacity: 1;
    transform: scale(1);
  }

  .love-heart {
    opacity: 0;
    transform-box: fill-box;
    transform-origin: bottom center;
    transform: translateY(4px) scale(0.3);
    transition: opacity 0.2s ease, transform 0.36s cubic-bezier(0.34, 1.56, 0.64, 1);
    pointer-events: none;
  }
  .love-heart.pop {
    opacity: 1;
    transform: translateY(-6px) scale(1.05);
  }

  .apex-halo {
    transform-box: fill-box;
    transform-origin: center;
    opacity: 0;
  }
  .apex-halo.pulse {
    animation: apex-wave 1.5s cubic-bezier(0.16, 1, 0.3, 1) infinite;
  }
  @keyframes apex-wave {
    0% { transform: scale(0.6); opacity: 0.85; }
    100% { transform: scale(2.8); opacity: 0; }
  }

  .sparkle-dot {
    position: fixed;
    pointer-events: none;
    z-index: 20;
    animation: sparkle-out 0.65s cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }
  @keyframes sparkle-out {
    0% { transform: translate(-50%, -50%) scale(1) rotate(0deg); opacity: 0.85; }
    100% { transform: translate(-50%, -145%) scale(0.15) rotate(90deg); opacity: 0; }
  }
</style>
</head>
<body>
  <div class="stage" id="stage">
    <div class="paper-dots"></div>
    <div class="warm-aura"></div>

    <div class="canvas-wrap" id="canvasWrap">
      <svg viewBox="0 0 740 370" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="bullCurveGrad" x1="65" y1="305" x2="670" y2="55" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#10B981"/>
            <stop offset="20%" stop-color="#F43F5E"/>
            <stop offset="32%" stop-color="#D97757"/>
            <stop offset="46%" stop-color="#10A37F"/>
            <stop offset="75%" stop-color="#3B82F6"/>
            <stop offset="100%" stop-color="#10B981"/>
          </linearGradient>

          <linearGradient id="areaFillGrad" x1="370" y1="55" x2="370" y2="325" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stop-color="#10B981" stop-opacity="0.14"/>
            <stop offset="65%" stop-color="#D97757" stop-opacity="0.05"/>
            <stop offset="100%" stop-color="#FAF8F3" stop-opacity="0"/>
          </linearGradient>

          <filter id="cardShadow" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="4" stdDeviation="5" flood-color="#78716C" flood-opacity="0.16"/>
          </filter>
        </defs>

        <!-- 极简水平基准虚线 -->
        <line x1="50" y1="322" x2="690" y2="322" stroke="#E7E5E4" stroke-width="1.5" stroke-linecap="round" stroke-dasharray="4 6"/>
        <line x1="50" y1="192" x2="690" y2="192" stroke="#E7E5E4" stroke-width="1.2" stroke-linecap="round" stroke-dasharray="4 8"/>

        <!-- 曲线下方柔和面积 -->
        <path id="areaPath" d="" fill="url(#areaFillGrad)"/>

        <!-- 美股韧性攀升主曲线 -->
        <path id="mainCurve"
              d="M 65 302 C 102 288, 128 250, 154 248 C 172 246, 184 298, 206 298 C 244 298, 298 238, 370 194 C 455 144, 555 96, 668 54"
              stroke="url(#bullCurveGrad)" stroke-width="4.5" stroke-linecap="round"/>

        <!-- 顶点脉冲光环 -->
        <g transform="translate(668, 54)">
          <circle id="apexHalo" class="apex-halo" cx="0" cy="0" r="9" stroke="#10B981" stroke-width="2"/>
          <circle id="apexDot" cx="0" cy="0" r="0" fill="#10B981"/>
        </g>

        <!-- 坑底 AI 弹射光波 -->
        <g transform="translate(206, 298)">
          <circle id="bounceRing" class="bounce-ring" cx="0" cy="0" r="22" stroke="#F59E0B" stroke-width="2.2"/>
        </g>

        <!-- ========== 沿上升曲线从低到高依次排开的 9 枚公司原版矢量标志 ========== -->
        <!-- 1. OpenAI 原版官方矢量图标（现行极简黑配色） -->
        <g id="node-openai">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.2"/>
            <g class="openai-rot">
              <path transform="translate(-9.6, -9.6) scale(0.8)" fill="#171717"
                    d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.911 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.182a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .511 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.989 5.989 0 0 0 3.998-2.9 6.056 6.056 0 0 0-.748-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5Z"/>
            </g>
          </g>
        </g>

        <!-- 2. Claude (Anthropic) 原版暖陶橘星芒图标 -->
        <g id="node-claude">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.2"/>
            <g class="claude-breathe" stroke="#D97757" stroke-width="2.15" stroke-linecap="round">
              <circle cx="0" cy="0" r="2.2" fill="#D97757" stroke="none"/>
              <line x1="0" y1="-2" x2="0" y2="-8.6"/>
              <line x1="1.1" y1="-1.7" x2="4.6" y2="-7.2"/>
              <line x1="1.8" y1="-0.9" x2="8.1" y2="-3.6"/>
              <line x1="2" y1="0.3" x2="8.6" y2="1.4"/>
              <line x1="1.5" y1="1.4" x2="6.3" y2="6.2"/>
              <line x1="0.3" y1="2" x2="1.2" y2="8.5"/>
              <line x1="-1.1" y1="1.7" x2="-4.4" y2="7.4"/>
              <line x1="-1.9" y1="0.7" x2="-8.2" y2="3.1"/>
              <line x1="-2" y1="-0.5" x2="-8.5" y2="-2.1"/>
              <line x1="-1.4" y1="-1.5" x2="-5.6" y2="-6.6"/>
            </g>
          </g>
        </g>

        <!-- 3. NVIDIA 原版官方绿眼图标 -->
        <g id="mag-1">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#76B900"/>
            <path transform="translate(-10.2, -10.2) scale(0.85)" fill="#FFFFFF"
                  d="M8.948 8.798v-1.43a6.7 6.7 0 0 1 .424-.018c3.922-.124 6.493 3.374 6.493 3.374s-2.774 3.851-5.75 3.851c-.398 0-.787-.062-1.167-.185v-4.348c1.528.185 1.837.857 2.747 2.385l2.04-1.714s-1.492-1.952-4-1.952a6.016 6.016 0 0 0-.787.037m0-4.735v2.138l.424-.027c5.45-.185 9.01 4.47 9.01 4.47s-4.08 4.964-8.33 4.964c-.37 0-.733-.035-1.104-.102v1.325c.318.044.636.08.963.08 3.957 0 6.82-2.023 9.593-4.426.46.371 2.34 1.263 2.73 1.652-2.633 2.208-8.772 3.984-12.253 3.984-.335 0-.653-.018-.971-.053v1.864H24V4.063zm0 10.326v1.131c-3.657-.654-4.673-4.46-4.673-4.46s1.758-1.944 4.673-2.262v1.237h-.009c-1.528-.186-2.73 1.245-2.73 1.245s.68 2.412 2.739 3.109M2.456 10.9s2.164-3.188 6.492-3.532V6.201C4.156 6.589 0 10.653 0 10.653s2.35 6.802 8.948 7.42v-1.237c-4.84-.6-6.492-5.936-6.492-5.936z"/>
          </g>
        </g>

        <!-- 4. Microsoft 原版四色田字格 -->
        <g id="mag-2">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.2"/>
            <rect x="-8" y="-8" width="7.2" height="7.2" fill="#F25022"/>
            <rect x="0.8" y="-8" width="7.2" height="7.2" fill="#7FBA00"/>
            <rect x="-8" y="0.8" width="7.2" height="7.2" fill="#00A4EF"/>
            <rect x="0.8" y="0.8" width="7.2" height="7.2" fill="#FFB900"/>
          </g>
        </g>

        <!-- 5. Amazon 原版 'a' + 微笑箭头图标 -->
        <g id="mag-3">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.2"/>
            <!-- 经典深灰小写 'a' -->
            <path d="M 3.8 2.6 C 2.9 3.6 1.5 4.2 -0.3 4.2 C -2.8 4.2 -4.6 2.7 -4.6 0.6 C -4.6 -1.7 -2.7 -3.0 0.5 -3.0 L 2.2 -3.0 L 2.2 -3.7 C 2.2 -5.0 1.4 -5.7 -0.2 -5.7 C -1.4 -5.7 -2.2 -5.2 -2.5 -4.4 L -4.4 -4.8 C -3.9 -6.6 -2.3 -7.6 0.1 -7.6 C 3.0 -7.6 4.5 -6.2 4.5 -3.5 L 4.5 1.2 C 4.5 2.0 4.7 2.5 5.2 2.9 L 3.8 3.9 C 3.5 3.5 3.3 3.1 3.8 2.6 Z M 2.2 -1.3 L 0.6 -1.3 C -1.3 -1.3 -2.3 -0.6 -2.3 0.6 C -2.3 1.7 -1.4 2.4 -0.1 2.4 C 1.4 2.4 2.2 1.4 2.2 -0.2 Z"
                  fill="#232F3E"/>
            <!-- 标志性橙色微笑弯钩箭头 -->
            <path d="M -7.6 5.6 C -3.2 8.8 3.2 8.9 7.8 5.8"
                  fill="none" stroke="#FF9900" stroke-width="1.9" stroke-linecap="round"/>
            <path d="M 5.4 4.7 L 8.8 5.2 L 7.8 8.3"
                  fill="none" stroke="#FF9900" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
          </g>
        </g>

        <!-- 6. Google 原版四色 "G" 字标 -->
        <g id="mag-4">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.2"/>
            <g transform="scale(0.82)">
              <!-- 蓝色右臂与横杠 -->
              <path d="M 9.6 0.2 C 9.6 -0.5 9.5 -1.2 9.4 -1.8 L 0 -1.8 L 0 2.0 L 5.4 2.0 C 5.2 3.3 4.4 4.4 3.3 5.1 L 3.3 7.6 L 6.5 7.6 C 8.4 5.8 9.6 3.2 9.6 0.2 Z" fill="#4285F4"/>
              <!-- 绿色底部弧 -->
              <path d="M 0 10 C 2.7 10 5.0 9.1 6.5 7.6 L 3.3 5.1 C 2.4 5.7 1.3 6.1 0 6.1 C -2.5 6.1 -4.7 4.4 -5.5 2.1 L -8.8 2.1 L -8.8 4.6 C -7.1 7.9 -3.8 10 0 10 Z" fill="#34A853"/>
              <!-- 黄色左侧弧 -->
              <path d="M -5.5 2.1 C -5.7 1.4 -5.8 0.7 -5.8 0 C -5.8 -0.7 -5.7 -1.4 -5.5 -2.1 L -5.5 -4.6 L -8.8 -4.6 C -9.5 -3.2 -9.9 -1.6 -9.9 0 C -9.9 1.6 -9.5 3.2 -8.8 4.6 L -5.5 2.1 Z" fill="#FBBC05"/>
              <!-- 红色顶部弧 -->
              <path d="M 0 -6.1 C 1.5 -6.1 2.8 -5.6 3.9 -4.6 L 6.7 -7.4 C 5.0 -9.0 2.7 -10 0 -10 C -3.8 -10 -7.1 -7.9 -8.8 -4.6 L -5.5 -2.1 C -4.7 -4.4 -2.5 -6.1 0 -6.1 Z" fill="#EA4335"/>
            </g>
          </g>
        </g>

        <!-- 7. Meta 原版官方蓝环图标 -->
        <g id="mag-5">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.2"/>
            <path transform="translate(-10.2, -10.2) scale(0.85)" fill="#0081FB"
                  d="M6.915 4.03c-1.968 0-3.683 1.28-4.871 3.113C.704 9.208 0 11.883 0 14.449c0 .706.07 1.369.21 1.973a6.624 6.624 0 0 0 .265.86 5.297 5.297 0 0 0 .371.761c.696 1.159 1.818 1.927 3.593 1.927 1.497 0 2.633-.671 3.965-2.444.76-1.012 1.144-1.626 2.663-4.32l.756-1.339.186-.325c.061.1.121.196.183.3l2.152 3.595c.724 1.21 1.665 2.556 2.47 3.314 1.046.987 1.992 1.22 3.06 1.22 1.075 0 1.876-.355 2.455-.843a3.743 3.743 0 0 0 .81-.973c.542-.939.861-2.127.861-3.745 0-2.72-.681-5.357-2.084-7.45-1.282-1.912-2.957-2.93-4.716-2.93-1.047 0-2.088.467-3.053 1.308-.652.57-1.257 1.29-1.82 2.05-.69-.875-1.39-1.577-2.114-2.072-.94-.64-1.998-1.079-3.173-1.079zm-.166 3.17c1.324 0 2.376 1.072 3.935 3.382l-1.33 2.345c-1.407 2.492-2.114 3.377-3.193 3.377-1.314 0-2.141-1.069-2.141-2.797 0-1.872.933-4.361 2.137-5.578a3.16 3.16 0 0 1 2.592-.729zm10.17 0c1.424 0 2.377 1.168 2.377 2.91 0 1.792-.836 4.125-2.033 5.336-.732.742-1.55 1.084-2.456 1.084-.846 0-1.498-.349-2.233-1.256-.536-.662-1.13-1.568-1.884-2.83l-1.368-2.292c1.288-1.891 2.388-2.952 3.77-2.952h3.827z"/>
          </g>
        </g>

        <!-- 8. Apple 原版带缺口苹果剪影 -->
        <g id="mag-6">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#FFFFFF" stroke="#E2E8F0" stroke-width="1.2"/>
            <g transform="translate(0, 1) scale(0.84)">
              <!-- 苹果果实（含右侧经典咬痕） -->
              <path d="M 6.4 -1.2 C 6.4 -3.6 8.3 -4.8 8.4 -4.9 C 7.3 -6.5 5.6 -6.7 5.0 -6.8 C 3.6 -6.9 2.2 -5.9 1.5 -5.9 C 0.8 -5.9 -0.4 -6.8 -1.6 -6.8 C -3.2 -6.8 -4.7 -5.8 -5.5 -4.4 C -7.2 -1.4 -5.9 3.0 -4.3 5.4 C -3.5 6.6 -2.5 7.9 -1.2 7.8 C 0.0 7.7 0.5 7.0 2.0 7.0 C 3.5 7.0 3.9 7.8 5.2 7.8 C 6.5 7.8 7.4 6.6 8.2 5.4 C 9.1 4.0 9.5 2.7 9.5 2.6 C 9.4 2.5 6.4 1.4 6.4 -1.2 Z"
                    fill="#1D1D1F"/>
              <!-- 倾斜苹果叶 -->
              <path d="M 3.6 -8.4 C 4.3 -9.3 4.8 -10.5 4.6 -11.7 C 3.5 -11.6 2.2 -11.0 1.5 -10.1 C 0.8 -9.3 0.3 -8.1 0.5 -6.9 C 1.7 -6.8 2.9 -7.5 3.6 -8.4 Z"
                    fill="#1D1D1F"/>
            </g>
          </g>
        </g>

        <!-- 9. Tesla 原版盾形 "T" 字标 -->
        <g id="mag-7">
          <g class="node-inner" filter="url(#cardShadow)">
            <rect x="-15" y="-15" width="30" height="30" rx="9" fill="#E82127"/>
            <g transform="translate(0, 0.5) scale(0.86)">
              <!-- 顶部双弧顶梁 -->
              <path d="M -8.5 -6.6 C -4.2 -8.2 4.2 -8.2 8.5 -6.6 L 7.6 -4.8 C 4.0 -6.1 -4.0 -6.1 -7.6 -4.8 Z" fill="#FFFFFF"/>
              <!-- T 字主干与顶翼 -->
              <path d="M -6.8 -3.8 C -3.6 -4.8 -1.4 -4.8 -1.2 -3.2 L 0 8.5 L 1.2 -3.2 C 1.4 -4.8 3.6 -4.8 6.8 -3.8 L 5.8 -2.1 C 3.8 -2.7 2.4 -2.7 2.1 -1.5 L 0 9.5 L -2.1 -1.5 C -2.4 -2.7 -3.8 -2.7 -5.8 -2.1 Z" fill="#FFFFFF"/>
            </g>
          </g>
        </g>

        <!-- ========== 主角：华尔街萌系冲锋小公牛（弯月牛角 + 牛耳 + 奶油大鼻吻 + 奔跑四肢牛尾） ========== -->
        <g id="bullActor" transform="translate(65, 302)">
          <!-- AI 点火后的双色小喷射尾焰 -->
          <g id="jetFlames" opacity="0">
            <ellipse cx="-24" cy="-2" rx="8" ry="3" fill="#10A37F" opacity="0.85"/>
            <ellipse cx="-24" cy="3" rx="7" ry="2.6" fill="#D97757" opacity="0.85"/>
          </g>

          <g id="bullBody" filter="url(#cardShadow)">
            <!-- 甩动的小牛尾 -->
            <path class="bull-tail" d="M -15 -3 Q -22 -8 -21 -13" stroke="#059669" stroke-width="2.4" stroke-linecap="round" fill="none"/>
            <circle cx="-21" cy="-13.5" r="2.2" fill="#FEF3C7"/>

            <!-- 奔跑的四条小牛蹄 -->
            <rect class="leg-back" x="-12" y="4" width="4.2" height="7.5" rx="2" fill="#047857"/>
            <rect class="leg-front" x="-5" y="4" width="4.2" height="7.5" rx="2" fill="#059669"/>
            <rect class="leg-back" x="3" y="4" width="4.2" height="7.5" rx="2" fill="#047857"/>
            <rect class="leg-front" x="9" y="4" width="4.2" height="7.5" rx="2" fill="#059669"/>

            <!-- 敦实的小牛躯干 -->
            <rect x="-16" y="-8" width="26" height="15" rx="7.5" fill="#10B981"/>

            <!-- 牛角下方一对小牛耳 -->
            <ellipse cx="-2" cy="-14" rx="4.2" ry="2.2" transform="rotate(-25 -2 -14)" fill="#059669"/>
            <ellipse cx="16" cy="-14" rx="4.2" ry="2.2" transform="rotate(25 16 -14)" fill="#059669"/>

            <!-- 标志性弯月大牛角（根粗尖细，奶金色） -->
            <path d="M 0 -15 C -6 -17, -7 -24, -2 -26 C -3 -22, -1 -19, 3 -17 Z" fill="#FEF3C7" stroke="#D97706" stroke-width="0.9" stroke-linejoin="round"/>
            <path d="M 14 -15 C 20 -17, 21 -24, 16 -26 C 17 -22, 15 -19, 11 -17 Z" fill="#FEF3C7" stroke="#D97706" stroke-width="0.9" stroke-linejoin="round"/>

            <!-- 立体牛头 -->
            <rect x="-3" y="-18" width="20" height="19" rx="8" fill="#10B981" stroke="#34D399" stroke-width="1"/>

            <!-- 灵动豆豆眼（眼球追踪） -->
            <circle cx="3.2" cy="-11" r="2.7" fill="#FFFFFF"/>
            <circle cx="11.2" cy="-11" r="2.7" fill="#FFFFFF"/>
            <circle id="pupilL" cx="3.8" cy="-11" r="1.4" fill="#1E293B"/>
            <circle id="pupilR" cx="11.8" cy="-11" r="1.4" fill="#1E293B"/>

            <!-- 标志性暖奶油色大鼻吻 + 两个小鼻孔 -->
            <rect x="-1.5" y="-6.5" width="17" height="8.5" rx="4.2" fill="#FEF3C7" stroke="#F59E0B" stroke-width="0.8"/>
            <ellipse cx="3.5" cy="-2.3" rx="1.3" ry="1.8" fill="#92400E"/>
            <ellipse cx="10.5" cy="-2.3" rx="1.3" ry="1.8" fill="#92400E"/>
          </g>

          <!-- 深坑小汗滴 -->
          <path id="sweatDrop" class="sweat-drop"
                d="M 21 -26 C 21 -26, 25 -20.5, 25 -18 C 25 -15.8, 23.2 -14, 21 -14 C 18.8 -14, 17 -15.8, 17 -18 C 17 -20.5, 21 -26, 21 -26 Z"
                fill="#38BDF8"/>

          <!-- 点击爱心彩蛋 -->
          <path id="loveHeart" class="love-heart"
                d="M 7 -28 C 4 -32, -2 -30, -2 -25 C -2 -21, 7 -16, 7 -16 C 7 -16, 16 -21, 16 -25 C 16 -30, 10 -32, 7 -28 Z"
                fill="#F43F5E"/>
        </g>
      </svg>
    </div>
  </div>

<script>
  (function () {
    const mainCurve = document.getElementById("mainCurve");
    const areaPath = document.getElementById("areaPath");
    const bullActor = document.getElementById("bullActor");
    const bullBody = document.getElementById("bullBody");
    const jetFlames = document.getElementById("jetFlames");
    const sweatDrop = document.getElementById("sweatDrop");
    const bounceRing = document.getElementById("bounceRing");
    const apexDot = document.getElementById("apexDot");
    const apexHalo = document.getElementById("apexHalo");

    const totalLen = mainCurve.getTotalLength();
    mainCurve.style.strokeDasharray = totalLen;
    mainCurve.style.strokeDashoffset = totalLen;

    // 9 个原版公司标志沿上升曲线从低到高依次排列
    const badgeConfigs = [
      { id: "node-openai", progress: 0.30, lit: false },
      { id: "node-claude", progress: 0.38, lit: false },
      { id: "mag-1",       progress: 0.46, lit: false },
      { id: "mag-2",       progress: 0.54, lit: false },
      { id: "mag-3",       progress: 0.62, lit: false },
      { id: "mag-4",       progress: 0.70, lit: false },
      { id: "mag-5",       progress: 0.78, lit: false },
      { id: "mag-6",       progress: 0.86, lit: false },
      { id: "mag-7",       progress: 0.94, lit: false }
    ];

    const milestones = badgeConfigs.map((cfg) => {
      const outer = document.getElementById(cfg.id);
      const inner = outer.querySelector(".node-inner");
      const pt = mainCurve.getPointAtLength(totalLen * cfg.progress);
      outer.setAttribute("transform", `translate(${pt.x.toFixed(1)}, ${(pt.y - 38).toFixed(1)})`);
      return { ...cfg, inner };
    });

    let aiIgnited = false;
    let apexReached = false;
    let jumpOffset = 0;

    function storyEase(t) {
      if (t < 0.26) {
        const p = t / 0.26;
        return 0.26 * (1 - Math.pow(1 - p, 1.55));
      } else if (t < 0.33) {
        return 0.26;
      } else {
        const p = (t - 0.33) / 0.67;
        return 0.26 + 0.74 * (1 - Math.pow(1 - p, 2.0));
      }
    }

    const duration = 2750;
    let startTime = null;

    function animate(ts) {
      if (!startTime) startTime = ts;
      const rawT = Math.min((ts - startTime) / duration, 1);
      const prog = storyEase(rawT);

      const drawLen = totalLen * prog;
      mainCurve.style.strokeDashoffset = totalLen - drawLen;

      const pt = mainCurve.getPointAtLength(drawLen);
      const ptPrev = mainCurve.getPointAtLength(Math.max(0, drawLen - 4));
      const angle = Math.atan2(pt.y - ptPrev.y, pt.x - ptPrev.x) * (180 / Math.PI);

      if (prog > 0.02) {
        areaPath.setAttribute(
          "d",
          `M 65 322 L 65 302 Q ${(65 + pt.x) / 2} ${Math.max(pt.y, 265)} ${pt.x} ${pt.y} L ${pt.x} 322 Z`
        );
      }

      if (prog >= 0.15 && prog <= 0.28 && !aiIgnited) {
        sweatDrop.classList.add("show");
      } else {
        sweatDrop.classList.remove("show");
      }

      if (rawT >= 0.25 && !aiIgnited) {
        aiIgnited = true;
        bounceRing.classList.add("pop");
        jetFlames.setAttribute("opacity", "1");
      }

      milestones.forEach((m) => {
        if (!m.lit && prog >= m.progress) {
          m.lit = true;
          m.inner.classList.add("lit");
        }
      });

      if (prog >= 0.99 && !apexReached) {
        apexReached = true;
        apexDot.setAttribute("r", "5");
        apexHalo.classList.add("pulse");
      }

      const bounce = rawT < 1 ? Math.abs(Math.sin(rawT * Math.PI * 10)) * 4 : Math.sin(ts * 0.005) * 2;
      const stretchX = rawT < 1 ? 1 + Math.abs(Math.cos(rawT * Math.PI * 10)) * 0.06 : 1;
      const stretchY = 2 - stretchX;
      const tilt = rawT < 1 ? Math.max(-24, Math.min(24, angle * 0.45)) : 0;

      bullActor.setAttribute("transform", `translate(${pt.x.toFixed(1)}, ${(pt.y - 12 - bounce - jumpOffset).toFixed(1)})`);
      bullBody.setAttribute("transform", `rotate(${tilt.toFixed(1)}) scale(${stretchX.toFixed(2)}, ${stretchY.toFixed(2)})`);

      requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);

    const pupilL = document.getElementById("pupilL");
    const pupilR = document.getElementById("pupilR");
    let lastDust = 0;

    document.addEventListener("mousemove", (e) => {
      const dx = (e.clientX / window.innerWidth - 0.5) * 2.2;
      const dy = (e.clientY / window.innerHeight - 0.5) * 2.2;
      pupilL.setAttribute("cx", (3.2 + dx).toFixed(2));
      pupilL.setAttribute("cy", (-11.0 + dy).toFixed(2));
      pupilR.setAttribute("cx", (11.2 + dx).toFixed(2));
      pupilR.setAttribute("cy", (-11.0 + dy).toFixed(2));

      const now = performance.now();
      if (now - lastDust > 55) {
        lastDust = now;
        const dot = document.createElement("div");
        dot.className = "sparkle-dot";
        const isClaude = Math.random() > 0.5;
        dot.style.left = e.clientX + "px";
        dot.style.top = e.clientY + "px";
        dot.style.width = "7px";
        dot.style.height = "7px";
        dot.style.borderRadius = isClaude ? "2px" : "50%";
        dot.style.background = isClaude ? "#D97757" : "#10A37F";
        document.body.appendChild(dot);
        setTimeout(() => dot.remove(), 650);
      }
    });

    const loveHeart = document.getElementById("loveHeart");
    let heartTimer = null;
    document.getElementById("canvasWrap").addEventListener("mousedown", () => {
      jumpOffset = 18;
      setTimeout(() => { jumpOffset = 0; }, 180);
      loveHeart.classList.add("pop");
      clearTimeout(heartTimer);
      heartTimer = setTimeout(() => loveHeart.classList.remove("pop"), 850);
    });

    window.__triggerExit = function () {
      document.getElementById("stage").classList.add("exit-active");
    };
  })();
</script>
</body>
</html>"""

ERROR_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:#FAF8F3;color:#1E293B;
font-family:'Inter','Segoe UI','Microsoft YaHei',sans-serif;user-select:none}
.wrap{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;text-align:center}
.title{font-size:16px;font-weight:700;color:#F43F5E}
.body{font-size:13px;color:#64748B;line-height:1.8;max-width:520px}
code{background:#F1F5F9;border:1px solid #E2E8F0;padding:2px 6px;border-radius:4px;color:#0F172A}
</style></head><body><div class="wrap">
<div class="title">后端服务未能启动</div>
<div class="body">端口 <code>127.0.0.1:8000</code> 在 30 秒内没有响应。<br>
请确认依赖已安装，或在终端运行以下命令查看具体报错：<br>
<code>python stage_one/backend/desktop_main.py</code></div>
</div></body></html>"""


def main():
    setup_logging()

    if not check_single_instance():
        print("[StockVision] 应用程序已在运行中，请切换至已有窗口。")
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:8000/api/control/state")
            urllib.request.urlopen(req, timeout=1.0)
        except Exception:
            pass
        sys.exit(0)

    port = 8000

    t = threading.Thread(target=start_backend_server, args=(port,), daemon=True)
    t.start()

    import webview

    window = webview.create_window(
        title="StockVision 智能股票技术分析平台",
        html=SPLASH_HTML,
        width=1440,
        height=900,
        min_size=(1024, 680),
        background_color="#FAF8F3",
        text_select=False,
        confirm_close=False,
    )

    def _boot():
        boot_start = time.monotonic()
        backend_ok = wait_for_backend(port, timeout=30.0)

        if backend_ok:
            elapsed = time.monotonic() - boot_start
            remain = MIN_SPLASH_DURATION - elapsed
            if remain > 0:
                time.sleep(remain)

            try:
                window.evaluate_js("window.__triggerExit && window.__triggerExit();")
                time.sleep(0.45)
            except Exception:
                pass

            window.load_url(f"http://127.0.0.1:{port}")
        else:
            window.load_html(ERROR_HTML)

        # 确保窗口与任务栏图标生效 (通过 Windows API WM_SETICON 设为高分辨率图标)
        if sys.platform == "win32" and os.path.exists(ICON_PATH):
            try:
                hwnd = None
                if hasattr(window, "native") and window.native:
                    hwnd = getattr(window.native, "Handle", None)
                    if hasattr(hwnd, "ToInt32"):
                        hwnd = hwnd.ToInt32()
                if not hwnd:
                    hwnd = ctypes.windll.user32.FindWindowW(None, window.title)
                if hwnd:
                    WM_SETICON = 0x0080
                    ICON_SMALL = 0
                    ICON_BIG = 1
                    IMAGE_ICON = 1
                    LR_LOADFROMFILE = 0x00000010
                    # 加载大图标 (32x32 / 48x48) 与小图标 (16x16)
                    hicon_big = ctypes.windll.user32.LoadImageW(
                        None, os.path.abspath(ICON_PATH), IMAGE_ICON, 32, 32, LR_LOADFROMFILE
                    )
                    hicon_small = ctypes.windll.user32.LoadImageW(
                        None, os.path.abspath(ICON_PATH), IMAGE_ICON, 16, 16, LR_LOADFROMFILE
                    )
                    if hicon_big:
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
                    if hicon_small:
                        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
            except Exception:
                pass

    def _on_restored():
        try:
            window.evaluate_js("window.__onDesktopWindowRestored && window.__onDesktopWindowRestored();")
        except Exception:
            pass

    def _on_minimized():
        try:
            window.evaluate_js("window.__onDesktopWindowMinimized && window.__onDesktopWindowMinimized();")
        except Exception:
            pass

    window.events.restored += _on_restored
    window.events.shown += _on_restored
    window.events.maximized += _on_restored
    window.events.minimized += _on_minimized

    # 持久化 WebView2 缓存与 Profile，禁用 private_mode 保证 localStorage/IndexedDB 跨会话零冷启动
    profile_dir = os.path.join(BASE_DIR, "data", "webview_profile")
    try:
        os.makedirs(profile_dir, exist_ok=True)
    except Exception:
        pass

    webview.start(
        _boot,
        gui="edgechromium",
        debug=False,
        icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
        private_mode=False,
        storage_path=profile_dir,
    )


if __name__ == "__main__":
    main()
