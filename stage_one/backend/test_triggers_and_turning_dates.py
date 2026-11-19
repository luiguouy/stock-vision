# -*- coding: utf-8 -*-
"""
验证 buy_triggers、sell_triggers、turning_dates 与空头方向逻辑
路径: stage_one/backend/test_triggers_and_turning_dates.py
"""

import unittest
import pandas as pd
import numpy as np
from strategy_adapter import run_strategy_analysis


class TestTriggersAndTurningDates(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range("2026-01-01", periods=100, freq="B")
        # 构造明显的空头下行通道与跌破 200 EMA 数据
        # 从 380 跌至 320
        downtrend = np.linspace(380, 320, 100)
        # 加上小幅震荡形成波浪次级高低点
        downtrend += np.sin(np.linspace(0, 20, 100)) * 5.0
        self.df_bear = pd.DataFrame(
            {
                "Open": downtrend + 1.0,
                "High": downtrend + 3.0,
                "Low": downtrend - 3.0,
                "Close": downtrend,
                "Volume": [1500] * 100,
            },
            index=dates,
        )

        # 构造明显的多头上升通道数据
        uptrend = np.linspace(300, 380, 100) + np.sin(np.linspace(0, 20, 100)) * 5.0
        self.df_bull = pd.DataFrame(
            {
                "Open": uptrend - 1.0,
                "High": uptrend + 3.0,
                "Low": uptrend - 3.0,
                "Close": uptrend,
                "Volume": [2500] * 100,
            },
            index=dates,
        )

    def test_bear_market_triggers_and_direction(self):
        """测试空头市场下 buy_triggers 与 sell_triggers 完整存在且 direction_mode 为 SHORT"""
        res = run_strategy_analysis("usTSLA", period="1d", mode="swing", df=self.df_bear)
        summary = res["summary"]
        plan = summary["trade_plan"]

        # 1. 验证 direction_mode 严格映射
        self.assertEqual(plan.get("direction_mode"), "SHORT")

        # 2. 即使处于观望/0R门禁，也必须有 buy_triggers
        buy_trig = summary.get("buy_triggers")
        self.assertIsNotNone(buy_trig, "空头趋势下必须暴露 buy_triggers")
        self.assertIn("aggressive", buy_trig)
        self.assertIn("conservative", buy_trig)
        self.assertIn("price_range", buy_trig["aggressive"])
        self.assertIn("price_range", buy_trig["conservative"])
        self.assertIn("condition", buy_trig["aggressive"])
        self.assertIn("condition", buy_trig["conservative"])

        # 3. 顺势卖出点 sell_triggers 必须完整
        sell_trig = summary.get("sell_triggers")
        self.assertIsNotNone(sell_trig, "空头趋势下必须暴露 sell_triggers")
        self.assertIn("rebound_sell", sell_trig)
        self.assertIn("take_profit", sell_trig)
        self.assertIn("breakdown_stop", sell_trig)
        self.assertIn("resistance_zone_1", sell_trig["rebound_sell"])
        self.assertIn("resistance_zone_2", sell_trig["rebound_sell"])

        # 4. 验证变盘日期推演 turning_dates
        turning_dates = summary.get("turning_dates")
        self.assertIsNotNone(turning_dates)
        self.assertIsInstance(turning_dates, list)
        if len(turning_dates) > 0:
            td = turning_dates[0]
            self.assertIn("date", td)
            self.assertIn("day_offset_text", td)
            self.assertIn("basis", td)
            self.assertIn("focus", td)

        # 5. 图表 swing 标注严禁在空头波段标注 HL
        markers = res["annotations"].get("markers", [])
        for m in markers:
            if m.get("id", "").startswith("swing_"):
                self.assertNotEqual(m.get("text"), "HL", "空头波段中严禁错误标注多头符号 HL")

    def test_bull_market_triggers(self):
        """测试多头市场下 triggers 正常输出且 direction_mode 正确映射"""
        # 测试不受美股大盘过滤器影响的加密资产
        res_crypto = run_strategy_analysis("BTC-USD", period="1d", mode="swing", df=self.df_bull)
        plan_c = res_crypto["summary"]["trade_plan"]
        self.assertEqual(plan_c.get("direction_mode"), "LONG")
        self.assertIsNotNone(res_crypto["summary"].get("buy_triggers"))
        self.assertIsNotNone(res_crypto["summary"].get("sell_triggers"))

        # 测试美股资产（当大盘空头阻断时映射为 WAIT，大盘顺风时为 LONG）
        res_us = run_strategy_analysis("usAAPL", period="1d", mode="swing", df=self.df_bull)
        plan_us = res_us["summary"]["trade_plan"]
        self.assertIn(plan_us.get("direction_mode"), ("LONG", "WAIT"))
        self.assertIsNotNone(res_us["summary"].get("buy_triggers"))
        self.assertIsNotNone(res_us["summary"].get("sell_triggers"))


if __name__ == "__main__":
    unittest.main()
