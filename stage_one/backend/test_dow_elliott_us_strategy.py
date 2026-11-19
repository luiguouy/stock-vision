# -*- coding: utf-8 -*-
"""
单元测试：道氏理论大盘宏观过滤器与美股艾略特高抛低吸策略引擎验证
测试范围：
1. 道氏大盘指数相互验证（SPY 与 QQQ 同步上升放行，指数背离或主趋势向下拦截做多）
2. 买点 1（第 2 浪回调）：缩量回踩 0.500/0.618，止损严格设在浪1起点下方（2浪不破1浪底），TP1 达到 1.618x 高抛减半推保本
3. 买点 2（第 4 浪浅调）：横盘洗盘 0.382/0.236，止损设在浪1顶下方（4浪不破1浪顶），TP1 达到 1.000x 浪1等长位高抛
4. 高抛低吸执行梯次（TP1 减半 / TP2 目标 / 2-4通道与前低破位终极逃顶清仓）
5. 美股多头倾向与空头防守机制
"""

import unittest
import numpy as np
import pandas as pd
from strategy_adapter import run_strategy_analysis


class TestDowElliottUSStrategy(unittest.TestCase):
    def setUp(self):
        # 基础测试日期序列
        self.dates = pd.date_range("2026-01-01", periods=60, freq="B")

        # 构造健康的 SPY & QQQ 牛市同步抬升走势
        spy_closes = np.linspace(500, 560, 60) + 3 * np.sin(np.linspace(0, 2 * np.pi, 60))
        self.spy_bull = pd.DataFrame({
            "Open": spy_closes - 0.5,
            "High": spy_closes + 1.5,
            "Low": spy_closes - 1.5,
            "Close": spy_closes,
            "Volume": [1000000] * 60,
        }, index=self.dates)

        qqq_closes = np.linspace(400, 460, 60) + 3 * np.sin(np.linspace(0, 2 * np.pi, 60))
        self.qqq_bull = pd.DataFrame({
            "Open": qqq_closes - 0.5,
            "High": qqq_closes + 1.5,
            "Low": qqq_closes - 1.5,
            "Close": qqq_closes,
            "Volume": [1500000] * 60,
        }, index=self.dates)

        # 构造走弱/熊市的 QQQ (用于测试背离和主趋势向下)
        qqq_bear_closes = np.linspace(460, 390, 60) - 3 * np.sin(np.linspace(0, 2 * np.pi, 60))
        self.qqq_bear = pd.DataFrame({
            "Open": qqq_bear_closes + 0.5,
            "High": qqq_bear_closes + 1.5,
            "Low": qqq_bear_closes - 1.5,
            "Close": qqq_bear_closes,
            "Volume": [1200000] * 60,
        }, index=self.dates)

        # 构造第 2 浪回调形态数据 (P0=100 -> P1=140 -> P2=118 踩在 0.55 回撤)
        # 70 根 K 线: 0-25 浪1上升 (100->140), 26-45 浪2回调 (140->118), 46-70 企稳反弹 (118.5->126)
        dates70 = pd.date_range("2026-01-01", periods=70, freq="B")
        w2_closes = np.zeros(70)
        w2_closes[:26] = np.linspace(100, 140, 26)
        w2_closes[26:46] = np.linspace(140, 118, 20)
        w2_closes[46:] = np.linspace(118.5, 126.0, 24)
        self.df_wave2 = pd.DataFrame({
            "Open": w2_closes - 0.5,
            "High": w2_closes + 1.2,
            "Low": w2_closes - 1.2,
            "Close": w2_closes,
            "Volume": [100000 + int(i * 1000) if i < 26 else max(30000, 80000 - int(i * 1000)) for i in range(70)],
        }, index=dates70)

        # 构造包含完整浪1-2-3-4且正在浪4浅调的数据 (80根):
        # P0=100, P1=120, P2=110, P3=150, P4=135 (浪4低点 135 远高于浪1顶 120，回撤 0.375)
        dates80 = pd.date_range("2026-01-01", periods=80, freq="B")
        w4_closes = np.zeros(80)
        w4_closes[:16] = np.linspace(100, 120, 16)   # 浪1
        w4_closes[16:26] = np.linspace(120, 110, 10) # 浪2
        w4_closes[26:51] = np.linspace(110, 150, 25) # 浪3 主升
        w4_closes[51:66] = np.linspace(150, 135, 15) # 浪4 浅调
        w4_closes[66:] = np.linspace(135.5, 142.0, 14) # 浪5 推进中
        self.df_wave4 = pd.DataFrame({
            "Open": w4_closes - 0.5,
            "High": w4_closes + 1.5,
            "Low": w4_closes - 1.5,
            "Close": w4_closes,
            "Volume": [80000] * 80,
        }, index=dates80)

    def test_dow_macro_filter_mutual_verification_pass(self):
        """测试 1a: 当 SPY 与 QQQ 同步处于上升趋势时，宏观过滤器验证通过 (PASS)"""
        res = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=self.df_wave2,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        summary = res["summary"]
        dow_ver = summary["dow_market_verification"]

        self.assertIsNotNone(dow_ver)
        self.assertTrue(dow_ver["verified"], "SPY 与 QQQ 同步上涨时宏观验证必须为 True")
        self.assertEqual(dow_ver["status"], "PASS")
        self.assertIn("相互验证通过", dow_ver["description"])

    def test_dow_macro_filter_divergence_blocks_long(self):
        """测试 1b: 当 SPY 上涨但 QQQ 走弱（指数背离）时，宏观过滤器拦截做多并触发警告"""
        res = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=self.df_wave2,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bear,
        )
        plan = res["summary"]["trade_plan"]
        dow_ver = res["summary"]["dow_market_verification"]

        self.assertFalse(dow_ver["verified"], "指数背离时宏观验证必须未通过")
        self.assertIn(dow_ver["status"], ("DIVERGENCE", "WARN"))
        self.assertIn("背离", dow_ver["description"])

        # 严格执行门禁：禁止在大盘背离时直接做多
        self.assertFalse(plan["passed_gates"])
        self.assertIn("观望", plan["direction"])
        reasons_str = " ".join(plan["reasons"])
        self.assertTrue("背离" in reasons_str or "拦截" in reasons_str)

    def test_wave2_buy_point_setup_and_iron_rule(self):
        """测试 2: 验证买点 1（第 2 浪回调）点位计算、2浪不破1浪底铁律止损及 1.618x 兑现减半"""
        res = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=self.df_wave2,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        plan = res["summary"]["trade_plan"]
        wave_setup = plan.get("wave_setup")

        self.assertIsNotNone(wave_setup, "交易计划中必须包含波浪依据 wave_setup")
        self.assertIn("买点1", wave_setup["buy_point_type"])
        self.assertIn("第2浪回调", wave_setup["buy_point_type"])

        # 绝对铁律验证：止损必须设在第 1 浪起点下方
        sl_reason = plan["stop_loss_reason"]
        self.assertTrue("2浪不破1浪底" in sl_reason or "浪1起点" in sl_reason or "波谷" in sl_reason)
        self.assertLess(plan["stop_loss"], 101.0, "浪2止损点必须在浪1底 (100) 附近或下方")

        # 卖点 1 验证：达到 1.618x 高抛减半 (50%)
        tp1_src = plan["tp1_source"]
        self.assertIn("高抛减半", tp1_src)
        self.assertIn("1.618", tp1_src)

        # 终极逃顶：跌穿浪1起点证伪清仓
        self.assertIsNotNone(plan["escape_level"])
        self.assertIn("清仓", plan["escape_reason"])

    def test_wave4_buy_point_setup_and_rule(self):
        """测试 3: 验证买点 2（第 4 浪浅调）点位计算、浪4不破浪1顶止损及浪5冲顶高抛"""
        res = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=self.df_wave4,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        plan = res["summary"]["trade_plan"]
        wave_setup = plan.get("wave_setup")

        self.assertIsNotNone(wave_setup)
        # 买点 2 识别
        self.assertTrue(
            "买点2" in wave_setup["buy_point_type"] or "第4浪" in wave_setup["buy_point_type"] or "顺势" in wave_setup["buy_point_type"]
        )

        # 止损保护：必须守在浪1顶下方或前低波谷
        self.assertIsNotNone(plan["stop_loss"])
        self.assertLess(plan["stop_loss"], plan["entry"])

        # 止盈依据中包含高抛目标
        self.assertTrue(len(plan["tp1_source"]) > 0)
        self.assertIn("卖点", plan["tp1_source"])

    def test_sell_stages_high_selling_ladder(self):
        """测试 4: 验证高抛低吸三梯次（TP1 减半 / TP2 目标 / 终极逃顶清仓）结构完整性"""
        res = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=self.df_wave2,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        plan = res["summary"]["trade_plan"]
        wave_setup = plan.get("wave_setup")
        stages = wave_setup.get("sell_stages", [])

        self.assertEqual(len(stages), 3, "高抛低吸梯次必须严格包含 TP1, TP2, EXIT 三个阶段")
        self.assertEqual(len(plan.get("sell_stages", [])), 3, "trade_plan 根层级必须暴露 sell_stages 供前端消费")
        self.assertEqual(len(res["summary"].get("sell_stages", [])), 3, "summary 根层级必须同步暴露 sell_stages")
        stage_names = [s["stage"] for s in stages]
        self.assertIn("TP1", stage_names)
        self.assertIn("TP2", stage_names)
        self.assertIn("EXIT", stage_names)

        # 检查每个阶段的动作定义
        tp1_stage = next(s for s in stages if s["stage"] == "TP1")
        self.assertIn("高抛减半", tp1_stage["action"])
        self.assertIn("保本", tp1_stage["action"])

        exit_stage = next(s for s in stages if s["stage"] == "EXIT")
        self.assertIn("清仓", exit_stage["action"])

    def test_condition_playbook_wave_setups(self):
        """测试 5: 条件挂单剧本针对浪2/浪4精准输出斐波那契回撤与高抛低吸执行要领"""
        # 现价拉高脱离理想买点以触发条件挂单剧本
        df_extended = self.df_wave2.copy()
        df_extended.iloc[-1, df_extended.columns.get_loc("Close")] = 142.0

        res = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=df_extended,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        plan = res["summary"]["trade_plan"]
        playbook = plan.get("condition_playbook")

        if playbook is not None:
            self.assertIn("斐波那契", playbook["notes"])
            self.assertIn("高抛减半", playbook["notes"])
            self.assertLess(playbook["ideal_entry"], 142.0)
            self.assertGreaterEqual(playbook["estimated_rr"], 2.5)

    def test_us_bear_market_defense(self):
        """测试 6: 美股策略在单边空头下跌行情中启动防御性观望，禁止逆势盲目抄底"""
        closes_bear = np.linspace(150, 90, 60)
        df_bear = pd.DataFrame({
            "Open": closes_bear + 0.5,
            "High": closes_bear + 1.0,
            "Low": closes_bear - 1.0,
            "Close": closes_bear,
            "Volume": [100000] * 60,
        }, index=self.dates)

        res = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=df_bear,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        plan = res["summary"]["trade_plan"]

        self.assertFalse(plan["passed_gates"])
        self.assertIn("观望", plan["direction"])
        self.assertIn("防守", plan["direction"])

    def test_cn_stock_skips_us_dow_macro_filter(self):
        """测试 7: A股等非美股标的不会被错误应用 SPY/QQQ 宏观道氏过滤器"""
        res = run_strategy_analysis(
            "600519",
            period="1d",
            mode="swing",
            market="cn",
            df=self.df_wave2,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bear,
        )
        dow_ver = res["summary"]["dow_market_verification"]
        self.assertIn("非美股标的", dow_ver["description"])
        self.assertTrue(dow_ver["verified"])

    def test_channel_2_4_breakdown_triggers_escape_and_blocks_long(self):
        """测试 8: 2-4 通道基线破位时一票否决做多信号，强制触发逃顶清仓观望"""
        dates80 = pd.date_range("2026-01-01", periods=80, freq="B")
        w4_closes = np.zeros(80)
        w4_closes[:16] = np.linspace(100, 120, 16)
        w4_closes[16:26] = np.linspace(120, 110, 10)
        w4_closes[26:51] = np.linspace(110, 150, 25)
        w4_closes[51:66] = np.linspace(150, 135, 15)
        # 随后破位暴跌至 120
        w4_closes[66:] = np.linspace(134, 120, 14)
        df_broken = pd.DataFrame({
            "Open": w4_closes - 0.5,
            "High": w4_closes + 1.0,
            "Low": w4_closes - 1.0,
            "Close": w4_closes,
            "Volume": [90000] * 80,
        }, index=dates80)

        res = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=df_broken,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        plan = res["summary"]["trade_plan"]
        self.assertFalse(plan["passed_gates"])
        self.assertIn("观望", plan["direction"])
        reasons_str = " ".join(plan["reasons"])
        self.assertTrue("逃顶" in reasons_str or "破位" in reasons_str or "通道" in reasons_str)

    def test_wave4_conditional_playbook_fib_levels(self):
        """测试 9: 验证买点 2（第 4 浪浅调）挂单剧本正确锁定 0.236 与 0.382 斐波浅调位"""
        # P0=100, P1=120, P2=110, P3=150 (L3=40). fib_236=140.56, fib_382=134.72, P1(SL)=120
        # 构造收盘价在 146 (高于 fib_236)，期望挂单锁定 fib_236 (140.56)
        df_w4_high = self.df_wave4.copy()
        df_w4_high.iloc[-1, df_w4_high.columns.get_loc("Close")] = 146.0

        res_high = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=df_w4_high,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        pb_high = res_high["summary"]["trade_plan"].get("condition_playbook")
        if pb_high is not None:
            self.assertIn("买点2", pb_high["scenario_name"])
            self.assertAlmostEqual(pb_high["ideal_entry"], 140.56, delta=2.0)
            self.assertLess(pb_high["stop_loss"], 120.0, "浪4止损必须设在浪1顶 (120) 下方")

        # 构造收盘价在 138 (低于 fib_236 但高于 fib_382)，期望挂单锁定 fib_382 (134.72)
        df_w4_mid = self.df_wave4.copy()
        df_w4_mid.iloc[-1, df_w4_mid.columns.get_loc("Close")] = 138.0

        res_mid = run_strategy_analysis(
            "usAAPL",
            period="1d",
            mode="swing",
            df=df_w4_mid,
            spy_df=self.spy_bull,
            qqq_df=self.qqq_bull,
        )
        pb_mid = res_mid["summary"]["trade_plan"].get("condition_playbook")
        if pb_mid is not None:
            self.assertIn("买点2", pb_mid["scenario_name"])
            self.assertAlmostEqual(pb_mid["ideal_entry"], 134.72, delta=2.0)
            self.assertLess(pb_mid["stop_loss"], 120.0, "浪4止损必须设在浪1顶 (120) 下方")


if __name__ == "__main__":
    unittest.main()
