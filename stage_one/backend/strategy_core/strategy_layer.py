#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy_layer.py: 位置层（Location）、触发层（Trigger）与风控执行闭环（Execution）

理论依据（见 strategy_theory.md 与 backtest_result_v2.md）：
  1. 方向层 (Direction): 仅作为守门人（Gatekeeper），提供交易许可（side: +1 多 / -1 空）。
     严禁按突破K线市价盲目追高入场（解决 MAE -5.1% 的深幅回撤痛点）。
  2. 位置层 (Location): 突破后等待回调回踩关键结构位（Broken Swing High/Low）
     或斐波那契回撤区（Fib 50% / 61.8%），挂限价单（Limit Order）入场。
  3. 触发层 (Trigger): 在关键位置等待裸K反转确认（2B 流动性猎杀、拒绝 Pin Bar、吞没形态），
     配合基于 ATR/中位振幅 的紧密结构证伪止损（Tight Invalidation Stop）。
  4. 风险报酬与执行层 (Risk-Reward & Execution):
     - 硬闸门：RR >= min_rr (默认 2.0)，低于 1:2 一票否决；
     - 保守撮合：同一根 K 线若同时触及止损与止盈，一律判定为止损先触发；
     - 零未来函数：第 t 根决策，限价单/触发监控从 t+1 开始生效，触发后次根开盘入场。
"""

import numpy as np
import pandas as pd
from . import pa_engine as pe

# 默认风控参数
DEFAULT_STOP_BUFFER_K = 0.8
DEFAULT_MAX_WAIT_BARS = 15
DEFAULT_MIN_RR = 2.0
DEFAULT_MAX_HOLD_BARS = 40

# 美股重大系统性危机窗口（黑天鹅极端行情，供 --exclude-black-swans 全流程剔除）
# 窗口与 docs/backtest_result_v1.md 记录的历史危机覆盖期一致，取急性发作段边界
STOCK_BLACK_SWANS = [
    {
        "name": "2008 全球金融危机 (雷曼崩溃与 GFC)",
        "start": "2008-09-01",
        "end": "2009-03-31",
        "description": "系统性银行危机，指数自高点腰斩，流动性枯竭"
    },
    {
        "name": "2011 美债降级与欧债危机",
        "start": "2011-08-01",
        "end": "2011-10-31",
        "description": "标普下调美国主权评级，两周内近 20% 暴跌"
    },
    {
        "name": "2015-16 中国熔断与全球闪崩回调",
        "start": "2015-08-01",
        "end": "2016-02-29",
        "description": "8·24 美股闪崩 + 2016 年初连环暴跌"
    },
    {
        "name": "2018 Q4 加息恐慌滚动暴跌",
        "start": "2018-10-01",
        "end": "2018-12-31",
        "description": "鹰派加息预期引发四季度近 20% 滚动杀跌"
    },
    {
        "name": "2020 新冠疫情熔断危机",
        "start": "2020-02-19",
        "end": "2020-04-30",
        "description": "五周 34% 暴跌，十日内四次熔断，流动性挤兑"
    },
    {
        "name": "2022 加息周期熊市",
        "start": "2022-01-01",
        "end": "2022-10-31",
        "description": "激进加息压缩估值，指数近 25% 熊市至 10 月触底"
    }
]


def is_stock_black_swan(date_val) -> bool:
    """
    检查指定日期是否落在美股重大系统性危机窗口内。
    """
    if date_val is None:
        return False
    try:
        d = pd.to_datetime(date_val)
        d = d.tz_localize(None) if hasattr(d, 'tz_localize') and d.tz is not None else d
    except Exception:
        return False
    for bs in STOCK_BLACK_SWANS:
        s = pd.to_datetime(bs["start"])
        e = pd.to_datetime(bs["end"])
        if s <= d <= e:
            return True
    return False


def trade_overlaps_stock_black_swan(entry_date, exit_date) -> bool:
    """
    检查交易生命周期 [entry_date, exit_date] 是否与美股系统性危机窗口重叠。
    """
    try:
        e_d = pd.to_datetime(entry_date)
        e_d = e_d.tz_localize(None) if hasattr(e_d, 'tz_localize') and e_d.tz is not None else e_d
        x_d = pd.to_datetime(exit_date)
        x_d = x_d.tz_localize(None) if hasattr(x_d, 'tz_localize') and x_d.tz is not None else x_d
    except Exception:
        return False
    for bs in STOCK_BLACK_SWANS:
        s = pd.to_datetime(bs["start"])
        e = pd.to_datetime(bs["end"])
        if not (x_d < s or e_d > e):
            return True
    return False


# ==============================================================================
# 1. 结构位与斐波那契回撤提取 (Location Layer)
# ==============================================================================

def extract_breakout_levels(df: pd.DataFrame, t: int, side: int, swings: list,
                            buffer_k: float = 0.0) -> dict:
    """
    在第 t 根决策K线上，提取被突破的结构位、结构锚点以及斐波那契回撤位。
    严格只使用 <= t 的数据。
    """
    if len(swings) < 2 or t < 0 or t >= len(df):
        return {}

    conf = [s for s in swings if s.get("confirmed")]
    if len(conf) < 2:
        conf = swings

    highs = [s for s in conf if s.get("type") == "High"]
    lows = [s for s in conf if s.get("type") == "Low"]
    if not highs or not lows:
        return {}

    bar_rng = pe.median_bar_range(df.iloc[:t + 1], n=14)
    buf = buffer_k * bar_rng

    c_curr_high = float(df["High"].iloc[t])
    c_curr_low = float(df["Low"].iloc[t])
    c_close = float(df["Close"].iloc[t])

    if side == 1:
        # 多头突破：被突破的高点阻力转支撑
        h_break = float(highs[-1]["price"])
        l_anchor = float(lows[-1]["price"])
        l_anchor_idx = int(lows[-1].get("index", 0))
        # 提取自锚点低点以来整个冲量波段的真实最高点（严格 <= t，无未来函数）
        leg_high = float(df["High"].iloc[l_anchor_idx:t + 1].max()) if l_anchor_idx <= t else c_curr_high
        peak = max(c_curr_high, c_close, h_break, leg_high)
        impulse_leg = max(peak - l_anchor, bar_rng)

        fib50 = peak - 0.50 * impulse_leg
        fib618 = peak - 0.618 * impulse_leg
        structural_stop = round(l_anchor - DEFAULT_STOP_BUFFER_K * bar_rng, 2)

        return {
            "side": 1,
            "h_break": round(h_break, 2),
            "l_anchor": round(l_anchor, 2),
            "peak": round(peak, 2),
            "impulse_leg": round(impulse_leg, 2),
            "fib50": round(fib50, 2),
            "fib618": round(fib618, 2),
            "structural_stop": structural_stop,
            "bar_rng": round(bar_rng, 2),
            "swing_retest": round(h_break, 2),
        }
    elif side == -1:
        # 空头跌破：被跌破的低点支撑转阻力
        l_break = float(lows[-1]["price"])
        h_anchor = float(highs[-1]["price"])
        h_anchor_idx = int(highs[-1].get("index", 0))
        # 提取自锚点高点以来整个冲量下跌波段的真实最低点（严格 <= t，无未来函数）
        leg_low = float(df["Low"].iloc[h_anchor_idx:t + 1].min()) if h_anchor_idx <= t else c_curr_low
        trough = min(c_curr_low, c_close, l_break, leg_low)
        impulse_leg = max(h_anchor - trough, bar_rng)

        fib50 = trough + 0.50 * impulse_leg
        fib618 = trough + 0.618 * impulse_leg
        structural_stop = round(h_anchor + DEFAULT_STOP_BUFFER_K * bar_rng, 2)

        return {
            "side": -1,
            "l_break": round(l_break, 2),
            "h_anchor": round(h_anchor, 2),
            "trough": round(trough, 2),
            "impulse_leg": round(impulse_leg, 2),
            "fib50": round(fib50, 2),
            "fib618": round(fib618, 2),
            "structural_stop": structural_stop,
            "bar_rng": round(bar_rng, 2),
            "swing_retest": round(l_break, 2),
        }
    return {}


# ==============================================================================
# 2. 宏观主趋势与跨市场板块门禁 (Macro Primary Trend & Cross-Market Sector Gates)
# ==============================================================================

TECH_SECTORS = {
    "tech", "technology", "information_technology", "software", "semiconductor",
    "semiconductors", "hardware", "internet", "communication", "qqq", "xlk", "smh"
}
VALUE_INDUSTRIAL_SECTORS = {
    "industrial", "industrials", "manufacturing", "aerospace", "financial",
    "financials", "bank", "banks", "insurance", "energy", "oil", "gas",
    "materials", "basic_materials", "chemicals", "staples", "consumer_staples",
    "healthcare", "health", "pharma", "utilities", "utility", "value", "cyclical",
    "old_economy", "dia", "xli", "xlf", "xle", "xlv", "xlp", "xlu"
}
SMALL_CAP_SECTORS = {"small_cap", "smallcap", "russell", "iwm"}

SYMBOL_SECTOR_MAP = {
    # 科技类
    "AAPL": "technology", "MSFT": "technology", "NVDA": "technology", "GOOGL": "technology",
    "AMZN": "technology", "META": "technology", "TSLA": "technology", "QQQ": "technology",
    "XLK": "technology", "SMH": "technology", "AMD": "technology", "AVGO": "technology",
    # 工业 / 价值 / 金融类
    "CAT": "industrials", "BA": "industrials", "GE": "industrials", "HON": "industrials",
    "UNP": "industrials", "XLI": "industrials", "DIA": "industrials", "MMM": "industrials",
    "JPM": "financials", "BAC": "financials", "GS": "financials", "XLF": "financials",
    "XOM": "energy", "CVX": "energy", "XLE": "energy",
    "JNJ": "healthcare", "PFE": "healthcare", "XLV": "healthcare", "UNH": "healthcare",
    # 小盘类
    "IWM": "small_cap"
}


def verify_primary_trend_gate(df: pd.DataFrame, side: int, ema_period: int = 200, t: int = None) -> dict:
    """
    200 EMA 大级别主趋势顺势门禁 (Primary Trend Gate - Dow Theory Smooth Proxy):

    在理论与量化体系中确立 200 EMA 为道氏理论大级别主趋势（Primary Trend）的连续平滑数学代理。
    严格遵循纯因果律与零未来函数：
      - side == 1 (多头)：现价需 >= 200 EMA，顺应大级别主多头趋势；若现价 < 200 EMA 则一票否决 (rejected_by_primary_trend)；
      - side == -1 (空头)：现价需 <= 200 EMA，顺应大级别主空头趋势；若现价 > 200 EMA 则一票否决 (rejected_by_primary_trend)；
      - 历史数据不足 200 根时，采用可用序列自适应平滑降级，保证数值稳定与因果连续。

    返回格式：
      {"passed": bool, "status": str, "current_price": float, "ema_val": float, "reason": str}
    """
    if df is None or len(df) == 0:
        return {
            "passed": True,
            "status": "no_data",
            "current_price": 0.0,
            "ema_val": 0.0,
            "reason": "数据为空，大级别主趋势门禁默认放行"
        }

    sub_df = df if t is None or t < 0 or t >= len(df) else df.iloc[:t + 1]
    if sub_df.empty:
        return {
            "passed": True,
            "status": "no_data",
            "current_price": 0.0,
            "ema_val": 0.0,
            "reason": "切片数据为空，大级别主趋势门禁默认放行"
        }

    close_col = "Close" if "Close" in sub_df.columns else "close"
    if close_col not in sub_df.columns:
        return {
            "passed": True,
            "status": "no_data",
            "current_price": 0.0,
            "ema_val": 0.0,
            "reason": "缺少 Close 列，大级别主趋势门禁默认放行"
        }

    close_series = sub_df[close_col].astype(float)
    n_bars = len(close_series)
    curr_price = float(close_series.iloc[-1])

    # 纯因果 EMA 计算 (使用 pandas ewm, adjust=False 严格无未来函数)
    span_val = min(n_bars, ema_period) if n_bars < ema_period else ema_period
    ema_series = close_series.ewm(span=span_val, adjust=False).mean()
    ema_val = float(ema_series.iloc[-1])

    is_fallback = (n_bars < ema_period)
    fb_note = f"（历史数据仅 {n_bars} 根 < {ema_period} 根，采用可用周期自适应平滑代理）" if is_fallback else ""

    if side == 1:
        if curr_price >= ema_val - 1e-8:
            return {
                "passed": True,
                "status": "confirmed_by_primary_trend",
                "current_price": round(curr_price, 4),
                "ema_val": round(ema_val, 4),
                "reason": f"现价 (${curr_price:.2f}) >= {ema_period} EMA (${ema_val:.2f})，顺应道氏主要多头趋势{fb_note}"
            }
        else:
            return {
                "passed": False,
                "status": "rejected_by_primary_trend",
                "current_price": round(curr_price, 4),
                "ema_val": round(ema_val, 4),
                "reason": f"现价 (${curr_price:.2f}) < {ema_period} EMA (${ema_val:.2f})，逆势做多被大级别主趋势门禁驳回{fb_note}"
            }
    elif side == -1:
        if curr_price <= ema_val + 1e-8:
            return {
                "passed": True,
                "status": "confirmed_by_primary_trend",
                "current_price": round(curr_price, 4),
                "ema_val": round(ema_val, 4),
                "reason": f"现价 (${curr_price:.2f}) <= {ema_period} EMA (${ema_val:.2f})，顺应道氏主要空头趋势{fb_note}"
            }
        else:
            return {
                "passed": False,
                "status": "rejected_by_primary_trend",
                "current_price": round(curr_price, 4),
                "ema_val": round(ema_val, 4),
                "reason": f"现价 (${curr_price:.2f}) > {ema_period} EMA (${ema_val:.2f})，长牛大势下逆势摸顶做空被门禁驳回{fb_note}"
            }
    else:
        return {
            "passed": True,
            "status": "neutral",
            "current_price": round(curr_price, 4),
            "ema_val": round(ema_val, 4),
            "reason": f"无明确方向偏向 (side={side})"
        }


def verify_market_dow_gate(market_dow: dict = None,
                           target_symbol_or_side = None,
                           target_sector: str = None,
                           side: int = None,
                           allow_decoupling: bool = False,
                           micro_conviction: str = None,
                           target_symbol: str = None,
                           market_data: dict = None,
                           **kwargs) -> dict:
    """
    大盘多指数印证与板块解耦硬闸门 (Multi-Index Market Confirmation & Sector Decoupling Gate):

    重构特性 (M3 / Requirements R2 & R3):
      1. 解除 SPY/QQQ 机械死锁与同义反复，支持 SPY(大盘), QQQ(科技), DIA(工业/价值), IWM(小盘/广度) 多维度协同；
      2. 板块独立性印证：科技回调但工业走强时，判定为板块轮动，非科技标的多头放行；
      3. 微观结构超越宏观 (Micro Trumps Macro)：高确定性突破(strong_box_breakout / strong_2b_reversal)
         允许与宏观逆风脱钩，标记 decoupled_micro_alpha 放行；
      4. 美股做空非对称保护：大盘顺势长牛时严禁盲目做空，做空需大势破位确认或 2B 顶反转脱钩。
    """
    if market_dow is None and market_data is not None:
        market_dow = market_data

    # 解析多态参数 target_symbol_or_side
    if isinstance(target_symbol_or_side, (int, float)):
        actual_side = int(target_symbol_or_side)
        actual_target_symbol = target_symbol or kwargs.get("target_symbol")
    elif isinstance(target_symbol_or_side, str):
        actual_target_symbol = target_symbol_or_side
        actual_side = side if side is not None else kwargs.get("side", 1)
    else:
        actual_side = side if side is not None else kwargs.get("side", 1)
        actual_target_symbol = target_symbol or kwargs.get("target_symbol")

    actual_sector = target_sector or kwargs.get("target_sector")
    actual_allow_decoupling = allow_decoupling or kwargs.get("allow_decoupling", False)
    actual_micro_conviction = micro_conviction or kwargs.get("micro_conviction")

    if not market_dow:
        return {
            "passed": True,
            "status": "no_market_data",
            "reason": "未提供大盘数据，闸门默认放行",
            "indices_checked": []
        }

    candidate_indices = ["SPY", "QQQ", "DIA", "IWM"]
    # 额外补充字典中传入的其他大盘基准键 (如行业 ETF)
    extra_indices = [k for k in market_dow.keys() if isinstance(k, str) and len(k) <= 5 and k.isupper() and k not in candidate_indices]
    all_indices = candidate_indices + extra_indices

    indices_checked = []
    index_status = {}

    for sym in all_indices:
        has_direct = sym in market_dow
        has_phase = f"{sym}_phase" in market_dow
        has_bias = f"{sym}_bias" in market_dow
        has_bd = f"{sym}_breakdown" in market_dow

        if not (has_direct or has_phase or has_bias or has_bd):
            continue

        indices_checked.append(sym)
        is_bear = False
        is_bull = False
        is_breakdown = False
        bias_val = 0
        reason = ""

        val = market_dow.get(sym)
        if isinstance(val, dict):
            mtf_info = val.get("mtf", {})
            htf_info = val.get("htf", {})
            mtf_phase = str(mtf_info.get("phase", ""))
            htf_phase = str(htf_info.get("phase", ""))

            is_mtf_bear = ("空头" in mtf_phase or "偏空" in mtf_phase or "LH+LL" in mtf_phase or "bear" in mtf_phase.lower())
            is_htf_bear = ("空头" in htf_phase or "偏空" in htf_phase or "LH+LL" in htf_phase or "bear" in htf_phase.lower())
            is_mtf_bull = ("多头" in mtf_phase or "偏多" in mtf_phase or "HH+HL" in mtf_phase or "bull" in mtf_phase.lower())

            is_breakdown = bool(val.get("is_breakdown") or mtf_info.get("is_breakdown") or "破位" in mtf_phase)

            swings_mtf = mtf_info.get("swings", [])
            has_lh_ll = any("LH" in str(s) or "LL" in str(s) for s in swings_mtf[-2:]) if swings_mtf else False
            has_hh_hl = any("HH" in str(s) or "HL" in str(s) for s in swings_mtf[-2:]) if swings_mtf else False

            if is_breakdown:
                is_bear = True
                bias_val = -2
                reason = f"{sym} 当日收盘处于破位空翻状态"
            elif is_mtf_bear or (has_lh_ll and is_htf_bear):
                is_bear = True
                bias_val = -1
                reason = f"{sym} 处于道氏空头结构 ({mtf_phase or 'LH+LL'})"
            elif is_mtf_bull or has_hh_hl:
                is_bull = True
                bias_val = 1
                reason = f"{sym} 处于道氏多头结构 ({mtf_phase or 'HH+HL'})"

            if "bias" in val and isinstance(val["bias"], (int, float)):
                bias_val = val["bias"]
        elif isinstance(val, pd.DataFrame):
            if not val.empty and len(val) >= 10:
                sw = pe.extract_swings(val, order=5)
                b_val = pe.dow_bias(sw, df=val)
                bias_val = b_val
                if len(val) >= 200:
                    c_col = "Close" if "Close" in val.columns else "close"
                    ema200 = float(val[c_col].ewm(span=200, adjust=False).mean().iloc[-1])
                    curr_c = float(val[c_col].iloc[-1])
                    if curr_c < ema200:
                        is_breakdown = True
                        is_bear = True
                        reason = f"{sym} 收盘跌破 200 EMA 牛熊分水岭"
                if b_val <= -1:
                    is_bear = True
                    reason = f"{sym} 结构偏向处于空头破位 (dow_bias={b_val})"
                elif b_val >= 1:
                    is_bull = True
                    reason = f"{sym} 结构偏向处于多头顺势 (dow_bias={b_val})"
        elif isinstance(val, (int, float)):
            bias_val = val
            if val <= -1:
                is_bear = True
                reason = f"{sym} 道氏偏向为负 ({val})"
            elif val >= 1:
                is_bull = True
                reason = f"{sym} 道氏偏向为正 ({val})"
        elif isinstance(val, str):
            if "空头" in val or "bear" in val.lower() or "破位" in val or "breakdown" in val.lower():
                is_bear = True
                bias_val = -1
                reason = f"{sym} 状态标记为空头 ({val})"
                if "破位" in val or "breakdown" in val.lower():
                    is_breakdown = True
                    bias_val = -2
            elif "多头" in val or "bull" in val.lower():
                is_bull = True
                bias_val = 1
                reason = f"{sym} 状态标记为多头 ({val})"

        # 检查扁平键补强
        bd_flag = market_dow.get(f"{sym}_breakdown", False)
        if bd_flag:
            is_breakdown = True
            is_bear = True
            bias_val = -2
            reason = f"{sym} 处于破位空翻状态"

        phase_str = str(market_dow.get(f"{sym}_phase", ""))
        if phase_str:
            if "空头" in phase_str or "bear" in phase_str.lower() or "破位" in phase_str:
                is_bear = True
                bias_val = -1
                reason = f"{sym} 处于道氏空头结构 ({phase_str})"
                if "破位" in phase_str:
                    is_breakdown = True
                    bias_val = -2
            elif "多头" in phase_str or "bull" in phase_str.lower():
                is_bull = True
                bias_val = 1
                reason = f"{sym} 处于道氏多头结构 ({phase_str})"

        b_flat = market_dow.get(f"{sym}_bias")
        if b_flat is not None and isinstance(b_flat, (int, float)):
            bias_val = b_flat
            if b_flat <= -1:
                is_bear = True
                reason = f"{sym} 偏向为负 ({b_flat})"
            elif b_flat >= 1:
                is_bull = True
                reason = f"{sym} 偏向为正 ({b_flat})"

        index_status[sym] = {
            "is_bear": is_bear,
            "is_bull": is_bull,
            "is_breakdown": is_breakdown,
            "bias": bias_val,
            "reason": reason
        }

    if not indices_checked:
        return {
            "passed": True,
            "status": "no_market_data",
            "reason": "未提供有效大盘指数数据，闸门默认放行",
            "indices_checked": []
        }

    # 1. 微观结构超越宏观 (Micro Trumps Macro) 解耦规则
    valid_micro_convictions = {"strong_box_breakout", "strong_2b_reversal"}
    if actual_allow_decoupling and (actual_micro_conviction in valid_micro_convictions):
        return {
            "passed": True,
            "status": "decoupled_micro_alpha",
            "reason": f"微观高确定性形态 ({actual_micro_conviction}) 触发 Micro Trumps Macro 脱钩豁免，放行独立 Alpha 交易",
            "indices_checked": indices_checked
        }

    # 2. 多头交易判定 (side == 1)
    if actual_side == 1:
        # 识别标的行业归属
        sec = None
        if actual_sector:
            sec = str(actual_sector).lower()
        elif actual_target_symbol and str(actual_target_symbol).upper() in SYMBOL_SECTOR_MAP:
            sec = SYMBOL_SECTOR_MAP[str(actual_target_symbol).upper()]

        is_tech = sec in TECH_SECTORS if sec else False
        is_value_ind = sec in VALUE_INDUSTRIAL_SECTORS if sec else False
        is_small_cap = sec in SMALL_CAP_SECTORS if sec else False

        spy_st = index_status.get("SPY", {})
        qqq_st = index_status.get("QQQ", {})
        dia_st = index_status.get("DIA", {})
        iwm_st = index_status.get("IWM", {})

        # 系统性大盘崩盘检测：SPY 与 QQQ 同时出现破位/空头
        both_spy_qqq_breakdown = (
            spy_st.get("is_breakdown", False) and qqq_st.get("is_breakdown", False)
        )
        if both_spy_qqq_breakdown:
            return {
                "passed": False,
                "status": "rejected_by_market_dow",
                "reason": "标普 (SPY) 与纳指 (QQQ) 双双发生结构性空头破位，触发系统性市场危机拦截",
                "indices_checked": indices_checked
            }

        # 板块独立性与分化印证 (Sector Divergence & Corroboration)
        # 若纳指 QQQ 偏弱，但非科技基准（DIA 工业/价值 或 IWM 小盘）走强且 SPY 未破位：
        if qqq_st.get("is_bear", False) and not spy_st.get("is_breakdown", False):
            if is_value_ind and (dia_st.get("bias", 0) > 0 or dia_st.get("is_bull", False) or (not dia_st.get("is_bear", False) and dia_st)):
                return {
                    "passed": True,
                    "status": "confirmed_by_market",
                    "reason": "科技基准 (QQQ) 走弱但工业/价值基准 (DIA) 走强，判定为板块良性轮动，非科技标的多头放行",
                    "indices_checked": indices_checked
                }
            elif is_small_cap and (iwm_st.get("bias", 0) > 0 or iwm_st.get("is_bull", False)):
                return {
                    "passed": True,
                    "status": "confirmed_by_market",
                    "reason": "纳指 (QQQ) 回调但小盘股基准 (IWM) 走强，市场广度良好，小盘多头放行",
                    "indices_checked": indices_checked
                }

        # 常规多头门禁检查
        bearish_reasons = []
        # 根据板块决定检查的基准
        if is_value_ind and "DIA" in index_status:
            relevant_syms = ["SPY", "DIA"]
        elif is_small_cap and "IWM" in index_status:
            relevant_syms = ["SPY", "IWM"]
        elif is_tech:
            relevant_syms = ["SPY", "QQQ"]
        else:
            # 默认检查 SPY 与 QQQ（保持基线兼容）
            relevant_syms = [s for s in ["SPY", "QQQ"] if s in index_status]

        for s in relevant_syms:
            st = index_status.get(s, {})
            if st.get("is_bear"):
                bearish_reasons.append(st.get("reason", f"{s} 处于空头结构"))

        if bearish_reasons:
            return {
                "passed": False,
                "status": "rejected_by_market_dow",
                "reason": "；".join(bearish_reasons),
                "indices_checked": indices_checked
            }

        return {
            "passed": True,
            "status": "confirmed_by_market",
            "reason": f"大盘指数 ({', '.join(indices_checked)}) 未处于空头破位结构，印证通过",
            "indices_checked": indices_checked
        }

    # 3. 空头交易判定 (side == -1，非对称做空门禁)
    else:
        # 美股做空必须有大势逆转依据（大盘破位 / 偏向负向 / 200 EMA 下方）
        has_bearish_market = any(
            st.get("is_bear", False) or st.get("is_breakdown", False) or st.get("bias", 0) <= -1
            for st in index_status.values()
        )

        if has_bearish_market:
            bear_syms = [s for s, st in index_status.items() if st.get("is_bear") or st.get("bias", 0) <= -1]
            return {
                "passed": True,
                "status": "confirmed_by_market",
                "reason": f"大盘指数 ({', '.join(bear_syms)}) 出现空头破位/偏空结构，放行做空计划",
                "indices_checked": indices_checked
            }
        else:
            return {
                "passed": False,
                "status": "rejected_by_market_dow",
                "rejected_by": "rejected_by_macro_short_gate",
                "reason": f"大盘指数 ({', '.join(indices_checked)}) 处于多头顺势结构，美股长牛向上漂移环境下禁止盲目做空（rejected_by_macro_short_gate）",
                "indices_checked": indices_checked
            }


def verify_macro_short_gate(market_dow: dict = None,
                            df: pd.DataFrame = None,
                            t: int = None,
                            micro_conviction: str = None,
                            allow_decoupling: bool = False,
                            target_symbol: str = None,
                            **kwargs) -> dict:
    """
    非对称做空风险门禁 (Asymmetric Short-Selling Risk Gate - Requirement R4):
    美股长期具有向上漂移与内在正向偏向，严禁常规/盲目无差别做空。
    做空仅在满足以下任一高确定性条件时放行：
      1. 市场宏观结构破位：大盘指数 (SPY/QQQ/DIA/IWM) 跌破 200 EMA 或处于道氏空头破位结构 (bias <= -1 / breakdown)；
      2. 标的自身大级别破位：标的现价处于 200 EMA 下方；
      3. 高确定性微观流动性猎杀反转：高位 2B 假突破 (strong_2b_reversal / 2b_top_sweep / 2B_sweep_high) 扫除买方流动性；
    若大盘处于顺势多头且无高确定性 2B 反转/宏观破位，一票否决 (rejected_by_macro_short_gate)。
    """
    # 1. 高确定性 2B 顶假突破流动性猎杀反转豁免
    valid_reversals = {"strong_2b_reversal", "2b_top_sweep", "2B_sweep_high", "2B_sweep_high_PDH", "2B_sweep_high_PMH", "2B_sweep_high_ORH"}
    conv_str = str(micro_conviction or "")
    if conv_str in valid_reversals or any(vr in conv_str.lower() for vr in ["2b_reversal", "2b_sweep_high", "2b_top"]) or (allow_decoupling and conv_str in valid_reversals):
        return {
            "passed": True,
            "status": "decoupled_2b_short_reversal",
            "reason": f"高确定性 2B 顶流动性猎杀形态 ({conv_str}) 触发反转做空放行",
            "micro_conviction": conv_str
        }

    # 2. 标的自身跌破 200 EMA 大级别主趋势空翻
    if df is not None and not df.empty:
        trend_res = verify_primary_trend_gate(df, side=-1, t=t)
        if trend_res.get("passed"):
            return {
                "passed": True,
                "status": "confirmed_by_primary_trend",
                "reason": "标的现价处于 200 EMA 下方，顺应大级别主空头趋势放行做空",
                "trend_gate": trend_res
            }

    # 3. 大盘指数破位或空头结构印证
    if market_dow:
        market_res = verify_market_dow_gate(market_dow=market_dow, side=-1,
                                            allow_decoupling=allow_decoupling,
                                            micro_conviction=micro_conviction,
                                            target_symbol=target_symbol)
        if market_res.get("passed"):
            return {
                "passed": True,
                "status": "confirmed_by_macro_short_gate",
                "reason": market_res.get("reason", "大盘出现空头破位，放行做空"),
                "market_gate": market_res
            }
        else:
            return {
                "passed": False,
                "status": "rejected_by_macro_short_gate",
                "rejected_by": "rejected_by_macro_short_gate",
                "reason": market_res.get("reason", "大盘处于顺势多头结构，禁止盲目做空 (rejected_by_macro_short_gate)"),
                "market_gate": market_res
            }

    # 若未提供任何大盘或趋势数据，默认审慎拦截盲目做空
    return {
        "passed": False,
        "status": "rejected_by_macro_short_gate",
        "rejected_by": "rejected_by_macro_short_gate",
        "reason": "缺少宏观破位或高确定性 2B 反转依据，美股顺势长牛环境下禁止盲目做空 (rejected_by_macro_short_gate)"
    }


def verify_box_gate(df: pd.DataFrame, t: int, side: int, swings: list = None) -> dict:
    """
    箱体震荡门禁（Box Consolidation Gate - Wyckoff / Brooks 价格行为学）：
    严格基于 <= t 根历史切片检测箱体状态（零未来函数）。
    在箱体内部，严格禁止阻力追买或支撑追空：
      - side == 1 (多头)：若处于箱体阻力区（pos >= 0.70）或触顶2B假突破(SWEEP_HIGH)，一票否决；
        若处于触底2B假摔(SWEEP_LOW)或有效突破(BREAKOUT_UP)，明确放行并支持反转。
      - side == -1 (空头)：若处于箱体支撑区（pos <= 0.30）或触底2B假摔(SWEEP_LOW)，一票否决；
        若处于触顶2B假突破(SWEEP_HIGH)或有效破位(BREAKOUT_DOWN)，明确放行并支持反转。
    """
    if df is None or t < 0 or t >= len(df):
        return {"passed": True, "status": "no_data"}
    sub_d = df.iloc[:t + 1]
    box = pe.detect_consolidation_box(sub_d, swings=swings)
    if not box.get("is_box", False):
        return {"passed": True, "status": "not_in_box", "box": box}

    b_pos = box.get("box_pos", 0.5)
    b_state = box.get("state", "NONE")

    if side == 1:
        if b_state == "SWEEP_HIGH":
            return {"passed": False, "status": "rejected_by_box_sweep",
                    "reason": f"触及箱顶发生 2B 假突破诱多(SWEEP_HIGH ${box['box_high']:.2f})，禁止做多", "box": box}
        if b_state == "BREAKOUT_UP":
            return {"passed": True, "status": "confirmed_by_box_breakout", "box": box}
        if b_state == "SWEEP_LOW":
            return {"passed": True, "status": "confirmed_by_box_sweep_low", "box": box}
        if b_state == "IN_BOX" and b_pos >= 0.70:
            return {"passed": False, "status": "rejected_by_box_range",
                    "reason": f"处于箱体中上部阻力区(pos={b_pos:.2f} >= 0.70，阻力 ${box['box_high']:.2f})，禁止追高买入", "box": box}
    elif side == -1:
        if b_state == "SWEEP_LOW":
            return {"passed": False, "status": "rejected_by_box_sweep",
                    "reason": f"触及箱底发生 2B 假摔诱空(SWEEP_LOW ${box['box_low']:.2f})，禁止做空", "box": box}
        if b_state == "BREAKOUT_DOWN":
            return {"passed": True, "status": "confirmed_by_box_breakout", "box": box}
        if b_state == "SWEEP_HIGH":
            return {"passed": True, "status": "confirmed_by_box_sweep_high", "box": box}
        if b_state == "IN_BOX" and b_pos <= 0.30:
            return {"passed": False, "status": "rejected_by_box_range",
                    "reason": f"处于箱体中下部支撑区(pos={b_pos:.2f} <= 0.30，支撑 ${box['box_low']:.2f})，禁止低位追空", "box": box}

    return {"passed": True, "status": "confirmed_by_box", "box": box}


def verify_channel_gate(df: pd.DataFrame, t: int, side: int, swings: list = None) -> dict:
    """
    通道动态门禁（Channel Dynamic Gate - Brooks / Volman 趋势与轨道价格行为学）：
    严格基于 <= t 根历史切片计算线性回归通道（零未来函数），支持形态方向自适应过滤：
      - 上升通道 (ascending)：
          * 多头：pos <= 1.25 正常顺势推进；仅拦截极端加速冲顶脱轨区 (pos > 1.25)；
          * 空头：0.0 <= pos <= 0.25 处于下轨动态支撑区，严禁逆势杀跌；若向下击穿下轨 (pos < 0.0) 属破位放行。
      - 下降通道 (descending)：
          * 多头：0.65 <= pos <= 1.00 处于反弹测试上轨阻力区，严禁追多；若向上突破上轨 (pos > 1.00) 属反转破位放行；
          * 空头：顺势推进放行；仅拦截严重恐慌脱轨超跌区 (pos < -0.30)。
      - 水平通道 (horizontal)：
          * 多头：pos >= 0.85 上轨超买阻力区禁多；
          * 空头：pos <= 0.15 下轨超卖支撑区禁空。
    """
    if df is None or t < 0 or t >= len(df):
        return {"passed": True, "status": "no_data"}
    sub_d = df.iloc[:t + 1]
    chan = pe.detect_price_channel(sub_d, swings=swings)

    c_pos = chan.get("channel_pos", 0.5)
    c_type = chan.get("channel_type", "horizontal")

    if side == 1:
        if c_type == "ascending" and c_pos > 1.25:
            return {"passed": False, "status": "rejected_by_channel_overbought",
                    "reason": f"触及上升通道动态极度冲顶超买区(pos={c_pos:.2f} > 1.25，上轨 ${chan['upper_rail']:.2f})，禁止追高", "channel": chan}
        elif c_type == "descending" and (0.65 <= c_pos <= 1.00):
            return {"passed": False, "status": "rejected_by_channel_resistance",
                    "reason": f"触及下降通道上轨阻力区(pos={c_pos:.2f} in [0.65, 1.00]，阻力 ${chan['upper_rail']:.2f})，禁止逆势摸顶追多", "channel": chan}
        elif c_type == "horizontal" and c_pos >= 0.85:
            return {"passed": False, "status": "rejected_by_channel_overbought",
                    "reason": f"触及水平通道上轨超买区(pos={c_pos:.2f} >= 0.85，上轨 ${chan['upper_rail']:.2f})，禁止追多", "channel": chan}
    elif side == -1:
        if c_type == "descending" and c_pos < -0.30:
            return {"passed": False, "status": "rejected_by_channel_oversold",
                    "reason": f"触及下降通道极端恐慌超卖区(pos={c_pos:.2f} < -0.30，下轨 ${chan['lower_rail']:.2f})，禁止杀跌", "channel": chan}
        elif c_type == "ascending" and (0.0 <= c_pos <= 0.25):
            return {"passed": False, "status": "rejected_by_channel_support",
                    "reason": f"触及上升通道下轨动态支撑区(pos={c_pos:.2f} <= 0.25，下轨 ${chan['lower_rail']:.2f})，禁止逆势杀跌做空", "channel": chan}
        elif c_type == "horizontal" and c_pos <= 0.15:
            return {"passed": False, "status": "rejected_by_channel_oversold",
                    "reason": f"触及水平通道下轨超卖区(pos={c_pos:.2f} <= 0.15，下轨 ${chan['lower_rail']:.2f})，禁止杀跌", "channel": chan}

    return {"passed": True, "status": "confirmed_by_channel", "channel": chan}


# ==============================================================================
# 2. 限价回踩撮合模拟 (Pullback Limit Order Simulation)
# ==============================================================================

def simulate_limit_order(df: pd.DataFrame, t: int, side: int,
                         limit_price: float, stop_price: float,
                         max_wait_bars: int = DEFAULT_MAX_WAIT_BARS,
                         volume_filter: bool = False) -> dict:
    """
    模拟在第 t 根决策后挂限价回踩单（Limit Order）：
      - 挂单从 t+1 根生效，有效期限 max_wait_bars 根；
      - 多头限价单：当 Low[k] <= limit_price 时成交；若 Open[k] <= limit_price，按 Open[k] 更有利价成交；
      - 空头限价单：当 High[k] >= limit_price 时成交；若 Open[k] >= limit_price，按 Open[k] 更有利价成交；
      - 证伪撤单：若价格在成交前或同根K线击穿 stop_price，限价单被取消（失效撤单），避免接入单边崩盘；
      - 次级折返缩量洗盘过滤 (volume_filter=True)：
        检查突破后回踩至挂单成交期间的成交量：回踩期间必须呈现缩量态势（平均成交量小于突破日放量，
        且未出现异常巨量抛售或连续放量重挫），若回踩过程伴随异常巨量抛售，判定为派发，挂单自动撤销失效。
    """
    n = len(df)
    if t >= n - 1 or limit_price <= 0 or stop_price <= 0:
        return {"status": "invalid_input", "filled": False}
    if (side == 1 and limit_price <= stop_price) or (side == -1 and limit_price >= stop_price):
        return {"status": "invalid_levels", "filled": False}

    opens = df["Open"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)

    end_k = min(t + max_wait_bars, n - 1)

    for k in range(t + 1, end_k + 1):
        o, h, l = opens[k], highs[k], lows[k]

        if side == 1:
            # 多头：结构止损在下方
            stop_hit = (l <= stop_price)
            limit_hit = (l <= limit_price)

            if stop_hit and limit_hit:
                # 同一根触及止损和限价：保守判定为结构破坏，放弃入场
                return {"status": "cancelled_invalidated", "filled": False, "cancel_t": k}
            elif stop_hit:
                # 击穿止损结构位，撤单
                return {"status": "cancelled_invalidated", "filled": False, "cancel_t": k}
            elif limit_hit:
                # 次级折返缩量洗盘过滤
                if volume_filter and "Volume" in df.columns and t < n:
                    vol_break = float(df["Volume"].iloc[t])
                    if vol_break > 0:
                        pb_vols = df["Volume"].iloc[t + 1 : k + 1].to_numpy(dtype=float)
                        pb_closes = closes[t + 1 : k + 1]
                        pb_opens = opens[t + 1 : k + 1]

                        # 1. 回踩期间平均成交量大于等于突破日放量（无缩量特征）
                        avg_pb_vol = float(np.mean(pb_vols))
                        is_vol_expanding = (avg_pb_vol >= vol_break)

                        # 2. 单日异常巨量抛售（大阴线且成交量 >= 1.5 倍突破日量能）
                        single_spike = False
                        for i in range(len(pb_vols)):
                            if pb_closes[i] < pb_opens[i] and pb_vols[i] >= 1.5 * vol_break:
                                single_spike = True
                                break

                        # 3. 连续放量重挫（连续两根放量阴线）
                        consec_heavy = False
                        if len(pb_vols) >= 2:
                            for i in range(len(pb_vols) - 1):
                                if (pb_closes[i] < pb_opens[i] and pb_closes[i + 1] < pb_opens[i + 1] and
                                    pb_vols[i] >= 0.9 * vol_break and pb_vols[i + 1] >= 0.9 * vol_break):
                                    consec_heavy = True
                                    break

                        if is_vol_expanding or single_spike or consec_heavy:
                            return {
                                "status": "cancelled_volume_distribution",
                                "filled": False,
                                "cancel_t": k,
                                "reason": "回踩过程伴随放量抛售/派发，缩量洗盘假设破坏，挂单自动撤销"
                            }

                # 成功回踩限价位
                fill_price = min(o, limit_price)
                return {
                    "status": "filled",
                    "filled": True,
                    "entry_t": k,
                    "entry_price": round(float(fill_price), 2),
                    "wait_bars": k - t,
                    "stop_price": round(float(stop_price), 2)
                }
        else:
            # 空头：结构止损在上方
            stop_hit = (h >= stop_price)
            limit_hit = (h >= limit_price)

            if stop_hit and limit_hit:
                return {"status": "cancelled_invalidated", "filled": False, "cancel_t": k}
            elif stop_hit:
                return {"status": "cancelled_invalidated", "filled": False, "cancel_t": k}
            elif limit_hit:
                if volume_filter and "Volume" in df.columns and t < n:
                    vol_break = float(df["Volume"].iloc[t])
                    if vol_break > 0:
                        pb_vols = df["Volume"].iloc[t + 1 : k + 1].to_numpy(dtype=float)
                        pb_closes = closes[t + 1 : k + 1]
                        pb_opens = opens[t + 1 : k + 1]

                        avg_pb_vol = float(np.mean(pb_vols))
                        is_vol_expanding = (avg_pb_vol >= vol_break)

                        single_spike = False
                        for i in range(len(pb_vols)):
                            if pb_closes[i] > pb_opens[i] and pb_vols[i] >= 1.5 * vol_break:
                                single_spike = True
                                break

                        consec_heavy = False
                        if len(pb_vols) >= 2:
                            for i in range(len(pb_vols) - 1):
                                if (pb_closes[i] > pb_opens[i] and pb_closes[i + 1] > pb_opens[i + 1] and
                                    pb_vols[i] >= 0.9 * vol_break and pb_vols[i + 1] >= 0.9 * vol_break):
                                    consec_heavy = True
                                    break

                        if is_vol_expanding or single_spike or consec_heavy:
                            return {
                                "status": "cancelled_volume_distribution",
                                "filled": False,
                                "cancel_t": k,
                                "reason": "回抽过程伴随放量反扑，挂单自动撤销"
                            }

                fill_price = max(o, limit_price)
                return {
                    "status": "filled",
                    "filled": True,
                    "entry_t": k,
                    "entry_price": round(float(fill_price), 2),
                    "wait_bars": k - t,
                    "stop_price": round(float(stop_price), 2)
                }

    return {"status": "unfilled_expired", "filled": False, "wait_bars": end_k - t}


# ==============================================================================
# 3. 触发层形态检测 (Trigger Layer: 2B / Pin Bar / Engulfing)
# ==============================================================================

def detect_trigger_on_bar(df: pd.DataFrame, k: int, side: int,
                          key_level: float, bar_rng: float,
                          tol_k: float = 0.5) -> dict:
    """
    检测单根K线（k 根）在关键位 key_level 处是否出现同向裸K确认形态：
      1. Pin Bar（长影线拒绝）
      2. 2B 假突破 / 流动性猎杀（Liquidity Sweep）
      3. 吞没形态（Engulfing）
    返回检测结果及紧密证伪止损位。
    """
    if k < 1 or k >= len(df) or bar_rng <= 0:
        return {"triggered": False}

    curr = df.iloc[k]
    prev = df.iloc[k - 1]

    c_o, c_h, c_l, c_c = float(curr["Open"]), float(curr["High"]), float(curr["Low"]), float(curr["Close"])
    p_o, p_c = float(prev["Open"]), float(prev["Close"])

    rng = c_h - c_l
    if rng <= 0:
        return {"triggered": False}

    body = abs(c_c - c_o)
    tol = tol_k * bar_rng

    if side == 1:
        # 多头形态要求：下影线探底拒绝、假跌破收回、或阳包阴
        lower_shadow = min(c_o, c_c) - c_l
        # 1. 看涨 Pin Bar (锤子线)：下影线拒绝，且K线覆盖关键位容忍区 [key_level - tol, key_level + tol]
        is_pinbar = (lower_shadow >= 2.0 * body and (lower_shadow / rng) >= 0.55
                     and c_l <= key_level + tol and c_h >= key_level - tol)

        # 2. 2B 看涨假跌破 (Liquidity Sweep Low)
        is_2b = (c_l < key_level and c_c > key_level and c_c > c_o)

        # 3. 看涨吞没 (Bullish Engulfing)：实体吞没，且在关键位附近形成
        is_engulfing = (p_c < p_o and c_c > c_o and c_c >= p_o and c_o <= p_c
                        and c_l <= key_level + tol and c_h >= key_level - tol)

        if is_pinbar or is_2b or is_engulfing:
            pattern = ("2B_sweep" if is_2b else ("pin_bar" if is_pinbar else "engulfing"))
            # 紧密证伪止损：形态最低点下移 buffer
            tight_stop = round(c_l - DEFAULT_STOP_BUFFER_K * bar_rng, 2)
            return {
                "triggered": True,
                "pattern": pattern,
                "trigger_t": k,
                "trigger_bar_low": round(c_l, 2),
                "trigger_bar_high": round(c_h, 2),
                "tight_stop": tight_stop,
                "key_level": round(key_level, 2)
            }
    else:
        # 空头形态要求：上影线摸高拒绝、假突破收回、或阴包阳
        upper_shadow = c_h - max(c_o, c_c)
        # 1. 看跌 Pin Bar (流星线)：上影线拒绝，且K线覆盖关键位容忍区 [key_level - tol, key_level + tol]
        is_pinbar = (upper_shadow >= 2.0 * body and (upper_shadow / rng) >= 0.55
                     and c_h >= key_level - tol and c_l <= key_level + tol)

        # 2. 2B 看跌假突破 (Liquidity Sweep High)
        is_2b = (c_h > key_level and c_c < key_level and c_c < c_o)

        # 3. 看跌吞没 (Bearish Engulfing)：实体吞没，且在关键位附近形成
        is_engulfing = (p_c > p_o and c_c < c_o and c_c <= p_o and c_o >= p_c
                        and c_h >= key_level - tol and c_l <= key_level + tol)

        if is_pinbar or is_2b or is_engulfing:
            pattern = ("2B_sweep" if is_2b else ("pin_bar" if is_pinbar else "engulfing"))
            # 紧密证伪止损：形态最高点上移 buffer
            tight_stop = round(c_h + DEFAULT_STOP_BUFFER_K * bar_rng, 2)
            return {
                "triggered": True,
                "pattern": pattern,
                "trigger_t": k,
                "trigger_bar_low": round(c_l, 2),
                "trigger_bar_high": round(c_h, 2),
                "tight_stop": tight_stop,
                "key_level": round(key_level, 2)
            }

    return {"triggered": False}


def simulate_trigger_entry(df: pd.DataFrame, t: int, side: int,
                           key_level: float, bar_rng: float,
                           structural_stop: float,
                           max_wait_bars: int = DEFAULT_MAX_WAIT_BARS) -> dict:
    """
    在突破确认后（t 根），在关键位附近等待裸K反转确认信号：
      - 从 t+1 根开始扫描至 t+max_wait_bars 根；
      - 若某根 k 出现触发信号，在 k+1 根开盘（Open[k+1]）正式入场（绝对无未来函数）；
      - 止损锚定为触发K线极值外的紧密止损（Tight Stop），大幅压缩单位风险 R。
    """
    n = len(df)
    if t >= n - 2 or key_level <= 0 or bar_rng <= 0:
        return {"status": "invalid_input", "triggered": False}

    end_k = min(t + max_wait_bars, n - 2)

    for k in range(t + 1, end_k + 1):
        # 结构证伪检查：如果价格跌破了整体大结构止损，停止监控
        l_k, h_k = float(df["Low"].iloc[k]), float(df["High"].iloc[k])
        if side == 1 and l_k <= structural_stop:
            return {"status": "invalidated_before_trigger", "triggered": False, "t_stop": k}
        if side == -1 and h_k >= structural_stop:
            return {"status": "invalidated_before_trigger", "triggered": False, "t_stop": k}

        trig = detect_trigger_on_bar(df, k, side, key_level, bar_rng)
        if trig.get("triggered"):
            # k 根收盘确认形态，k+1 根开盘执行入场
            entry_t = k + 1
            entry_price = float(df["Open"].iloc[entry_t])
            tight_stop = float(trig["tight_stop"])

            # 极端开盘跳空过滤：如果开盘直接跳空穿越止损，放弃入场
            if side == 1 and entry_price <= tight_stop:
                continue
            if side == -1 and entry_price >= tight_stop:
                continue

            return {
                "status": "triggered",
                "triggered": True,
                "entry_t": entry_t,
                "entry_price": round(entry_price, 2),
                "stop_price": round(tight_stop, 2),
                "pattern": trig["pattern"],
                "trigger_bar_t": k,
                "wait_bars": k - t
            }

    return {"status": "no_trigger_expired", "triggered": False, "wait_bars": end_k - t}


# ==============================================================================
# 4. 真实持仓生命周期与风控闭环 (Risk-Reward & Execution Lifecycle)
# ==============================================================================

def simulate_strategy_trade(df: pd.DataFrame, entry_t: int, entry_price: float,
                            side: int, stop_price: float, tp_price: float,
                            max_hold_bars: int = DEFAULT_MAX_HOLD_BARS,
                            min_rr: float = DEFAULT_MIN_RR,
                            market_dow: dict = None,
                            wave_status: str = None,
                            box_gate: dict = None,
                            channel_gate: dict = None,
                            use_channel_tp: bool = False,
                            channel_info: dict = None,
                            use_tiered_tp: bool = False,
                            tp2_price: float = None,
                            impulse_leg: float = None,
                            trend_gate: dict = None,
                            use_trend_gate: bool = False,
                            target_symbol: str = None,
                            target_sector: str = None,
                            allow_decoupling: bool = False,
                            micro_conviction: str = None) -> dict:
    """
    全闭环策略持仓模拟：
      - 大盘硬闸门：若提供 market_dow，联动验证 SPY/QQQ/DIA/IWM，支持板块独立性与微观脱钩；
      - 主趋势顺势门禁：200 EMA 作为道氏大势平滑代理，顺势过滤；
      - 波浪降级约束：波浪仅作为客观结构证伪参考，不再做预测性一票否决拦截；
      - 箱体震荡门禁：若 box_gate.passed is False，拦截箱体内错误追单；
      - 通道动态门禁：若 channel_gate.passed is False，拦截通道超买追多与超卖杀跌；
      - 盈亏比硬闸门：实际规划盈亏比 RR = |tp - entry| / |entry - stop| 必须 >= min_rr，否则放弃入场；
      - 保守成交：当同一根 K 线的 [Low, High] 同时覆盖止损价与止盈价时，严格判定为「先击穿止损」；
      - 逐根推演：实时统计 MAE（最大不利偏移）、MFE（最大有利偏移）、持有根数、实现 R 倍数与收益率。
    """
    n = len(df)
    if entry_t >= n or entry_price <= 0 or stop_price <= 0 or tp_price <= 0:
        return {"status": "invalid_trade"}

    # 1. 大盘道氏印证硬闸门
    if market_dow is not None:
        m_gate = verify_market_dow_gate(
            market_dow=market_dow,
            side=side,
            target_symbol=target_symbol,
            target_sector=target_sector,
            allow_decoupling=allow_decoupling,
            micro_conviction=micro_conviction
        )
        if not m_gate.get("passed", True):
            return {
                "status": "rejected_by_market_dow",
                "rejected_by": m_gate.get("rejected_by", "rejected_by_market_dow"),
                "reason": m_gate.get("reason", "rejected_by_market_dow"),
                "entry_t": entry_t,
                "entry_price": entry_price,
                "side": side
            }

    # 1.5 200 EMA 大级别主趋势顺势门禁 (Primary Trend Gate - Dow Theory Proxy)
    if trend_gate is not None:
        if not trend_gate.get("passed", True):
            return {
                "status": "rejected_by_primary_trend",
                "reason": trend_gate.get("reason", "rejected_by_primary_trend"),
                "entry_t": entry_t,
                "entry_price": entry_price,
                "side": side
            }
    elif use_trend_gate:
        sub_d = df.iloc[:entry_t + 1] if df is not None and entry_t < len(df) else df
        t_gate = verify_primary_trend_gate(sub_d, side=side)
        if not t_gate.get("passed", True):
            return {
                "status": "rejected_by_primary_trend",
                "reason": t_gate.get("reason", "rejected_by_primary_trend"),
                "entry_t": entry_t,
                "entry_price": entry_price,
                "side": side
            }

    # 2. 波浪降级约束 (M2 / R1)
    # 彻底废除预测性数浪一票否决门禁（不再拦截 rejected_by_wave5_exhaustion）
    # 买卖决策 100% 锚定道氏结构、箱体门禁、动态通道与 2B 裸K反转

    # 3. 箱体震荡门禁 (Box Consolidation Gate)
    if box_gate is not None and not box_gate.get("passed", True):
        return {
            "status": "rejected_by_box_range",
            "reason": box_gate.get("reason", "rejected_by_box_range"),
            "entry_t": entry_t,
            "entry_price": entry_price,
            "side": side
        }

    # 4. 通道动态极值超买超卖门禁 (Channel Gate)
    if channel_gate is not None and not channel_gate.get("passed", True):
        return {
            "status": "rejected_by_channel_gate",
            "reason": channel_gate.get("reason", "rejected_by_channel_gate"),
            "entry_t": entry_t,
            "entry_price": entry_price,
            "side": side
        }

    risk = abs(entry_price - stop_price)
    reward = abs(tp_price - entry_price)

    if risk <= 0:
        return {"status": "zero_risk_invalid"}

    rr = reward / risk
    # 浮点数精度容差 1e-6，防止例如 9.86 / 4.93 = 1.9999999999999998 被误判驳回
    if rr < min_rr - 1e-6:
        return {
            "status": "rejected_by_min_rr",
            "rr": round(rr, 2),
            "min_rr": min_rr,
            "risk": round(risk, 2),
            "reward": round(reward, 2)
        }

    # 动态通道极值止盈锚定（需满足基础盈亏比 >= 1.8R）
    channel_tp = None
    if use_channel_tp and channel_info:
        if side == 1 and channel_info.get("upper_rail"):
            u_rail = float(channel_info["upper_rail"])
            if u_rail >= entry_price + 1.8 * risk:
                channel_tp = u_rail
        elif side == -1 and channel_info.get("lower_rail"):
            l_rail = float(channel_info["lower_rail"])
            if l_rail <= entry_price - 1.8 * risk:
                channel_tp = l_rail

    opens = df["Open"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)

    end_t = min(entry_t + max_hold_bars, n - 1)

    # 分级止盈模式 (Tiered Take-Profit: TP1 50%减半推保本 + TP2 25%兑现 + Runner 25%移动追踪)
    if use_tiered_tp:
        tp1_target = channel_tp if (use_channel_tp and channel_tp) else tp_price
        if side == 1:
            if tp2_price is not None:
                tp2_target = tp2_price
            elif impulse_leg and impulse_leg > 0:
                tp2_target = round(entry_price + 1.618 * impulse_leg, 2)
            else:
                tp2_target = round(entry_price + (min_rr + 1.5) * risk, 2)
            tp2_target = max(tp2_target, round(tp1_target + 0.5 * risk, 2))
        else:
            if tp2_price is not None:
                tp2_target = tp2_price
            elif impulse_leg and impulse_leg > 0:
                tp2_target = round(entry_price - 1.618 * impulse_leg, 2)
            else:
                tp2_target = round(entry_price - (min_rr + 1.5) * risk, 2)
            tp2_target = min(tp2_target, round(tp1_target - 0.5 * risk, 2))
            if tp2_target <= 0:
                tp2_target = round(max(0.01, tp1_target * 0.5), 2)

        stage = 0   # 0: 未触发 TP1; 1: 已达 TP1 (推保本); 2: 已达 TP2 (锁 TP1 利润，Runner 移动追踪)
        curr_stop = stop_price
        rem_pos = 1.0
        exit_records = []

        for bar in range(entry_t, end_t + 1):
            o, h, l, c = opens[bar], highs[bar], lows[bar], closes[bar]

            if side == 1:
                if stage == 0:
                    hit_stop = (l <= curr_stop)
                    hit_tp1 = (h >= tp1_target)

                    if hit_stop and hit_tp1:
                        fill_stop = min(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_stop, "weight": 1.0, "reason": "stop_loss_conservative"})
                        rem_pos = 0.0
                        break
                    elif hit_stop:
                        fill_stop = min(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_stop, "weight": 1.0, "reason": "stop_loss"})
                        rem_pos = 0.0
                        break
                    elif hit_tp1:
                        fill_tp1 = max(o, tp1_target)
                        exit_records.append({"bar": bar, "price": fill_tp1, "weight": 0.50, "reason": "tp1_half"})
                        rem_pos -= 0.50
                        stage = 1
                        curr_stop = entry_price  # 剩余推保本

                        hit_tp2 = (h >= tp2_target)
                        if hit_tp2:
                            fill_tp2 = max(o, tp2_target)
                            exit_records.append({"bar": bar, "price": fill_tp2, "weight": 0.25, "reason": "tp2_quarter"})
                            rem_pos -= 0.25
                            stage = 2
                            curr_stop = tp1_target
                elif stage == 1:
                    hit_be = (l <= curr_stop)
                    hit_tp2 = (h >= tp2_target)

                    if hit_be and hit_tp2:
                        fill_be = min(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_be, "weight": rem_pos, "reason": "break_even_conservative"})
                        rem_pos = 0.0
                        break
                    elif hit_be:
                        fill_be = min(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_be, "weight": rem_pos, "reason": "break_even_stop"})
                        rem_pos = 0.0
                        break
                    elif hit_tp2:
                        fill_tp2 = max(o, tp2_target)
                        exit_records.append({"bar": bar, "price": fill_tp2, "weight": 0.25, "reason": "tp2_quarter"})
                        rem_pos -= 0.25
                        stage = 2
                        curr_stop = tp1_target
                elif stage == 2:
                    trail_low = float(np.min(lows[max(entry_t, bar - 5):bar])) if bar > entry_t else tp1_target
                    curr_stop = max(curr_stop, trail_low)
                    hit_runner = (l <= curr_stop)
                    if hit_runner:
                        fill_r = min(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_r, "weight": rem_pos, "reason": "runner_stop"})
                        rem_pos = 0.0
                        break
            else:
                # 空头
                if stage == 0:
                    hit_stop = (h >= curr_stop)
                    hit_tp1 = (l <= tp1_target)

                    if hit_stop and hit_tp1:
                        fill_stop = max(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_stop, "weight": 1.0, "reason": "stop_loss_conservative"})
                        rem_pos = 0.0
                        break
                    elif hit_stop:
                        fill_stop = max(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_stop, "weight": 1.0, "reason": "stop_loss"})
                        rem_pos = 0.0
                        break
                    elif hit_tp1:
                        fill_tp1 = min(o, tp1_target)
                        exit_records.append({"bar": bar, "price": fill_tp1, "weight": 0.50, "reason": "tp1_half"})
                        rem_pos -= 0.50
                        stage = 1
                        curr_stop = entry_price

                        hit_tp2 = (l <= tp2_target)
                        if hit_tp2:
                            fill_tp2 = min(o, tp2_target)
                            exit_records.append({"bar": bar, "price": fill_tp2, "weight": 0.25, "reason": "tp2_quarter"})
                            rem_pos -= 0.25
                            stage = 2
                            curr_stop = tp1_target
                elif stage == 1:
                    hit_be = (h >= curr_stop)
                    hit_tp2 = (l <= tp2_target)

                    if hit_be and hit_tp2:
                        fill_be = max(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_be, "weight": rem_pos, "reason": "break_even_conservative"})
                        rem_pos = 0.0
                        break
                    elif hit_be:
                        fill_be = max(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_be, "weight": rem_pos, "reason": "break_even_stop"})
                        rem_pos = 0.0
                        break
                    elif hit_tp2:
                        fill_tp2 = min(o, tp2_target)
                        exit_records.append({"bar": bar, "price": fill_tp2, "weight": 0.25, "reason": "tp2_quarter"})
                        rem_pos -= 0.25
                        stage = 2
                        curr_stop = tp1_target
                elif stage == 2:
                    trail_high = float(np.max(highs[max(entry_t, bar - 5):bar])) if bar > entry_t else tp1_target
                    curr_stop = min(curr_stop, trail_high)
                    hit_runner = (h >= curr_stop)
                    if hit_runner:
                        fill_r = max(o, curr_stop)
                        exit_records.append({"bar": bar, "price": fill_r, "weight": rem_pos, "reason": "runner_stop"})
                        rem_pos = 0.0
                        break

        if rem_pos > 0:
            exit_records.append({"bar": end_t, "price": closes[end_t], "weight": rem_pos,
                                 "reason": "tp_partial_time_horizon" if stage > 0 else "time_horizon"})

        final_exit_bar = max(r["bar"] for r in exit_records)
        w_exit_price = float(sum(r["price"] * r["weight"] for r in exit_records))
        pnl_pct = float(sum(r["weight"] * (r["price"] / entry_price - 1.0) * side for r in exit_records))
        r_multiple = float(((w_exit_price - entry_price) * side) / risk)
        hold_bars = int(final_exit_bar - entry_t)

        reasons = [r["reason"] for r in exit_records]
        if any("runner_stop" in r for r in reasons):
            primary_reason = "tp_runner_captured"
        elif any("break_even" in r for r in reasons):
            primary_reason = "tp1_then_be_protected"
        elif any("tp_partial_time_horizon" in r for r in reasons):
            primary_reason = "tp_partial_time_horizon"
        elif any("stop_loss_conservative" in r for r in reasons):
            primary_reason = "stop_loss_conservative"
        elif any("stop_loss" in r for r in reasons):
            primary_reason = "stop_loss"
        elif any("time_horizon" in r for r in reasons):
            primary_reason = "time_horizon"
        else:
            primary_reason = "take_profit"

        if side == 1:
            sub_low = float(np.min(lows[entry_t:final_exit_bar + 1]))
            sub_high = float(np.max(highs[entry_t:final_exit_bar + 1]))
            mae = min(sub_low / entry_price - 1.0, 0.0)
            mfe = max(sub_high / entry_price - 1.0, 0.0)
        else:
            sub_low = float(np.min(lows[entry_t:final_exit_bar + 1]))
            sub_high = float(np.max(highs[entry_t:final_exit_bar + 1]))
            mae = min(-(sub_high / entry_price - 1.0), 0.0)
            mfe = max(-(sub_low / entry_price - 1.0), 0.0)

        return {
            "status": "completed",
            "entry_t": entry_t,
            "entry_price": round(entry_price, 2),
            "exit_t": final_exit_bar,
            "exit_price": round(w_exit_price, 2),
            "exit_reason": primary_reason,
            "pnl_pct": pnl_pct,
            "r_multiple": r_multiple,
            "hold_bars": hold_bars,
            "mae": float(mae),
            "mfe": float(mfe),
            "win": bool(pnl_pct > 0),
            "risk": float(risk),
            "reward": float(reward),
            "planned_rr": float(rr),
            "tp1_price": round(tp1_target, 2),
            "tp2_price": round(tp2_target, 2)
        }

    exit_t = None
    exit_price = None
    exit_reason = None

    # 从入场根 entry_t 开始推演（开盘入场后，当天盘中即可触及止损或止盈）
    for bar in range(entry_t, end_t + 1):
        o, h, l, c = opens[bar], highs[bar], lows[bar], closes[bar]

        if side == 1:
            hit_stop = (l <= stop_price)
            hit_tp = (h >= tp_price)
            hit_chan = (channel_tp is not None and h >= channel_tp)

            if hit_stop and (hit_tp or hit_chan):
                # 极端同根K线双触：按理论保守约束5，一律按止损出场
                exit_t = bar
                exit_price = min(o, stop_price)
                exit_reason = "stop_loss_conservative"
                break
            elif hit_stop:
                exit_t = bar
                exit_price = min(o, stop_price)
                exit_reason = "stop_loss"
                break
            elif hit_chan:
                exit_t = bar
                exit_price = max(o, channel_tp)
                exit_reason = "take_profit_channel"
                break
            elif hit_tp:
                exit_t = bar
                exit_price = max(o, tp_price)
                exit_reason = "take_profit"
                break
        else:
            hit_stop = (h >= stop_price)
            hit_tp = (l <= tp_price)
            hit_chan = (channel_tp is not None and l <= channel_tp)

            if hit_stop and (hit_tp or hit_chan):
                exit_t = bar
                exit_price = max(o, stop_price)
                exit_reason = "stop_loss_conservative"
                break
            elif hit_stop:
                exit_t = bar
                exit_price = max(o, stop_price)
                exit_reason = "stop_loss"
                break
            elif hit_chan:
                exit_t = bar
                exit_price = min(o, channel_tp)
                exit_reason = "take_profit_channel"
                break
            elif hit_tp:
                exit_t = bar
                exit_price = min(o, tp_price)
                exit_reason = "take_profit"
                break

    if exit_t is None:
        exit_t = end_t
        exit_price = closes[end_t]
        exit_reason = "time_horizon"

    pnl_pct = (exit_price / entry_price - 1.0) * side
    r_multiple = ((exit_price - entry_price) * side) / risk
    hold_bars = exit_t - entry_t

    # 持仓区间 MAE / MFE
    if side == 1:
        sub_low = float(np.min(lows[entry_t:exit_t + 1]))
        sub_high = float(np.max(highs[entry_t:exit_t + 1]))
        mae = min(sub_low / entry_price - 1.0, 0.0)
        mfe = max(sub_high / entry_price - 1.0, 0.0)
    else:
        sub_low = float(np.min(lows[entry_t:exit_t + 1]))
        sub_high = float(np.max(highs[entry_t:exit_t + 1]))
        mae = min(-(sub_high / entry_price - 1.0), 0.0)
        mfe = max(-(sub_low / entry_price - 1.0), 0.0)

    return {
        "status": "completed",
        "entry_t": entry_t,
        "entry_price": round(entry_price, 2),
        "exit_t": exit_t,
        "exit_price": round(exit_price, 2),
        "exit_reason": exit_reason,
        "pnl_pct": float(pnl_pct),
        "r_multiple": float(r_multiple),
        "hold_bars": int(hold_bars),
        "mae": float(mae),
        "mfe": float(mfe),
        "win": bool(pnl_pct > 0),
        "risk": float(risk),
        "reward": float(reward),
        "planned_rr": float(rr)
    }


# ==============================================================================
# 5. 任意入场点的前向多周期度量 (Fixed Horizons Evaluation)
# ==============================================================================

def calc_entry_horizon_stats(df: pd.DataFrame, entry_t: int, entry_price: float,
                             side: int, h: int) -> dict:
    """
    计算从 entry_t 根以 entry_price 入场后，持有 h 根的收益 / MAE / MFE。
    """
    n = len(df)
    if entry_t < 0 or entry_t + h >= n or entry_price <= 0:
        return None

    close_h = float(df["Close"].iloc[entry_t + h])
    sub_low = float(df["Low"].iloc[entry_t:entry_t + h + 1].min())
    sub_high = float(df["High"].iloc[entry_t:entry_t + h + 1].max())

    ret = (close_h / entry_price - 1.0) * side
    if side == 1:
        mae = min(sub_low / entry_price - 1.0, 0.0)
        mfe = max(sub_high / entry_price - 1.0, 0.0)
    else:
        mae = min(-(sub_high / entry_price - 1.0), 0.0)
        mfe = max(-(sub_low / entry_price - 1.0), 0.0)

    return {
        "ret": float(ret),
        "mae": float(mae),
        "mfe": float(mfe)
    }
