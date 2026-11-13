# -*- coding: utf-8 -*-
"""
单元与端点测试: Investment_Assistant 价格行为策略矩阵中的波浪与通道标注与 HTML 导出
"""

import unittest
import pandas as pd
from fastapi.testclient import TestClient

from main import app
from strategy_adapter import run_strategy_analysis, generate_wave_chart_html


class TestWaveAndChannelAnnotations(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
        # 构造包含完整波段形态的 60 根测试 K 线
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        import numpy as np
        # 构造一个先升后调的周期波形
        trend = np.linspace(100, 160, 60)
        cycles = 15 * np.sin(np.linspace(0, 3 * np.pi, 60))
        closes = trend + cycles
        
        self.df = pd.DataFrame({
            "Open": closes - 1.0,
            "High": closes + 2.5,
            "Low": closes - 2.5,
            "Close": closes,
            "Volume": [10000] * 60,
        }, index=dates)

    def test_run_strategy_analysis_returns_wave_and_channel(self):
        res = run_strategy_analysis("usAAPL", period="1d", mode="swing", df=self.df)
        self.assertEqual(res["symbol"], "usAAPL")
        self.assertIn("summary", res)
        self.assertIn("annotations", res)

        summary = res["summary"]
        self.assertIn("channel", summary)
        self.assertIn("wave", summary)
        self.assertIn("html_url", summary)
        self.assertTrue(summary["html_url"].startswith("/api/strategy/html?symbol=usAAPL"))

        # 检查 channel 摘要字段
        chan = summary["channel"]
        self.assertIn("channel_type", chan)
        self.assertIn("slope", chan)
        self.assertIn("upper_rail", chan)
        self.assertIn("mid_rail", chan)
        self.assertIn("lower_rail", chan)

        # 检查 annotations 包含波浪和通道
        annos = res["annotations"]
        self.assertIn("markers", annos)
        self.assertIn("lines", annos)
        self.assertIn("channel_lines", annos)
        self.assertIn("wave_lines", annos)

        # 检查通道线结构
        channel_lines = annos["channel_lines"]
        self.assertTrue(len(channel_lines) >= 3, "应至少包含通道上轨、中轴、下轨 3 条线")
        for cl in channel_lines:
            self.assertIn("id", cl)
            self.assertIn("time1", cl)
            self.assertIn("price1", cl)
            self.assertIn("time2", cl)
            self.assertIn("price2", cl)
            self.assertIn("title", cl)

        # 检查波浪折线结构
        wave_lines = annos["wave_lines"]
        self.assertIsNotNone(wave_lines)
        self.assertIn("points", wave_lines)
        self.assertTrue(len(wave_lines["points"]) >= 3, "波浪结构应至少提取出 3 个关键拐点")
        for pt in wave_lines["points"]:
            self.assertIn("time", pt)
            self.assertIn("price", pt)
            self.assertIn("label", pt)
        self.assertIn("extension", wave_lines)
        self.assertIn("price", wave_lines["extension"])

    def test_api_control_strategy_endpoint(self):
        """测试 POST /api/control/strategy 返回通道与波浪标注"""
        response = self.client.post("/api/control/strategy", json={
            "symbol": "usAAPL",
            "period": "1d",
            "mode": "swing",
            "draw_on_chart": False,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("annotations", data)
        annos = data["annotations"]
        self.assertIn("channel_lines", annos)
        self.assertIn("wave_lines", annos)
        self.assertIn("channel", data["summary"])

    def test_api_strategy_html_endpoint(self):
        """测试 GET /api/strategy/html 导出 Plotly 单文件 HTML 报告"""
        response = self.client.get("/api/strategy/html?symbol=usAAPL&period=1d")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertTrue(len(response.text) > 500)
        self.assertIn("AAPL", response.text)

    def test_edge_cases_empty_or_small_df(self):
        """测试极端短数据下的稳健降级"""
        small_df = self.df.head(5)
        res = run_strategy_analysis("TEST_UNKNOWN_NONEXISTENT", period="1d", mode="swing", df=small_df)
        self.assertIn("error", res)
        self.assertEqual(res["annotations"]["markers"], [])

    def test_control_strategy_with_frontend_klines(self):
        """测试前端直接传入 klines 时一键策略分析成功"""
        records = [
            {"time": d.strftime("%Y-%m-%d"), "open": row["Open"], "high": row["High"], "low": row["Low"], "close": row["Close"], "volume": row["Volume"]}
            for d, row in self.df.iterrows()
        ]
        response = self.client.post("/api/control/strategy", json={
            "symbol": "CUSTOM_SYM",
            "period": "1d",
            "mode": "swing",
            "draw_on_chart": False,
            "klines": records,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("annotations", data)
        self.assertIn("channel_lines", data["annotations"])
        self.assertIn("wave_lines", data["annotations"])
        self.assertTrue(len(data["annotations"]["channel_lines"]) >= 3)

    def test_normalize_df_with_records_list(self):
        """测试 run_strategy_analysis 直接接收 list 结构字典数组"""
        records = [
            {"time": d.strftime("%Y-%m-%d"), "open": row["Open"], "high": row["High"], "low": row["Low"], "close": row["Close"], "volume": row["Volume"]}
            for d, row in self.df.iterrows()
        ]
        res = run_strategy_analysis("TEST_LIST", period="1d", mode="swing", df=records)
        self.assertIn("annotations", res)
        self.assertIn("wave_lines", res["annotations"])
        self.assertIn("channel_lines", res["annotations"])


if __name__ == "__main__":
    unittest.main()
