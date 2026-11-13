# -*- coding: utf-8 -*-
"""
StockVision 桌面化、策略融合与控制面端到端自动化测试
"""

import sys
import os
import unittest
import pandas as pd
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from main import app, SUPPORTED_PERIODS
from strategy_adapter import run_strategy_analysis
import mcp_server


class TestStockVisionTransformation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_supported_periods_expansion(self):
        """测试周期扩充: 5m, 15m, 1h, 4h 均已纳入支持列表"""
        required = ['5m', '15m', '1h', '4h', '1d', '1w', '1M']
        for p in required:
            self.assertIn(p, SUPPORTED_PERIODS, f"周期 {p} 应被支持")

    def test_fuzzy_search_matching_and_no_phantom_tickers(self):
        """测试高精模糊检索、错别字容错与杜绝假代码生成"""
        # 1. 错别字容错测试: gogle -> GOOGL
        resp = self.client.get("/api/search?keyword=gogle")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        symbols = [item["symbol"].upper() for item in data]
        self.assertIn("USGOOGL", symbols, "搜索 gogle 必须精准纠错推荐 USGOOGL")
        self.assertNotIn("USGOGLE", symbols, "搜索 gogle 严禁盲目生成虚假代码 USGOGLE")

        # 2. 拼音首字母测试: gg -> GOOGL/GOOG
        resp_gg = self.client.get("/api/search?keyword=gg")
        self.assertEqual(resp_gg.status_code, 200)
        symbols_gg = [item["symbol"].upper() for item in resp_gg.json()]
        self.assertIn("USGOOGL", symbols_gg)

        # 3. 错别字容错测试: telsa -> TSLA
        resp_ts = self.client.get("/api/search?keyword=telsa")
        self.assertEqual(resp_ts.status_code, 200)
        symbols_ts = [item["symbol"].upper() for item in resp_ts.json()]
        self.assertIn("USTSLA", symbols_ts)

        # 4. 彻底杜绝虚假代码: 不存在的长代码必须返回空结果而不是生成假股票
        resp_fake = self.client.get("/api/search?keyword=nonexistentxyz123")
        self.assertEqual(resp_fake.status_code, 200)
        self.assertEqual(len(resp_fake.json()), 0, "不存在的代码严禁生成伪股票")

    def test_strategy_adapter_pa_matrix(self):
        """测试 strategy_adapter: 200EMA、道氏结构、波浪证伪、箱体、2.5R硬门禁"""
        # 构造模拟单调上升后假突破形态的 DataFrame
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        closes = [100.0 + i * 1.5 for i in range(50)] + [175.0, 178.0, 180.0, 176.0, 174.0, 172.0, 170.0, 171.0, 173.0, 175.0]
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        opens = [c - 0.2 for c in closes]
        vols = [1000000.0] * 60

        df = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": vols,
        })

        res = run_strategy_analysis("TEST", period="1d", mode="swing", df=df)
        self.assertEqual(res["symbol"], "TEST")
        self.assertIn("summary", res)
        summary = res["summary"]

        # 验证道氏与 200 EMA
        self.assertIn("dow_phase", summary)
        self.assertIn("ema_200_gate", summary)
        self.assertEqual(summary["ema_200_gate"]["status"], "PASS")

        # 验证波浪与交易计划
        self.assertIn("wave", summary)
        self.assertIn("trade_plan", summary)
        plan = summary["trade_plan"]
        self.assertIn(plan["direction"], ["做多 (Long)", "做空 (Short 防御性)", "观望"])

        # 验证 Lightweight Charts 标注协议输出
        annos = res.get("annotations", {})
        self.assertIn("markers", annos)
        self.assertIn("lines", annos)
        self.assertIn("boxes", annos)
        self.assertTrue(len(annos["markers"]) > 0, "应提取出道氏结构拐点标注")

        # 深入验证：构造清晰的箱体与波浪结构测试用例
        dates_box = pd.date_range("2024-01-01", periods=60, freq="D")
        closes_box = [100.0, 105.0, 95.0, 104.0, 96.0, 103.0, 97.0, 102.0, 98.0, 104.0] * 6
        df_box = pd.DataFrame({
            "date": [d.strftime("%Y-%m-%d") for d in dates_box],
            "open": closes_box,
            "high": [c + 2.0 for c in closes_box],
            "low": [c - 2.0 for c in closes_box],
            "close": closes_box,
            "volume": [500000.0] * 60,
        })
        res_box = run_strategy_analysis("TEST_BOX", period="1d", mode="swing", df=df_box)
        summary_box = res_box.get("summary", {})
        
        # 验证箱体状态机与矩形标注
        self.assertTrue(summary_box.get("box", {}).get("is_in_box"), "应正确识别箱体震荡状态")
        self.assertIn(summary_box.get("box", {}).get("state"), ["IN_BOX", "SWEEP_HIGH", "SWEEP_LOW", "BREAKOUT_UP", "BREAKOUT_DOWN"])
        self.assertTrue(len(res_box["annotations"]["boxes"]) > 0, "箱体状态下应生成矩形 BoxPrimitive 标注")

        # 验证波浪证伪价与证伪水平线
        self.assertIsNotNone(summary_box.get("wave", {}).get("invalidation_price"), "应提取出波浪理论客观证伪价位")
        line_ids = [l["id"] for l in res_box["annotations"]["lines"]]
        self.assertIn("line_wave_inv", line_ids, "应包含波浪客观证伪水平线")

    def test_control_endpoints_crud(self):
        """测试 Antigravity 控制面 REST 接口"""
        # 1. 切换标的
        open_resp = self.client.post("/api/control/open", json={"symbol": "usMSFT", "period": "15m"})
        self.assertEqual(open_resp.status_code, 200)
        self.assertEqual(open_resp.json()["state"]["symbol"], "USMSFT")
        self.assertEqual(open_resp.json()["state"]["period"], "15m")

        # 2. 读取状态
        st_resp = self.client.get("/api/control/state")
        self.assertEqual(st_resp.status_code, 200)
        self.assertEqual(st_resp.json()["state"]["symbol"], "USMSFT")

        # 3. 添加 Marker
        mark_resp = self.client.post("/api/control/markers", json={
            "symbol": "usMSFT",
            "markers": [
                {"time": "2024-05-01", "position": "aboveBar", "color": "#10b981", "shape": "arrowDown", "text": "Sell 2B"}
            ]
        })
        self.assertEqual(mark_resp.status_code, 200)
        self.assertEqual(mark_resp.json()["count"], 1)

        # 4. 绘制水平线
        line_resp = self.client.post("/api/control/lines", json={
            "symbol": "usMSFT",
            "lines": [
                {"price": 420.5, "color": "#ef4444", "lineWidth": 2, "lineStyle": 2, "title": "浪4证伪线"}
            ]
        })
        self.assertEqual(line_resp.status_code, 200)
        self.assertEqual(line_resp.json()["count"], 1)

        # 5. 绘制箱体
        box_resp = self.client.post("/api/control/boxes", json={
            "symbol": "usMSFT",
            "boxes": [
                {"price1": 430.0, "price2": 415.0, "time1": "2024-04-01", "time2": "2024-05-01", "label": "箱体震荡区"}
            ]
        })
        self.assertEqual(box_resp.status_code, 200)
        self.assertEqual(box_resp.json()["count"], 1)

        # 6. 查询标注
        anno_resp = self.client.get("/api/control/annotations?symbol=usMSFT")
        self.assertEqual(anno_resp.status_code, 200)
        self.assertTrue(len(anno_resp.json()["annotations"]) >= 3)

        # 7. 清理标注
        clr_resp = self.client.post("/api/control/clear", json={"symbol": "usMSFT"})
        self.assertEqual(clr_resp.status_code, 200)
        self.assertTrue(clr_resp.json()["deleted"] >= 3)

    def test_mcp_server_tools_registered(self):
        """测试 MCP Server 导出的全部工具均已正确注册"""
        tools = [t.name for t in mcp_server.server._tool_manager.list_tools()]
        expected_tools = [
            "stock_get_state",
            "stock_open_chart",
            "stock_add_markers",
            "stock_draw_price_lines",
            "stock_draw_boxes",
            "stock_run_pa_strategy",
            "stock_capture_chart",
            "stock_clear_annotations",
        ]
        for et in expected_tools:
            self.assertIn(et, tools, f"MCP 工具 {et} 应被注册")


if __name__ == "__main__":
    unittest.main()
