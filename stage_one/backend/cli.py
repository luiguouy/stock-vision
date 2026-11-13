# -*- coding: utf-8 -*-
"""
StockVision CLI 工具 (sv)

供命令行和脚本直接操作 StockVision 桌面端软件。
用法示例:
  sv open usAAPL --period 15m
  sv state
  sv analyze usAAPL --mode swing
  sv mark usAAPL --time "2026-11-12" --text "Buy 2B" --color "#10b981"
  sv line usAAPL --price 185.5 --title "止损位" --color "#ef4444"
  sv box usAAPL --price1 190 --price2 180 --time1 "2026-11-10" --time2 "2026-11-12" --label "箱体"
  sv capture
  sv clear usAAPL
"""

import sys
import os
import json
import argparse
import time
import subprocess
import httpx

BASE_URL = "http://127.0.0.1:8000"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
client = httpx.Client(base_url=BASE_URL, timeout=10.0, trust_env=False)


def _ensure_app_running() -> bool:
    try:
        resp = client.get("/api/health")
        if resp.status_code == 200:
            return True
    except Exception:
        pass
    venv_py = os.path.join(os.path.dirname(os.path.dirname(APP_DIR)), ".venv", "Scripts", "python.exe")
    python_exe = venv_py if os.path.exists(venv_py) else sys.executable
    desktop_script = os.path.join(APP_DIR, "desktop_main.py")
    subprocess.Popen([python_exe, desktop_script], cwd=APP_DIR)
    for _ in range(15):
        time.sleep(0.2)
        try:
            resp = client.get("/api/health")
            if resp.status_code == 200:
                return True
        except Exception:
            continue
    return False


def cmd_open(args):
    _ensure_app_running()
    try:
        resp = client.post("/api/control/open", json={"symbol": args.symbol, "period": args.period})
        data = resp.json()
        print(f"已成功切换至: {data.get('state', {}).get('symbol')} ({data.get('state', {}).get('period')})")
    except Exception as e:
        print(f"打开图表失败 (请先启动桌面软件): {e}")


def cmd_state(args):
    try:
        resp = client.get("/api/control/state")
        data = resp.json()
        st = data.get("state", {})
        print(f"当前标的: {st.get('symbol')} | 周期: {st.get('period')} | 最新价: {st.get('current_price')}")
        print(f"已连接前端窗口: {data.get('connected_clients', 0)} 个")
        annos = data.get("annotations", [])
        print(f"当前图表已有标注: {len(annos)} 项")
        for a in annos[:5]:
            print(f"  - [{a.get('kind')}] {a.get('id')}: {a.get('source')}")
    except Exception as e:
        print(f"获取状态失败: {e}")


def cmd_mark(args):
    try:
        marker = {
            "time": args.time,
            "position": args.pos,
            "color": args.color,
            "shape": args.shape,
            "text": args.text,
        }
        resp = client.post("/api/control/markers", json={"symbol": args.symbol, "markers": [marker]})
        print(f"成功添加标记: {args.text} 于 {args.time}")
    except Exception as e:
        print(f"添加标记失败: {e}")


def cmd_line(args):
    try:
        line = {
            "price": float(args.price),
            "color": args.color,
            "lineWidth": 2,
            "lineStyle": int(args.style),
            "title": args.title,
        }
        resp = client.post("/api/control/lines", json={"symbol": args.symbol, "lines": [line]})
        print(f"成功绘制水平线: {args.title} (${args.price})")
    except Exception as e:
        print(f"绘制价格线失败: {e}")


def cmd_box(args):
    try:
        box = {
            "price1": float(args.price1),
            "price2": float(args.price2),
            "time1": args.time1,
            "time2": args.time2,
            "label": args.label,
            "fillColor": args.fill,
            "borderColor": args.border,
        }
        resp = client.post("/api/control/boxes", json={"symbol": args.symbol, "boxes": [box]})
        print(f"成功绘制矩形区间: {args.label} [{args.price2} ~ {args.price1}]")
    except Exception as e:
        print(f"绘制矩形失败: {e}")


def cmd_analyze(args):
    try:
        resp = client.post(
            "/api/control/strategy",
            json={
                "symbol": args.symbol,
                "period": args.period,
                "mode": args.mode,
                "draw_on_chart": args.draw,
            },
        )
        data = resp.json()
        summary = data.get("summary", {})
        print(f"=== {args.symbol} 价格行为策略分析结果 ===")
        print(f"道氏结构: {summary.get('dow_phase')}")
        print(f"200 EMA 门禁: {summary.get('ema_200_gate', {}).get('trend')} ({summary.get('ema_200_gate', {}).get('status')})")
        print(f"波浪结构: {summary.get('wave', {}).get('pattern')} -> {summary.get('wave', {}).get('current_wave')}")
        if summary.get('wave', {}).get('invalidation_price'):
            print(f"波浪铁律证伪价: ${summary.get('wave', {}).get('invalidation_price')} ({summary.get('wave', {}).get('invalidation_reason')})")
        tp = summary.get("trade_plan", {})
        print(f"交易计划: {tp.get('direction')} | 入场: ${tp.get('entry')} | 止损: ${tp.get('stop_loss')} | TP1: ${tp.get('tp1')}")
        print(f"净盈亏比 (已扣8bps): {tp.get('rr_ratio')}R (>=2.5R 门禁: {'通过' if tp.get('passed_gates') else '未通过'})")
        if args.draw:
            print("✓ 已自动将标注、水平线与箱体渲染至桌面图表")
    except Exception as e:
        print(f"执行策略失败: {e}")


def cmd_capture(args):
    try:
        resp = client.post("/api/control/capture")
        data = resp.json()
        if data.get("status") == "ok":
            print(f"✓ 图表截图已保存至: {data.get('file_path')}")
        else:
            print(f"截图失败: {data.get('message')}")
    except Exception as e:
        print(f"截取图表失败: {e}")


def cmd_clear(args):
    try:
        resp = client.post("/api/control/clear", json={"symbol": args.symbol, "kind": args.kind})
        data = resp.json()
        print(f"✓ 已清除 {args.symbol} 的标注 (共删除 {data.get('deleted', 0)} 项)")
    except Exception as e:
        print(f"清除标注失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="StockVision CLI 控制终端")
    subparsers = parser.add_subparsers(dest="cmd")

    # open
    p_open = subparsers.add_parser("open", help="打开指定标的与周期")
    p_open.add_argument("symbol", help="股票代码, 如 usAAPL")
    p_open.add_argument("--period", default="1d", help="K线周期, 如 15m, 1h, 1d")

    # state
    subparsers.add_parser("state", help="获取当前软件状态与标注")

    # mark
    p_mark = subparsers.add_parser("mark", help="在图表上打标记")
    p_mark.add_argument("symbol", help="股票代码")
    p_mark.add_argument("--time", required=True, help="时间 (YYYY-MM-DD 或 YYYY-MM-DD HH:MM)")
    p_mark.add_argument("--text", required=True, help="文字描述")
    p_mark.add_argument("--pos", default="aboveBar", choices=["aboveBar", "belowBar"], help="位置")
    p_mark.add_argument("--color", default="#10b981", help="颜色 HEX")
    p_mark.add_argument("--shape", default="arrowDown", choices=["arrowDown", "arrowUp", "circle", "square"], help="形状")

    # line
    p_line = subparsers.add_parser("line", help="在图表上画水平线")
    p_line.add_argument("symbol", help="股票代码")
    p_line.add_argument("--price", required=True, type=float, help="价格")
    p_line.add_argument("--title", default="", help="说明标题")
    p_line.add_argument("--color", default="#3b82f6", help="颜色 HEX")
    p_line.add_argument("--style", default=2, type=int, choices=[0, 1, 2], help="线型 (0=实线, 1=点线, 2=虚线)")

    # box
    p_box = subparsers.add_parser("box", help="在图表上画矩形箱体")
    p_box.add_argument("symbol", help="股票代码")
    p_box.add_argument("--price1", required=True, type=float, help="顶价格")
    p_box.add_argument("--price2", required=True, type=float, help="底价格")
    p_box.add_argument("--time1", required=True, help="起始时间")
    p_box.add_argument("--time2", required=True, help="截止时间")
    p_box.add_argument("--label", default="", help="标注文字")
    p_box.add_argument("--fill", default="rgba(59, 130, 246, 0.12)", help="填充颜色")
    p_box.add_argument("--border", default="#3b82f6", help="边框颜色")

    # analyze
    p_ana = subparsers.add_parser("analyze", help="执行 Investment_Assistant 价格行为策略")
    p_ana.add_argument("symbol", help="股票代码")
    p_ana.add_argument("--period", default="1d", help="周期")
    p_ana.add_argument("--mode", default="swing", choices=["swing", "day"], help="模式")
    p_ana.add_argument("--draw", action="store_true", default=True, help="是否自动画到图表上")

    # capture
    subparsers.add_parser("capture", help="截取当前图表画面")

    # clear
    p_clr = subparsers.add_parser("clear", help="清除图表标注")
    p_clr.add_argument("symbol", help="股票代码")
    p_clr.add_argument("--kind", default=None, choices=["marker", "line", "box"], help="指定清除类型")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "open": cmd_open,
        "state": cmd_state,
        "mark": cmd_mark,
        "line": cmd_line,
        "box": cmd_box,
        "analyze": cmd_analyze,
        "capture": cmd_capture,
        "clear": cmd_clear,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
