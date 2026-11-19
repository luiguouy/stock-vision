# -*- coding: utf-8 -*-
"""
加密货币专项单元测试
覆盖:
1. YahooProvider._to_yahoo_ticker 转换与清洗
2. DataProviderManager.fetch_klines 的加密货币独立路由与腾讯隔离
3. main.py 中 normalize_symbol、market_of、STOCKS_POOL 搜索别名
4. quote_config.py 与 quote_provider.py 中 YahooCryptoQuoteProvider 实时行情拉取与路由
"""

import unittest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
import pandas as pd
from fastapi.testclient import TestClient

from main import app, normalize_symbol as main_norm, market_of as main_market_of, MARKET_LABEL
from data_provider import YahooProvider, DataProviderManager
from quote_config import MARKET, market_of as config_market_of, get_market_cfg
from quote_provider import YahooCryptoQuoteProvider, TencentQuoteProvider


class TestCryptoFeatures(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    # -------------------------------------------------------------
    # 1. 测试 YahooProvider._to_yahoo_ticker
    # -------------------------------------------------------------
    def test_to_yahoo_ticker_crypto_variants(self):
        cases = {
            "BTC/USDT": "BTC-USD",
            "BTCUSDT": "BTC-USD",
            "btcusdt": "BTC-USD",
            "BTC/USD": "BTC-USD",
            "btcusd": "BTC-USD",
            "USBTC": "BTC-USD",
            "usbtc": "BTC-USD",
            "usBTCUSDT": "BTC-USD",
            "usBTC/USDT": "BTC-USD",
            "usBTC-USDT": "BTC-USD",
            "BTC-USD": "BTC-USD",
            "BTC-USDT": "BTC-USD",
            "BTC": "BTC-USD",
            "btc": "BTC-USD",
            "ETH/USDT": "ETH-USD",
            "ETHUSDT": "ETH-USD",
            "USETH": "ETH-USD",
            "SOL/USDT": "SOL-USD",
            "SOLUSDT": "SOL-USD",
            "USSOL": "SOL-USD",
            "DOGE/USDT": "DOGE-USD",
            "DOGEUSDT": "DOGE-USD",
            "USDOGE": "DOGE-USD",
            "DOGEUSD": "DOGE-USD",
            "XRP/USDT": "XRP-USD",
            "XRPUSDT": "XRP-USD",
            "USXRP": "XRP-USD",
            "BNB/USDT": "BNB-USD",
            "BNBUSDT": "BNB-USD",
            "USBNB": "BNB-USD",
        }
        for raw, expected in cases.items():
            result = YahooProvider._to_yahoo_ticker(raw)
            self.assertEqual(result, expected, f"Failed for raw={raw}: got {result}, expected {expected}")

    def test_to_yahoo_ticker_non_crypto(self):
        self.assertEqual(YahooProvider._to_yahoo_ticker("usAAPL"), "AAPL")
        self.assertEqual(YahooProvider._to_yahoo_ticker("AAPL"), "AAPL")
        self.assertEqual(YahooProvider._to_yahoo_ticker("NQmain"), "NQ=F")

    # -------------------------------------------------------------
    # 2. 测试 main.py 中 normalize_symbol 与 market_of
    # -------------------------------------------------------------
    def test_normalize_symbol_crypto(self):
        cases = {
            "BTC/USDT": "BTC-USD",
            "BTCUSDT": "BTC-USD",
            "btcusdt": "BTC-USD",
            "BTC-USDT": "BTC-USD",
            "BTC/USD": "BTC-USD",
            "btcusd": "BTC-USD",
            "BTC-USD": "BTC-USD",
            "USBTC": "BTC-USD",
            "usbtc": "BTC-USD",
            "usBTCUSDT": "BTC-USD",
            "usBTC/USDT": "BTC-USD",
            "usBTC-USDT": "BTC-USD",
            "BTC": "BTC-USD",
            "btc": "BTC-USD",
            "ETH/USDT": "ETH-USD",
            "ETHUSDT": "ETH-USD",
            "USETH": "ETH-USD",
            "ETH": "ETH-USD",
            "SOL/USDT": "SOL-USD",
            "SOLUSDT": "SOL-USD",
            "USSOL": "SOL-USD",
            "SOL": "SOL-USD",
            "DOGE/USDT": "DOGE-USD",
            "DOGEUSDT": "DOGE-USD",
            "USDOGE": "DOGE-USD",
            "DOGEUSD": "DOGE-USD",
            "XRP/USDT": "XRP-USD",
            "XRPUSDT": "XRP-USD",
            "USXRP": "XRP-USD",
            "BNB/USDT": "BNB-USD",
            "BNBUSDT": "BNB-USD",
            "USBNB": "BNB-USD",
        }
        for raw, expected in cases.items():
            result = main_norm(raw)
            self.assertEqual(result, expected, f"normalize_symbol failed for {raw}: got {result}, expected {expected}")

    def test_normalize_symbol_stocks_and_futures(self):
        self.assertEqual(main_norm("AAPL"), "USAAPL")
        self.assertEqual(main_norm("usAAPL"), "USAAPL")
        self.assertEqual(main_norm("NQmain"), "NQmain")

    def test_market_of_crypto(self):
        crypto_symbols = [
            "BTC-USD", "ETH-USD", "SOL-USD",
            "BTC/USDT", "BTCUSDT", "btcusdt", "BTC-USDT", "BTC/USD", "btcusd",
            "USBTC", "usbtc", "usBTCUSDT", "usBTC/USDT", "usBTC-USDT",
            "BTC", "btc", "ETH", "SOL",
            "ETHUSDT", "USETH", "SOLUSDT", "USSOL",
            "DOGE/USDT", "DOGEUSDT", "USDOGE", "DOGE-USD", "DOGE", "DOGEUSD",
            "XRP/USDT", "XRPUSDT", "USXRP", "XRP-USD", "XRP", "XRPUSD",
            "BNB/USDT", "BNBUSDT", "USBNB", "BNB-USD", "BNB", "BNBUSD",
        ]
        for sym in crypto_symbols:
            self.assertEqual(main_market_of(sym), "crypto", f"main.market_of failed for {sym}")
            self.assertEqual(config_market_of(sym), "crypto", f"quote_config.market_of failed for {sym}")

    def test_market_labels_and_config(self):
        self.assertIn("crypto", MARKET_LABEL)
        self.assertEqual(MARKET_LABEL["crypto"], "加密")

        self.assertIn("crypto", MARKET)
        cfg = get_market_cfg("crypto")
        self.assertEqual(cfg["name"], "加密")
        self.assertEqual(cfg["delay_label"], "实时行情 (24/7)")

    # -------------------------------------------------------------
    # 3. 测试搜索接口命中加密货币别名
    # -------------------------------------------------------------
    def test_search_crypto_aliases(self):
        search_terms = ["BTC/USDT", "BTCUSDT", "BTC-USDT", "BTC", "BITCOIN", "BTCUSD"]
        for kw in search_terms:
            resp = self.client.get(f"/api/search?keyword={kw}")
            self.assertEqual(resp.status_code, 200)
            items = resp.json()
            self.assertTrue(len(items) > 0, f"No results for {kw}")
            self.assertEqual(items[0]["symbol"], "BTC-USD", f"First result for {kw} is not BTC-USD: {items[0]}")

        # ETH & SOL
        resp_eth = self.client.get("/api/search?keyword=ETH/USDT")
        self.assertEqual(resp_eth.status_code, 200)
        self.assertEqual(resp_eth.json()[0]["symbol"], "ETH-USD")

        resp_sol = self.client.get("/api/search?keyword=SOL/USDT")
        self.assertEqual(resp_sol.status_code, 200)
        self.assertEqual(resp_sol.json()[0]["symbol"], "SOL-USD")

        resp_doge = self.client.get("/api/search?keyword=DOGE/USDT")
        self.assertEqual(resp_doge.status_code, 200)
        self.assertEqual(resp_doge.json()[0]["symbol"], "DOGE-USD")

        resp_xrp = self.client.get("/api/search?keyword=XRP/USDT")
        self.assertEqual(resp_xrp.status_code, 200)
        self.assertEqual(resp_xrp.json()[0]["symbol"], "XRP-USD")

        resp_bnb = self.client.get("/api/search?keyword=BNB/USDT")
        self.assertEqual(resp_bnb.status_code, 200)
        self.assertEqual(resp_bnb.json()[0]["symbol"], "BNB-USD")

    def test_us_stock_prefix_not_colliding_with_crypto(self):
        """防止以 SOL/ETH/BTC 开头的非加密美股代码 (如 SOLV) 被误判为加密货币。"""
        self.assertEqual(main_market_of("usSOLV"), "us")
        self.assertEqual(config_market_of("usSOLV"), "us")
        self.assertEqual(main_norm("usSOLV"), "USSOLV")
        self.assertEqual(YahooProvider._to_yahoo_ticker("usSOLV"), "SOLV")

    # -------------------------------------------------------------
    # 4. 测试 DataProviderManager.fetch_klines 加密货币隔离腾讯源
    # -------------------------------------------------------------
    def test_data_provider_manager_crypto_routes_only_yahoo(self):
        manager = DataProviderManager()
        fake_df = pd.DataFrame({
            "date": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
            "open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "high": [105.0, 106.0, 107.0, 108.0, 109.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "close": [104.0, 105.0, 106.0, 107.0, 108.0],
            "volume": [1000.0, 1100.0, 1200.0, 1300.0, 1400.0],
        })

        test_variants = [
            "BTC-USD", "BTC/USDT", "BTCUSDT", "btcusdt",
            "USBTC", "usbtc", "usBTCUSDT", "usBTC/USDT", "usBTC-USDT",
            "ETHUSDT", "USETH", "SOLUSDT", "USSOL", "DOGEUSDT",
        ]

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            for sym in test_variants:
                manager.yahoo.fetch_klines = AsyncMock(return_value=fake_df)
                manager.tencent.fetch_klines = AsyncMock(return_value=pd.DataFrame())
                res = loop.run_until_complete(manager.fetch_klines(sym, period="1d", bypass_cache=True))
                self.assertFalse(res.empty, f"Failed for {sym}")
                self.assertEqual(manager.last_source, "yahoo", f"Wrong source for {sym}")
                manager.yahoo.fetch_klines.assert_called_once()
                manager.tencent.fetch_klines.assert_not_called()
        finally:
            loop.close()

    # -------------------------------------------------------------
    # 5. 测试 YahooCryptoQuoteProvider 实时行情拉取与错误兜底
    # -------------------------------------------------------------
    def test_yahoo_crypto_quote_provider_parsing(self):
        provider = YahooCryptoQuoteProvider()

        fake_resp_data = {
            "chart": {
                "result": [{
                    "meta": {
                        "regularMarketPrice": 92500.5,
                        "chartPreviousClose": 91000.0,
                        "regularMarketOpen": 91200.0,
                        "regularMarketDayHigh": 93000.0,
                        "regularMarketDayLow": 90800.0,
                    }
                }]
            }
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = fake_resp_data

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_resp
                quotes = loop.run_until_complete(provider.get_quotes(["BTC-USD"]))
                self.assertEqual(len(quotes), 1)
                q = quotes[0]
                self.assertEqual(q["symbol"], "BTC-USD")
                self.assertEqual(q["price"], 92500.5)
                self.assertEqual(q["prev_close"], 91000.0)
                self.assertEqual(q["change"], 1500.5)
                self.assertEqual(q["change_pct"], 1.65)
                self.assertEqual(q["market"], "crypto")
                self.assertEqual(q["status"], "ok")

                # 测试网络波动时命中 _last_good 缓存
                mock_get.side_effect = httpx.ConnectError("Network timeout")
                fallback_quotes = loop.run_until_complete(provider.get_quotes(["BTC-USD"]))
                self.assertEqual(len(fallback_quotes), 1)
                self.assertEqual(fallback_quotes[0]["price"], 92500.5)

                # 测试从未成功过的标的返回 empty 错误结构
                empty_quotes = loop.run_until_complete(provider.get_quotes(["UNKNOWN-USD"]))
                self.assertEqual(len(empty_quotes), 1)
                self.assertEqual(empty_quotes[0]["status"], "empty")
        finally:
            loop.close()

    # -------------------------------------------------------------
    # 6. 测试 TencentQuoteProvider.get_quotes 路由到 crypto_provider
    # -------------------------------------------------------------
    def test_tencent_quote_provider_routes_crypto(self):
        t_provider = TencentQuoteProvider()
        t_provider.crypto_provider.get_quotes = AsyncMock(return_value=[{
            "symbol": "BTC-USD", "price": 93000.0, "status": "ok"
        }])
        t_provider._get_tencent_quotes = AsyncMock(return_value=[{
            "symbol": "usAAPL", "price": 230.0, "status": "ok"
        }])

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            res = loop.run_until_complete(t_provider.get_quotes(["BTC-USD", "usAAPL"]))
            self.assertEqual(len(res), 2)
            t_provider.crypto_provider.get_quotes.assert_called_once_with(["BTC-USD"])
            t_provider._get_tencent_quotes.assert_called_once_with(["usAAPL"])
        finally:
            loop.close()

    # -------------------------------------------------------------
    # 7. 测试 YahooProvider 加密货币日线使用 10y 周期并能成功拉取
    # -------------------------------------------------------------
    def test_yahoo_crypto_daily_uses_10y_range(self):
        yahoo = YahooProvider()
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            with patch("data_provider.get_proxy_client") as mock_get_client:
                mock_client = AsyncMock()
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                # 模拟 5 根日线数据
                mock_resp.json.return_value = {
                    "chart": {
                        "result": [{
                            "timestamp": [1700000000, 1700086400, 1700172800, 1700259200, 1700345600],
                            "indicators": {
                                "quote": [{
                                    "open": [90000, 91000, 92000, 93000, 94000],
                                    "high": [90500, 91500, 92500, 93500, 94500],
                                    "low": [89500, 90500, 91500, 92500, 93500],
                                    "close": [90200, 91200, 92200, 93200, 94200],
                                    "volume": [1000, 1100, 1200, 1300, 1400],
                                }]
                            }
                        }]
                    }
                }
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_get_client.return_value = mock_client

                df = loop.run_until_complete(yahoo._fetch_yahoo_direct("BTC-USD", "1d", False))
                self.assertFalse(df.empty)
                self.assertEqual(len(df), 5)
                # 确认请求的 URL 中包含了 range=10y
                call_args = mock_client.get.call_args[0][0]
                self.assertIn("range=10y", call_args)
        finally:
            loop.close()

    def test_live_get_klines_btc_usdt_daily(self):
        """端到端实盘验证：BTC/USDT 1d K线能正常返回且根数充足、校验通过。"""
        import asyncio
        from data_provider import provider_manager, validate_klines
        loop = asyncio.new_event_loop()
        try:
            df = loop.run_until_complete(provider_manager.fetch_klines("BTC/USDT", "1d", bypass_cache=True))
            self.assertFalse(df.empty)
            self.assertGreaterEqual(len(df), 100)
            self.assertTrue(validate_klines(df, "1d"))
        finally:
            loop.close()


class TestCryptoDowntrendAndRRGates(unittest.TestCase):
    """
    针对加密货币（以 BTC-USD 为主）在主跌/空头场景及盈亏比门禁的专项单元测试：
    1. BTC-USD 下跌趋势测试：
       - 验证止损不会锚定 1 个月前的远古历史高点（如 108,000），而是锚定波浪证伪线/通道上轨/200EMA/近端次级阻力 + 波动缓冲；
       - TP1 采用前瞻斐波那契延展目标（如 1.618x），规避未确认的盘中即时低点；
       - 风险报酬比 (RR) 计算公式正确且与多空方向匹配。
    2. 盈亏比门禁 (RR Gate) 一致性测试：
       - 验证当策略处于“观望”或未达标时，若条件挂单剧本预估 RR < 2.0R (加密货币) 或 < 2.5R (标准标的)，
         绝对不会输出劣质剧本暴露给用户 (condition_playbook 必须为 None 或 passed_gates 为 True 且 >= 门禁)。
    """

    def setUp(self):
        import numpy as np
        # 构造包含 30 天前 108000 高点，但近期在 94500 -> 88500 下行的 BTC 日线数据 (60根)
        dates = pd.date_range("2026-01-01", periods=60, freq="D")
        prices = np.zeros(60)
        # 前 15 天冲高至 108000 远古高点
        prices[:15] = np.linspace(95000, 108000, 15)
        # 第 16-45 天从 108000 回落至 93000
        prices[15:45] = np.linspace(108000, 93000, 30)
        # 第 46-50 天次级反弹至 94500
        prices[45:50] = np.linspace(93000, 94500, 5)
        # 第 51-60 天破位主跌至 88500
        prices[50:] = np.linspace(94500, 88500, 10)

        self.df_btc_downtrend = pd.DataFrame({
            "Open": prices + 200,
            "High": prices + 600,
            "Low": prices - 600,
            "Close": prices,
            "Volume": [5000 + int(i * 100) for i in range(60)],
        }, index=dates)

    def test_btc_downtrend_stop_loss_not_taking_ancient_high(self):
        """
        BTC-USD 下跌趋势场景：
        验证止损位不会生硬选取 30 天前的 108,000 历史远古高点，
        而是锚定波浪失效位、通道阻力或近端次级阻力（如 94,000 左右）+ 波动缓冲。
        """
        from strategy_adapter import run_strategy_analysis

        res = run_strategy_analysis("BTC-USD", period="1d", mode="swing", df=self.df_btc_downtrend)
        plan = res["summary"]["trade_plan"]

        self.assertIsNotNone(plan["stop_loss"], "应输出有效的止损价格")
        # 远古历史高点为 108000，当前入场价为 88500
        # 合理的动态止损应当远低于 100,000（在 92,000 - 96,000 区域），绝不应取 108,000
        self.assertLess(plan["stop_loss"], 100000.0, f"止损位 ${plan['stop_loss']} 不应锚定远古历史高点 108,000")
        self.assertGreater(plan["stop_loss"], plan["entry"], "空头防守止损必须高于入场价")

        # 验证止损依据包含结构化锚点描述及防守缓冲
        sl_reason = plan["stop_loss_reason"]
        self.assertTrue(len(sl_reason) > 0)
        has_anchor_keyword = any(kw in sl_reason for kw in ["证伪线", "失效位", "通道", "EMA", "波峰", "阻力", "扫损"])
        self.assertTrue(has_anchor_keyword, f"止损依据应为结构性锚点: {sl_reason}")
        self.assertIn("缓冲", sl_reason, f"止损依据应包含波动率防守缓冲: {sl_reason}")

    def test_btc_downtrend_tp1_uses_forward_fibonacci_projection(self):
        """
        BTC-USD 下跌趋势场景：
        验证 TP1 采用前瞻斐波那契空头扩展目标（如 1.618x），
        而不是未确认的盘中即时低点。
        """
        from strategy_adapter import run_strategy_analysis

        res = run_strategy_analysis("BTC-USD", period="1d", mode="swing", df=self.df_btc_downtrend)
        plan = res["summary"]["trade_plan"]

        entry = plan["entry"]
        tp1 = plan["tp1"]
        self.assertIsNotNone(tp1, "应输出 TP1 止盈目标")
        self.assertLess(tp1, entry, "空头方向 TP1 必须严格低于入场价")

        # 验证 TP1 来源为前瞻扩展测算，规避未确认即时极值
        tp1_source = plan.get("tp1_source") or plan.get("tp_source")
        self.assertIsNotNone(tp1_source)
        is_forward_fib = any(kw in tp1_source for kw in ["斐波", "扩展", "测算", "目标"])
        self.assertTrue(is_forward_fib, f"TP1 来源必须是前瞻斐波那契测算: {tp1_source}")

    def test_btc_downtrend_rr_calculation_accuracy(self):
        """
        BTC-USD 下跌趋势场景：
        验证盈亏比 (RR Ratio) 计算精确符合空头逻辑:
        effective_risk = (stop_loss - entry) + friction
        net_reward = (entry - tp1) - friction
        rr = net_reward / effective_risk
        """
        from strategy_adapter import run_strategy_analysis

        res = run_strategy_analysis("BTC-USD", period="1d", mode="swing", df=self.df_btc_downtrend)
        plan = res["summary"]["trade_plan"]

        entry = plan["entry"]
        sl = plan["stop_loss"]
        tp1 = plan["tp1"]
        reported_rr = plan["rr_ratio"]

        # 空头方向：风险 = sl - entry, 收益 = entry - tp1
        friction = entry * 0.0008
        effective_risk = max(0.01, (sl - entry) + friction)
        net_reward = max(0.0, (entry - tp1) - friction)
        expected_rr = round(net_reward / effective_risk, 2)

        self.assertAlmostEqual(reported_rr, expected_rr, delta=0.05,
                               msg=f"报告的盈亏比 {reported_rr} 与预期公式计算值 {expected_rr} 不一致")
        self.assertGreater(reported_rr, 0.0)

    def test_rr_gate_consistency_no_poor_playbook_exposed(self):
        """
        盈亏比硬门禁 (RR Gate) 一致性测试：
        验证任何情况下，若策略处于“观望”且条件挂单剧本预估 RR 低于门禁
        （加密资产 2.0R，标准美股 2.5R），
        系统绝不能将劣质剧本暴露给用户（condition_playbook 必须为 None 或其 RR >= 门禁）。
        """
        import numpy as np
        from strategy_adapter import run_strategy_analysis

        # 构造多种不同的行情数据（多头、空头、横盘震荡、大幅突刺）
        dates = pd.date_range("2026-01-01", periods=60, freq="B")
        test_dfs = []

        # 1. 窄幅微幅震荡
        flat_prices = 100.0 + np.sin(np.linspace(0, 10, 60)) * 0.5
        test_dfs.append(("flat", pd.DataFrame({
            "Open": flat_prices - 0.1, "High": flat_prices + 0.15,
            "Low": flat_prices - 0.15, "Close": flat_prices,
            "Volume": [1000] * 60,
        }, index=dates)))

        # 2. 陡峭上涨后高位钝化
        steep_up = np.linspace(100, 200, 50).tolist() + [199, 201, 198, 202, 199, 200, 201, 199, 200, 200]
        test_dfs.append(("steep_up", pd.DataFrame({
            "Open": np.array(steep_up) - 0.5, "High": np.array(steep_up) + 1.0,
            "Low": np.array(steep_up) - 1.0, "Close": np.array(steep_up),
            "Volume": [2000] * 60,
        }, index=dates)))

        # 3. 陡峭下跌后低位钝化
        steep_down = np.linspace(200, 100, 50).tolist() + [101, 99, 102, 98, 101, 100, 99, 101, 100, 100]
        test_dfs.append(("steep_down", pd.DataFrame({
            "Open": np.array(steep_down) + 0.5, "High": np.array(steep_down) + 1.0,
            "Low": np.array(steep_down) - 1.0, "Close": np.array(steep_down),
            "Volume": [2000] * 60,
        }, index=dates)))

        for label, df in test_dfs:
            # 测试加密资产 (BTC-USD): 门禁为 2.0R
            res_crypto = run_strategy_analysis("BTC-USD", period="1d", mode="swing", df=df)
            plan_c = res_crypto["summary"]["trade_plan"]
            playbook_c = plan_c.get("condition_playbook")
            if playbook_c is not None:
                self.assertGreaterEqual(
                    playbook_c["estimated_rr"], 2.0,
                    f"[{label}] 加密货币条件剧本的预估盈亏比必须 >= 2.0R，实际为: {playbook_c['estimated_rr']}"
                )
                self.assertTrue(playbook_c["passed_gates"])

            # 测试标准股票 (usAAPL): 门禁为 2.5R
            res_stock = run_strategy_analysis("usAAPL", period="1d", mode="swing", df=df)
            plan_s = res_stock["summary"]["trade_plan"]
            playbook_s = plan_s.get("condition_playbook")
            if playbook_s is not None:
                self.assertGreaterEqual(
                    playbook_s["estimated_rr"], 2.5,
                    f"[{label}] 标准资产条件剧本的预估盈亏比必须 >= 2.5R，实际为: {playbook_s['estimated_rr']}"
                )
                self.assertTrue(playbook_s["passed_gates"])

    def test_anti_chase_and_honest_structural_targets(self):
        """
        防追单极值超卖拦截与真实结构止盈测试：
        使用真实 BTC-USD 日线数据验证：
        1. 价格触及通道动态下轨极值超卖区 (pos <= 0.15) 时，严禁发出市价做空信号，主方向必须强制拦截为【观望】；
        2. 绝不允许采用 entry - risk * 2.5 虚构暴跌 45% ($36,000) 的假目标，止盈必须锚定真实结构支撑 ($60,000)；
        3. 真实盈亏比实事求是（如 0.26R），且风控理由明确提示超卖拦截；
        4. 顺势反弹挂单剧本达到合格门禁 (>= 2.0R)。
        """
        from strategy_adapter import run_strategy_analysis

        res = run_strategy_analysis("BTC-USD", period="1d", mode="swing")
        plan = res["summary"]["trade_plan"]

        # 1. 主计划必须为观望，禁止地板做空
        self.assertEqual(plan["direction"], "观望", "极端超卖区主计划必须强制拦截为观望")
        self.assertFalse(plan["passed_gates"])

        # 2. 止盈目标必须是真实下行支撑（如 $60,000），绝不能虚构到 $36,000 腰斩
        self.assertGreater(plan["tp1"], 50000.0, f"TP1 止盈目标 ${plan['tp1']} 绝不能凭空捏造至暴跌 45% 的火星价位")

        # 3. 盈亏比真实反映结构空间，未被强行凑成 2.5R
        self.assertLess(plan["rr_ratio"], 1.0, f"在当前超卖严重空间受限的位置，真实盈亏比应当 < 1.0R，实际为: {plan['rr_ratio']}")

        # 4. 必须包含超卖风控拦截理由
        has_anti_chase_reason = any("超卖" in r or "严禁" in r or "透支" in r for r in plan["reasons"])
        self.assertTrue(has_anti_chase_reason, f"风控理由中必须明确提示超卖防追单拦截: {plan['reasons']}")

        # 5. 反弹挂单剧本达到 >= 2.0R
        playbook = plan.get("condition_playbook")
        if playbook is not None:
            self.assertGreaterEqual(playbook["estimated_rr"], 2.0, "反弹挂单剧本预期 RR 必须 >= 2.0R")


if __name__ == "__main__":
    unittest.main()
