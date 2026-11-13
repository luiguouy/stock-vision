# -*- coding: utf-8 -*-
"""
Investment_Assistant 交易策略适配器 (高性能 / 延迟懒加载)

职责:
  1. 延迟导入 Investment_Assistant 核心模块 (pa_engine, strategy_layer, strategy_day, strategy_crypto)
     与重型计算库 (pandas, scipy, numpy, yfinance)，保证桌面主程序启动时间 < 1.0 秒。
  2. 对接道氏理论拐点、波浪理论客观证伪线、200 EMA 宏观门禁、箱体状态机与日内 2.5R 硬门禁。
  3. 格式化生成 Lightweight Charts 图表标注协议 (Markers, PriceLines, Boxes)。
"""

import sys
import os
from typing import Dict, Any, Optional, List

# 将 Investment_Assistant 路径加入搜索路径
INVESTMENT_ASSISTANT_DIR = r"D:\Antigravity_Workspaces\Investment_Assistant"
if INVESTMENT_ASSISTANT_DIR not in sys.path:
    sys.path.insert(0, INVESTMENT_ASSISTANT_DIR)

_MODULES_CACHE = None


def _get_modules():
    """按需延迟加载计算库与策略模块。"""
    global _MODULES_CACHE
    if _MODULES_CACHE is None:
        import numpy as np
        import pandas as pd
        import pa_engine
        import strategy_layer
        import strategy_day
        import strategy_crypto

        _MODULES_CACHE = {
            "np": np,
            "pd": pd,
            "pa": pa_engine,
            "layer": strategy_layer,
            "day": strategy_day,
            "crypto": strategy_crypto,
        }
    return _MODULES_CACHE


def _normalize_df(df) -> Any:
    """规整 DataFrame 为 pa_engine 所需的大写 OHLCV 列与时间索引。"""
    mods = _get_modules()
    pd = mods["pd"]

    if df is None:
        return None

    if isinstance(df, list):
        if not df:
            return None
        d = pd.DataFrame(df)
    elif isinstance(df, pd.DataFrame):
        if df.empty:
            return None
        d = df.copy()
    else:
        return None

    col_map = {
        "Date": "Datetime",
        "date": "Datetime",
        "time": "Datetime",
        "Time": "Datetime",
        "datetime": "Datetime",
        "Datetime": "Datetime",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
    }
    for old_c, new_c in col_map.items():
        if old_c in d.columns and new_c not in d.columns:
            d = d.rename(columns={old_c: new_c})

    if "Datetime" in d.columns:
        d["Datetime"] = pd.to_datetime(d["Datetime"], errors="coerce")
        d = d.dropna(subset=["Datetime"]).sort_values("Datetime")
        d = d.set_index("Datetime")
    elif not isinstance(d.index, pd.DatetimeIndex):
        try:
            converted = pd.to_datetime(d.index, errors="coerce")
            if not converted.isna().all():
                d.index = converted
        except Exception:
            pass

    # 确保数值列为 float
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")

    d = d.dropna(subset=["Open", "High", "Low", "Close"])
    return d


def run_strategy_analysis(
    symbol: str,
    period: str = "1d",
    mode: str = "swing",
    df: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    运行 Investment_Assistant 完整交易策略矩阵并生成图表标注。
    
    返回字典包含:
      - summary: 道氏结构、波浪计数、200 EMA 状态、箱体状态、交易计划与 2.5R 盈亏比
      - annotations: markers (打标点), lines (水平线), boxes (矩形区域)
    """
    mods = _get_modules()
    pa = mods["pa"]
    layer = mods["layer"]
    day = mods["day"]
    pd = mods["pd"]
    np = mods["np"]

    # 1. 准备数据
    df_clean = _normalize_df(df)
    if df_clean is None or len(df_clean) < 10:
        clean_sym = symbol.upper()
        for prefix in ("US", "SH", "SZ", "HK", "BJ"):
            if clean_sym.startswith(prefix) and len(clean_sym) > len(prefix):
                clean_sym = clean_sym[len(prefix):]
                break
        csv_file = os.path.join(INVESTMENT_ASSISTANT_DIR, "data", f"{clean_sym}.csv")
        if os.path.exists(csv_file):
            try:
                local_df = pd.read_csv(csv_file)
                df_clean = _normalize_df(local_df)
            except Exception:
                pass

    if df_clean is None or len(df_clean) < 10:
        return {
            "symbol": symbol,
            "period": period,
            "mode": mode,
            "error": "有效K线数据不足以执行策略分析 (至少需要 10 根)",
            "summary": {},
            "annotations": {"markers": [], "lines": [], "boxes": []},
        }

    current_price = float(df_clean["Close"].iloc[-1])
    is_intraday = period in ("5m", "15m", "1h", "4h")

    # 2. 提取道氏波段拐点 (Swing High / Swing Low)
    order = 3 if len(df_clean) < 50 else (4 if is_intraday else 5)
    swings = pa.extract_swings(df_clean, order=order, confirmed_only=False)

    dow_bias_val = pa.dow_bias(swings, df_clean) if swings else 0
    dow_phase_desc = pa._determine_dow_phase(swings) if swings else "数据不足"

    # 3. 200 EMA 宏观门禁检查
    ema_200_gate = {"status": "HOLD", "trend": "Unknown", "value": None}
    if len(df_clean) >= 30:
        ema_span = min(200, len(df_clean))
        ema_series = df_clean["Close"].ewm(span=ema_span, adjust=False).mean()
        latest_ema = float(ema_series.iloc[-1])
        is_above_ema = current_price >= latest_ema
        ema_200_gate = {
            "status": "PASS" if is_above_ema else "WARN",
            "trend": f"价格在 {ema_span}EMA 之{'上 (多头走廊)' if is_above_ema else '下 (空头防御)'}",
            "value": round(latest_ema, 2),
        }

    # 4. 箱体状态机 (Consolidation Box)
    box_info = pa.detect_consolidation_box(df_clean, swings=swings)
    is_box = bool(box_info.get("is_box", box_info.get("is_in_box", False)))
    box_state = box_info.get("state", "NONE")
    box_high = box_info.get("box_high")
    box_low = box_info.get("box_low")
    box_detail = box_info.get("detail", box_state if box_state != "NONE" else "无明显箱体")
    box_summary = {
        "is_in_box": is_box,
        "state": box_state,
        "box_high": round(float(box_high), 2) if box_high is not None else None,
        "box_low": round(float(box_low), 2) if box_low is not None else None,
        "status": box_detail,
    }

    # 4b. 线性回归动态通道 (LRC / Price Channel)
    chan = pa.detect_price_channel(df_clean, swings=swings)
    chan_type = chan.get("channel_type", "horizontal")
    slope = float(chan.get("slope") or 0.0)
    chan_summary = {
        "channel_type": chan_type,
        "slope": round(slope, 4),
        "r_squared": round(float(chan.get("r_squared") or 0.0), 3),
        "upper_rail": round(float(chan.get("upper_rail")), 2) if chan.get("upper_rail") is not None else None,
        "mid_rail": round(float(chan.get("mid_rail")), 2) if chan.get("mid_rail") is not None else None,
        "lower_rail": round(float(chan.get("lower_rail")), 2) if chan.get("lower_rail") is not None else None,
        "channel_pos": round(float(chan.get("channel_pos") or 0.5), 2),
        "is_overbought": bool(chan.get("is_overbought", False)),
        "is_oversold": bool(chan.get("is_oversold", False)),
        "detail": chan.get("detail", ""),
    }

    # 5. 波浪理论客观状态与铁律证伪线
    wp_raw = pa.classify_wave_pattern(swings, df_clean) or {}
    wave_pos = pa.evaluate_wave_position(swings, df_clean, current_price) or {}
    wp = wave_pos.get("wave_pattern_detail") or wp_raw
    
    # 提取客观证伪价位 (浪4不侵入浪1顶 / 浪2不破浪1起点)
    w4_inv = wave_pos.get("wave4_invalidation_level")
    r1_inv = wave_pos.get("rule1_invalidation_level")
    
    invalidation_price = None
    invalidation_reason = "浪4不侵入浪1顶 / 浪2不破浪1起点"
    if w4_inv is not None:
        invalidation_price = round(float(w4_inv), 2)
        invalidation_reason = "浪4客观证伪线 (不破浪1顶)"
    elif r1_inv is not None:
        invalidation_price = round(float(r1_inv), 2)
        invalidation_reason = "浪2客观证伪线 (不破浪1起点)"
    elif wave_pos.get("reason"):
        invalidation_reason = str(wave_pos["reason"])[:24]

    wave_summary = {
        "pattern": wp.get("pattern") or wave_pos.get("wave_pattern") or "未形成清晰5浪/ABC结构",
        "current_wave": wp.get("summary") or wp.get("current_wave") or wave_pos.get("status") or "阶段未定",
        "invalidation_price": invalidation_price,
        "invalidation_reason": invalidation_reason,
        "points": [],
    }

    # 6. 构造交易计划 (带日内 8bps 摩擦扣减与 2.5R 硬门禁)
    trade_plan = {
        "direction": "观望",
        "entry": None,
        "stop_loss": None,
        "tp1": None,
        "tp2": None,
        "rr_ratio": 0.0,
        "passed_gates": False,
        "reasons": [],
    }

    med_range = pa.median_bar_range(df_clean)
    last_high_swings = [s for s in swings if s["type"] == "High"]
    last_low_swings = [s for s in swings if s["type"] == "Low"]

    if last_low_swings and last_high_swings:
        recent_low = last_low_swings[-1]["price"]
        recent_high = last_high_swings[-1]["price"]

        if dow_bias_val > 0 or (ema_200_gate["status"] == "PASS" and current_price > recent_low):
            # 多头计划
            entry = current_price
            stop_loss = round(recent_low - med_range * 0.8, 2)
            risk = entry - stop_loss
            if risk > 0:
                # 往返 8bps 摩擦扣除 (单边 3bps 滑点 + 1bps 规费)
                friction = entry * 0.0008
                effective_risk = risk + friction
                
                # 结构性目标优先 (如前高或箱顶)，若无则按 2.5R 硬门禁目标投影
                target_price = recent_high if recent_high > entry + 0.1 else (entry + effective_risk * 2.5)
                gross_reward = max(0.0, target_price - entry)
                net_reward = max(0.0, gross_reward - friction)
                rr = round(net_reward / max(0.01, effective_risk), 2)
                
                # 箱体阻力门禁拦截
                box_blocked = (is_box and box_state == "SWEEP_HIGH") or (is_box and box_high and current_price >= box_high * 0.98)
                passed = (rr >= 2.5) and not box_blocked

                tp1 = round(entry + effective_risk * 2.5, 2)
                tp2 = round(entry + effective_risk * 3.5, 2)

                reasons = [
                    f"道氏形态: {dow_phase_desc}",
                    f"200 EMA 审查: {ema_200_gate['trend']}",
                    f"净盈亏比 (已扣 8bps): {rr}R (>=2.5R 硬门禁: {'达成' if passed else '未达成或受阻'})",
                ]
                if box_blocked:
                    reasons.append(f"箱体警示: {box_detail}，拦截高位追多")

                trade_plan = {
                    "direction": "做多 (Long)" if passed else "观望",
                    "entry": round(entry, 2),
                    "stop_loss": stop_loss,
                    "tp1": tp1,
                    "tp2": tp2,
                    "rr_ratio": rr,
                    "passed_gates": passed,
                    "reasons": reasons,
                }
        elif dow_bias_val < 0 or (ema_200_gate["status"] == "WARN" and current_price < recent_high):
            # 空头计划 (美股严格非对称做空风控)
            entry = current_price
            stop_loss = round(recent_high + med_range * 0.8, 2)
            risk = stop_loss - entry
            if risk > 0:
                friction = entry * 0.0008
                effective_risk = risk + friction

                target_price = recent_low if recent_low < entry - 0.1 else (entry - effective_risk * 2.5)
                gross_reward = max(0.0, entry - target_price)
                net_reward = max(0.0, gross_reward - friction)
                rr = round(net_reward / max(0.01, effective_risk), 2)

                box_blocked = (is_box and box_state == "SWEEP_LOW") or (is_box and box_low and current_price <= box_low * 1.02)
                passed = (rr >= 2.5) and not box_blocked

                tp1 = round(entry - effective_risk * 2.5, 2)
                tp2 = round(entry - effective_risk * 3.5, 2)

                reasons = [
                    f"道氏形态: {dow_phase_desc}",
                    f"200 EMA 审查: {ema_200_gate['trend']}",
                    "做空风控: 严格对冲/日内交易，防轧空挤压",
                    f"净盈亏比: {rr}R (>=2.5R 硬门禁: {'达成' if passed else '未达成'})",
                ]
                if box_blocked:
                    reasons.append(f"箱体警示: {box_detail}，拦截低位追空")

                trade_plan = {
                    "direction": "做空 (Short 防御性)" if passed else "观望",
                    "entry": round(entry, 2),
                    "stop_loss": stop_loss,
                    "tp1": tp1,
                    "tp2": tp2,
                    "rr_ratio": rr,
                    "passed_gates": passed,
                    "reasons": reasons,
                }

    # 7. 打包生成前端 Lightweight Charts 标注
    markers = []
    lines = []
    boxes = []

    # (A) 拐点打标 (Dow Swings: HH, HL, LH, LL)
    for idx, sw in enumerate(swings[-30:]):  # 仅保留最近30个关键拐点防图表过密
        time_val = str(sw["time"])
        if len(time_val) > 10 and not is_intraday:
            time_val = time_val[:10]
        elif len(time_val) > 16:
            time_val = time_val[:16]

        is_high = sw["type"] == "High"
        dow_label = sw.get("dow", "H" if is_high else "L")
        color = "#10b981" if dow_label in ("HH", "HL") else ("#ef4444" if dow_label in ("LH", "LL") else "#3b82f6")

        markers.append({
            "id": f"swing_{idx}_{sw.get('index', idx)}",
            "time": time_val,
            "position": "aboveBar" if is_high else "belowBar",
            "color": color,
            "shape": "arrowDown" if is_high else "arrowUp",
            "text": dow_label,
        })

    # (B) 2B 假突破与结构转换标记 (MSS)
    mss_events = pa.detect_mss(swings, df_clean) if swings else []
    for idx, mss in enumerate(mss_events[-3:]):
        raw_t = mss.get("trigger_time") or mss.get("time") or ""
        time_val = str(raw_t)[:16 if is_intraday else 10]
        if not time_val:
            continue
        mss_type = str(mss.get("type", ""))
        is_bearish = "Bearish" in mss_type or "空翻" in mss_type
        markers.append({
            "id": f"mss_{idx}_{time_val}",
            "time": time_val,
            "position": "aboveBar" if is_bearish else "belowBar",
            "color": "#ef4444" if is_bearish else "#10b981",
            "shape": "square",
            "text": "MSS-空" if is_bearish else "MSS-多",
        })

    # 2B 假突破信号 (若处于箱体 SWEEP 状态或扫描到 2B)
    if is_box and box_state in ("SWEEP_HIGH", "SWEEP_LOW"):
        last_t = str(df_clean.index[-1])[:16 if is_intraday else 10]
        is_sweep_high = box_state == "SWEEP_HIGH"
        markers.append({
            "id": f"box_sweep_{last_t}",
            "time": last_t,
            "position": "aboveBar" if is_sweep_high else "belowBar",
            "color": "#ec4899",
            "shape": "arrowDown" if is_sweep_high else "arrowUp",
            "text": "2B假突破" if is_sweep_high else "2B假摔",
        })

    # (C) 水平线 PriceLines (入场点、止损点、TP1目标点、波浪证伪线)
    if trade_plan.get("entry"):
        lines.append({
            "id": "line_entry",
            "price": trade_plan["entry"],
            "color": "#3b82f6",
            "lineWidth": 2,
            "lineStyle": 0,  # Solid
            "title": f"入场: ${trade_plan['entry']:.2f}",
        })
    if trade_plan.get("stop_loss"):
        lines.append({
            "id": "line_sl",
            "price": trade_plan["stop_loss"],
            "color": "#ef4444",
            "lineWidth": 2,
            "lineStyle": 2,  # Dashed
            "title": f"止损: ${trade_plan['stop_loss']:.2f}",
        })
    if trade_plan.get("tp1"):
        lines.append({
            "id": "line_tp1",
            "price": trade_plan["tp1"],
            "color": "#10b981",
            "lineWidth": 2,
            "lineStyle": 2,  # Dashed
            "title": f"目标 TP1 ({trade_plan['rr_ratio']}R): ${trade_plan['tp1']:.2f}",
        })
    if wave_summary.get("invalidation_price"):
        lines.append({
            "id": "line_wave_inv",
            "price": wave_summary["invalidation_price"],
            "color": "#a855f7",
            "lineWidth": 2,
            "lineStyle": 2,  # Dashed
            "title": f"波浪证伪: ${wave_summary['invalidation_price']:.2f} ({wave_summary['invalidation_reason'][:14]})",
        })

    # (D) 矩形区域 Boxes (箱体震荡区)
    if box_summary.get("is_in_box") and box_summary.get("box_high") and box_summary.get("box_low"):
        # 时间跨度: 最近 20~30 根 K 线
        box_slice = df_clean.tail(min(35, len(df_clean)))
        t_start = str(box_slice.index[0])[:16 if is_intraday else 10]
        t_end = str(box_slice.index[-1])[:16 if is_intraday else 10]
        boxes.append({
            "id": "box_consolidation",
            "time1": t_start,
            "time2": t_end,
            "price1": float(box_summary["box_high"]),
            "price2": float(box_summary["box_low"]),
            "fillColor": "rgba(59, 130, 246, 0.12)",
            "borderColor": "#3b82f6",
            "label": f"箱体区间: [{box_summary['box_low']:.2f} - {box_summary['box_high']:.2f}]",
        })

    def _format_time_str(val) -> str:
        if val is None:
            return ""
        if isinstance(val, pd.Timestamp):
            return val.strftime("%Y-%m-%d %H:%M" if is_intraday else "%Y-%m-%d")
        s = str(val).strip()
        # 严格防御：纯数字整数行号如 '4213' 说明无实际时间索引，不能当作时间坐标下发前端
        if s.isdigit() and len(s) < 8:
            return ""
        if len(s) > 10 and not is_intraday:
            return s[:10]
        elif len(s) > 16:
            return s[:16]
        return s

    # (E) 动态价格通道 (Price Channel / LRC)
    channel_lines = []
    if chan and chan.get("upper_rail") is not None and chan.get("lower_rail") is not None:
        n_win = min(len(df_clean), 30)
        slice_df = df_clean.tail(n_win)
        t_start = _format_time_str(slice_df.index[0])
        t_end = _format_time_str(slice_df.index[-1])
        if not t_start or not t_end:
            if "date" in slice_df.columns:
                t_start = _format_time_str(slice_df["date"].iloc[0])
                t_end = _format_time_str(slice_df["date"].iloc[-1])
            elif "Date" in slice_df.columns:
                t_start = _format_time_str(slice_df["Date"].iloc[0])
                t_end = _format_time_str(slice_df["Date"].iloc[-1])

        # 只有两个端点的时间戳均有效时才生成通道线
        if t_start and t_end:
            upper_end = float(chan["upper_rail"])
            mid_end = float(chan["mid_rail"])
            lower_end = float(chan["lower_rail"])
            upper_start = round(upper_end - slope * (n_win - 1), 2)
            mid_start = round(mid_end - slope * (n_win - 1), 2)
            lower_start = round(lower_end - slope * (n_win - 1), 2)

            type_name = "上升通道" if chan_type == "ascending" else ("下降通道" if chan_type == "descending" else "动态通道")
            channel_lines = [
                {
                    "id": "chan_upper",
                    "time1": t_start,
                    "price1": upper_start,
                    "time2": t_end,
                    "price2": round(upper_end, 2),
                    "color": "#f59e0b",
                    "lineWidth": 1.5,
                    "lineStyle": "dashed",
                    "title": f"{type_name}上轨: ${upper_end:.2f}",
                },
                {
                    "id": "chan_mid",
                    "time1": t_start,
                    "price1": mid_start,
                    "time2": t_end,
                    "price2": round(mid_end, 2),
                    "color": "#94a3b8",
                    "lineWidth": 1.0,
                    "lineStyle": "dotted",
                    "title": f"中轴: ${mid_end:.2f}",
                },
                {
                    "id": "chan_lower",
                    "time1": t_start,
                    "price1": lower_start,
                    "time2": t_end,
                    "price2": round(lower_end, 2),
                    "color": "#10b981",
                    "lineWidth": 1.5,
                    "lineStyle": "dashed",
                    "title": f"{type_name}下轨: ${lower_end:.2f}",
                },
            ]

    # (F) 波浪理论结构标注与折线 (Wave Structure & Pivots)
    def _resolve_pt_time(pt, idx):
        t = _format_time_str(pt.get("time"))
        if not t and 0 <= idx < len(df_clean):
            t = _format_time_str(df_clean.index[idx])
        if not t and 0 <= idx < len(df_clean):
            if "date" in df_clean.columns:
                t = _format_time_str(df_clean["date"].iloc[idx])
            elif "Date" in df_clean.columns:
                t = _format_time_str(df_clean["Date"].iloc[idx])
        return t

    wave_annots = []
    wp_points = wp.get("wave_points") or {}
    if wp.get("pattern") == "corrective_abc" and all(k in wp_points for k in ("0", "A", "B", "C")):
        mapping = [
            ("0", "0", "#8b5cf6", "aboveBar" if wp_points["0"].get("type") == "High" else "belowBar"),
            ("A", "A", "#ef4444" if wp_points["A"].get("type") == "Low" else "#10b981", "belowBar" if wp_points["A"].get("type") == "Low" else "aboveBar"),
            ("B", "B", "#10b981" if wp_points["B"].get("type") == "High" else "#ef4444", "aboveBar" if wp_points["B"].get("type") == "High" else "belowBar"),
            ("C", "C", "#ef4444" if wp_points["C"].get("type") == "Low" else "#10b981", "belowBar" if wp_points["C"].get("type") == "Low" else "aboveBar"),
        ]
        for key, lbl, col, pos in mapping:
            pt = wp_points[key]
            idx = int(pt.get("index", 0))
            t_val = _resolve_pt_time(pt, idx)
            if t_val:
                wave_annots.append({
                    "key": key,
                    "label": f"浪{lbl}",
                    "short_label": lbl,
                    "time": t_val,
                    "price": round(float(pt["price"]), 2),
                    "color": col,
                    "pos": pos,
                    "type": pt.get("type", "High"),
                })
    elif wp_points:
        sorted_items = sorted(wp_points.items(), key=lambda x: int(x[1].get("index", 0)))
        for key, pt in sorted_items:
            idx = int(pt.get("index", 0))
            t_val = _resolve_pt_time(pt, idx)
            if t_val:
                is_high = pt.get("type") == "High"
                lbl = str(key)
                col = "#10b981" if is_high else "#ef4444"
                wave_annots.append({
                    "key": str(key),
                    "label": f"浪{lbl}",
                    "short_label": lbl,
                    "time": t_val,
                    "price": round(float(pt["price"]), 2),
                    "color": col,
                    "pos": "aboveBar" if is_high else "belowBar",
                    "type": pt.get("type", "High"),
                })
    else:
        # 未成型时兜底最近 5 个有效摆动拐点形成结构折线
        for idx_s, s in enumerate(swings[-5:]):
            idx = int(s.get("index", 0))
            t_val = _resolve_pt_time(s, idx)
            if t_val:
                is_high = s.get("type") == "High"
                dow_lbl = s.get("dow", f"P{idx_s+1}")
                col = "#10b981" if is_high else "#ef4444"
                wave_annots.append({
                    "key": str(idx_s),
                    "label": f"拐点 {dow_lbl}",
                    "short_label": dow_lbl,
                    "time": t_val,
                    "price": round(float(s["price"]), 2),
                    "color": col,
                    "pos": "aboveBar" if is_high else "belowBar",
                    "type": s.get("type", "High"),
                })

    wave_summary["points"] = [
        {"label": wa["label"], "price": wa["price"], "time": wa["time"]}
        for wa in wave_annots
    ]

    wave_lines = None
    if wave_annots:
        last_bar_time = str(df_clean.index[-1])[:16 if is_intraday else 10]
        wave_lines = {
            "id": "wave_structure",
            "pattern": wave_summary["pattern"],
            "color": "#8b5cf6",
            "lineWidth": 2.2,
            "points": [
                {
                    "time": wa["time"],
                    "price": wa["price"],
                    "label": wa["label"],
                    "color": wa["color"],
                }
                for wa in wave_annots
            ],
            "extension": {
                "time": last_bar_time,
                "price": current_price,
            },
        }

        # 将浪型标志加入 markers 渲染
        for wa in wave_annots:
            markers.append({
                "id": f"wave_{wa['key']}_{wa['time']}",
                "time": wa["time"],
                "position": wa["pos"],
                "color": wa["color"],
                "shape": "arrowDown" if wa["type"] == "High" else "arrowUp",
                "text": wa["label"],
            })

    return {
        "symbol": symbol,
        "period": period,
        "mode": mode,
        "current_price": current_price,
        "summary": {
            "dow_phase": dow_phase_desc,
            "dow_bias": dow_bias_val,
            "ema_200_gate": ema_200_gate,
            "box": box_summary,
            "channel": chan_summary,
            "wave": wave_summary,
            "trade_plan": trade_plan,
            "html_url": f"/api/strategy/html?symbol={symbol}&period={period}",
        },
        "annotations": {
            "markers": markers,
            "lines": lines,
            "boxes": boxes,
            "channel_lines": channel_lines,
            "wave_lines": wave_lines,
        },
    }


def generate_wave_chart_html(symbol: str, period: str = "1d", df: Optional[Any] = None) -> str:
    """
    调用 Investment_Assistant 高保真交互式波浪与通道分析引擎，
    生成与 plot_wave_chart 一致的单文件独立 HTML 页面。
    """
    mods = _get_modules()
    pd = mods["pd"]
    from pathlib import Path

    clean_sym = symbol.upper()
    for prefix in ("US", "SH", "SZ", "HK", "BJ"):
        if clean_sym.startswith(prefix) and len(clean_sym) > len(prefix):
            clean_sym = clean_sym[len(prefix):]
            break

    scripts_dir = os.path.join(INVESTMENT_ASSISTANT_DIR, "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    results_dir = os.path.join(INVESTMENT_ASSISTANT_DIR, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = Path(os.path.join(results_dir, f"{clean_sym}_wave_chart.html"))

    temp_csv = None
    data_dir = os.path.join(INVESTMENT_ASSISTANT_DIR, "data")
    local_csv = os.path.join(data_dir, f"{clean_sym}.csv")
    if os.path.exists(local_csv):
        temp_csv = Path(local_csv)

    df_norm = _normalize_df(df) if df is not None else None
    if df_norm is not None and not df_norm.empty:
        os.makedirs(data_dir, exist_ok=True)
        csv_file = os.path.join(data_dir, f"{clean_sym}.csv")
        df_norm.to_csv(csv_file)
        temp_csv = Path(csv_file)

    try:
        from plot_wave_chart import plot_wave_chart
        bars_count = len(df_norm) if df_norm is not None else 120
        plot_wave_chart(
            ticker=clean_sym,
            csv_path=temp_csv,
            output_path=out_path,
            lookback_bars=min(120, bars_count) if bars_count > 0 else 120,
        )
        if out_path.exists():
            with open(out_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{clean_sym} - 波浪分析报告</title>
    <style>body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 40px; background: #0f172a; color: #f8fafc; }}</style>
</head>
<body>
    <h2>{clean_sym} 波浪图表生成中</h2>
    <p style="color: #94a3b8;">{str(e)}</p>
</body>
</html>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{clean_sym} - 波浪图表</title></head>
<body style="font-family: sans-serif; padding: 30px;">
    <h3>未找到 {clean_sym} 的波浪图表文件</h3>
</body>
</html>"""
