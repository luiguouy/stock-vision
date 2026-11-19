#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strategy_crypto.py: 比特币与加密资产专用交易策略引擎 (Crypto Native Strategy Engine)

理论依据与设计原则：
  1. 资产解耦与原生牛熊架构 (Asset Decoupling):
     彻底解除美股大盘指数（SPY / QQQ）硬闸门对加密货币的拦截。
     BTC/ETH 遵循独立的加密多周期原生牛熊结构（日线 MTF + 周线 HTF）。
  2. 波动率脱敏与宽幅防插针止损 (Anti-wick Stop Loss):
     针对比特币回踩 MAE 中位数达 -7%~-8% 的高波动插针特性，将止损缓冲自适应扩大至
     1.3 ~ 1.5x ATR (或 median_bar_range)；
     对于 2B 假跌破扫损形态，止损锚定在扫损极值针尖外 0.35x ATR，杜绝假摔被震出。
  3. 加密核心触发形态 (2B Liquidity Sweep):
     深度内化 2B 流动性猎杀作为最高置信度入场形态（跌破关键支撑引爆流动性踩踏后强力实体收回）。
  4. 非对称大赔率分级止盈 (Asymmetric Multi-tier Take Profit, RR >= 2.0):
     - 初始规划盈亏比 RR >= 2.0 硬闸门；
     - TP1 (50% 仓位): 结构前高或 >= 2.0R 处止盈减半，并立即将剩余仓位止损推至保本位 (Break-Even Stop)；
     - TP2 (25% 仓位): 顺势 1.618 斐波那契扩展位 (Fibonacci Extension) 止盈，剩余仓位锁定 TP1 防守；
     - Runner (25% 仓位): 移动追踪止损 (Trailing Stop)，捕捉长牛主升单边行情。
  5. 严格零未来函数与保守撮合：
     第 t 根决策，t+1 根开盘入场；同根 K 线若同时触及止损与目标，一律判定为止损优先出场。
"""

import os
import sys
import numpy as np
import pandas as pd
from . import pa_engine as pe

# 加密策略核心配置参数
CRYPTO_STOP_BUFFER_K = 1.4       # 常规结构止损缓冲 (1.3 ~ 1.5x ATR/bar_rng)
CRYPTO_2B_STOP_BUFFER_K = 0.35   # 2B 扫损极值针尖外缓冲 (0.3 ~ 0.5x ATR/bar_rng)
CRYPTO_MIN_RR = 2.0             # 最小风险报酬比硬闸门
CRYPTO_MAX_WAIT_BARS = 15       # 突破后最大等待回踩触发根数
CRYPTO_MAX_HOLD_BARS = 60       # 最大持仓跟踪周期 (加密顺势主升波段较长)

# 分级止盈比例配置
CRYPTO_TP1_RATIO = 0.50         # TP1 减半比例 (50%)
CRYPTO_TP2_RATIO = 0.25         # TP2 兑现比例 (25%)
CRYPTO_RUNNER_RATIO = 0.25      # Runner 趋势追踪仓位 (25%)

# 加密历史重大系统性黑天鹅事件窗口（全网穿仓踩踏、交易所挤兑、流动性枯竭）
CRYPTO_BLACK_SWANS = [
    {
        "name": "Covid 312流动性危机 (BitMEX全网多头踩踏清算)",
        "start": "2020-03-08",
        "end": "2020-03-22",
        "description": "全球流动性挤兑，日内断崖暴跌50%，衍生品清算穿仓"
    },
    {
        "name": "519 监管清退与全网大爆仓",
        "start": "2021-05-15",
        "end": "2021-05-25",
        "description": "政策清退引爆杠杆踩踏，单日爆仓逾百亿美元"
    },
    {
        "name": "Terra Luna/UST 算法稳定币死亡螺旋",
        "start": "2022-05-05",
        "end": "2022-05-18",
        "description": "百亿市值稳定币脱锚归零，机构连锁爆仓流动性危机"
    },
    {
        "name": "FTX 交易所暴雷破产与全网挤兑",
        "start": "2022-11-05",
        "end": "2022-11-18",
        "description": "第二大加密衍生品交易所挪用资金资不抵债，恐慌蔓延"
    }
]


def is_crypto_black_swan(date_val) -> bool:
    """
    检查指定日期是否落在加密货币重大系统性黑天鹅事件窗口内。
    """
    if date_val is None:
        return False
    try:
        d = pd.to_datetime(date_val).tz_localize(None) if hasattr(pd.to_datetime(date_val), 'tz_localize') else pd.to_datetime(date_val)
    except Exception:
        return False
    for bs in CRYPTO_BLACK_SWANS:
        s = pd.to_datetime(bs["start"])
        e = pd.to_datetime(bs["end"])
        if s <= d <= e:
            return True
    return False


def trade_overlaps_black_swan(entry_date, exit_date) -> bool:
    """
    检查交易生命周期 [entry_date, exit_date] 是否与系统性黑天鹅窗口发生重叠。
    """
    try:
        e_d = pd.to_datetime(entry_date).tz_localize(None) if hasattr(pd.to_datetime(entry_date), 'tz_localize') else pd.to_datetime(entry_date)
        x_d = pd.to_datetime(exit_date).tz_localize(None) if hasattr(pd.to_datetime(exit_date), 'tz_localize') else pd.to_datetime(exit_date)
    except Exception:
        return False
    for bs in CRYPTO_BLACK_SWANS:
        s = pd.to_datetime(bs["start"])
        e = pd.to_datetime(bs["end"])
        if not (x_d < s or e_d > e):
            return True
    return False


def is_crypto_asset(ticker: str) -> bool:
    """
    判断指定资产代码是否属于加密货币资产：
    支持 BTC, ETH, SOL, *-USD, *-USDT, *-USDC 等代码。
    严格排除美股与传统外汇法定货币对 (如 EUR-USD, GBP-USD 等)。
    """
    if not ticker:
        return False
    t = str(ticker).strip().upper()
    crypto_symbols = {
        "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "MATIC",
        "LINK", "NEAR", "UNI", "LTC", "BCH", "ATOM", "APT", "SUI", "OP", "ARB",
        "FIL", "ICP", "ETC", "XLM", "TRX", "TON", "SHIB", "PEPE", "WIF", "RENDER"
    }
    if t in crypto_symbols:
        return True
    if any(t.startswith(c + "-") or t.startswith(c + "/") for c in crypto_symbols):
        return True
    if t.endswith("-USDT") or t.endswith("-USDC") or t.endswith("/USDT") or t.endswith("/USDC"):
        return True
    if t.endswith("-USD") or t.endswith("/USD"):
        base = t.split("-")[0].split("/")[0]
        if base in crypto_symbols or "BTC" in t or "ETH" in t:
            return True
        # 排除传统外汇法定货币与美股指数及常见股票
        fiat_and_stocks = {
            "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNH", "NZD", "DXY",
            "SPY", "QQQ", "DIA", "IWM", "AAPL", "MSFT", "GOOGL", "GOOG", "NVDA", "AMD",
            "TSLA", "META", "AMZN", "NFLX", "INTC", "BABA", "COIN"
        }
        if base not in fiat_and_stocks:
            return True
    return False


# ==============================================================================
# 1. 加密结构位与斐波那契顺势扩展提取 (Location Layer)
# ==============================================================================

def extract_crypto_levels(df: pd.DataFrame, t: int, side: int, swings: list,
                          buffer_k: float = CRYPTO_STOP_BUFFER_K) -> dict:
    """
    在第 t 根决策K线上，提取加密资产被突破的结构位、冲量波段与顺势斐波那契扩展位。
    严格只使用 <= t 的数据（零未来函数）。
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
    if bar_rng <= 0:
        bar_rng = float(df["Close"].iloc[t]) * 0.02  # 兜底 2%

    c_curr_high = float(df["High"].iloc[t])
    c_curr_low = float(df["Low"].iloc[t])
    c_close = float(df["Close"].iloc[t])

    if side == 1:
        # 多头突破：被突破的高点阻力转支撑 (Swing Retest)
        h_break = float(highs[-1]["price"])
        l_anchor = float(lows[-1]["price"])
        l_anchor_idx = int(lows[-1].get("index", 0))

        # 提取自锚点低点以来整个冲量波段的真实最高点（严格 <= t，无未来函数）
        leg_high = float(df["High"].iloc[l_anchor_idx:t + 1].max()) if l_anchor_idx <= t else c_curr_high
        peak = max(c_curr_high, c_close, h_break, leg_high)
        impulse_leg = max(peak - l_anchor, bar_rng)

        fib50 = peak - 0.50 * impulse_leg
        fib618 = peak - 0.618 * impulse_leg

        # 宽幅防插针结构止损 (1.3 ~ 1.5x ATR 缓冲)
        structural_stop = round(l_anchor - buffer_k * bar_rng, 2)

        # 顺势目标设计：
        # TP1: 冲量波段前高 (Peak)
        tp1 = round(peak, 2)
        # TP2: 1.618 斐波那契顺势扩展位 (Fibonacci Extension 1.618)
        tp2 = round(l_anchor + 1.618 * impulse_leg, 2)
        if tp2 <= tp1:
            tp2 = round(peak + 0.618 * impulse_leg, 2)

        return {
            "side": 1,
            "h_break": round(h_break, 2),
            "l_anchor": round(l_anchor, 2),
            "peak": round(peak, 2),
            "fib50": round(fib50, 2),
            "fib618": round(fib618, 2),
            "structural_stop": structural_stop,
            "bar_rng": round(bar_rng, 2),
            "swing_retest": round(h_break, 2),
            "impulse_leg": round(impulse_leg, 2),
            "tp1_target": tp1,
            "tp2_target": tp2,
        }
    elif side == -1:
        # 空头跌破：被跌破的低点支撑转阻力 (Swing Retest)
        l_break = float(lows[-1]["price"])
        h_anchor = float(highs[-1]["price"])
        h_anchor_idx = int(highs[-1].get("index", 0))

        leg_low = float(df["Low"].iloc[h_anchor_idx:t + 1].min()) if h_anchor_idx <= t else c_curr_low
        trough = min(c_curr_low, c_close, l_break, leg_low)
        impulse_leg = max(h_anchor - trough, bar_rng)

        fib50 = trough + 0.50 * impulse_leg
        fib618 = trough + 0.618 * impulse_leg

        structural_stop = round(h_anchor + buffer_k * bar_rng, 2)
        tp1 = round(trough, 2)
        tp2 = round(h_anchor - 1.618 * impulse_leg, 2)
        if tp2 >= tp1:
            tp2 = round(trough - 0.618 * impulse_leg, 2)
        if tp1 <= 0:
            tp1 = round(max(0.01, trough * 0.5), 2)
        if tp2 <= 0:
            tp2 = round(max(0.01, tp1 * 0.5), 2)

        return {
            "side": -1,
            "l_break": round(l_break, 2),
            "h_anchor": round(h_anchor, 2),
            "trough": round(trough, 2),
            "fib50": round(fib50, 2),
            "fib618": round(fib618, 2),
            "structural_stop": structural_stop,
            "bar_rng": round(bar_rng, 2),
            "swing_retest": round(l_break, 2),
            "impulse_leg": round(impulse_leg, 2),
            "tp1_target": tp1,
            "tp2_target": tp2,
        }

    return {}


# ==============================================================================
# 2. 加密核心触发形态 (Trigger Layer: 2B Liquidity Sweep & Rejection Pin)
# ==============================================================================

def detect_crypto_trigger_on_bar(df: pd.DataFrame, k: int, side: int,
                                 key_level: float, bar_rng: float,
                                 tol_k: float = 0.6) -> dict:
    """
    检测单根K线在关键位 key_level 处是否出现加密高置信度反转确认形态：
      1. 2B 流动性猎杀 (2B Liquidity Sweep - 最高置信度)
         向下跌破支撑触发止损踩踏后，收盘强力收回关键位上方，止损锚定于针尖外 0.35x ATR；
      2. 加密拒绝 Pin Bar (锤子线 / 流星线)
         长影线拒绝关键位，止损带 1.4x ATR 呼吸空间；
      3. 加密看涨 / 看跌吞没 (Engulfing)。
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
        # 多头形态要求
        lower_shadow = min(c_o, c_c) - c_l

        # 1. 2B 流动性猎杀扫损 (2B Bullish Liquidity Sweep Low)
        # 条件：盘中下破关键位引爆止损，收盘稳稳站回关键位之上，且阳线或收盘位于上半区
        is_sweep_depth_ok = (key_level - c_l) <= 3.5 * bar_rng
        is_2b = (c_l < key_level and c_c > key_level and
                 (c_c > c_o or ((c_c - c_l) / rng >= 0.50)) and is_sweep_depth_ok)

        # 2. 看涨 Pin Bar：长下影拒绝，且覆盖关键位容忍区
        is_pinbar = (lower_shadow >= 1.8 * body and (lower_shadow / rng) >= 0.50
                     and c_l <= key_level + tol and c_h >= key_level - tol)

        # 3. 看涨吞没 (Bullish Engulfing)
        is_engulfing = (p_c < p_o and c_c > c_o and c_c >= p_o and c_o <= p_c
                        and c_l <= key_level + tol and c_h >= key_level - tol)

        if is_2b or is_pinbar or is_engulfing:
            pattern = "2B_sweep" if is_2b else ("pin_bar" if is_pinbar else "engulfing")
            # 止损缓冲差异化标定：
            # 若为 2B 扫损，极值点 c_l 已经将流动性扫空，止损紧贴针尖外 0.35x ATR
            # 若为普通 PinBar/吞没，给予 1.4x ATR 充足宽幅防插针空间
            buf_k = CRYPTO_2B_STOP_BUFFER_K if is_2b else CRYPTO_STOP_BUFFER_K
            tight_stop = round(c_l - buf_k * bar_rng, 2)

            return {
                "triggered": True,
                "pattern": pattern,
                "trigger_t": k,
                "trigger_bar_low": round(c_l, 2),
                "trigger_bar_high": round(c_h, 2),
                "tight_stop": tight_stop,
                "key_level": round(key_level, 2),
                "is_2b": bool(is_2b)
            }
    else:
        # 空头形态要求
        upper_shadow = c_h - max(c_o, c_c)

        # 1. 2B 空头流动性猎杀 (2B Bearish Liquidity Sweep High)
        is_sweep_depth_ok = (c_h - key_level) <= 3.5 * bar_rng
        is_2b = (c_h > key_level and c_c < key_level and
                 (c_c < c_o or ((c_h - c_c) / rng >= 0.50)) and is_sweep_depth_ok)

        # 2. 看跌 Pin Bar
        is_pinbar = (upper_shadow >= 1.8 * body and (upper_shadow / rng) >= 0.50
                     and c_h >= key_level - tol and c_l <= key_level + tol)

        # 3. 看跌吞没
        is_engulfing = (p_c > p_o and c_c < c_o and c_c <= p_o and c_o >= p_c
                        and c_h >= key_level - tol and c_l <= key_level + tol)

        if is_2b or is_pinbar or is_engulfing:
            pattern = "2B_sweep" if is_2b else ("pin_bar" if is_pinbar else "engulfing")
            buf_k = CRYPTO_2B_STOP_BUFFER_K if is_2b else CRYPTO_STOP_BUFFER_K
            tight_stop = round(c_h + buf_k * bar_rng, 2)

            return {
                "triggered": True,
                "pattern": pattern,
                "trigger_t": k,
                "trigger_bar_low": round(c_l, 2),
                "trigger_bar_high": round(c_h, 2),
                "tight_stop": tight_stop,
                "key_level": round(key_level, 2),
                "is_2b": bool(is_2b)
            }

    return {"triggered": False}


def check_recent_crypto_2b_sweep(df: pd.DataFrame, side: int, swings: list,
                                 bar_rng: float = None, lookback: int = 5) -> dict:
    """
    针对加密资产最近几根 K 线扫描 2B 流动性猎杀 (2B Liquidity Sweep) 形态：
      多头：跌破关键前低引爆多头止损盘后迅速收回，止损锚定于刺透针尖外 0.35x ATR；
      空头：突破关键前高引爆空头止损盘后迅速收回，止损锚定于刺透针尖外 0.35x ATR。
    """
    if df is None or len(df) < 3 or not swings:
        return {"detected": False}

    if bar_rng is None or bar_rng <= 0:
        bar_rng = pe.median_bar_range(df, n=14)
    if bar_rng <= 0:
        bar_rng = float(df["Close"].iloc[-1]) * 0.02

    n = len(df)
    conf = [s for s in swings if s.get("confirmed", True)] or swings
    if side == 1:
        lows = [s for s in conf if s.get("type") == "Low"]
        if not lows:
            return {"detected": False}
        key_low = float(lows[-1]["price"])
        low_idx = int(lows[-1].get("index", 0))

        start_k = max(low_idx + 1, n - lookback)
        for k in range(start_k, n):
            trig = detect_crypto_trigger_on_bar(df, k, side=1, key_level=key_low, bar_rng=bar_rng)
            if trig.get("triggered") and trig.get("is_2b"):
                return {
                    "detected": True,
                    "pattern": "2B_bull_sweep",
                    "bar_index": k,
                    "sweep_price": trig["trigger_bar_low"],
                    "key_level": key_low,
                    "stop_loss": trig["tight_stop"],
                    "buffer_used": round(CRYPTO_2B_STOP_BUFFER_K * bar_rng, 2),
                    "desc": f"2B多头扫损猎杀: 针尖 ${trig['trigger_bar_low']:.2f} 刺破前低 ${key_low:.2f} 后强力收回，防守止损锚定针尖外 0.35x ATR (${trig['tight_stop']:.2f})"
                }
    else:
        highs = [s for s in conf if s.get("type") == "High"]
        if not highs:
            return {"detected": False}
        key_high = float(highs[-1]["price"])
        high_idx = int(highs[-1].get("index", 0))

        start_k = max(high_idx + 1, n - lookback)
        for k in range(start_k, n):
            trig = detect_crypto_trigger_on_bar(df, k, side=-1, key_level=key_high, bar_rng=bar_rng)
            if trig.get("triggered") and trig.get("is_2b"):
                return {
                    "detected": True,
                    "pattern": "2B_bear_sweep",
                    "bar_index": k,
                    "sweep_price": trig["trigger_bar_high"],
                    "key_level": key_high,
                    "stop_loss": trig["tight_stop"],
                    "buffer_used": round(CRYPTO_2B_STOP_BUFFER_K * bar_rng, 2),
                    "desc": f"2B空头扫损猎杀: 针尖 ${trig['trigger_bar_high']:.2f} 刺破前高 ${key_high:.2f} 后强力收回，防守止损锚定针尖外 0.35x ATR (${trig['tight_stop']:.2f})"
                }

    return {"detected": False}


# ==============================================================================
# 2.5 周线结构顺势门禁 (HTF Structure Trend Gate — 纯价格结构, 零滞后指标)
# ==============================================================================

def _weekly_prefix(df: pd.DataFrame, t: int) -> pd.DataFrame:
    """将 <= t 的日线切片聚合为周线 (W-FRI, 与 backtest.weekly_from_daily 同口径)。"""
    sub = df.iloc[:t + 1]
    agg_map = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in sub.columns:
        agg_map["Volume"] = "sum"
    w = sub.resample("W-FRI").agg(agg_map)
    return w.dropna(subset=["Open", "High", "Low", "Close"])


def check_crypto_primary_trend(df: pd.DataFrame, t: int, side: int) -> dict:
    """
    周线结构顺势门禁 (Higher-Timeframe Structure Trend Gate):
      - 裸K流派边界: 趋势由结构定义 (HH/HL vs LH/LL), 禁用 MA/EMA 等滞后方向指标
        (docs/pa_engine_audit_2026-10-22.md 方向性指标禁令; 替换消融证据见
        docs/index_stat_validation.md 附录);
      - 由 <= t 的日线切片聚合周线, 提取周线摆动结构 (order=3), 以道氏 MSS 偏向
        (pe.dow_bias) 判定高周期结构方向, 严格零未来函数;
      - 多头 (side == 1): 周线结构偏向须为 +1 (高周期上升结构);
      - 空头 (side == -1): 周线结构偏向须为 -1 (高周期下降结构);
      - 历史不足 50 根日线 (单元测试小样本) 自动放行。
      2026-10-24 消融 (SPY/QQQ, 剔除黑天鹅): 与原 200 EMA 门禁过滤效果几乎等价
      (16 vs 17 笔, PF 1.41 vs 1.50, 期望 +1.12% vs +1.36%), 且多头交易集在
      无门禁/EMA门禁/结构门禁下逐笔相同——EMA 对多头从不拦截, 其职能可被
      周线结构完全接管, 无需保留任何滞后指标。
    """
    if df is None or len(df) < 50 or t < 0 or t >= len(df):
        return {"aligned": True, "structure_bias": None, "reason": "insufficient_history_neutral"}

    weekly = _weekly_prefix(df, t)
    if weekly.empty:
        return {"aligned": True, "structure_bias": None, "reason": "insufficient_history_neutral"}

    w_swings = pe.extract_swings(weekly, order=3)
    bias = pe.dow_bias(w_swings, df=weekly, buffer_k=0.0)

    if side == 1:
        aligned = bool(bias == 1)
        reason = "bull_structure_long_ok" if aligned else "counter_structure_long_blocked"
    else:
        aligned = bool(bias == -1)
        reason = "bear_structure_short_ok" if aligned else "counter_structure_short_blocked"

    return {"aligned": aligned, "structure_bias": int(bias), "reason": reason}


def simulate_crypto_trigger_entry(df: pd.DataFrame, t: int, side: int,
                                  key_level: float, bar_rng: float,
                                  structural_stop: float,
                                  max_wait_bars: int = CRYPTO_MAX_WAIT_BARS,
                                  use_trend_gate: bool = True,
                                  disallow_short_engulfing: bool = True) -> dict:
    """
    突破确认后（t 根），在关键位附近监控加密裸K确认形态：
      - 从 t+1 开始扫描至 t+max_wait_bars 根；
      - 若 k 根收盘确认形态，k+1 根开盘执行入场（严格零未来函数）；
      - 若价格击穿大结构止损 structural_stop，提前终止失效；
      - 内置周线结构顺势门禁与空头非对称过滤（剔除空头吞没滞后追跌陷阱）。
    """
    n = len(df)
    if t >= n - 2 or key_level <= 0 or bar_rng <= 0:
        return {"status": "invalid_input", "triggered": False}

    end_k = min(t + max_wait_bars, n - 2)

    for k in range(t + 1, end_k + 1):
        l_k, h_k = float(df["Low"].iloc[k]), float(df["High"].iloc[k])
        if side == 1 and l_k <= structural_stop:
            return {"status": "invalidated_before_trigger", "triggered": False, "t_stop": k}
        if side == -1 and h_k >= structural_stop:
            return {"status": "invalidated_before_trigger", "triggered": False, "t_stop": k}

        trig = detect_crypto_trigger_on_bar(df, k, side, key_level, bar_rng)
        if trig.get("triggered"):
            # 1. 做空形态非对称严苛化：排除做空吞没形态（实测为空头滞后追跌陷阱）
            if side == -1 and disallow_short_engulfing and trig.get("pattern") == "engulfing":
                continue

            # 2. 周线结构顺势门禁 (HTF Structure Gate, 纯价格结构零滞后指标)
            if use_trend_gate:
                trend_chk = check_crypto_primary_trend(df, k, side)
                if not trend_chk.get("aligned", True):
                    continue

            entry_t = k + 1
            entry_price = float(df["Open"].iloc[entry_t])
            tight_stop = float(trig["tight_stop"])

            # 宽幅防插针止损：
            # 若形态处于结构内部，止损锚定大结构失效点 structural_stop (提供 1.4x ATR 呼吸空间)；
            # 若 2B 扫损极值针尖击穿了原结构位，止损顺延至扫损针尖外 0.35x ATR 极值防守
            if side == 1:
                final_stop = min(structural_stop, tight_stop)
                if entry_price <= final_stop:
                    continue
            else:
                final_stop = max(structural_stop, tight_stop)
                if entry_price >= final_stop:
                    continue

            return {
                "status": "triggered",
                "triggered": True,
                "entry_t": entry_t,
                "entry_price": round(entry_price, 2),
                "stop_price": round(final_stop, 2),
                "pattern": trig["pattern"],
                "trigger_bar_t": k,
                "wait_bars": k - t,
                "is_2b": trig.get("is_2b", False)
            }

    return {"status": "no_trigger_expired", "triggered": False, "wait_bars": end_k - t}


# ==============================================================================
# 3. 非对称大赔率分级止盈执行生命周期 (Multi-tier Take Profit Execution)
# ==============================================================================

def simulate_crypto_trade(df: pd.DataFrame, entry_t: int, entry_price: float,
                         side: int, stop_price: float,
                         tp1_price: float = None,
                         tp2_price: float = None,
                         impulse_leg: float = None,
                         max_hold_bars: int = CRYPTO_MAX_HOLD_BARS,
                         min_rr: float = CRYPTO_MIN_RR) -> dict:
    """
    加密专用非对称分级止盈生命周期模拟：
      - 资产解耦：不拦截 SPY/QQQ 大盘；
      - 盈亏比硬闸门：初始规划 TP1 盈亏比必须 >= min_rr (默认 2.0)；
      - 分级止盈阶梯：
        * TP1 (50% 仓位): 达到时兑现 50%，并将剩余仓位止损推至保本价 (Break-Even Stop: entry_price)；
        * TP2 (25% 仓位): 达到 1.618 扩展位时兑现 25%，剩余 25% Runner 止损提至 TP1 锁定利润；
        * Runner (25% 仓位): 近 10 根最低价/最高价追踪止损（纯价格极值，非均线）或满期平仓，捕捉大牛市主升浪；
      - 保守撮合原则：
        同根 K 线内若同时触及当期止损与止盈，严格判定为止损优先出场。
    """
    n = len(df)
    if entry_t >= n or entry_price <= 0 or stop_price <= 0:
        return {"status": "invalid_trade"}

    risk = abs(entry_price - stop_price)
    if risk <= 0:
        return {"status": "zero_risk_invalid"}

    # 目标价位确定与非负保护
    if side == 1:
        if tp1_price is None or tp1_price <= entry_price:
            tp1_price = round(entry_price + min_rr * risk, 2)
    else:
        # 空头：若 2.0R 目标跌破或等于 0，物理上无法触及，硬闸门驳回
        if entry_price - min_rr * risk <= 0:
            return {
                "status": "rejected_by_min_rr",
                "reason": "short_target_non_positive",
                "entry_price": entry_price,
                "risk": risk,
                "min_rr": min_rr
            }
        if tp1_price is None or tp1_price >= entry_price or tp1_price <= 0:
            tp1_price = round(entry_price - min_rr * risk, 2)

    reward1 = abs(tp1_price - entry_price)
    planned_rr = reward1 / risk

    # 盈亏比硬闸门
    if planned_rr < min_rr - 1e-6:
        return {
            "status": "rejected_by_min_rr",
            "rr": round(planned_rr, 2),
            "min_rr": min_rr,
            "risk": round(risk, 2),
            "reward": round(reward1, 2)
        }

    # TP2 目标位（顺势 1.618 斐波那契扩展，必须严格顺势超出 TP1）
    if side == 1:
        fib_ext = round(entry_price + 1.618 * impulse_leg, 2) if (impulse_leg and impulse_leg > 0) else 0.0
        min_tp2 = round(max(tp1_price + 0.5 * risk, entry_price + (min_rr + 1.5) * risk), 2)
        if tp2_price is None or tp2_price <= tp1_price:
            tp2_price = max(fib_ext, min_tp2)
        else:
            tp2_price = max(tp2_price, min_tp2)
    else:
        fib_ext = round(entry_price - 1.618 * impulse_leg, 2) if (impulse_leg and impulse_leg > 0) else 0.0
        min_tp2 = round(min(tp1_price - 0.5 * risk, entry_price - (min_rr + 1.5) * risk), 2)
        if tp2_price is None or tp2_price >= tp1_price:
            calc_tp2 = min(fib_ext, min_tp2) if fib_ext > 0 else min_tp2
            tp2_price = calc_tp2
        else:
            tp2_price = min(tp2_price, min_tp2)
        if tp2_price <= 0:
            tp2_price = round(max(0.01, tp1_price * 0.5), 2)

    opens = df["Open"].to_numpy(dtype=float)
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    closes = df["Close"].to_numpy(dtype=float)

    end_t = min(entry_t + max_hold_bars, n - 1)

    stage = 0                # 0: 未触发 TP1; 1: 已过 TP1 (推保本); 2: 已过 TP2 (锁 TP1)
    curr_stop = stop_price
    rem_pos = 1.0            # 剩余持仓比例
    exit_records = []        # 记录平仓明细: {"bar": int, "price": float, "weight": float, "reason": str}
    final_exit_bar = entry_t

    for bar in range(entry_t, end_t + 1):
        o, h, l, c = opens[bar], highs[bar], lows[bar], closes[bar]

        if side == 1:
            # 多头持仓推演
            if stage == 0:
                # 阶段 0：完整持仓，止损在 stop_price
                hit_stop = (l <= curr_stop)
                hit_tp1 = (h >= tp1_price)

                if hit_stop and hit_tp1:
                    # 同根K线双触：保守判定为止损优先出场
                    fill_stop = min(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_stop, "weight": 1.0, "reason": "stop_loss_conservative"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break
                elif hit_stop:
                    fill_stop = min(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_stop, "weight": 1.0, "reason": "stop_loss"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break
                elif hit_tp1:
                    # 触发 TP1 减半 (50%)
                    fill_tp1 = max(o, tp1_price)
                    exit_records.append({"bar": bar, "price": fill_tp1, "weight": CRYPTO_TP1_RATIO, "reason": "tp1_half"})
                    rem_pos -= CRYPTO_TP1_RATIO
                    stage = 1
                    # 剩余仓位止损推至保本位 (Break-Even Stop: entry_price)
                    curr_stop = entry_price

                    # 检查同根大阳线是否直接贯通 TP2
                    hit_tp2 = (h >= tp2_price)
                    if hit_tp2:
                        fill_tp2 = max(o, tp2_price)
                        exit_records.append({"bar": bar, "price": fill_tp2, "weight": CRYPTO_TP2_RATIO, "reason": "tp2_quarter"})
                        rem_pos -= CRYPTO_TP2_RATIO
                        stage = 2
                        # Runner 止损锁定在 TP1
                        curr_stop = tp1_price

            elif stage == 1:
                # 阶段 1：已减半，剩余 50% 仓位推保本防守
                hit_be = (l <= curr_stop)
                hit_tp2 = (h >= tp2_price)

                if hit_be and hit_tp2:
                    # 同根双触保本损与 TP2：保守判定为保本离场
                    fill_be = min(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_be, "weight": rem_pos, "reason": "break_even_conservative"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break
                elif hit_be:
                    fill_be = min(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_be, "weight": rem_pos, "reason": "break_even_stop"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break
                elif hit_tp2:
                    fill_tp2 = max(o, tp2_price)
                    exit_records.append({"bar": bar, "price": fill_tp2, "weight": CRYPTO_TP2_RATIO, "reason": "tp2_quarter"})
                    rem_pos -= CRYPTO_TP2_RATIO
                    stage = 2
                    curr_stop = tp1_price  # 锁定利润

            elif stage == 2:
                # 阶段 2：已兑现 75%，剩余 25% Runner 追踪长牛
                # 追踪移动止损：不低于 tp1_price，且跟踪过去 10 日最低点（严格限制在入场之后，杜绝入场前数据污染）
                trail_low = float(np.min(lows[max(entry_t, bar - 10):bar])) if bar > entry_t else tp1_price
                curr_stop = max(curr_stop, trail_low)

                hit_runner_stop = (l <= curr_stop)
                if hit_runner_stop:
                    fill_r_stop = min(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_r_stop, "weight": rem_pos, "reason": "runner_stop"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break

        else:
            # 空头持仓推演
            if stage == 0:
                hit_stop = (h >= curr_stop)
                hit_tp1 = (l <= tp1_price)

                if hit_stop and hit_tp1:
                    fill_stop = max(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_stop, "weight": 1.0, "reason": "stop_loss_conservative"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break
                elif hit_stop:
                    fill_stop = max(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_stop, "weight": 1.0, "reason": "stop_loss"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break
                elif hit_tp1:
                    fill_tp1 = min(o, tp1_price)
                    exit_records.append({"bar": bar, "price": fill_tp1, "weight": CRYPTO_TP1_RATIO, "reason": "tp1_half"})
                    rem_pos -= CRYPTO_TP1_RATIO
                    stage = 1
                    curr_stop = entry_price

                    hit_tp2 = (l <= tp2_price)
                    if hit_tp2:
                        fill_tp2 = min(o, tp2_price)
                        exit_records.append({"bar": bar, "price": fill_tp2, "weight": CRYPTO_TP2_RATIO, "reason": "tp2_quarter"})
                        rem_pos -= CRYPTO_TP2_RATIO
                        stage = 2
                        curr_stop = tp1_price

            elif stage == 1:
                hit_be = (h >= curr_stop)
                hit_tp2 = (l <= tp2_price)

                if hit_be and hit_tp2:
                    fill_be = max(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_be, "weight": rem_pos, "reason": "break_even_conservative"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break
                elif hit_be:
                    fill_be = max(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_be, "weight": rem_pos, "reason": "break_even_stop"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break
                elif hit_tp2:
                    fill_tp2 = min(o, tp2_price)
                    exit_records.append({"bar": bar, "price": fill_tp2, "weight": CRYPTO_TP2_RATIO, "reason": "tp2_quarter"})
                    rem_pos -= CRYPTO_TP2_RATIO
                    stage = 2
                    curr_stop = tp1_price

            elif stage == 2:
                trail_high = float(np.max(highs[max(entry_t, bar - 10):bar])) if bar > entry_t else tp1_price
                curr_stop = min(curr_stop, trail_high)

                hit_runner_stop = (h >= curr_stop)
                if hit_runner_stop:
                    fill_r_stop = max(o, curr_stop)
                    exit_records.append({"bar": bar, "price": fill_r_stop, "weight": rem_pos, "reason": "runner_stop"})
                    rem_pos = 0.0
                    final_exit_bar = bar
                    break

    # 若到达最大持仓周期仍有剩余仓位，市价到期平仓
    if rem_pos > 1e-5:
        final_exit_bar = end_t
        exit_records.append({"bar": end_t, "price": closes[end_t], "weight": rem_pos, "reason": "time_horizon"})

    # 计算加权平均出场价格、实现收益率与实现 R 倍数
    tot_weight = sum(r["weight"] for r in exit_records)
    if tot_weight <= 0:
        tot_weight = 1.0

    avg_exit_price = sum(r["price"] * r["weight"] for r in exit_records) / tot_weight
    weighted_pnl = sum(((r["price"] / entry_price - 1.0) * side) * r["weight"] for r in exit_records) / tot_weight
    weighted_r = sum((((r["price"] - entry_price) * side) / risk) * r["weight"] for r in exit_records) / tot_weight

    hold_bars = final_exit_bar - entry_t

    # 持仓全周期 MAE / MFE
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

    # 主出场原因判定
    main_reason = exit_records[-1]["reason"] if exit_records else "unknown"
    if any(r["reason"] in ("tp1_half", "tp2_quarter") for r in exit_records):
        if any(r["reason"] == "runner_stop" for r in exit_records):
            main_reason = "tp_runner_captured"
        elif any(r["reason"] == "break_even_stop" for r in exit_records):
            main_reason = "tp1_then_be_protected"
        elif any(r["reason"] == "time_horizon" for r in exit_records):
            main_reason = "tp_partial_time_horizon"
        else:
            main_reason = "take_profit_multi_tier"

    return {
        "status": "completed",
        "entry_t": entry_t,
        "entry_price": round(entry_price, 2),
        "exit_t": final_exit_bar,
        "exit_price": round(avg_exit_price, 2),
        "exit_reason": main_reason,
        "pnl_pct": float(weighted_pnl),
        "r_multiple": float(weighted_r),
        "hold_bars": int(hold_bars),
        "mae": float(mae),
        "mfe": float(mfe),
        "win": bool(weighted_pnl > 0),
        "side": side,
        "risk": float(risk),
        "reward": float(reward1),
        "planned_rr": float(planned_rr),
        "tp1_price": round(tp1_price, 2),
        "tp2_price": round(tp2_price, 2),
        "exit_records": exit_records,
    }
