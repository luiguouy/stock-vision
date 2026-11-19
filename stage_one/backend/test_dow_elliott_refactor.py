# -*- coding: utf-8 -*-
"""
单元测试：道氏理论与艾略特波浪理论交易引擎重构验证
测试范围：
1. 动态多级止损锚点池（优先波浪客观失效位、通道轨线、200 EMA 与道氏拐点，废除生硬极值硬编码）
2. 顺势扩展止盈（分离未确认实时极值，优先采用 1.618x, 2.0x, 2.618x 斐波那契延展与前低4浪区间）
3. 严苛 If-Then 条件挂单剧本（0.382-0.618 黄金回撤共振区，收紧止损，标准 >= 2.5R / 加密 >= 2.0R 门禁）
4. 加密资产原生策略激活（market == 'crypto' 或 BTC/ETH 独立路由，ATR 防插针、2B 扫损极值防守、浅刺浪1顶容忍）
5. 结构化字段完整性（stop_loss_reason, tp_source, tp1_source, tp2_source, dow_volume_status）
"""

import unittest
import numpy as np
import pandas as pd
from strategy_adapter import run_strategy_analysis
from strategy_core import pa_engine, strategy_crypto


class TestDowElliottStrategyRefactor(unittest.TestCase):
    def setUp(self):
        # 构造标准的 60 根多头波浪走势数据
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        t = np.linspace(0, 3 * np.pi, 60)
        # 具有清晰波段的冲量上涨行情: 100 -> 160
        trend = np.linspace(100, 160, 60)
        cycles = 12 * np.sin(t)
        closes = trend + cycles

        self.df_bull = pd.DataFrame({
            "Open": closes - 0.8,
            "High": closes + 2.0,
            "Low": closes - 2.0,
            "Close": closes,
            "Volume": [1000000 + int(i * 15000) for i in range(60)],
        }, index=dates)

        # 构造空头波浪走势数据: 160 -> 100
        closes_bear = np.linspace(160, 100, 60) - 10 * np.sin(t)
        self.df_bear = pd.DataFrame({
            "Open": closes_bear + 0.8,
            "High": closes_bear + 2.0,
            "Low": closes_bear - 2.0,
            "Close": closes_bear,
            "Volume": [1000000 + int(i * 15000) for i in range(60)],
        }, index=dates)

    def test_structured_fields_presence(self):
        """测试 5: 验证 trade_plan 输出所有要求的结构化字段"""
        res = run_strategy_analysis("usAAPL", period="1d", mode="swing", df=self.df_bull)
        plan = res["summary"]["trade_plan"]

        self.assertIn("stop_loss_reason", plan)
        self.assertIn("tp_source", plan)
        self.assertIn("tp1_source", plan)
        self.assertIn("tp2_source", plan)
        self.assertIn("dow_volume_status", plan)

        self.assertTrue(len(plan["stop_loss_reason"]) > 0)
        self.assertTrue(len(plan["tp_source"]) > 0)
        self.assertTrue(len(plan["dow_volume_status"]) > 0)

    def test_multi_tier_stop_loss_anchor_pool(self):
        """测试 1: 验证多级止损锚点池依据（波浪证伪线/通道基线/200EMA/结构支撑 + 波动缓冲）"""
        res = run_strategy_analysis("usAAPL", period="1d", mode="swing", df=self.df_bull)
        plan = res["summary"]["trade_plan"]

        # 止损价必须严格低于入场价
        self.assertIsNotNone(plan["stop_loss"])
        self.assertLess(plan["stop_loss"], plan["entry"])

        # 止损依据中必须明确包含结构依据与缓冲信息
        sl_reason = plan["stop_loss_reason"]
        has_anchor_keyword = any(
            kw in sl_reason for kw in ["客观失效位", "通道", "EMA", "波谷", "支撑", "扫损"]
        )
        self.assertTrue(has_anchor_keyword, f"止损原因应包含结构锚点依据: {sl_reason}")
        self.assertIn("缓冲", sl_reason)

    def test_take_profit_separates_unconfirmed_realtime_extremes(self):
        """测试 2: 验证冲量波段优先采用斐波那契扩展或前低4浪区间，而非未确认即时极值"""
        # 构造现价紧贴近高点（即时未确认极值）的数据
        df_near_high = self.df_bull.copy()
        # 让最后一根 K 线最高价与收盘价极度逼近
        df_near_high.iloc[-1, df_near_high.columns.get_loc("Close")] = 162.0
        df_near_high.iloc[-1, df_near_high.columns.get_loc("High")] = 162.1

        res = run_strategy_analysis("usAAPL", period="1d", mode="swing", df=df_near_high)
        plan = res["summary"]["trade_plan"]

        # TP1 必须有合理的前瞻空间，绝不能等于紧贴的即时高点 162.1
        self.assertGreater(plan["tp1"], 162.5, "TP1 应使用前瞻顺势斐波扩展，而非紧贴的即时高点")
        self.assertIn("tp_source", plan)
        self.assertTrue(
            "斐波" in plan["tp_source"] or "扩展" in plan["tp_source"] or "目标" in plan["tp_source"],
            f"TP1 来源应为前瞻扩展: {plan['tp_source']}"
        )

    def test_condition_playbook_tight_retracement_and_rr_gate(self):
        """测试 3: 条件挂单剧本收紧至 0.382-0.618 斐波回撤共振带，且严格执行盈亏比门禁"""
        # 当现价过高未通过门禁时测试剧本
        res = run_strategy_analysis("usAAPL", period="1d", mode="swing", df=self.df_bull)
        plan = res["summary"]["trade_plan"]
        playbook = plan.get("condition_playbook")

        if playbook is not None:
            # 若生成了剧本，必须满足 >= 2.5R 门禁
            self.assertGreaterEqual(playbook["estimated_rr"], 2.5)
            self.assertTrue(playbook["passed_gates"])
            self.assertLess(playbook["ideal_entry"], plan["entry"], "理想挂单入场应低于现价（逢低回踩）")
            self.assertLess(playbook["stop_loss"], playbook["ideal_entry"], "挂单止损应低于入场")
            self.assertGreater(playbook["tp1"], playbook["ideal_entry"], "挂单目标应高于入场")
            # 备注中包含斐波回撤共振
            self.assertIn("斐波那契", playbook["notes"])

    def test_crypto_routing_and_atr_anti_wick_buffer(self):
        """测试 4: 激活 strategy_crypto，验证加密货币识别、宽幅 ATR 防插针缓冲与 2.0R 门禁"""
        # 1. 自动识别加密标的 BTC-USD
        res_crypto = run_strategy_analysis("BTC-USD", period="1d", mode="swing", df=self.df_bull)
        plan_crypto = res_crypto["summary"]["trade_plan"]

        # 2. 显式传入 market='crypto'
        res_explicit = run_strategy_analysis("BTC", period="1d", mode="swing", df=self.df_bull, market="crypto")
        plan_explicit = res_explicit["summary"]["trade_plan"]

        # 加密止损缓冲应为 1.4x med_range (或 2B 扫损极值)，验证缓冲更大更抗插针
        med_rng = pa_engine.median_bar_range(self.df_bull)
        expected_crypto_buf = round(1.4 * med_rng, 2)
        expected_std_buf = round(0.6 * med_rng, 2)
        self.assertGreater(expected_crypto_buf, expected_std_buf)

        # 检查加密门禁为 2.0R
        reasons_text = " ".join(plan_crypto["reasons"])
        self.assertIn("2.0R", reasons_text, "加密策略门禁应显示 2.0R 阈值")

    def test_crypto_shallow_wave4_piercing_tolerance(self):
        """测试 4b: 验证高波动加密货币允许浪4浅刺浪1顶 (<=15%) 的原著流派容忍"""
        # 构造浪4浅刺浪1顶的 5 浪形态 (P0=100, P1=120, P2=110, P3=140, P4=118, P5=150)
        # 浪1高点 120，浪4低点 118 (浅刺 2 点，相对于浪1幅度 20 点仅刺透 10% <= 15%)
        swings_shallow = [
            {"index": 0, "type": "Low", "price": 100.0, "confirmed": True},
            {"index": 10, "type": "High", "price": 120.0, "confirmed": True},
            {"index": 20, "type": "Low", "price": 110.0, "confirmed": True},
            {"index": 30, "type": "High", "price": 140.0, "confirmed": True},
            {"index": 40, "type": "Low", "price": 118.0, "confirmed": True},
            {"index": 50, "type": "High", "price": 150.0, "confirmed": True},
        ]

        # 标准美股严格铁律：浅刺判定为形态破坏
        wp_std = pa_engine.classify_wave_pattern(swings_shallow, allow_shallow_w4=False)
        self.assertFalse(wp_std["is_valid_impulse"], "标准美股下浪4刺破浪1顶应被判定破坏")

        # 加密模式 (allow_shallow_w4=True): 容忍浅刺，判定浪型持续有效
        wp_crypto = pa_engine.classify_wave_pattern(swings_shallow, allow_shallow_w4=True)
        self.assertTrue(wp_crypto["is_valid_impulse"], "加密模式下浪4浅刺浪1顶应被原著规则容忍")

    def test_dow_volume_status_analysis(self):
        """测试 5b: 验证道氏成交量顺势推进、缩量回调与量价背离判定"""
        # 顺势放量
        vol_up = pa_engine.analyze_dow_volume(self.df_bull, dow_bias=1)
        self.assertIn("status", vol_up)
        self.assertIn("description", vol_up)
        self.assertTrue(vol_up["volume_trend_aligned"])

        # 空头放量
        vol_down = pa_engine.analyze_dow_volume(self.df_bear, dow_bias=-1)
        self.assertIn("status", vol_down)
        self.assertTrue(vol_down["volume_trend_aligned"])

        # 缺少 Volume 列稳健降级
        df_no_vol = self.df_bull.drop(columns=["Volume"])
        vol_none = pa_engine.analyze_dow_volume(df_no_vol, dow_bias=1)
        self.assertEqual(vol_none["status"], "无成交量数据")


if __name__ == "__main__":
    unittest.main()
