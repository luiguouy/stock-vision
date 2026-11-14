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
import argparse

import control_client as cc


def cmd_open(args):
    data = cc.open_chart(args.symbol, period=args.period)
    if data.get("status") == "error":
        print(data.get("message"))
        return
    st = data.get("state", {})
    print(f"已成功切换至: {st.get('symbol')} ({st.get('period')})")


def cmd_state(args):
    data = cc.get_state()
    if data.get("status") == "error":
        print(data.get("message"))
        return
    st = data.get("state", {})
    print(f"当前标的: {st.get('symbol')} | 周期: {st.get('period')} | 最新价: {st.get('current_price')}")
    print(f"已连接前端窗口: {data.get('connected_clients', 0)} 个")
    annos = data.get("annotations", [])
    print(f"当前图表已有标注: {len(annos)} 项")
    for a in annos[:5]:
        print(f"  - [{a.get('kind')}] {a.get('id')}: {a.get('source')}")


def cmd_mark(args):
    marker = {
        "time": args.time,
        "position": args.pos,
        "color": args.color,
        "shape": args.shape,
        "text": args.text,
    }
    data = cc.add_markers(args.symbol, [marker])
    if data.get("status") == "error":
        print(data.get("message"))
        return
    print(f"成功添加标记: {args.text} 于 {args.time}")


def cmd_line(args):
    line = {
        "price": float(args.price),
        "color": args.color,
        "lineWidth": 2,
        "lineStyle": int(args.style),
        "title": args.title,
    }
    data = cc.draw_lines(args.symbol, [line])
    if data.get("status") == "error":
        print(data.get("message"))
        return
    print(f"成功绘制水平线: {args.title} (${args.price})")


def cmd_box(args):
    box = {
        "price1": float(args.price1),
        "price2": float(args.price2),
        "time1": args.time1,
        "time2": args.time2,
        "label": args.label,
        "fillColor": args.fill,
        "borderColor": args.border,
    }
    data = cc.draw_boxes(args.symbol, [box])
    if data.get("status") == "error":
        print(data.get("message"))
        return
    print(f"成功绘制矩形区间: {args.label} [{args.price2} ~ {args.price1}]")


def cmd_analyze(args):
    data = cc.run_strategy(
        args.symbol,
        period=args.period,
        mode=args.mode,
        draw_on_chart=args.draw,
    )
    if data.get("status") == "error":
        print(data.get("message"))
        return

    summary = data.get("summary", {})
    print(f"=== {args.symbol} 价格行为策略分析结果 ===")
    print(f"道氏结构: {summary.get('dow_phase')}")
    ema_gate = summary.get("ema_200_gate", {})
    print(f"200 EMA 门禁: {ema_gate.get('trend')} ({ema_gate.get('status')})")
    wave = summary.get("wave", {})
    print(f"波浪结构: {wave.get('pattern')} -> {wave.get('current_wave')}")
    if wave.get("invalidation_price"):
        print(f"波浪铁律证伪价: ${wave.get('invalidation_price')} ({wave.get('invalidation_reason')})")
    tp = summary.get("trade_plan", {})
    print(f"交易计划: {tp.get('direction')} | 入场: ${tp.get('entry')} | 止损: ${tp.get('stop_loss')} | TP1: ${tp.get('tp1')}")
    print(f"净盈亏比 (已扣8bps): {tp.get('rr_ratio')}R (>=2.5R 门禁: {'通过' if tp.get('passed_gates') else '未通过'})")
    if args.draw:
        print("✓ 已自动将标注、水平线与箱体渲染至桌面图表")


def cmd_capture(args):
    data = cc.capture_chart()
    if data.get("status") == "ok":
        print(f"✓ 图表截图已保存至: {data.get('file_path')}")
    else:
        print(f"截图失败: {data.get('message')}")


def cmd_clear(args):
    data = cc.clear_annotations(args.symbol, kind=args.kind)
    if data.get("status") == "error":
        print(data.get("message"))
        return
    print(f"✓ 已清除 {args.symbol} 的标注 (共删除 {data.get('deleted', 0)} 项)")


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
    p_ana = subparsers.add_parser("analyze", help="执行价格行为策略")
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
