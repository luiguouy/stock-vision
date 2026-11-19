# -*- coding: utf-8 -*-
"""
Investment_Assistant 交易策略适配器 (自包含核心 + 主图波浪报告融合 + If-Then条件剧本)
路径: stage_one/backend/strategy_adapter.py
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from symbols import strip_prefix, market_of
from time_window import predict_turn_windows

BASE_DIR = Path(__file__).resolve().parent
LOCAL_DATA_DIR = BASE_DIR / "data"

_MODULES_CACHE = None


def _get_modules() -> Dict[str, Any]:
    """按需延迟加载内置策略核心模块 (自包含于 strategy_core/)。"""
    global _MODULES_CACHE
    if _MODULES_CACHE is None:
        import numpy as np
        import pandas as pd

        try:
            from strategy_core import pa_engine, strategy_crypto, strategy_day, strategy_layer
        except ImportError as e:
            raise RuntimeError(f"无法加载内置策略核心模块 (strategy_core): {e}")

        _MODULES_CACHE = {
            "np": np,
            "pd": pd,
            "pa": pa_engine,
            "layer": strategy_layer,
            "day": strategy_day,
            "crypto": strategy_crypto,
        }
    return _MODULES_CACHE


def _normalize_df(df: Any) -> Any:
    """规整 DataFrame 为 pa_engine 所需的大写 OHLCV 列与时间索引。"""
    pd = _get_modules()["pd"]

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
        d = d.dropna(subset=["Datetime"]).sort_values("Datetime").set_index("Datetime")
    elif not isinstance(d.index, pd.DatetimeIndex):
        try:
            converted = pd.to_datetime(d.index, errors="coerce")
            if not converted.isna().all():
                d.index = converted
        except Exception:
            pass

    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce")

    return d.dropna(subset=["Open", "High", "Low", "Close"])


def _prepare_strategy_df(symbol: str, df: Optional[Any]) -> Any:
    """管道阶段 1：规整传入的 K 线数据，不足时读取本地 data/<SYMBOL>.csv 兜底。"""
    pd = _get_modules()["pd"]
    df_clean = _normalize_df(df)
    if df_clean is None or len(df_clean) < 10:
        clean_sym = strip_prefix(symbol)
        csv_file = LOCAL_DATA_DIR / f"{clean_sym}.csv"
        if csv_file.exists():
            try:
                df_clean = _normalize_df(pd.read_csv(csv_file))
            except Exception:
                pass
    return df_clean


def _evaluate_market_structure(
    pa: Any, df_clean: Any, current_price: float, is_intraday: bool, is_crypto: bool = False
) -> Dict[str, Any]:
    """管道阶段 2：计算道氏拐点、200 EMA、箱体、动态回归通道、波浪客观形态与道氏成交量结构。"""
    order = 3 if len(df_clean) < 50 else (4 if is_intraday else 5)
    swings = pa.extract_swings(df_clean, order=order, confirmed_only=False)
    conf_swings = [s for s in swings if s.get("confirmed", True)]
    dow_bias_val = pa.dow_bias(conf_swings, df_clean) if conf_swings else 0
    dow_phase_desc = pa._determine_dow_phase(conf_swings) if conf_swings else "数据不足"

    # 道氏成交量验证 (Dow Theory Volume Confirmation)
    dow_volume = (
        pa.analyze_dow_volume(df_clean, dow_bias=dow_bias_val)
        if hasattr(pa, "analyze_dow_volume")
        else {"status": "量能平稳正常", "description": "道氏量能常态", "volume_trend_aligned": True}
    )

    # 200 EMA 宏观门禁与全序列数据 (主图平滑线渲染)
    ema_200_gate: Dict[str, Any] = {"status": "HOLD", "trend": "Unknown", "value": None}
    ema_span = min(200, len(df_clean))
    ema200_series = df_clean["Close"].ewm(span=ema_span, adjust=False).mean()
    latest_ema = float(ema200_series.iloc[-1])
    is_above_ema = current_price >= latest_ema
    ema_200_gate = {
        "status": "PASS" if is_above_ema else "WARN",
        "trend": "站上 200EMA" if is_above_ema else "跌破 200EMA",
        "value": round(latest_ema, 2),
    }

    # 箱体状态机
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

    # 线性回归动态通道
    chan = pa.detect_price_channel(df_clean, swings=swings)
    c_type = chan.get("channel_type", "horizontal")
    slope_val = float(chan.get("slope") or 0.0)
    type_map = {"ascending": "上升通道", "descending": "下降通道", "horizontal": "水平通道"}
    c_type_cn = type_map.get(c_type, "动态通道")
    clean_chan_detail = f"{c_type_cn} (斜率 {slope_val:+.2f})"

    chan_summary = {
        "channel_type": c_type,
        "slope": round(slope_val, 4),
        "r_squared": round(float(chan.get("r_squared") or 0.0), 3),
        "upper_rail": round(float(chan["upper_rail"]), 2) if chan.get("upper_rail") is not None else None,
        "mid_rail": round(float(chan["mid_rail"]), 2) if chan.get("mid_rail") is not None else None,
        "lower_rail": round(float(chan["lower_rail"]), 2) if chan.get("lower_rail") is not None else None,
        "channel_pos": round(float(chan.get("channel_pos") or 0.5), 2),
        "is_overbought": bool(chan.get("is_overbought", False)),
        "is_oversold": bool(chan.get("is_oversold", False)),
        "detail": clean_chan_detail,
    }

    # 波浪客观状态与铁律证伪线 (支持加密/高波动下浪4浅刺容忍)
    # 使用已确认拐点做波浪判定，避免未确认拐点导致形态反复重绘；直接复用 evaluate_wave_position 的 wave_pattern_detail，避免重复计算
    wave_pos = pa.evaluate_wave_position(conf_swings, df_clean, current_price, allow_shallow_w4=is_crypto) or {}
    wp = wave_pos.get("wave_pattern_detail") or {}
    elliott_chan = wave_pos.get("elliott_channel") or {}

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

    WAVE_PATTERN_MAP = {
        "corrective_abc": "ABC 调整浪",
        "impulse": "5浪驱动结构",
        "impulse_5": "5浪驱动结构",
        "impulse_5_wave": "5浪驱动结构",
        "developing_wave_3": "第3浪推进中",
        "developing_wave_5": "第5浪推进中",
        "leading_diagonal": "引导楔形",
        "ending_diagonal": "终结楔形",
        "diagonal": "楔形结构",
        "triangle": "三角形调整浪",
        "flat": "平坦型调整浪",
        "zigzag": "之字型调整浪",
        "double_three": "双重三波调整",
        "triple_three": "三重三波调整",
    }
    raw_pattern = str(wp.get("pattern") or wave_pos.get("wave_pattern") or "")
    pattern_cn = WAVE_PATTERN_MAP.get(raw_pattern.lower(), raw_pattern) or "未形成清晰5浪/ABC结构"

    wave_summary = {
        "pattern": pattern_cn,
        "current_wave": wp.get("summary") or wp.get("current_wave") or wave_pos.get("status") or "阶段未定",
        "invalidation_price": invalidation_price,
        "invalidation_reason": invalidation_reason,
        "fib_projections": wave_pos.get("fib_projections") or {},
        "points": [],
    }

    # 缺口与价格失衡带
    gaps = pa.detect_gaps(df_clean) if len(df_clean) >= 5 else []

    return {
        "swings": swings,
        "conf_swings": conf_swings,
        "dow_bias": dow_bias_val,
        "dow_phase": dow_phase_desc,
        "dow_volume": dow_volume,
        "ema_200_gate": ema_200_gate,
        "ema200_series": ema200_series,
        "box_raw": {
            "is_box": is_box,
            "state": box_state,
            "high": box_high,
            "low": box_low,
            "detail": box_detail,
        },
        "box": box_summary,
        "chan_raw": chan,
        "channel": chan_summary,
        "elliott_channel": elliott_chan,
        "wp": wp,
        "wave": wave_summary,
        "gaps": gaps,
        "wave_pos": wave_pos,
    }


_DOW_MARKET_CACHE: Dict[str, Any] = {}


def _verify_us_market_dow(
    pa: Any,
    spy_df: Optional[Any] = None,
    qqq_df: Optional[Any] = None,
    iwm_df: Optional[Any] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    道氏理论宏观大势定性与指数相互验证 (SPY & QQQ & IWM 市场广度):
    现代美股实战映射：标普 500 指数 (SPY) 与 纳斯达克 100 指数 (QQQ) 必须处于上升趋势 (HH+HL) 且相互确认。
    引入罗素 2000 (IWM) 作为中小盘市场广度验证；若走势背离（如一涨一跌、一创新高另一未确认）或主趋势向下，禁止盲目做多。
    """
    global _DOW_MARKET_CACHE
    if not force_refresh and spy_df is None and qqq_df is None and iwm_df is None and _DOW_MARKET_CACHE:
        return _DOW_MARKET_CACHE

    s_clean = _normalize_df(spy_df) if spy_df is not None else _prepare_strategy_df("SPY", None)
    q_clean = _normalize_df(qqq_df) if qqq_df is not None else _prepare_strategy_df("QQQ", None)

    if s_clean is None or q_clean is None or len(s_clean) < 10 or len(q_clean) < 10:
        res = {
            "status": "PASS",
            "verified": True,
            "spy_phase": "未加载",
            "qqq_phase": "未加载",
            "iwm_phase": "未加载",
            "aligned": True,
            "description": "大盘指数数据未配置，按单标的结构研判",
            "desc": "大盘指数数据未配置，按单标的结构研判",
        }
        if spy_df is None and qqq_df is None and iwm_df is None:
            _DOW_MARKET_CACHE = res
        return res

    def _eval_index(df: Any) -> Tuple[str, bool, bool, float, float]:
        tail = df.tail(250) if len(df) >= 250 else df
        order = 5 if len(tail) < 120 else 8
        sw = pa.extract_swings(tail, order=order, confirmed_only=False)
        conf_sw = [s for s in sw if s.get("confirmed", True)]
        phase = pa._determine_dow_phase(conf_sw) if conf_sw else "数据不足"
        bias = pa.dow_bias(conf_sw, tail) if conf_sw else 0
        c = float(tail["Close"].iloc[-1])
        span_len = min(200, len(tail))
        ema = float(tail["Close"].ewm(span=span_len, adjust=False).mean().iloc[-1])
        lookback = min(20, len(tail) - 1)
        prev_c = float(tail["Close"].iloc[-lookback]) if lookback > 0 else c

        has_bull = (bias > 0 or "多头" in phase or "偏多" in phase)
        has_bear = (bias < 0 or "空头" in phase or "偏空" in phase)

        # 道氏上升趋势 (HH+HL): 结构抬升或在结构未走坏(无偏空/空头)时价格稳站200EMA且中短期均线上行
        is_bull = bool(
            not has_bear
            and (has_bull or (c >= ema and c >= prev_c))
            and c >= ema * 0.98
        )
        # 道氏下降趋势 (LH+LL) 或深度破位200 EMA
        is_bear = bool(
            (has_bear or (c < ema * 0.95 and c < prev_c))
            and not is_bull
        )
        return phase, is_bull, is_bear, c, ema

    spy_phase, spy_bull, spy_bear, sc, sema = _eval_index(s_clean)
    qqq_phase, qqq_bull, qqq_bear, qc, qema = _eval_index(q_clean)

    # 补充 IWM 广度校验 (若调用方显式提供了 spy_df/qqq_df 且未传 iwm_df，不回退加载本地文件以保持测试/调用方隔离)
    i_clean = _normalize_df(iwm_df) if iwm_df is not None else (_prepare_strategy_df("IWM", None) if (spy_df is None and qqq_df is None) else None)
    iwm_phase, iwm_bear = "未加载", False
    if i_clean is not None and len(i_clean) >= 10:
        iwm_phase, _, iwm_bear, _, _ = _eval_index(i_clean)

    if spy_bull and qqq_bull:
        if iwm_bear:
            status = "BREADTH_DIVERGENCE"
            verified = True
            aligned = False
            desc = f"道氏市场广度背离预警：SPY/QQQ 走强但罗素2000 (IWM, {iwm_phase}) 偏空，警惕权重股独涨风险，建议缩减仓位。"
        else:
            status = "PASS"
            verified = True
            aligned = True
            desc = f"道氏大盘指数相互验证通过：标普500 (SPY, {spy_phase}) 与 纳指100 (QQQ, {qqq_phase}) 同步上升 (HH+HL)，IWM({iwm_phase}) 广度配合，大势顺风允许做多。"
    elif (spy_bull and not qqq_bull) or (qqq_bull and not spy_bull):
        status = "DIVERGENCE"
        verified = False
        aligned = False
        desc = f"道氏大盘指数背离预警：SPY（{spy_phase}）与 QQQ（{qqq_phase}）未同步确认（市场广度分化背离），禁止盲目追高做多。"
    else:
        status = "BEAR"
        verified = False
        aligned = True
        desc = f"道氏大盘主趋势向下：SPY（{spy_phase}）与 QQQ（{qqq_phase}）均处于下降趋势（LH+LL）或破位均线，禁止在主趋势向下时盲目做多。"

    res = {
        "status": status,
        "verified": verified,
        "spy_phase": spy_phase,
        "qqq_phase": qqq_phase,
        "iwm_phase": iwm_phase,
        "aligned": aligned,
        "description": desc,
        "desc": desc,
    }
    if spy_df is None and qqq_df is None and iwm_df is None:
        _DOW_MARKET_CACHE = res
    return res


def _build_trade_plan(
    pa: Any,
    df_clean: Any,
    current_price: float,
    struct: Dict[str, Any],
    turn_windows_res: Dict[str, Any],
    is_crypto: bool = False,
    is_us: bool = True,
    dow_market_ver: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """管道阶段 3：构建动态多级止损锚点池、顺势扩展分级止盈、道氏成交量验证与严苛条件挂单剧本的交易计划。"""
    crypto_mod = _get_modules()["crypto"]

    trade_plan: Dict[str, Any] = {
        "direction": "观望",
        "entry": round(current_price, 2),
        "stop_loss": None,
        "stop_loss_reason": "未触发有效交易方向",
        "tp1": None,
        "tp1_source": None,
        "tp2": None,
        "tp2_source": None,
        "tp_source": None,
        "rr_ratio": 0.0,
        "passed_gates": False,
        "reasons": [],
        "dow_volume_status": "量能平稳正常",
        "condition_playbook": None,
        "escape_level": None,
        "escape_reason": None,
        "wave_setup": None,
        "dow_market_verification": dow_market_ver,
    }

    swings = struct["swings"]
    conf = struct.get("conf_swings") or [s for s in swings if s.get("confirmed", True)]
    conf_highs = [s for s in conf if s["type"] == "High"]
    conf_lows = [s for s in conf if s["type"] == "Low"]

    last_high_swings = conf_highs if conf_highs else [s for s in swings if s["type"] == "High"]
    last_low_swings = conf_lows if conf_lows else [s for s in swings if s["type"] == "Low"]
    conf_swings = conf if (conf_highs and conf_lows) else swings
    if not last_low_swings or not last_high_swings:
        return trade_plan

    med_range = pa.median_bar_range(df_clean)
    if med_range <= 0:
        med_range = current_price * 0.015

    recent_low = float(last_low_swings[-1]["price"])
    recent_high = float(last_high_swings[-1]["price"])
    dow_bias_val = struct["dow_bias"]
    dow_phase_desc = struct["dow_phase"]
    ema_200_gate = struct["ema_200_gate"]
    box = struct["box_raw"]
    chan = struct["channel"]
    wp = struct["wp"]
    wave_summary = struct["wave"]
    wave_pos = struct.get("wave_pos") or {}
    elliott_chan = struct.get("elliott_channel") or {}
    dow_vol = struct.get("dow_volume") or {}
    dow_vol_status = dow_vol.get("status", "量能平稳正常")

    # 最小风险报酬比门禁：加密货币 2.0R，标准资产 2.5R
    min_rr_gate = 2.0 if is_crypto else 2.5
    # 防守止损波动率缓冲：加密宽幅防插针 1.4x ATR/bar_rng，标准资产 0.6x bar_rng
    base_sl_buffer = round(1.4 * med_range if is_crypto else 0.6 * med_range, 2)

    fib_proj = wave_summary.get("fib_projections") or {}
    raw_pat = str(wp.get("pattern") or wave_pos.get("wave_pattern") or "").lower()
    inv_p = wave_summary.get("invalidation_price")
    inv_r = wave_summary.get("invalidation_reason", "波浪客观失效位")
    baseline_val = elliott_chan.get("baseline_val")
    pts = wp.get("wave_points") or {}

    is_bull = (
        dow_bias_val > 0
        or (ema_200_gate["status"] == "PASS" and current_price > recent_low)
        or bool(wp.get("is_valid_impulse") and wp.get("direction") == 1)
        or (raw_pat in ("developing_wave_3", "developing_wave_5", "impulse_5_wave") and wp.get("direction") == 1)
    )

    def _get_pt_p(key: Any) -> Optional[float]:
        if key in pts and isinstance(pts[key], dict):
            return float(pts[key].get("price", 0))
        if str(key) in pts and isinstance(pts[str(key)], dict):
            return float(pts[str(key)].get("price", 0))
        return None

    # 大盘宏观门禁（仅美股非加密标的启用）
    macro_filter_passed = True
    if is_us and not is_crypto and dow_market_ver:
        macro_filter_passed = bool(dow_market_ver.get("verified", True))

    if is_bull:
        entry = current_price

        # 判断具体波浪形态位置（买点1：第2浪回调 / 买点2：第4浪浅调 / 道氏顺势低吸）
        is_wave2 = (
            ("developing_wave_3" in raw_pat or "wave_3" in raw_pat)
            and _get_pt_p(0) is not None
            and _get_pt_p(1) is not None
        )
        is_wave4 = (
            ("developing_wave_5" in raw_pat or "impulse_5" in raw_pat)
            and _get_pt_p(1) is not None
            and _get_pt_p(3) is not None
        )
        is_wave_abc = ("corrective_abc" in raw_pat or "abc" in raw_pat)

        buy_point_type = "道氏顺势低吸"
        buy_point_desc = "道氏主要趋势向上 (HH+HL)，等待次要趋势缩量回踩至 0.500/0.618 斐波那契回撤位企稳低吸"
        wave_stage_name = "道氏主趋势推进"
        stop_loss = None
        stop_loss_reason = ""
        target_price = None
        tp_source = ""
        tp2_val = None
        tp2_source = ""
        escape_level = recent_low
        escape_reason = f"击穿道氏结构前低波谷 (${recent_low:.2f})，上升趋势破坏，全额清仓离场"

        # -------------------------------------------------------------
        # 买点 1（第 2 浪回调）
        # -------------------------------------------------------------
        if is_wave2:
            p0 = _get_pt_p(0)
            p1 = _get_pt_p(1)
            p2 = _get_pt_p(2)
            l1 = max(0.01, p1 - p0)
            fib_500 = round(p1 - 0.500 * l1, 2)
            fib_618 = round(p1 - 0.618 * l1, 2)
            p2_ref = p2 if p2 is not None else fib_500

            buy_point_type = "买点1 (第2浪回调)"
            buy_point_desc = (
                f"第1浪放量上攻后缩量回踩，点位锁定在第1浪 0.500 (${fib_500:.2f}) 或 0.618 (${fib_618:.2f}) "
                f"斐波那契回撤位，止损设在第1浪起点 (${p0:.2f}) 下方（绝对铁律：2浪不破1浪底）"
            )
            wave_stage_name = "第2浪回调蓄势 / 第3浪初期推进"
            stop_loss = round(p0 - base_sl_buffer, 2)
            stop_loss_reason = f"买点1（第2浪回调）：绝对铁律2浪不破1浪底 (${p0:.2f}) 支撑外加防守缓冲 ${base_sl_buffer:.2f}"

            ext_1618 = round(p2_ref + 1.618 * l1, 2)
            target_price = ext_1618
            tp_source = f"卖点1（第3浪兑现）：冲击1-2临时通道上轨/第1浪1.618x (${target_price:.2f}) 处高抛减半(50%)，剩余仓位推保本损"
            tp2_val = round(p2_ref + 2.618 * l1, 2)
            tp2_source = f"卖点2（第3浪强势扩展）：第1浪2.618x (${tp2_val:.2f}) 极值斐波扩展位"
            escape_level = round(p0, 2)
            escape_reason = f"跌破第1浪起点 (${p0:.2f})，绝对铁律证伪原数浪形态，全额清仓离场"

        # -------------------------------------------------------------
        # 买点 2（第 4 浪浅调）
        # -------------------------------------------------------------
        elif is_wave4:
            p0 = _get_pt_p(0)
            p1 = _get_pt_p(1)
            p2 = _get_pt_p(2)
            p3 = _get_pt_p(3)
            p4 = _get_pt_p(4)
            l1 = max(0.01, p1 - (p0 if p0 is not None else (p1 - med_range * 3.0)))
            l3 = max(0.01, p3 - (p2 if p2 is not None else (p3 - med_range * 4.0)))
            fib_382 = round(p3 - 0.382 * l3, 2)
            fib_236 = round(p3 - 0.236 * l3, 2)
            p4_ref = p4 if p4 is not None else fib_382

            buy_point_type = "买点2 (第4浪浅调)"
            buy_point_desc = (
                f"第3浪放量主升后横盘洗盘（成交量萎缩），点位锁定在第3浪 0.382 (${fib_382:.2f}) 或 0.236 (${fib_236:.2f}) "
                f"浅调位（或前低一级第4浪区间终点），止损设在第1浪顶 (${p1:.2f}) 下方"
            )
            wave_stage_name = "第4浪浅调洗盘 / 第5浪冲顶推进"
            stop_loss = round(p1 - base_sl_buffer, 2)
            stop_loss_reason = f"买点2（第4浪浅调）：波浪客观铁律浪4不破浪1顶 (${p1:.2f}) 支撑外加防守缓冲 ${base_sl_buffer:.2f}"

            eq_target = round(p4_ref + 1.000 * l1, 2)
            target_price = eq_target if eq_target > entry + 0.5 * med_range else round(p4_ref + 0.618 * (p3 - (p0 if p0 else (p2 if p2 else entry))), 2)
            tp_source = f"卖点1（第5浪等长冲顶兑现）：1.000x浪1等长测算位 (${target_price:.2f}) 处高抛减半(50%)，余仓推保本损"
            tp2_cand = round(p4_ref + 0.618 * (p3 - (p0 if p0 else (p2 if p2 else entry))), 2)
            tp2_val = tp2_cand if tp2_cand > target_price else round(target_price + 1.0 * med_range, 2)
            tp2_source = f"卖点2（第5浪极值冲顶）：1-3浪0.618扩展/2-4主通道上轨 (${tp2_val:.2f}) 高抛止盈"
            esc_p = baseline_val if baseline_val else (p4 if p4 else recent_low)
            escape_level = round(float(esc_p), 2)
            escape_reason = f"终极逃顶卖点：放量跌穿 2-4 主通道基线 (${escape_level:.2f}) 或道氏前低，全额清仓离场"

        # -------------------------------------------------------------
        # ABC 调整浪末端低吸
        # -------------------------------------------------------------
        elif is_wave_abc:
            p0 = _get_pt_p(0) or _get_pt_p("0")
            pa_p = _get_pt_p("A")
            pb_p = _get_pt_p("B")
            pc_p = _get_pt_p("C")
            c_bot = pc_p if pc_p is not None else recent_low

            buy_point_type = "ABC调整浪末端低吸"
            buy_point_desc = f"ABC三浪调整完毕（C浪终点 ${c_bot:.2f} 企稳），次要趋势修正结束，顺大势做多"
            wave_stage_name = "ABC调整末段 / 新浪潮启动"
            stop_loss = round(c_bot - base_sl_buffer, 2)
            stop_loss_reason = f"ABC调整浪C浪底 (${c_bot:.2f}) 支撑外加防守缓冲 ${base_sl_buffer:.2f}"
            target_price = round(pb_p if (pb_p and pb_p > entry + 1.0 * med_range) else (entry + 1.618 * med_range), 2)
            tp_source = f"卖点1（次级反弹兑现）：B浪反弹高点/斐波位 (${target_price:.2f}) 处高抛减半(50%)，余仓推保本损"
            tp2_val = round(max((p0 if p0 else target_price), target_price + 1.0 * med_range), 2)
            tp2_source = f"卖点2（新驱动浪推进）：前期大波段起点 (${tp2_val:.2f})"
            escape_level = round(c_bot, 2)
            escape_reason = f"跌破 ABC 调整浪底 (${escape_level:.2f})，反弹形态失效全额清仓离场"

        # -------------------------------------------------------------
        # 道氏上升趋势通用顺势低吸 (Dow Trend Setup)
        # -------------------------------------------------------------
        else:
            anchors_below = []
            if inv_p is not None and 0 < inv_p < entry:
                anchors_below.append((inv_p, inv_r, 1))
            if baseline_val is not None and 0 < baseline_val < entry:
                ch_label = "艾略特2-4主通道基线支撑" if "2-4" in elliott_chan.get("channel_stage", "") else "艾略特1-2通道基线支撑"
                anchors_below.append((baseline_val, ch_label, 2))
            lower_rail = chan.get("lower_rail")
            if lower_rail is not None and 0 < lower_rail < entry:
                anchors_below.append((lower_rail, "动态回归通道下轨支撑", 3))
            ema_val = ema_200_gate.get("value")
            if ema_val is not None and 0 < ema_val < entry:
                anchors_below.append((ema_val, "200日均线 (200EMA) 支撑", 4))
            anchors_below.append((recent_low, "道氏结构前低波谷支撑", 5))

            close_anchors = [a for a in anchors_below if (entry - a[0]) <= 4.0 * med_range]
            chosen = close_anchors[0] if close_anchors else anchors_below[0]
            anchor_price, anchor_desc, _ = chosen
            stop_loss = round(anchor_price - base_sl_buffer, 2)
            stop_loss_reason = f"{anchor_desc} (${anchor_price:.2f}) 结构外加防守缓冲 ${base_sl_buffer:.2f}"

            if is_crypto:
                impulse_leg = max(recent_high - recent_low, med_range * 2.0)
                fib_ext_1618 = round(recent_low + 1.618 * impulse_leg, 2)
                if recent_high > entry + 1.5 * (entry - stop_loss):
                    target_price = recent_high
                    tp_source = "冲量波段前高结构阻力 (Peak)"
                    tp2_val = max(fib_ext_1618, round(recent_high + 0.618 * impulse_leg, 2))
                    tp2_source = "加密顺势 1.618x 斐波那契扩展位"
                else:
                    target_price = fib_ext_1618
                    tp_source = "加密顺势 1.618x 斐波那契扩展位 (规避即时未确认极值)"
                    tp2_val = round(recent_high + 0.618 * impulse_leg, 2)
                    tp2_source = "加密顺势 2.0x+ 斐波那契扩展位"
            else:
                if recent_high >= entry + 1.5 * (entry - stop_loss):
                    target_price = recent_high
                    tp_source = "道氏前期显著波峰阻力"
                    tp2_val = round(recent_high + 1.0 * med_range, 2)
                    tp2_source = "顺势扩展目标"
                else:
                    forward_ext = round(entry + 1.618 * max(med_range * 2.0, recent_high - recent_low), 2)
                    target_price = forward_ext
                    tp_source = "顺势 1.618x 斐波那契扩展位 (规避即时未确认极值)"
                    tp2_val = round(entry + 2.618 * max(med_range * 2.0, recent_high - recent_low), 2)
                    tp2_source = "顺势 2.618x 斐波那契扩展位"
            escape_level = round(recent_low, 2)
            escape_reason = f"击穿道氏结构前低波谷 (${recent_low:.2f})，上升结构破坏，全额清仓离场"

        # 加密货币 2B 扫损极值专属优先覆盖
        if is_crypto and hasattr(crypto_mod, "check_recent_crypto_2b_sweep"):
            sweep_info = crypto_mod.check_recent_crypto_2b_sweep(df_clean, side=1, swings=conf_swings, bar_rng=med_range)
            if sweep_info.get("detected"):
                stop_loss = round(float(sweep_info["stop_loss"]), 2)
                stop_loss_reason = sweep_info["desc"]

        risk = entry - stop_loss
        if risk <= 0:
            stop_loss = round(entry - base_sl_buffer, 2)
            risk = entry - stop_loss

        friction = entry * 0.0008
        effective_risk = max(0.01, risk + friction)

        if tp2_val is None:
            tp2_val = round(target_price + 1.0 * med_range, 2)
            tp2_source = "顺势扩展目标"

        net_reward = max(0.0, target_price - entry - friction)
        rr = round(net_reward / max(0.01, effective_risk), 2)

        # 多头防追高与衰竭门禁 (Anti-Chase Long Guard)
        chan_pos = float(chan.get("channel_pos") if chan.get("channel_pos") is not None else 0.5)
        anti_chase_blocked = False
        anti_chase_reason = ""

        if chan.get("is_overbought", False) or chan_pos >= 0.85:
            anti_chase_blocked = True
            anti_chase_reason = f"触及通道动态上轨极值超买区 (pos={chan_pos:.2f})，警惕冲高回落/严禁高位追多"
        elif ("developing_wave_3" in raw_pat or "wave_3" in raw_pat) and "2.618" in fib_proj and current_price >= float(fib_proj["2.618"]) * 0.99:
            anti_chase_blocked = True
            anti_chase_reason = f"多头第3浪已触及 2.618x 极值延展位 (${float(fib_proj['2.618']):.2f})，多头动能过度透支，严禁追多"

        box_blocked = (box["is_box"] and box["state"] == "SWEEP_HIGH") or (
            box["is_box"] and box["high"] and current_price >= box["high"] * 0.98
        )

        # 通道与逃顶破位硬防守 (Channel Breakdown & Escape Rule)
        channel_broken = bool(elliott_chan.get("channel_stage") == "2-4_primary" and elliott_chan.get("trend_broken"))
        escape_triggered = bool(escape_level and current_price < escape_level)

        passed = (
            (rr >= min_rr_gate)
            and not box_blocked
            and not anti_chase_blocked
            and macro_filter_passed
            and not channel_broken
            and not escape_triggered
        )

        # 构建高抛低吸执行梯次 (Sell Stages Ladder)
        sell_stages = [
            {
                "stage": "TP1",
                "name": "卖点1 (TP1 减半)",
                "action": "高抛减半 (50%) · 剩余推保本",
                "target": round(target_price, 2),
                "basis": tp_source,
            },
            {
                "stage": "TP2",
                "name": "卖点2 (TP2 目标)",
                "action": "冲顶高抛止盈",
                "target": round(tp2_val, 2),
                "basis": tp2_source,
            },
            {
                "stage": "EXIT",
                "name": "终极逃顶卖点",
                "action": "全额清仓离场",
                "target": round(escape_level, 2),
                "basis": escape_reason,
            },
        ]

        wave_setup = {
            "buy_point_type": buy_point_type,
            "buy_point_desc": buy_point_desc,
            "wave_stage": wave_stage_name,
            "sell_stages": sell_stages,
            "escape_level": round(escape_level, 2),
            "escape_reason": escape_reason,
        }

        reasons = []
        if dow_market_ver and is_us and not is_crypto:
            reasons.append(f"道氏大盘：{dow_market_ver['description']}")
        reasons.extend([
            f"道氏结构：{dow_phase_desc}",
            f"波浪定位：{buy_point_type} ({wave_stage_name})",
            f"均线过滤：{ema_200_gate['trend']}" + (f" (${ema_200_gate['value']})" if ema_200_gate.get('value') else ""),
            f"盈亏比：{rr}R" + (f"（达标 >={min_rr_gate}R）" if (rr >= min_rr_gate) else f"（真实空间不足，低于 {min_rr_gate}R 门禁）"),
            f"道氏量能：{dow_vol_status}" + (f" - {dow_vol['description']}" if dow_vol.get("description") else ""),
            f"防守依据：{stop_loss_reason}",
            f"止盈依据：{tp_source}",
            f"逃顶依据：{escape_reason}",
        ])
        if box_blocked:
            reasons.append(f"箱体警示: {box['detail']}")
        if anti_chase_blocked:
            reasons.append(f"风控拦截：{anti_chase_reason}")
        if channel_broken:
            reasons.append(f"通道破位拦截：价格已跌穿 2-4 主通道基线 (${baseline_val:.2f})，宣告驱动浪终结，全额清仓离场。")
        if escape_triggered:
            reasons.append(f"逃顶清仓警报：现价 (${current_price:.2f}) 跌破逃顶位 (${escape_level:.2f})，严禁做多。")
        if not macro_filter_passed and dow_market_ver:
            reasons.append(f"宏观过滤器拦截：{dow_market_ver['description']}")

        tp1_val = round(target_price, 2)
        dir_label = "做多 (Long)" if passed else "观望"
        dir_mode = "WAIT" if (not macro_filter_passed and dow_market_ver) else "LONG"

        # 多头场景买卖点结构化定义
        down_span = max(recent_high - recent_low, med_range * 2.0)
        ema_val = float(ema_200_gate.get("value") or (recent_low - med_range))

        buy_triggers = {
            "aggressive": {
                "name": "激进波段买点 (顺势低吸)",
                "condition": f"次级趋势缩量回踩至 0.500~0.618 斐波那契回撤位企稳低吸（{buy_point_type}），守关键波段起点不破",
                "price_range": [round(entry - 0.5 * med_range, 2), round(entry, 2)],
                "price_range_text": f"${round(entry - 0.5 * med_range, 2):.2f} ~ ${entry:.2f}",
                "stop_loss": stop_loss,
                "stop_loss_text": f"${stop_loss:.2f} ({stop_loss_reason})",
                "target": round(target_price, 2),
                "target_text": f"${round(target_price, 2):.2f} (第一目标位)",
            },
            "conservative": {
                "name": "稳健趋势买点 (放量突破加仓)",
                "condition": f"放量突破前高波峰 (${recent_high:.2f}) 并站稳，大盘双指数相互印证顺风时顺势跟进",
                "price_range": [round(recent_high, 2), round(recent_high + 0.5 * med_range, 2)],
                "price_range_text": f"${recent_high:.2f} ~ ${round(recent_high + 0.5 * med_range, 2):.2f}",
                "stop_loss": round(entry - base_sl_buffer, 2),
                "stop_loss_text": f"${round(entry - base_sl_buffer, 2):.2f} (假突破止损)",
                "target": round(tp2_val, 2),
                "target_text": f"${round(tp2_val, 2):.2f} (极值扩展目标位)",
            },
        }

        sell_triggers = {
            "rebound_sell": {
                "name": "多头分级兑现与止盈区",
                "resistance_zone_1": {
                    "label": "第一兑现区 (TP1)",
                    "price_range": [round(target_price * 0.99, 2), round(target_price, 2)],
                    "price_range_text": f"${round(target_price * 0.99, 2):.2f} ~ ${round(target_price, 2):.2f}",
                    "basis": tp_source,
                },
                "resistance_zone_2": {
                    "label": "冲顶延伸区 (TP2)",
                    "price_range": [round(tp2_val * 0.99, 2), round(tp2_val, 2)],
                    "price_range_text": f"${round(tp2_val * 0.99, 2):.2f} ~ ${round(tp2_val, 2):.2f}",
                    "basis": tp2_source,
                },
            },
            "take_profit": {
                "tp1": {
                    "price": round(target_price, 2),
                    "price_text": f"${round(target_price, 2):.2f}",
                    "label": "第一止盈目标 TP1",
                    "basis": tp_source,
                },
                "tp2": {
                    "price": round(tp2_val, 2),
                    "price_text": f"${round(tp2_val, 2):.2f}",
                    "label": "第二止盈目标 TP2",
                    "basis": tp2_source,
                },
            },
            "breakdown_stop": {
                "long_clear_line": {
                    "price": round(escape_level, 2),
                    "price_text": f"${round(escape_level, 2):.2f}",
                    "label": "多单无条件清仓线",
                    "basis": escape_reason,
                },
                "short_stop_line": {
                    "price": round(recent_high + base_sl_buffer, 2),
                    "price_text": f"${round(recent_high + base_sl_buffer, 2):.2f}",
                    "label": "空头防守分水岭",
                    "basis": "多头强劲推进，严禁左侧做空",
                },
            },
        }

        trade_plan = {
            "direction": dir_label,
            "direction_mode": dir_mode,
            "entry": round(entry, 2),
            "stop_loss": stop_loss,
            "stop_loss_reason": stop_loss_reason,
            "tp1": tp1_val,
            "tp1_source": tp_source,
            "tp2": tp2_val,
            "tp2_source": tp2_source,
            "tp_source": tp_source,
            "rr_ratio": rr,
            "passed_gates": passed,
            "reasons": reasons,
            "dow_volume_status": dow_vol_status,
            "condition_playbook": None,
            "escape_level": round(escape_level, 2),
            "escape_reason": escape_reason,
            "wave_setup": wave_setup,
            "sell_stages": sell_stages,
            "dow_market_verification": dow_market_ver,
            "buy_triggers": buy_triggers,
            "sell_triggers": sell_triggers,
        }

        # -------------------------------------------------------------
        # 3. 严苛 If-Then 条件挂单剧本 (Buy the Dip: 黄金回撤共振与波浪低吸)
        # -------------------------------------------------------------
        if not passed:
            tight_buf = 0.35 * med_range if is_crypto else 0.5 * med_range

            if is_wave2:
                p0 = _get_pt_p(0)
                p1 = _get_pt_p(1)
                l1 = max(0.01, p1 - p0)
                fib_500 = round(p1 - 0.500 * l1, 2)
                fib_618 = round(p1 - 0.618 * l1, 2)
                cond_entry = round(fib_500 if current_price > fib_500 else (fib_618 if current_price > fib_618 else current_price - 0.5 * med_range), 2)
                cond_sl = round(p0 - tight_buf, 2)
                cond_risk = cond_entry - cond_sl
                if cond_risk <= 0:
                    cond_sl = round(cond_entry - 0.8 * med_range, 2)
                    cond_risk = cond_entry - cond_sl
                cond_tp1 = tp1_val
                cond_tp2 = tp2_val
                cond_rr = round((cond_tp1 - cond_entry) / max(0.01, cond_risk), 2)
                playbook_name = "买点1: 第2浪回调低吸剧本"
                playbook_cond = f"等待第1浪放量上攻后缩量回踩，在 0.500 (${fib_500:.2f}) - 0.618 (${fib_618:.2f}) 斐波那契回撤带企稳"
                playbook_notes = (
                    f"斐波那契 0.500-0.618 黄金分割回撤共振带（${fib_618:.2f}-${fib_500:.2f}），绝对铁律2浪不破1浪底；"
                    f"达到 1.618x (${cond_tp1:.2f}) 高抛减半(50%)推保本损，达到 2.618x (${cond_tp2:.2f}) 极值结清，"
                    f"跌破浪1起点 (${p0:.2f}) 全额清仓"
                )
            elif is_wave4:
                p1 = _get_pt_p(1)
                p2 = _get_pt_p(2)
                p3 = _get_pt_p(3)
                l3 = max(0.01, p3 - (p2 if p2 is not None else (p3 - med_range * 4.0)))
                fib_382 = round(p3 - 0.382 * l3, 2)
                fib_236 = round(p3 - 0.236 * l3, 2)
                if current_price > fib_236:
                    cond_entry = fib_236
                elif current_price > fib_382:
                    cond_entry = fib_382
                else:
                    cond_entry = round(current_price - 0.5 * med_range, 2)
                cond_sl = round(p1 - tight_buf, 2)
                cond_risk = cond_entry - cond_sl
                if cond_risk <= 0:
                    cond_sl = round(cond_entry - 0.8 * med_range, 2)
                    cond_risk = cond_entry - cond_sl
                cond_tp1 = tp1_val
                cond_tp2 = tp2_val
                cond_rr = round((cond_tp1 - cond_entry) / max(0.01, cond_risk), 2)
                playbook_name = "买点2: 第4浪浅调低吸剧本"
                playbook_cond = f"等待第3浪主升后横盘洗盘缩量回抽，在 0.382 (${fib_382:.2f}) - 0.236 (${fib_236:.2f}) 浅调支撑位企稳"
                playbook_notes = (
                    f"斐波那契 0.382/0.236 浅调支撑带（${fib_382:.2f}-${fib_236:.2f}），守浪1顶 (${p1:.2f}) 不入；"
                    f"达第5浪冲顶测算位 (${cond_tp1:.2f}) 高抛减半(50%)推保本损，达极值目标 (${cond_tp2:.2f}) 结清，"
                    f"跌穿2-4主通道基线 (${escape_level:.2f}) 全额清仓"
                )
            else:
                leg_high = max(recent_high, current_price)
                leg_low = min(recent_low, current_price)
                leg_span = max(leg_high - leg_low, med_range * 2.0)

                fib_382 = round(leg_high - 0.382 * leg_span, 2)
                fib_500 = round(leg_high - 0.500 * leg_span, 2)
                fib_618 = round(leg_high - 0.618 * leg_span, 2)

                cand_levels = []
                mid_val = chan.get("mid_rail")
                lower_val = chan.get("lower_rail")
                ema_val = ema_200_gate.get("value")
                if mid_val and mid_val < current_price:
                    cand_levels.append((mid_val, "通道中轨"))
                if lower_val and lower_val < current_price:
                    cand_levels.append((lower_val, "通道下轨"))
                if ema_val and ema_val < current_price:
                    cand_levels.append((ema_val, "200 EMA"))
                if inv_p and inv_p < current_price:
                    cand_levels.append((inv_p, "波浪客观失效位"))

                matching_cands = [
                    c for c in cand_levels
                    if (fib_618 - 1.5 * med_range) <= c[0] <= (fib_382 + 1.5 * med_range)
                ]

                if matching_cands:
                    best_cand, best_name = min(matching_cands, key=lambda x: abs(x[0] - fib_500))
                    cond_entry = round(best_cand, 2)
                    confluence_note = f"斐波那契 0.382-0.618 回撤带与 {best_name} (${best_cand:.2f}) 形成双重支撑共振"
                else:
                    cond_entry = round(min(fib_500, current_price - 0.5 * med_range), 2)
                    confluence_note = f"斐波那契 50% 核心折返共振位 (${fib_500:.2f})"

                anchor_sl = min(fib_618, (inv_p if (inv_p and inv_p < cond_entry) else fib_618))
                cond_sl = round(anchor_sl - tight_buf, 2)
                cond_risk = cond_entry - cond_sl
                if cond_risk <= 0:
                    cond_sl = round(cond_entry - 0.8 * med_range, 2)
                    cond_risk = cond_entry - cond_sl

                cond_tp1 = round(target_price if target_price > cond_entry + 1.5 * cond_risk else (leg_high if leg_high > cond_entry + 1.5 * cond_risk else (cond_entry + 1.618 * leg_span)), 2)
                cond_tp2 = round(tp2_val if tp2_val > cond_tp1 else (cond_entry + 2.618 * leg_span), 2)
                cond_reward = cond_tp1 - cond_entry
                cond_rr = round(cond_reward / max(0.01, cond_risk), 2)
                playbook_name = "顺势回踩共振挂单剧本"
                playbook_cond = f"等待价格回踩 [${cond_sl:.2f} - ${cond_entry:.2f}] 支撑区间企稳"
                playbook_notes = (
                    f"{confluence_note}，拒绝现价追高，待回踩完成博弈高盈亏比主升浪；"
                    f"达 TP1 (${cond_tp1:.2f}) 斐波那契扩展位高抛减半(50%)推保本损，达到 TP2 (${cond_tp2:.2f}) 目标位结清，"
                    f"跌穿止损或道氏前低全额清仓"
                )

            if cond_rr >= min_rr_gate:
                trade_plan["condition_playbook"] = {
                    "scenario_name": playbook_name,
                    "trigger_condition": playbook_cond,
                    "ideal_entry": cond_entry,
                    "stop_loss": cond_sl,
                    "tp1": cond_tp1,
                    "tp2": cond_tp2,
                    "estimated_rr": cond_rr,
                    "passed_gates": True,
                    "notes": playbook_notes,
                }
            else:
                trade_plan["condition_playbook"] = None

    else:
        entry = current_price
        down_span = max(recent_high - recent_low, med_range * 2.0)
        ema_val = float(ema_200_gate.get("value") or (recent_high + med_range))

        # -------------------------------------------------------------
        # 补充完整的“买卖点”计算引擎（道氏定大势 × 波浪找点位）
        # 即使触发 0R 门禁或处于逆势调整期，明确输出触发条件与价格区间
        # -------------------------------------------------------------
        # 1. 右侧买入点 (做多反转触发条件)
        agg_buy_low = round(recent_low + 0.500 * down_span, 2)
        agg_buy_high = round(recent_low + 0.618 * down_span, 2)
        agg_sl = round(recent_low - base_sl_buffer, 2)
        agg_tp = round(recent_high + 0.618 * down_span, 2)

        cons_buy_low = round(ema_val, 2)
        cons_buy_high = round(ema_val * 1.015, 2)
        cons_sl = round(ema_val * 0.985, 2)
        cons_tp = round(recent_high + 1.000 * down_span, 2)

        buy_triggers = {
            "aggressive": {
                "name": "激进波段买点 (突破回踩确认)",
                "condition": (
                    f"价格放量突破下降通道上轨及前高 LH (${recent_high:.2f}) 阻力位后，"
                    f"缩量回踩不破前低 (${recent_low:.2f})，构筑有效 HL 抬高低点 "
                    f"(对应潜在新周期 2 浪回撤 0.500~0.618 区间) 时触发买入"
                ),
                "price_range": [agg_buy_low, agg_buy_high],
                "price_range_text": f"${agg_buy_low:.2f} ~ ${agg_buy_high:.2f}",
                "stop_loss": agg_sl,
                "stop_loss_text": f"${agg_sl:.2f} (跌破前低 LL 无条件止损)",
                "target": agg_tp,
                "target_text": f"${agg_tp:.2f} (新周期驱动浪 1.618x 延展)",
            },
            "conservative": {
                "name": "稳健趋势买点 (收复200EMA与大盘共振)",
                "condition": (
                    f"价格放量收复并站稳 200 EMA (${ema_val:.2f})，"
                    f"且核心大盘指数 (SPY 与 QQQ) 同步形成多头相互验证时触发买入"
                ),
                "price_range": [cons_buy_low, cons_buy_high],
                "price_range_text": f"${cons_buy_low:.2f} ~ ${cons_buy_high:.2f}",
                "stop_loss": cons_sl,
                "stop_loss_text": f"${cons_sl:.2f} (重新失守 200 EMA 止损离场)",
                "target": cons_tp,
                "target_text": f"${cons_tp:.2f} (大周期主推浪目标位)",
            },
        }

        # 2. 顺势卖出点 (多单止盈/止损 & 空单入场点)
        fib_382 = round(recent_low + 0.382 * down_span, 2)
        fib_500 = round(recent_low + 0.500 * down_span, 2)
        fib_618 = round(recent_low + 0.618 * down_span, 2)
        chan_up = float(chan.get("upper_rail") or fib_618)

        res1_low = fib_382
        res1_high = fib_500
        res2_low = fib_500
        res2_high = max(fib_618, round(chan_up, 2))

        c_support = recent_low
        if "C" in pts and isinstance(pts["C"], dict):
            c_support = float(pts["C"].get("price", recent_low))

        long_clear_line = round(c_support - base_sl_buffer, 2)
        short_stop_line = round(recent_high + base_sl_buffer, 2)
        tp1_target = round(recent_low, 2)
        tp2_target = round(max(0.01, recent_low - 0.618 * down_span), 2)

        sell_triggers = {
            "rebound_sell": {
                "name": "反弹高抛卖出区 (空单入场 / 多单解套)",
                "resistance_zone_1": {
                    "label": "第一阻力卖出区 (TP1)",
                    "price_range": [res1_low, res1_high],
                    "price_range_text": f"${res1_low:.2f} ~ ${res1_high:.2f}",
                    "basis": f"前一下跌波浪 0.382 (${fib_382:.2f}) ~ 0.500 (${fib_500:.2f}) 斐波那契回撤与阻力带",
                },
                "resistance_zone_2": {
                    "label": "第二阻力卖出区 (TP2)",
                    "price_range": [res2_low, res2_high],
                    "price_range_text": f"${res2_low:.2f} ~ ${res2_high:.2f}",
                    "basis": f"0.618 黄金分割位 (${fib_618:.2f}) 与下降通道上轨重叠共振",
                },
            },
            "take_profit": {
                "tp1": {
                    "price": tp1_target,
                    "price_text": f"${tp1_target:.2f}",
                    "label": "下探止盈目标 TP1",
                    "basis": f"道氏前期波谷支撑位 (${tp1_target:.2f})，空单减半兑现/多单最后防守",
                },
                "tp2": {
                    "price": tp2_target,
                    "price_text": f"${tp2_target:.2f}",
                    "label": "下探止盈目标 TP2",
                    "basis": f"空头顺势 1.618x 斐波那契延展位 (${tp2_target:.2f}) / 通道下轨",
                },
            },
            "breakdown_stop": {
                "long_clear_line": {
                    "price": long_clear_line,
                    "price_text": f"${long_clear_line:.2f}",
                    "label": "多单无条件清仓线",
                    "basis": f"跌破前低 C 浪支撑位 (${c_support:.2f})，顺势空头破位，多单坚决离场",
                },
                "short_stop_line": {
                    "price": short_stop_line,
                    "price_text": f"${short_stop_line:.2f}",
                    "label": "空单突破止损线",
                    "basis": f"放量站稳前高 LH 阻力位 (${recent_high:.2f})，空头下降结构被破坏",
                },
            },
        }

        sell_stages = [
            {
                "stage": "TP1",
                "name": "第一阻力卖出区 (TP1)",
                "action": "反弹遇阻高抛 (50%)",
                "target": res1_high,
                "basis": f"前下跌浪 0.382-0.500 回撤带 (${res1_low:.2f}-${res1_high:.2f})",
            },
            {
                "stage": "TP2",
                "name": "第二阻力卖出区 (TP2)",
                "action": "通道上轨清仓",
                "target": res2_high,
                "basis": f"0.618 黄金回撤位与通道上轨 (${res2_high:.2f})",
            },
            {
                "stage": "EXIT",
                "name": "破位离场线",
                "action": "多单清仓 / 空单止损",
                "target": long_clear_line,
                "basis": f"击穿前低 C 浪支撑 (${c_support:.2f})，顺势下探",
            },
        ]

        stop_loss = short_stop_line
        stop_loss_reason = f"空单突破止损线：放量站稳前高 LH 阻力位 (${recent_high:.2f}) 结构外加防守缓冲 ${base_sl_buffer:.2f}"

        # 严苛条件挂单剧本：仅当预估盈亏比达到硬门禁 (>= min_rr_gate) 时才输出
        playbook_rr = round((res1_high - tp1_target) / max(0.01, short_stop_line - res1_high), 2)
        condition_pb = None
        if playbook_rr >= min_rr_gate:
            condition_pb = {
                "scenario_name": "反弹高抛做空/解套剧本",
                "trigger_condition": f"等待价格反弹至 [${res1_low:.2f} - ${res1_high:.2f}] 第一阻力卖出区滞涨回落",
                "ideal_entry": res1_high,
                "stop_loss": short_stop_line,
                "tp1": tp1_target,
                "tp2": tp2_target,
                "estimated_rr": playbook_rr,
                "passed_gates": True,
                "notes": f"在 0.382-0.500 反弹阻力区反弹遇阻高抛或多单解套，止损设在突破前高 LH (${short_stop_line:.2f})，下探第一目标 ${tp1_target:.2f}。",
            }

        # 美股做多偏好防护：美股空头趋势下防守观望，杜绝盲目抄底
        if is_us and not is_crypto:
            trade_plan = {
                "direction": "观望 (空头趋势防守)",
                "direction_mode": "SHORT",
                "entry": round(entry, 2),
                "stop_loss": stop_loss,
                "stop_loss_reason": stop_loss_reason,
                "tp1": tp1_target,
                "tp1_source": f"下探止盈目标：道氏前期波谷支撑 (${tp1_target:.2f})",
                "tp2": tp2_target,
                "tp2_source": f"下探止盈目标：空头顺势扩展支撑 (${tp2_target:.2f})",
                "tp_source": f"下探止盈目标：道氏前期波谷支撑 (${tp1_target:.2f})",
                "rr_ratio": 0.0,
                "passed_gates": False,
                "reasons": [
                    f"道氏大盘：{dow_market_ver['description']}" if dow_market_ver else "道氏大盘研判",
                    f"道氏结构：{dow_phase_desc}（主趋势非多头，禁止盲目做多）",
                    f"均线过滤：{ema_200_gate['trend']}" + (f" (${ema_200_gate['value']})" if ema_200_gate.get('value') else ""),
                    "美股策略原则：用户明确偏好顺势做多，当前标的处于空头结构，遵循道氏理论顺势原则，防守观望，严禁逆势抄底。",
                    f"防守依据：{stop_loss_reason}",
                ],
                "dow_volume_status": dow_vol_status,
                "condition_playbook": condition_pb,
                "escape_level": stop_loss,
                "escape_reason": "空头趋势严格防守，未筑底翻多前不盲目建仓",
                "wave_setup": {
                    "buy_point_type": "右侧反转买点 (未触发)",
                    "buy_point_desc": f"标的处于下降通道 (LH+LL)，严禁左侧抄底；等待放量突破前高 LH (${recent_high:.2f}) 后缩量回踩确认，或放量收复 200 EMA (${ema_val:.2f})",
                    "wave_stage": "次级调整或主跌段",
                    "sell_stages": sell_stages,
                    "escape_level": stop_loss,
                    "escape_reason": "空头趋势严格防守",
                },
                "sell_stages": sell_stages,
                "dow_market_verification": dow_market_ver,
                "buy_triggers": buy_triggers,
                "sell_triggers": sell_triggers,
            }
            return trade_plan

        # -------------------------------------------------------------
        # 1. 动态多级止损锚点池 (Multi-tier Stop Loss Anchor Pool - 空头，非美股/加密使用)
        # -------------------------------------------------------------
        stop_loss = None
        stop_loss_reason = ""
        is_2b_active = False

        if is_crypto and hasattr(crypto_mod, "check_recent_crypto_2b_sweep"):
            sweep_info = crypto_mod.check_recent_crypto_2b_sweep(df_clean, side=-1, swings=conf_swings, bar_rng=med_range)
            if sweep_info.get("detected"):
                is_2b_active = True
                stop_loss = round(float(sweep_info["stop_loss"]), 2)
                stop_loss_reason = sweep_info["desc"]

        if not is_2b_active:
            anchors_above = []
            if inv_p is not None and inv_p > entry:
                anchors_above.append((inv_p, inv_r, 1))
            if baseline_val is not None and baseline_val > entry:
                ch_label = "艾略特2-4主通道基线阻力" if "2-4" in elliott_chan.get("channel_stage", "") else "艾略特1-2通道基线阻力"
                anchors_above.append((baseline_val, ch_label, 2))
            upper_rail = chan.get("upper_rail")
            if upper_rail is not None and upper_rail > entry:
                anchors_above.append((upper_rail, "动态回归通道上轨阻力", 3))
            ema_val = ema_200_gate.get("value")
            if ema_val is not None and ema_val > entry:
                anchors_above.append((ema_val, "200日均线 (200EMA) 阻力", 4))
            anchors_above.append((recent_high, "道氏结构前高波峰阻力", 5))

            close_anchors = [a for a in anchors_above if (a[0] - entry) <= 4.0 * med_range]
            chosen = close_anchors[0] if close_anchors else anchors_above[0]
            anchor_price, anchor_desc, _ = chosen
            stop_loss = round(anchor_price + base_sl_buffer, 2)
            stop_loss_reason = f"{anchor_desc} (${anchor_price:.2f}) 结构外加防守缓冲 ${base_sl_buffer:.2f}"

        risk = stop_loss - entry
        if risk <= 0:
            stop_loss = round(entry + base_sl_buffer, 2)
            risk = stop_loss - entry

        friction = entry * 0.0008
        effective_risk = max(0.01, risk + friction)

        # -------------------------------------------------------------
        # 2. 顺势拓展分级止盈 (Take Profit: 分离未确认即时极值，杜绝强凑盈亏比)
        # -------------------------------------------------------------
        tp2_val = None
        tp2_source = None
        valid_exts = [float(v) for k, v in fib_proj.items() if 0 < float(v) < entry]
        if "developing_wave_3" in raw_pat or "wave_3" in raw_pat:
            if valid_exts:
                target_price = max(valid_exts)
                tp_source = f"波浪3浪顺势空头斐波扩展位 (${target_price:.2f})"
                tp2_val = round(min(valid_exts), 2) if len(valid_exts) > 1 else round(max(0.01, target_price - 1.0 * med_range), 2)
                tp2_source = "波浪3浪极值空头斐波扩展位"
            else:
                if is_crypto and entry > 10000:
                    round_level = float((int(entry) // 5000) * 5000)
                    if round_level >= entry:
                        round_level -= 5000
                    target_price = round(max(0.01, round_level), 2)
                    tp_source = f"空头3浪极值延伸下行心理大关 (${target_price:.2f})"
                elif recent_low < entry - 0.5 * med_range and recent_low > 0:
                    target_price = recent_low
                    tp_source = "道氏前期显著波谷支撑"
                else:
                    target_price = round(max(0.01, entry - 1.5 * med_range), 2)
                    tp_source = "冲量波段阶梯下行支撑 (真实结构目标)"
                tp2_val = round(max(0.01, target_price - 1.0 * med_range), 2)
                tp2_source = "空头顺势极值扩展目标"
        elif "developing_wave_5" in raw_pat or "impulse_5" in raw_pat:
            if valid_exts:
                target_price = max(valid_exts)
                tp_source = f"波浪5浪空头测算位 (${target_price:.2f})"
                tp2_val = round(min(valid_exts), 2) if len(valid_exts) > 1 else round(max(0.01, target_price - 1.0 * med_range), 2)
                tp2_source = "波浪5浪极值空头扩展位"
            else:
                target_price = round(max(0.01, entry - 1.5 * med_range), 2)
                tp_source = "波浪5浪探底阶梯支撑 (真实结构目标)"
                tp2_val = round(max(0.01, target_price - 1.0 * med_range), 2)
                tp2_source = "波浪5浪极值空头目标"
        elif "corrective_abc" in raw_pat or "abc" in raw_pat:
            if valid_exts:
                target_price = max(valid_exts)
                tp_source = f"空头ABC调整浪目标位 (${target_price:.2f})"
                tp2_val = round(min(valid_exts), 2) if len(valid_exts) > 1 else round(max(0.01, target_price - 1.0 * med_range), 2)
                tp2_source = "空头ABC浪扩展位"
            else:
                target_price = round(max(0.01, entry - 1.5 * med_range), 2)
                tp_source = "空头次级回调空间目标 (真实结构目标)"
                tp2_val = round(max(0.01, target_price - 1.0 * med_range), 2)
                tp2_source = "空头顺势扩展目标"
        elif is_crypto:
            impulse_leg = max(recent_high - recent_low, med_range * 2.0)
            fib_ext_1618 = round(max(0.01, recent_high - 1.618 * impulse_leg), 2)
            if recent_low < entry - 1.5 * effective_risk and recent_low > 0:
                target_price = recent_low
                tp_source = "冲量波段前低结构支撑 (Trough)"
                tp2_val = min(fib_ext_1618, round(max(0.01, recent_low - 0.618 * impulse_leg), 2))
                tp2_source = "加密顺势 1.618x 空头斐波扩展位"
            else:
                target_price = fib_ext_1618
                tp_source = "加密顺势 1.618x 空头斐波扩展位 (规避即时未确认极值)"
                tp2_val = round(max(0.01, recent_low - 0.618 * impulse_leg), 2)
                tp2_source = "加密顺势 2.0x+ 空头斐波扩展位"
        else:
            if recent_low <= entry - 1.5 * effective_risk and recent_low > 0:
                target_price = recent_low
                tp_source = "道氏前期显著波谷支撑"
                tp2_val = round(max(0.01, recent_low - 1.0 * med_range), 2)
                tp2_source = "空头扩展目标"
            else:
                forward_ext = round(max(0.01, entry - 1.618 * max(med_range * 2.0, recent_high - recent_low)), 2)
                target_price = forward_ext
                tp_source = "空头 1.618x 斐波那契扩展位 (规避即时未确认极值)"
                tp2_val = round(max(0.01, entry - 2.618 * max(med_range * 2.0, recent_high - recent_low)), 2)
                tp2_source = "空头 2.618x 斐波那契扩展位"

        if tp2_val is None:
            tp2_val = round(max(0.01, target_price - 1.0 * med_range), 2)
            tp2_source = "空头顺势扩展目标"

        net_reward = max(0.0, entry - target_price - friction)
        rr = round(net_reward / max(0.01, effective_risk), 2)

        # 空头防杀跌与超卖门禁 (Anti-Chase Short Guard)
        chan_pos = float(chan.get("channel_pos") if chan.get("channel_pos") is not None else 0.5)
        anti_chase_blocked = False
        anti_chase_reason = ""

        if chan.get("is_oversold", False) or chan_pos <= 0.15:
            anti_chase_blocked = True
            anti_chase_reason = f"触及通道动态下轨极值超卖区 (pos={chan_pos:.2f})，警惕反弹/严禁地板杀跌"
        elif ("developing_wave_3" in raw_pat or "wave_3" in raw_pat) and "2.618" in fib_proj and current_price <= float(fib_proj["2.618"]) * 1.01:
            anti_chase_blocked = True
            anti_chase_reason = f"空头第3浪已触及 2.618x 极值延展位 (${float(fib_proj['2.618']):.2f})，主跌动能过度透支，严禁追空"

        box_blocked = (box["is_box"] and box["state"] == "SWEEP_LOW") or (
            box["is_box"] and box["low"] and current_price <= box["low"] * 1.02
        )
        passed = (rr >= min_rr_gate) and not box_blocked and not anti_chase_blocked

        reasons = [
            f"道氏结构：{dow_phase_desc}",
            f"均线过滤：{ema_200_gate['trend']}" + (f" (${ema_200_gate['value']})" if ema_200_gate.get('value') else ""),
            f"盈亏比：{rr}R" + (f"（达标 >={min_rr_gate}R）" if (rr >= min_rr_gate) else f"（真实空间不足，低于 {min_rr_gate}R 门禁）"),
            f"道氏量能：{dow_vol_status}" + (f" - {dow_vol['description']}" if dow_vol.get("description") else ""),
            f"防守依据：{stop_loss_reason}",
            f"止盈依据：{tp_source}",
        ]
        if box_blocked:
            reasons.append(f"箱体警示: {box['detail']}")
        if anti_chase_blocked:
            reasons.append(f"风控拦截：{anti_chase_reason}")

        tp1_val = round(target_price, 2)

        trade_plan = {
            "direction": "做空 (Short 防御性)" if passed else "观望",
            "direction_mode": "SHORT",
            "entry": round(entry, 2),
            "stop_loss": stop_loss,
            "stop_loss_reason": stop_loss_reason,
            "tp1": tp1_val,
            "tp1_source": tp_source,
            "tp2": tp2_val,
            "tp2_source": tp2_source,
            "tp_source": tp_source,
            "rr_ratio": rr,
            "passed_gates": passed,
            "reasons": reasons,
            "dow_volume_status": dow_vol_status,
            "condition_playbook": None,
            "escape_level": stop_loss,
            "escape_reason": "突破阻力止损",
            "wave_setup": None,
            "sell_stages": sell_stages,
            "dow_market_verification": dow_market_ver,
            "buy_triggers": buy_triggers,
            "sell_triggers": sell_triggers,
        }

        # -------------------------------------------------------------
        # 3. 严苛 If-Then 条件挂单剧本 (Fade the Rally: 黄金反弹共振与严格门禁)
        # -------------------------------------------------------------
        if not passed:
            leg_high = max(recent_high, current_price)
            leg_low = min(recent_low, current_price)
            leg_span = max(leg_high - leg_low, med_range * 2.0)

            fib_382 = round(leg_low + 0.382 * leg_span, 2)
            fib_500 = round(leg_low + 0.500 * leg_span, 2)
            fib_618 = round(leg_low + 0.618 * leg_span, 2)

            cand_levels = []
            mid_val = chan.get("mid_rail")
            upper_val = chan.get("upper_rail")
            ema_val = ema_200_gate.get("value")
            if mid_val and mid_val > current_price:
                cand_levels.append((mid_val, "通道中轨"))
            if upper_val and upper_val > current_price:
                cand_levels.append((upper_val, "通道上轨"))
            if ema_val and ema_val > current_price:
                cand_levels.append((ema_val, "200 EMA"))
            if inv_p and inv_p > current_price:
                cand_levels.append((inv_p, "波浪客观失效位"))

            matching_cands = [
                c for c in cand_levels
                if (fib_382 - 1.5 * med_range) <= c[0] <= (fib_618 + 1.5 * med_range)
            ]

            if matching_cands:
                best_cand, best_name = min(matching_cands, key=lambda x: abs(x[0] - fib_500))
                cond_entry = round(best_cand, 2)
                confluence_note = f"斐波那契 0.382-0.618 反弹带与 {best_name} (${best_cand:.2f}) 形成双重阻力共振"
            else:
                cond_entry = round(max(fib_500, current_price + 0.5 * med_range), 2)
                confluence_note = f"斐波那契 50% 核心反弹共振位 (${fib_500:.2f})"

            tight_buf = 0.35 * med_range if is_crypto else 0.5 * med_range
            anchor_sl = max(fib_618, (inv_p if (inv_p and inv_p > cond_entry) else fib_618))
            cond_sl = round(anchor_sl + tight_buf, 2)
            cond_risk = cond_sl - cond_entry
            if cond_risk <= 0:
                cond_sl = round(cond_entry + 0.8 * med_range, 2)
                cond_risk = cond_sl - cond_entry

            cond_tp1 = round(target_price if target_price < cond_entry - 1.5 * cond_risk else (leg_low if leg_low < cond_entry - 1.5 * cond_risk else max(0.01, cond_entry - 1.618 * leg_span)), 2)
            cond_tp2 = round(tp2_val if tp2_val < cond_tp1 else max(0.01, cond_entry - 2.618 * leg_span), 2)
            cond_reward = cond_entry - cond_tp1
            cond_rr = round(cond_reward / max(0.01, cond_risk), 2)

            if cond_rr >= min_rr_gate:
                trade_plan["condition_playbook"] = {
                    "scenario_name": "顺势反弹沽空剧本",
                    "trigger_condition": f"等待反弹至 [${cond_entry:.2f} - ${cond_sl:.2f}] 阻力区间遇阻衰竭",
                    "ideal_entry": cond_entry,
                    "stop_loss": cond_sl,
                    "tp1": cond_tp1,
                    "tp2": cond_tp2,
                    "estimated_rr": cond_rr,
                    "passed_gates": True,
                    "notes": f"{confluence_note}，禁止低位追空，等待反抽阻力位确认证伪线后择机沽空",
                }
            else:
                trade_plan["condition_playbook"] = None

    return trade_plan

    return trade_plan


def _build_chart_annotations(
    pa: Any,
    df_clean: Any,
    current_price: float,
    is_intraday: bool,
    struct: Dict[str, Any],
    trade_plan: Dict[str, Any],
    turn_windows_res: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """管道阶段 4：生成前端精简且无重叠的标注体系 (卡片化波浪锚点 + 右延Fib/缺口 + 仅保留最近2个时间窗 + 200EMA)。"""
    pd = _get_modules()["pd"]
    swings = struct["swings"]
    box = struct["box_raw"]
    box_summary = struct["box"]
    chan = struct["chan_raw"]
    chan_summary = struct["channel"]
    wp = struct["wp"]
    wave_summary = struct["wave"]
    gaps = struct["gaps"]

    def _format_time_str(val: Any) -> str:
        if val is None:
            return ""
        if isinstance(val, pd.Timestamp):
            return val.strftime("%Y-%m-%d %H:%M" if is_intraday else "%Y-%m-%d")
        s = str(val).strip()
        if s.isdigit() and len(s) < 8:
            return ""
        if len(s) > 10 and not is_intraday:
            return s[:10]
        if len(s) > 16:
            return s[:16]
        return s

    def _resolve_pt_time(pt: Dict[str, Any], idx: int) -> str:
        t = _format_time_str(pt.get("time"))
        if not t and 0 <= idx < len(df_clean):
            t = _format_time_str(df_clean.index[idx])
        return t

    markers: List[Dict[str, Any]] = []
    lines: List[Dict[str, Any]] = []
    boxes: List[Dict[str, Any]] = []

    # 1. 结构破坏与假突破 Markers (若无 MSS 则保留少量 swing 拐点确保轻量兼容)
    mss_events = pa.detect_mss(swings, df_clean) if swings else []
    for idx, mss in enumerate(mss_events[-2:]):
        raw_t = mss.get("trigger_time") or mss.get("time") or ""
        time_val = str(raw_t)[: 16 if is_intraday else 10]
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

    # 当未触发 MSS 时，添加最近的 2~3 个关键拐点标记，保证单图拐点可见性
    if not markers and swings:
        is_bear_env = (struct.get("dow_bias", 0) < 0) or ("空头" in struct.get("dow_phase", "")) or (current_price < struct.get("ema_200_gate", {}).get("value", float("inf")))
        for idx_s, s in enumerate(swings[-4:]):
            t_val = _resolve_pt_time(s, int(s.get("index", 0)))
            if t_val:
                is_high = s.get("type") == "High"
                dow_lbl = s.get("dow", "H" if is_high else "L")
                if is_bear_env:
                    dow_lbl = "LH" if is_high else "LL"
                markers.append({
                    "id": f"swing_{idx_s}_{t_val}",
                    "time": t_val,
                    "position": "aboveBar" if is_high else "belowBar",
                    "color": "#10b981" if is_high else "#ef4444",
                    "shape": "arrowDown" if is_high else "arrowUp",
                    "text": dow_lbl,
                })

    if box["is_box"] and box["state"] in ("SWEEP_HIGH", "SWEEP_LOW"):
        last_t = str(df_clean.index[-1])[: 16 if is_intraday else 10]
        is_sweep_high = box["state"] == "SWEEP_HIGH"
        markers.append({
            "id": f"box_sweep_{last_t}",
            "time": last_t,
            "position": "aboveBar" if is_sweep_high else "belowBar",
            "color": "#ec4899",
            "shape": "arrowDown" if is_sweep_high else "arrowUp",
            "text": "2B假突破" if is_sweep_high else "2B假摔",
        })

    # 2. 交易计划水平线（入场/止损/目标/波浪证伪）
    dir_mode = trade_plan.get("direction_mode") or ("SHORT" if struct.get("dow_bias", 0) < 0 else "LONG")
    is_short_plan = (dir_mode == "SHORT")

    if trade_plan.get("entry"):
        lines.append({
            "id": "line_entry",
            "price": trade_plan["entry"],
            "color": "#3b82f6",
            "lineWidth": 2,
            "lineStyle": 0,
            "title": f"现价参考: ${trade_plan['entry']:.2f}" if is_short_plan else f"参考入场: ${trade_plan['entry']:.2f}",
        })
    if trade_plan.get("stop_loss"):
        lines.append({
            "id": "line_sl",
            "price": trade_plan["stop_loss"],
            "color": "#ef4444",
            "lineWidth": 2,
            "lineStyle": 2,
            "title": f"突破止损: ${trade_plan['stop_loss']:.2f}" if is_short_plan else f"跌破止损: ${trade_plan['stop_loss']:.2f}",
        })
    if trade_plan.get("tp1"):
        lines.append({
            "id": "line_tp1",
            "price": trade_plan["tp1"],
            "color": "#10b981",
            "lineWidth": 2,
            "lineStyle": 2,
            "title": f"下探目标 TP1: ${trade_plan['tp1']:.2f}" if is_short_plan else f"目标 TP1 ({trade_plan.get('rr_ratio', 0)}R): ${trade_plan['tp1']:.2f}",
        })
    if trade_plan.get("tp2"):
        lines.append({
            "id": "line_tp2",
            "price": trade_plan["tp2"],
            "color": "#059669",
            "lineWidth": 1.5,
            "lineStyle": 2,
            "title": f"下探目标 TP2: ${trade_plan['tp2']:.2f}" if is_short_plan else f"目标 TP2: ${trade_plan['tp2']:.2f}",
        })
    if wave_summary.get("invalidation_price"):
        lines.append({
            "id": "line_wave_inv",
            "price": wave_summary["invalidation_price"],
            "color": "#a855f7",
            "lineWidth": 2,
            "lineStyle": 2,
            "title": f"波浪证伪: ${wave_summary['invalidation_price']:.2f}",
        })

    # 3. 盘整箱体
    if box_summary.get("is_in_box") and box_summary.get("box_high") and box_summary.get("box_low"):
        box_slice = df_clean.tail(min(35, len(df_clean)))
        boxes.append({
            "id": "box_consolidation",
            "time1": str(box_slice.index[0])[: 16 if is_intraday else 10],
            "time2": str(box_slice.index[-1])[: 16 if is_intraday else 10],
            "price1": float(box_summary["box_high"]),
            "price2": float(box_summary["box_low"]),
            "fillColor": "rgba(59, 130, 246, 0.10)",
            "borderColor": "#3b82f6",
            "label": f"箱体区间: [{box_summary['box_low']:.2f} - {box_summary['box_high']:.2f}]",
        })

    # 4. 线性回归通道 (紧凑短标签，紧贴右端点)
    channel_lines: List[Dict[str, Any]] = []
    if chan and chan.get("upper_rail") is not None and chan.get("lower_rail") is not None:
        n_win = min(len(df_clean), 30)
        slice_df = df_clean.tail(n_win)
        t_start = _format_time_str(slice_df.index[0])
        t_end = _format_time_str(slice_df.index[-1])

        if t_start and t_end:
            slope = float(chan.get("slope") or 0.0)
            upper_end = float(chan["upper_rail"])
            mid_end = float(chan["mid_rail"])
            lower_end = float(chan["lower_rail"])
            upper_start = round(upper_end - slope * (n_win - 1), 2)
            mid_start = round(mid_end - slope * (n_win - 1), 2)
            lower_start = round(lower_end - slope * (n_win - 1), 2)

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
                    "title": f"通道上轨 ${upper_end:.2f}",
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
                    "title": f"中轴 ${mid_end:.2f}",
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
                    "title": f"通道下轨 ${lower_end:.2f}",
                },
            ]

    # 5. 波浪节点解析 (统一构建白底细边框卡片标注数据，次级摆动输出淡灰辅助线)
    wave_annots: List[Dict[str, Any]] = []
    wp_pts = wp.get("wave_points") or {}
    if wp.get("pattern") == "corrective_abc" and all(k in wp_pts for k in ("0", "A", "B", "C")):
        mapping = [
            ("0", "0", "#64748b", "aboveBar" if wp_pts["0"].get("type") == "High" else "belowBar"),
            ("A", "A", "#ef4444" if wp_pts["A"].get("type") == "Low" else "#10b981", "belowBar" if wp_pts["A"].get("type") == "Low" else "aboveBar"),
            ("B", "B", "#10b981" if wp_pts["B"].get("type") == "High" else "#ef4444", "aboveBar" if wp_pts["B"].get("type") == "High" else "belowBar"),
            ("C", "C", "#ef4444" if wp_pts["C"].get("type") == "Low" else "#10b981", "belowBar" if wp_pts["C"].get("type") == "Low" else "aboveBar"),
        ]
        for key, lbl, col, pos in mapping:
            pt = wp_pts[key]
            t_val = _resolve_pt_time(pt, int(pt.get("index", 0)))
            if t_val:
                dt_str = t_val[5:10] if len(t_val) >= 10 else ""
                is_high = pt.get("type") == "High"
                prefix = "▼" if is_high else "▲"
                card_text = f"{prefix}{lbl} ${float(pt['price']):.2f}" + (f" ({dt_str})" if dt_str else "")
                wave_annots.append({
                    "key": key,
                    "label": card_text,
                    "short_label": lbl,
                    "time": t_val,
                    "price": round(float(pt["price"]), 2),
                    "color": col,
                    "pos": pos,
                    "type": pt.get("type", "High"),
                })
    elif wp_pts:
        for key, pt in sorted(wp_pts.items(), key=lambda x: int(x[1].get("index", 0))):
            t_val = _resolve_pt_time(pt, int(pt.get("index", 0)))
            if t_val:
                is_high = pt.get("type") == "High"
                lbl = str(key)
                dt_str = t_val[5:10] if len(t_val) >= 10 else ""
                prefix = "▼" if is_high else "▲"
                card_text = f"{prefix}{lbl} ${float(pt['price']):.2f}" + (f" ({dt_str})" if dt_str else "")
                wave_annots.append({
                    "key": lbl,
                    "label": card_text,
                    "short_label": lbl,
                    "time": t_val,
                    "price": round(float(pt["price"]), 2),
                    "color": "#10b981" if is_high else "#ef4444",
                    "pos": "aboveBar" if is_high else "belowBar",
                    "type": pt.get("type", "High"),
                })
    else:
        is_bear_env = (struct.get("dow_bias", 0) < 0) or ("空头" in struct.get("dow_phase", "")) or (current_price < struct.get("ema_200_gate", {}).get("value", float("inf")))
        for idx_s, s in enumerate(swings[-5:]):
            t_val = _resolve_pt_time(s, int(s.get("index", 0)))
            if t_val:
                is_high = s.get("type") == "High"
                dow_lbl = s.get("dow", f"P{idx_s + 1}")
                if is_bear_env:
                    dow_lbl = "LH" if is_high else "LL"
                dt_str = t_val[5:10] if len(t_val) >= 10 else ""
                prefix = "▼" if is_high else "▲"
                card_text = f"{prefix}{dow_lbl} ${float(s['price']):.2f}" + (f" ({dt_str})" if dt_str else "")
                wave_annots.append({
                    "key": str(idx_s),
                    "label": card_text,
                    "short_label": dow_lbl,
                    "time": t_val,
                    "price": round(float(s["price"]), 2),
                    "color": "#10b981" if is_high else "#ef4444",
                    "pos": "aboveBar" if is_high else "belowBar",
                    "type": s.get("type", "High"),
                })

    wave_points_summary = [{"label": wa["label"], "price": wa["price"], "time": wa["time"]} for wa in wave_annots]
    last_bar_time = str(df_clean.index[-1])[: 16 if is_intraday else 10]

    # 次级摆动淡灰连线
    subtle_swings = [
        {"time": _format_time_str(s["time"]), "price": round(float(s["price"]), 2)}
        for s in swings[-25:]
        if _format_time_str(s.get("time"))
    ]

    wave_lines = {
        "id": "wave_structure",
        "pattern": wave_summary["pattern"],
        "color": "#8b5cf6",
        "lineWidth": 2.2,
        "points": [
            {"time": wa["time"], "price": wa["price"], "label": wa["label"], "color": wa["color"]}
            for wa in wave_annots
        ],
        "extension": {"time": last_bar_time, "price": current_price},
        "subtle_swings": subtle_swings,
    }

    # 6. Fibonacci 局部向右延伸目标线与价格失衡带 (仅从最后一个拐点向右延伸，不干扰左侧)
    last_pivot_time = wave_annots[-1]["time"] if wave_annots else last_bar_time
    fib_projections_data = wave_summary.get("fib_projections") or {}
    fib_lines: List[Dict[str, Any]] = []

    fib_style_map = {
        "0.618": ("Fib 61.8%", "#f59e0b"),
        "1.000": ("Fib 100%", "#f97316"),
        "1.272": ("Fib 127.2%", "#ea580c"),
        "1.618": ("Fib 161.8%", "#dc2626"),
        "2.000": ("Fib 200%", "#8b5cf6"),
        "2.618": ("Fib 261.8%", "#7c3aed"),
    }
    for ratio_k, price_v in fib_projections_data.items():
        if ratio_k in fib_style_map:
            name, color = fib_style_map[ratio_k]
            fib_lines.append({
                "id": f"fib_{ratio_k}",
                "ratio": ratio_k,
                "name": name,
                "price": round(float(price_v), 2),
                "startTime": last_pivot_time,
                "color": color,
                "label": f"{name} ${float(price_v):.2f}",
            })

    # 缺口与价格失衡带 (仅保留未回补最近 1~2 个缺口，向右延展)
    gap_boxes: List[Dict[str, Any]] = []
    for idx_g, gap in enumerate(gaps[-2:]):
        import re
        nums = re.findall(r"\d+(?:\.\d+)?", str(gap.get("range", "")))
        if len(nums) >= 2:
            g_low, g_high = sorted((float(nums[0]), float(nums[1])))
            is_bear = "Bearish" in str(gap.get("type", "")) or "阻力" in str(gap.get("type", ""))
            gap_boxes.append({
                "id": f"gap_{idx_g}",
                "startTime": _format_time_str(gap.get("date")) or last_pivot_time,
                "price1": g_high,
                "price2": g_low,
                "fillColor": "rgba(244, 63, 94, 0.12)" if is_bear else "rgba(16, 185, 129, 0.12)",
                "borderColor": "#f43f5e" if is_bear else "#10b981",
                "label": f"{'缺口阻力' if is_bear else '缺口支撑'} [${g_low:.2f}-${g_high:.2f}]",
            })

    # 7. 变盘时间窗克制化：仅保留未来最近的 2 个时间窗
    time_lines: List[Dict[str, Any]] = []
    if turn_windows_res.get("enabled"):
        clusters = turn_windows_res.get("clusters", [])
        future_clusters = [c for c in clusters if c.get("days_from_now", 0) >= 0]
        if not future_clusters and clusters:
            future_clusters = clusters[-2:]
        display_clusters = future_clusters[:2]

        for c in display_clusters:
            is_res = bool(c.get("is_resonance"))
            prefix = "⚡共振窗" if is_res else "⏳时间窗"
            first_seq = c.get("reasons", [""])[0].split()[0] if c.get("reasons") else ""
            compact_label = f"{prefix} {first_seq} (~{c['date'][5:]})".strip()
            time_lines.append({
                "id": f"turn_line_{c['date']}",
                "time": c["date"],
                "color": "#f59e0b" if is_res else "#6366f1",
                "lineWidth": 1.5,
                "lineStyle": "dashed",
                "isResonance": is_res,
                "score": c.get("score", 0),
                "daysFromNow": c.get("days_from_now", 0),
                "label": compact_label,
                "reasons": c.get("reasons", []),
            })

    # 8. 200 EMA 主图平滑连续参考线
    ema200_data: List[Dict[str, Any]] = []
    ema200_series = struct.get("ema200_series")
    if ema200_series is not None and not ema200_series.empty:
        for t_idx, val in ema200_series.items():
            t_str = _format_time_str(t_idx)
            if t_str and not pd.isna(val):
                ema200_data.append({"time": t_str, "value": round(float(val), 2)})

    annotations = {
        "markers": markers,
        "lines": lines,
        "boxes": boxes,
        "channel_lines": channel_lines,
        "wave_lines": wave_lines,
        "time_lines": time_lines,
        "fib_lines": fib_lines,
        "gap_boxes": gap_boxes,
        "ema200_data": ema200_data,
    }

    # 9. 紧凑型关键价位标尺 (离现价最近的上方第一阻力与下方第一支撑)
    candidates_above = []
    candidates_below = []

    up_rail = chan_summary.get("upper_rail")
    low_rail = chan_summary.get("lower_rail")
    if up_rail and up_rail > current_price:
        candidates_above.append((up_rail, "通道上轨"))
    if low_rail and low_rail < current_price:
        candidates_below.append((low_rail, "通道下轨"))

    ema_val = struct["ema_200_gate"].get("value")
    if ema_val:
        if ema_val > current_price:
            candidates_above.append((ema_val, "200 EMA"))
        elif ema_val < current_price:
            candidates_below.append((ema_val, "200 EMA"))

    inv_p = wave_summary.get("invalidation_price")
    if inv_p:
        if inv_p > current_price:
            candidates_above.append((inv_p, "波浪证伪线"))
        elif inv_p < current_price:
            candidates_below.append((inv_p, "波浪证伪线"))

    for fl in fib_lines:
        fp = fl["price"]
        if fp > current_price:
            candidates_above.append((fp, fl["name"]))
        elif fp < current_price:
            candidates_below.append((fp, fl["name"]))

    nearest_resistance = min(candidates_above, key=lambda x: x[0]) if candidates_above else None
    nearest_support = max(candidates_below, key=lambda x: x[0]) if candidates_below else None

    compact_scale = {
        "current_price": round(current_price, 2),
        "nearest_resistance": {
            "price": round(nearest_resistance[0], 2),
            "label": nearest_resistance[1],
            "diff_pct": round((nearest_resistance[0] - current_price) / current_price * 100, 2),
        } if nearest_resistance else None,
        "nearest_support": {
            "price": round(nearest_support[0], 2),
            "label": nearest_support[1],
            "diff_pct": round((current_price - nearest_support[0]) / current_price * 100, 2),
        } if nearest_support else None,
    }

    return annotations, wave_points_summary, compact_scale


def _generate_depth_diagnosis(
    struct: Dict[str, Any],
    trade_plan: Dict[str, Any],
    turn_windows_res: Dict[str, Any],
    current_price: float,
    dow_market_ver: Optional[Dict[str, Any]] = None,
) -> str:
    """生成结构化深度行情中文诊断综述。"""
    dow_phase = struct["dow_phase"]
    ema_gate = struct["ema_200_gate"]
    wave = struct["wave"]
    chan = struct["channel"]

    parts = []

    # 0. 道氏大盘指数相互验证
    if dow_market_ver and dow_market_ver.get("description"):
        parts.append(f"【道氏大盘】{dow_market_ver['description']}")

    # 1. 趋势与位置定性
    wave_name = wave["pattern"]
    curr_wave_stage = wave["current_wave"]
    wave_setup = trade_plan.get("wave_setup") or {}
    bp_type = wave_setup.get("buy_point_type")
    bp_tag = f"，低吸定位【{bp_type}】" if bp_type else ""
    ema_desc = f"现价位于 200 EMA (${ema_gate['value']}) 之{'上' if ema_gate['status'] == 'PASS' else '下'}" if ema_gate.get("value") else ""
    parts.append(
        f"【形态趋势】标的处于{dow_phase}，{wave_name}（{curr_wave_stage}）{bp_tag}。{ema_desc}，"
        f"通道状态为{chan.get('detail', '动态通道')}。"
    )

    # 2. 波浪买点依据与高抛低吸梯次
    if wave_setup.get("buy_point_desc"):
        parts.append(f"【买点依据】{wave_setup['buy_point_desc']}。")

    if trade_plan.get("tp1") is not None:
        esc_str = f"终极逃顶: 跌破 ${trade_plan['escape_level']:.2f} 全额清仓离场。" if trade_plan.get("escape_level") else ""
        parts.append(
            f"【高抛低吸梯次】第一目标 TP1: ${trade_plan.get('tp1', 0):.2f}（高抛减半50%推保本损）；"
            f"第二目标 TP2: ${trade_plan.get('tp2', 0):.2f}（冲顶高抛止盈）；"
            f"{esc_str}"
        )

    # 3. 核心防守与客观证伪线
    inv_p = wave.get("invalidation_price")
    inv_r = wave.get("invalidation_reason", "客观防守线")
    if inv_p:
        parts.append(f"【关键证伪】核心客观防守位于 ${inv_p:.2f}（{inv_r}），未跌破前原有主推/结构判定持续有效。")
    else:
        parts.append("【关键防守】当前波浪形态未触发刚性单边铁律止损，以道氏极值拐点作为动态止损基准。")

    # 4. 近期时空共振提醒
    clusters = turn_windows_res.get("clusters", [])
    future_tw = [c for c in clusters if c.get("days_from_now", 0) >= 0]
    if future_tw:
        next_tw = future_tw[0]
        resonance_text = "为高置信度共振窗" if next_tw.get("is_resonance") else "为变盘观察窗"
        parts.append(
            f"【时间共振】距离最近时间窗（{next_tw['date']}，T+{next_tw.get('days_from_now', 0)}日）{resonance_text}，"
            f"须密切留意关键阻力/支撑位附近的K线收线反应。"
        )
    elif turn_windows_res.get("imminent_alert"):
        parts.append(f"【时间提示】{turn_windows_res['imminent_alert']}")

    return "".join(parts)


def run_strategy_analysis(
    symbol: str,
    period: str = "1d",
    mode: str = "swing",
    df: Optional[Any] = None,
    market: Optional[str] = None,
    spy_df: Optional[Any] = None,
    qqq_df: Optional[Any] = None,
    iwm_df: Optional[Any] = None,
) -> Dict[str, Any]:
    """运行 StockVision 完整自包含交易策略矩阵、艾略特波浪与双数列变盘时间窗预测。"""
    modules = _get_modules()
    pa = modules["pa"]
    crypto_mod = modules["crypto"]

    # 阶段 1：数据准备 (统一使用 stage_one/backend/data/)
    df_clean = _prepare_strategy_df(symbol, df)
    if df_clean is None or len(df_clean) < 10:
        return {
            "symbol": symbol,
            "period": period,
            "mode": mode,
            "error": "有效K线数据不足以执行策略分析 (至少需要 10 根)",
            "summary": {},
            "annotations": {"markers": [], "lines": [], "boxes": [], "time_lines": []},
        }

    clean_sym = strip_prefix(symbol)
    is_crypto = bool(
        (market == "crypto")
        or (market_of(symbol) == "crypto")
        or (market_of(clean_sym) == "crypto")
        or (hasattr(crypto_mod, "is_crypto_asset") and (crypto_mod.is_crypto_asset(symbol) or crypto_mod.is_crypto_asset(clean_sym)))
    )
    if market:
        is_us = bool(str(market).lower() == "us")
    else:
        clean_upper = clean_sym.upper()
        sym_upper = symbol.upper()
        if sym_upper.startswith(("SH", "SZ", "HK")) or clean_upper.startswith(("SH", "SZ", "HK")):
            is_us = False
        elif is_crypto:
            is_us = False
        else:
            m = market_of(symbol, default_us=False) or market_of(clean_sym, default_us=False)
            if m and m != "us":
                is_us = False
            else:
                is_us = True

    current_price = float(df_clean["Close"].iloc[-1])
    is_intraday = period in ("5m", "15m", "1h", "4h")

    # 阶段 2：市场结构与波浪识别 (路由原生加密逻辑与浅刺容忍)
    struct = _evaluate_market_structure(pa, df_clean, current_price, is_intraday, is_crypto=is_crypto)

    # 阶段 3：变盘时间窗预测与交易计划构建
    wp_points = struct["wp"].get("wave_points") if isinstance(struct["wp"], dict) else None
    turn_windows_res = predict_turn_windows(
        df=df_clean,
        swings=struct["swings"],
        wave_points=wp_points,
        period=period,
        lookahead_bars=25,
        is_crypto=is_crypto,
    )

    # 美股大盘道氏相互验证 (SPY & QQQ & IWM 广度)
    dow_market_ver = _verify_us_market_dow(pa, spy_df=spy_df, qqq_df=qqq_df, iwm_df=iwm_df) if (is_us and not is_crypto) else {
        "status": "PASS",
        "verified": True,
        "spy_phase": "未适用",
        "qqq_phase": "未适用",
        "iwm_phase": "未适用",
        "aligned": True,
        "description": "非美股标的，跳过美股大盘指数相互验证",
        "desc": "非美股标的，跳过美股大盘指数相互验证",
    }

    # 周线-日线分形嵌套共振 (1d 周期)
    fractal_resonance = {"active": False, "desc": "未触发跨周期共振"}
    if period == "1d" and len(df_clean) >= 40:
        try:
            df_temp = df_clean.copy()
            if not isinstance(df_temp.index, pd.DatetimeIndex):
                dt_idx = pd.to_datetime(df_temp.index, errors="coerce")
                if not dt_idx.isna().all():
                    df_temp.index = dt_idx
            if isinstance(df_temp.index, pd.DatetimeIndex):
                agg_dict = {
                    "Open": "first", "High": "max", "Low": "min", "Close": "last"
                }
                if "Volume" in df_temp.columns:
                    agg_dict["Volume"] = "sum"
                df_w = df_temp.resample("W-FRI").agg(agg_dict).dropna(subset=["Open", "High", "Low", "Close"])
                if len(df_w) >= 15:
                    w_swings = pa.extract_swings(df_w, order=3, confirmed_only=True)
                    htf_wave = pa.classify_wave_pattern(w_swings, df_w)
                    htf_pat = htf_wave.get("pattern", "")
                    htf_cur = str(htf_wave.get("current_wave", ""))
                    d_pat = struct["wp"].get("pattern", "")
                    d_cur = str(struct["wp"].get("current_wave", ""))

                    is_htf_w3 = (htf_pat in ("developing_wave_3", "impulse_5_wave") or "3" in htf_cur)
                    is_daily_w24 = (d_pat in ("wave_2_correction", "wave_4_correction", "developing_wave_3", "developing_wave_5")
                                    or "2" in d_cur or "4" in d_cur or "3" in d_cur)
                    if is_htf_w3 and is_daily_w24:
                        fractal_resonance = {
                            "active": True,
                            "htf_period": "1w",
                            "htf_wave_pattern": htf_pat,
                            "daily_wave_pattern": d_pat,
                            "desc": "周线大级别第3浪主升 + 日线健康次回调/推进，跨周期共振高胜率买点"
                        }
        except Exception:
            pass

    trade_plan = _build_trade_plan(
        pa,
        df_clean,
        current_price,
        struct,
        turn_windows_res,
        is_crypto=is_crypto,
        is_us=is_us,
        dow_market_ver=dow_market_ver,
    )

    # 阶段 4：前端图表标注序列化与紧凑价位标尺
    annotations, wave_points_summary, compact_scale = _build_chart_annotations(
        pa, df_clean, current_price, is_intraday, struct, trade_plan, turn_windows_res
    )
    struct["wave"]["points"] = wave_points_summary

    # 生成结构化深度诊断综述
    depth_diagnosis = _generate_depth_diagnosis(struct, trade_plan, turn_windows_res, current_price, dow_market_ver=dow_market_ver)

    return {
        "symbol": symbol,
        "period": period,
        "mode": mode,
        "current_price": current_price,
        "summary": {
            "dow_phase": struct["dow_phase"],
            "dow_bias": struct["dow_bias"],
            "ema_200_gate": struct["ema_200_gate"],
            "box": struct["box"],
            "channel": struct["channel"],
            "wave": struct["wave"],
            "fractal_resonance": fractal_resonance,
            "turn_windows": turn_windows_res,
            "turning_dates": turn_windows_res.get("turning_dates", []),
            "trade_plan": trade_plan,
            "buy_triggers": trade_plan.get("buy_triggers"),
            "sell_triggers": trade_plan.get("sell_triggers"),
            "depth_diagnosis": depth_diagnosis,
            "compact_scale": compact_scale,
            "dow_market_verification": dow_market_ver,
            "escape_level": trade_plan.get("escape_level"),
            "wave_setup": trade_plan.get("wave_setup"),
            "sell_stages": trade_plan.get("sell_stages", []),
            "html_url": f"/api/strategy/html?symbol={symbol}&period={period}",
        },
        "annotations": annotations,
    }


def generate_wave_chart_html(symbol: str, period: str = "1d", df: Optional[Any] = None) -> str:
    """生成波浪报告 HTML 视图 (优先调用内置 plot_wave_chart 生成 Plotly 单文件报表)。"""
    clean_sym = strip_prefix(symbol)
    df_norm = _prepare_strategy_df(symbol, df)
    
    try:
        from strategy_core.plot_wave_chart import plot_wave_chart
        
        results_dir = BASE_DIR / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        out_path = results_dir / f"{clean_sym}_wave_chart.html"
        
        temp_csv = None
        if df_norm is not None and not df_norm.empty:
            temp_csv = LOCAL_DATA_DIR / f"{clean_sym}_temp.csv"
            df_norm.to_csv(temp_csv)
            
        bars_count = len(df_norm) if df_norm is not None else 120
        plot_wave_chart(
            ticker=clean_sym,
            csv_path=temp_csv or (LOCAL_DATA_DIR / f"{clean_sym}.csv"),
            output_path=out_path,
            lookback_bars=min(120, bars_count) if bars_count > 0 else 120,
        )
        if temp_csv and temp_csv.exists():
            try:
                temp_csv.unlink()
            except Exception:
                pass

        if out_path.exists():
            with open(out_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        pass

    # 兜底轻量级 HTML
    return (
        f"<html><head><meta charset='utf-8'></head><body style='background:#0f172a;color:#f8fafc;padding:40px;font-family:sans-serif;'>"
        f"<h2>{clean_sym} 波浪报告已全面合入主图</h2>"
        f"<p style='color:#94a3b8;'>StockVision 现已在主图直观呈现结构锚点卡片、局部右延 Fibonacci 扩展位、缺口共振区与 200 EMA 均线，无需额外跳转。</p>"
        f"<div style='margin-top:20px;padding:16px;background:#1e293b;border-radius:8px;font-family:monospace;'>{clean_sym} ({period}) 数据分析完成</div>"
        f"</body></html>"
    )
