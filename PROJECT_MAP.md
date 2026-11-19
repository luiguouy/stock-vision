# StockVision — 项目结构图谱

> 本文件由 graft 结构层自动导出，是对代码库的**索引**，不是实现说明。
> 每条记录都带 `文件:行号`，用于精确定位；这里**不含函数体**，需要实现细节时应另行取源码。
> 生成时间：2026-11-19 21:35

## 1. 概览

| 指标 | 数值 |
|---|---|
| 源文件 | 55 |
| 语言 | javascript, python, typescript, vue |
| 符号总数 | 707（不含 55 个文件节点） |
| 符号构成 | function 431 / method 195 / file 55 / class 41 / interface 30 / type 10 |
| 依赖边 | 249（跨文件调用、导入、继承） |

后端为 FastAPI + WebSockets（Python），前端为 Vue 3 + Vite + Tailwind（TypeScript/Vue）。

## 2. 模块分布

| 目录 | 文件数 | 符号数 | 被依赖 | 依赖外部 |
|---|---|---|---|---|
| `stage_one/backend/` | 25 | 329 | 137 | 138 |
| `stage_one/backend/assets/` | 1 | 1 | 0 | 0 |
| `stage_one/backend/strategy_core/` | 6 | 91 | 1 | 0 |
| `stage_one/frontend/` | 3 | 0 | 0 | 0 |
| `stage_one/frontend/src/` | 2 | 48 | 1 | 61 |
| `stage_one/frontend/src/components/` | 4 | 41 | 3 | 7 |
| `stage_one/frontend/src/composables/` | 8 | 136 | 45 | 35 |
| `stage_one/frontend/src/utils/` | 6 | 61 | 62 | 8 |

## 3. 核心枢纽

按**被调用次数**排序。改动这些符号的影响面最大，属于优先理解对象。

| 符号 | 位置 | 被调用 | 签名 |
|---|---|---|---|
| `run_strategy_analysis` | `stage_one/backend/strategy_adapter.py:L1926-L2090` | 28 | `def run_strategy_analysis( symbol: str, period: str = "1d", mode: str = "swing", df: Op...` |
| `canonSym` | `stage_one/frontend/src/composables/useWatchlist.ts:L52-L56` | 14 | `canonSym = (s: string): string` |
| `normalize_symbol` | `stage_one/backend/symbols.py:L42-L85` | 13 | `def normalize_symbol(raw: str, market: Optional[str] = None) -> Optional[str]` |
| `normalizeSymbol` | `stage_one/frontend/src/utils/symbols.ts:L87-L136` | 13 | `function normalizeSymbol(raw: string, market?: Market): string` |
| `requestUpdate` | `stage_one/frontend/src/composables/useChartAnnotations.ts:L782-L786` | 11 | `private requestUpdate()` |
| `validate_klines` | `stage_one/backend/data_provider.py:L86-L116` | 8 | `def validate_klines(df: "pd.DataFrame", period: str) -> bool` |
| `_get_connection` | `stage_one/backend/db_cache.py:L68-L80` | 8 | `def _get_connection() -> sqlite3.Connection` |
| `broadcast` | `stage_one/backend/main.py:L768-L773` | 8 | `async def broadcast(self, data: dict)` |
| `marketOf` | `stage_one/frontend/src/utils/symbols.ts:L43-L70` | 8 | `function marketOf(sym: string): Market \| null` |
| `_post` | `stage_one/backend/control_client.py:L58-L64` | 7 | `def _post(path: str, payload: Optional[Dict[str, Any]] = None, err_prefix: str = "请求失败"...` |
| `resample_to_period` | `stage_one/backend/data_provider.py:L193-L218` | 7 | `def resample_to_period(df: pd.DataFrame, rule: str) -> pd.DataFrame` |
| `get_market_cfg` | `stage_one/backend/quote_config.py:L65-L67` | 7 | `def get_market_cfg(market: Optional[str]) -> dict` |
| `strip_prefix` | `stage_one/backend/symbols.py:L123-L129` | 6 | `def strip_prefix(symbol: str) -> str` |
| `median_bar_range` | `stage_one/backend/strategy_core/pa_engine.py:L84-L93` | 6 | `def median_bar_range(df: pd.DataFrame, n: int = 14) -> float` |
| `loadKlineData` | `stage_one/frontend/src/composables/useChartViewport.ts:L697-L798` | 6 | `loadKlineData = async (targetSymbol: string, targetPeriod: Period)` |

## 4. 文件级依赖

只列**项目内跨文件**关系，同文件内的包含关系与标准库导入已剔除。括号内为关系类型与出现次数。

- **stage_one/backend/control_client.py** → `stage_one/backend/symbols.py` (calls ×2, imports)
- **stage_one/backend/data_provider.py** → `stage_one/backend/symbols.py` (calls, imports)
- **stage_one/backend/db_cache.py** → `stage_one/backend/data_provider.py` (calls, imports)
- **stage_one/backend/main.py** → `stage_one/backend/analysis.py` (calls ×2, imports), `stage_one/backend/data_provider.py` (imports), `stage_one/backend/db_cache.py` (calls ×10, imports), `stage_one/backend/quote_config.py` (imports), `stage_one/backend/quote_provider.py` (imports), `stage_one/backend/strategy_adapter.py` (calls ×2, imports), `stage_one/backend/symbols.py` (calls ×16, imports)
- **stage_one/backend/quote_config.py** → `stage_one/backend/symbols.py` (imports)
- **stage_one/backend/quote_provider.py** → `stage_one/backend/data_provider.py` (imports), `stage_one/backend/quote_config.py` (calls ×6, imports)
- **stage_one/backend/strategy_adapter.py** → `stage_one/backend/strategy_core/plot_wave_chart.py` (calls), `stage_one/backend/symbols.py` (calls ×3, imports), `stage_one/backend/time_window.py` (calls, imports)
- **stage_one/backend/test_adjustment.py** → `stage_one/backend/data_provider.py` (calls, imports)
- **stage_one/backend/test_crypto_features.py** → `stage_one/backend/data_provider.py` (calls ×5, imports), `stage_one/backend/main.py` (imports), `stage_one/backend/quote_config.py` (calls, imports), `stage_one/backend/quote_provider.py` (calls ×4, imports), `stage_one/backend/strategy_adapter.py` (calls ×5, imports)
- **stage_one/backend/test_dow_elliott_refactor.py** → `stage_one/backend/strategy_adapter.py` (calls ×5, imports)
- **stage_one/backend/test_dow_elliott_us_strategy.py** → `stage_one/backend/strategy_adapter.py` (calls ×10, imports)
- **stage_one/backend/test_endpoints.py** → `stage_one/backend/analysis.py` (calls ×2, imports), `stage_one/backend/data_provider.py` (calls ×3, imports), `stage_one/backend/main.py` (imports), `stage_one/backend/mcp_server.py` (imports), `stage_one/backend/quote_config.py` (imports), `stage_one/backend/quote_provider.py` (imports), `stage_one/backend/symbols.py` (calls)
- **stage_one/backend/test_optimization_and_refactor.py** → `stage_one/backend/analysis.py` (calls ×2, imports), `stage_one/backend/strategy_adapter.py` (calls ×2, imports)
- **stage_one/backend/test_resample.py** → `stage_one/backend/data_provider.py` (calls ×6, imports)
- **stage_one/backend/test_strategy_wave_channel.py** → `stage_one/backend/main.py` (imports), `stage_one/backend/strategy_adapter.py` (calls ×3, imports)
- **stage_one/backend/test_transformation_new.py** → `stage_one/backend/main.py` (imports), `stage_one/backend/mcp_server.py` (imports), `stage_one/backend/strategy_adapter.py` (calls, imports)
- **stage_one/backend/test_triggers_and_turning_dates.py** → `stage_one/backend/strategy_adapter.py` (calls ×2, imports)
- **stage_one/backend/test_validate.py** → `stage_one/backend/data_provider.py` (calls, imports)
- **stage_one/frontend/src/App.vue** → `stage_one/frontend/src/components/GlobalSecuritySearch.vue` (imports), `stage_one/frontend/src/components/StrategyPanel.vue` (imports), `stage_one/frontend/src/components/ThemeToggle.vue` (imports), `stage_one/frontend/src/composables/useChartAnnotations.ts` (calls, imports), `stage_one/frontend/src/composables/useChartCore.ts` (calls ×2, imports), `stage_one/frontend/src/composables/useChartIndicators.ts` (calls ×3, imports), `stage_one/frontend/src/composables/useChartViewport.ts` (calls ×9, imports), `stage_one/frontend/src/composables/useLiveQuoteSync.ts` (calls ×5, imports), `stage_one/frontend/src/composables/useSmartThrottling.ts` (calls, imports), `stage_one/frontend/src/composables/useWatchlist.ts` (calls ×6, imports), `stage_one/frontend/src/composables/useWebSocketControl.ts` (calls, imports), `stage_one/frontend/src/utils/api.ts` (calls ×3, imports), `stage_one/frontend/src/utils/chartUtils.ts` (calls, imports), `stage_one/frontend/src/utils/symbols.ts` (calls ×15)
- **stage_one/frontend/src/components/GlobalSecuritySearch.vue** → `stage_one/frontend/src/utils/api.ts` (calls ×2, imports), `stage_one/frontend/src/utils/symbols.ts` (calls)
- **stage_one/frontend/src/components/StrategyPanel.vue** → `stage_one/frontend/src/utils/api.ts` (imports), `stage_one/frontend/src/utils/srUtils.ts` (calls, imports)
- **stage_one/frontend/src/composables/useChartCore.ts** → `stage_one/frontend/src/utils/chartUtils.ts` (calls, imports)
- **stage_one/frontend/src/composables/useChartIndicators.ts** → `stage_one/frontend/src/composables/useChartAnnotations.ts` (imports), `stage_one/frontend/src/utils/api.ts` (imports)
- **stage_one/frontend/src/composables/useChartViewport.ts** → `stage_one/frontend/src/composables/useChartAnnotations.ts` (imports), `stage_one/frontend/src/composables/useChartIndicators.ts` (calls ×2), `stage_one/frontend/src/utils/api.ts` (calls, imports), `stage_one/frontend/src/utils/mockEngine.ts` (calls, imports), `stage_one/frontend/src/utils/srUtils.ts` (calls, imports), `stage_one/frontend/src/utils/symbols.ts` (calls)
- **stage_one/frontend/src/composables/useLiveQuoteSync.ts** → `stage_one/frontend/src/composables/useChartAnnotations.ts` (imports), `stage_one/frontend/src/composables/useChartViewport.ts` (calls), `stage_one/frontend/src/composables/useWatchlist.ts` (calls ×2, imports), `stage_one/frontend/src/utils/api.ts` (calls, imports), `stage_one/frontend/src/utils/quote.ts` (calls, imports), `stage_one/frontend/src/utils/symbols.ts` (calls)
- **stage_one/frontend/src/composables/useWatchlist.ts** → `stage_one/frontend/src/utils/api.ts` (calls ×2, imports), `stage_one/frontend/src/utils/quote.ts` (calls, imports), `stage_one/frontend/src/utils/symbols.ts` (calls ×6)
- **stage_one/frontend/src/main.ts** → `stage_one/frontend/src/App.vue` (imports)
- **stage_one/frontend/src/utils/api.ts** → `stage_one/frontend/src/utils/mockEngine.ts` (calls ×2, imports)
- **stage_one/frontend/src/utils/quote.ts** → `stage_one/frontend/src/utils/api.ts` (imports), `stage_one/frontend/src/utils/symbols.ts` (calls ×3)
- **stage_one/frontend/src/utils/srUtils.ts** → `stage_one/frontend/src/utils/api.ts` (imports)

### 外部依赖

项目外部模块（标准库 / 第三方包），仅列被导入者：

- **stage_one/backend/analysis.py**：scipy.ndimage, typing
- **stage_one/backend/assets/make_icons.py**：PIL, cv2, os, struct
- **stage_one/backend/cli.py**：argparse, sys
- **stage_one/backend/control_client.py**：httpx, os, subprocess, sys, time, typing, uuid
- **stage_one/backend/data_provider.py**：asyncio, datetime, fastapi, httpx, json, re, typing, zoneinfo
- **stage_one/backend/db_cache.py**：datetime, json, os, sqlite3, typing
- **stage_one/backend/desktop_main.py**：ctypes, os, socket, sys, threading, time, urllib.request, uvicorn, webview
- **stage_one/backend/main.py**：asyncio, base64, contextlib, datetime, difflib, fastapi, fastapi.middleware.cors, fastapi.responses, fastapi.staticfiles, httpx, json, os, pydantic, re, typing, uuid, uvicorn
- **stage_one/backend/mcp_server.py**：mcp.server.fastmcp, mcp.server.mcpserver, typing
- **stage_one/backend/quote_config.py**：typing
- **stage_one/backend/quote_provider.py**：asyncio, datetime, httpx, time, typing
- **stage_one/backend/strategy_adapter.py**：os, pathlib, re, strategy_core, strategy_core.plot_wave_chart, sys, typing
- **stage_one/backend/strategy_core/__init__.py**：.
- **stage_one/backend/strategy_core/pa_engine.py**：argparse, datetime, json, os, scipy.signal, sys, time
- **stage_one/backend/strategy_core/plot_wave_chart.py**：., argparse, pathlib, plotly.subplots, re, sys
- **stage_one/backend/strategy_core/strategy_crypto.py**：., os, sys
- **stage_one/backend/strategy_core/strategy_day.py**：., datetime, json, os, sys
- **stage_one/backend/strategy_core/strategy_layer.py**：.
- **stage_one/backend/symbols.py**：re, typing
- **stage_one/backend/test_adjustment.py**：os, sys
- **stage_one/backend/test_crypto_features.py**：asyncio, fastapi.testclient, httpx, unittest, unittest.mock
- **stage_one/backend/test_dow_elliott_refactor.py**：strategy_core, unittest
- **stage_one/backend/test_dow_elliott_us_strategy.py**：unittest
- **stage_one/backend/test_endpoints.py**：asyncio, fastapi, fastapi.testclient, math, os, sys, unittest
- **stage_one/backend/test_optimization_and_refactor.py**：scipy.signal, strategy_core, unittest
- **stage_one/backend/test_pagination.py**：datetime, httpx, json
- **stage_one/backend/test_resample.py**：os, sys
- **stage_one/backend/test_strategy_wave_channel.py**：fastapi.testclient, unittest
- **stage_one/backend/test_transformation_new.py**：fastapi.testclient, os, sys, unittest
- **stage_one/backend/test_triggers_and_turning_dates.py**：unittest
- **stage_one/backend/test_validate.py**：datetime
- **stage_one/backend/time_window.py**：datetime, typing
- **stage_one/frontend/src/App.vue**：vue
- **stage_one/frontend/src/components/DateRangePicker.vue**：vue
- **stage_one/frontend/src/components/GlobalSecuritySearch.vue**：vue
- **stage_one/frontend/src/components/StrategyPanel.vue**：vue
- **stage_one/frontend/src/components/ThemeToggle.vue**：vue
- **stage_one/frontend/src/composables/useChartAnnotations.ts**：lightweight-charts, vue
- **stage_one/frontend/src/composables/useChartCore.ts**：lightweight-charts, vue
- **stage_one/frontend/src/composables/useChartIndicators.ts**：lightweight-charts, vue
- **stage_one/frontend/src/composables/useChartViewport.ts**：lightweight-charts, vue
- **stage_one/frontend/src/composables/useLiveQuoteSync.ts**：lightweight-charts, vue
- **stage_one/frontend/src/composables/useSmartThrottling.ts**：vue
- **stage_one/frontend/src/composables/useWatchlist.ts**：vue
- **stage_one/frontend/src/composables/useWebSocketControl.ts**：vue
- **stage_one/frontend/src/main.ts**：./style.css, vue
- **stage_one/frontend/src/utils/chartUtils.ts**：lightweight-charts
- **stage_one/frontend/vite.config.ts**：@vitejs/plugin-vue, vite

## 5. 符号清单

按文件分组，格式：`名称` · 类型 · 行范围 · 签名。前缀 `+` 表示对外导出。

### stage_one/backend/analysis.py

共 3 个符号 · 被依赖 9 · 依赖外部 0

-   `_extract_ohlc` · function · L32-L38 — `def _extract_ohlc(df: pd.DataFrame) -> pd.DataFrame`
- + `calculate_sr_levels` · function · L41-L161 — `def calculate_sr_levels( df: pd.DataFrame, window: int = 5, distance_pct: float = 0.015, period: str = "1d", ) -> List[Dict[str, Any]]`
- + `calculate_range_stats` · function · L164-L266 — `def calculate_range_stats( df: pd.DataFrame, start_date: str, end_date: str ) -> Dict[str, Any]`

### stage_one/backend/assets/make_icons.py

共 1 个符号 · 被依赖 0 · 依赖外部 0

- + `generate_icons` · function · L22-L102 — `def generate_icons()`

### stage_one/backend/cli.py

共 9 个符号 · 被依赖 0 · 依赖外部 0

- + `cmd_open` · function · L23-L29 — `def cmd_open(args)`
- + `cmd_state` · function · L32-L43 — `def cmd_state(args)`
- + `cmd_mark` · function · L46-L58 — `def cmd_mark(args)`
- + `cmd_line` · function · L61-L73 — `def cmd_line(args)`
- + `cmd_box` · function · L76-L90 — `def cmd_box(args)`
- + `cmd_analyze` · function · L93-L117 — `def cmd_analyze(args)`
- + `cmd_capture` · function · L120-L125 — `def cmd_capture(args)`
- + `cmd_clear` · function · L128-L133 — `def cmd_clear(args)`
- + `main` · function · L136-L206 — `def main()`

### stage_one/backend/control_client.py

共 14 个符号 · 被依赖 0 · 依赖外部 3

- + `ensure_app_running` · function · L25-L49 — `def ensure_app_running() -> bool`
-   `_format_symbol` · function · L52-L55 — `def _format_symbol(raw: str) -> str`
-   `_post` · function · L58-L64 — `def _post(path: str, payload: Optional[Dict[str, Any]] = None, err_prefix: str = "请求失败") -> Dict[str, Any]`
- + `get_state` · function · L67-L72 — `def get_state() -> Dict[str, Any]`
- + `open_chart` · function · L75-L76 — `def open_chart(symbol: str, period: str = "1d") -> Dict[str, Any]`
- + `add_markers` · function · L79-L80 — `def add_markers(symbol: str, markers: List[Dict[str, Any]]) -> Dict[str, Any]`
- + `draw_lines` · function · L83-L84 — `def draw_lines(symbol: str, lines: List[Dict[str, Any]]) -> Dict[str, Any]`
- + `draw_boxes` · function · L87-L88 — `def draw_boxes(symbol: str, boxes: List[Dict[str, Any]]) -> Dict[str, Any]`
- + `run_strategy` · function · L91-L106 — `def run_strategy( symbol: str, period: str = "1d", mode: str = "swing", draw_on_chart: bool = True, ) -> Dict[str, Any]`
- + `capture_chart` · function · L109-L110 — `def capture_chart() -> Dict[str, Any]`
- + `clear_annotations` · function · L113-L123 — `def clear_annotations( symbol: str, kind: Optional[str] = None, source: Optional[str] = None, ) -> Dict[str, Any]`
- + `get_watchlist` · function · L126-L131 — `def get_watchlist() -> Dict[str, Any]`
- + `update_watchlist` · function · L134-L187 — `def update_watchlist( action: str, symbol: str, group_name: Optional[str] = None, ) -> Dict[str, Any]`
- + `search_symbols` · function · L190-L202 — `def search_symbols(keyword: str, limit: int = 10) -> Dict[str, Any]`

### stage_one/backend/data_provider.py

共 40 个符号 · 被依赖 25 · 依赖外部 2

-   `_get_http_client` · function · L34-L60 — `async def _get_http_client(use_proxy: bool, timeout: float) -> httpx.AsyncClient`
- + `get_direct_client` · function · L63-L65 — `async def get_direct_client() -> httpx.AsyncClient`
- + `get_proxy_client` · function · L68-L70 — `async def get_proxy_client() -> httpx.AsyncClient`
-   `_normalize_date` · function · L72-L84 — `def _normalize_date(raw: str) -> str`
- + `validate_klines` · function · L86-L116 — `def validate_klines(df: "pd.DataFrame", period: str) -> bool`
-   `_is_split_ratio` · function · L120-L129 — `def _is_split_ratio(r: float) -> bool`
- + `apply_forward_adjustment` · function · L131-L159 — `def apply_forward_adjustment(df: "pd.DataFrame") -> "pd.DataFrame"`
- + `resample_to_4h` · function · L162-L190 — `def resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame`
- + `resample_to_period` · function · L193-L218 — `def resample_to_period(df: pd.DataFrame, rule: str) -> pd.DataFrame`
- + `DataProvider` · class · L254-L262 — `class DataProvider`
-   `__init__` · method · L255-L256 — `def __init__(self, name: str)`
- + `fetch_klines` · method · L258-L259 — `async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame`
- + `supports_period` · method · L261-L262 — `def supports_period(self, period: str) -> bool`
- + `TencentProvider` · class · L264-L400 — `class TencentProvider(DataProvider)`
-   `__init__` · method · L270-L271 — `def __init__(self)`
- + `supports_period` · method · L273-L274 — `def supports_period(self, period: str) -> bool`
-   `_fetch_raw` · method · L276-L330 — `async def _fetch_raw(self, symbol: str, tencent_period: str, count: int, end: str = None) -> pd.DataFrame`
-   `_fetch_full_via_pagination` · method · L332-L359 — `async def _fetch_full_via_pagination( self, symbol: str, tencent_period: str, page_count: int = 1000, max_pages: int = 8 ) -> pd.DataFrame`
- + `fetch_klines` · method · L361-L389 — `async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame`
-   `_get_symbol_candidates` · method · L391-L400 — `def _get_symbol_candidates(self, symbol: str) -> List[str]`
- + `YahooProvider` · class · L403-L568 — `class YahooProvider(DataProvider)`
-   `__init__` · method · L406-L407 — `def __init__(self)`
- + `supports_period` · method · L409-L410 — `def supports_period(self, period: str) -> bool`
- + `fetch_klines` · method · L412-L429 — `async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame`
-   `_dispatch_resample` · method · L432-L439 — `def _dispatch_resample(df: pd.DataFrame, rule: str) -> pd.DataFrame`
-   `_fetch_yahoo_direct` · method · L441-L542 — `async def _fetch_yahoo_direct( self, ticker: str, interval: str, need_resample: bool, resample_rule: str = None ) -> pd.DataFrame`
-   `_query_data` · function · L462-L472 — `async def _query_data(query_range: str)`
-   `_parse_chart_json` · function · L474-L522 — `def _parse_chart_json(data_json) -> pd.DataFrame`
-   `_to_yahoo_ticker` · method · L545-L568 — `def _to_yahoo_ticker(symbol: str) -> str`
- + `SinaFuturesProvider` · class · L570-L648 — `class SinaFuturesProvider(DataProvider)`
-   `__init__` · method · L581-L582 — `def __init__(self)`
- + `supports_period` · method · L584-L585 — `def supports_period(self, period: str) -> bool`
-   `_to_code` · method · L587-L588 — `def _to_code(self, symbol: str) -> Optional[str]`
- + `fetch_klines` · method · L590-L600 — `async def fetch_klines(self, symbol: str, period: str, count: int = 320, full: bool = False) -> pd.DataFrame`
-   `_fetch_daily` · method · L602-L617 — `async def _fetch_daily(self, code: str) -> pd.DataFrame`
-   `_parse_klines` · method · L620-L648 — `def _parse_klines(text: str) -> "pd.DataFrame"`
- + `DataProviderManager` · class · L650-L731 — `class DataProviderManager`
-   `__init__` · method · L653-L658 — `def __init__(self)`
- + `last_source` · method · L661-L662 — `def last_source(self) -> Optional[str]`
- + `fetch_klines` · method · L664-L731 — `async def fetch_klines( self, symbol: str, period: str = '1d', count: int = 320, full: bool = False, bypass_cache: bool = False ) -> pd.DataFrame`

### stage_one/backend/db_cache.py

共 9 个符号 · 被依赖 11 · 依赖外部 2

-   `_get_connection` · function · L68-L80 — `def _get_connection() -> sqlite3.Connection`
- + `init_db` · function · L83-L92 — `def init_db() -> None`
- + `get_cached_klines` · function · L95-L149 — `def get_cached_klines( symbol: str, period: str, max_age_hours: Union[int, float] = 24 ) -> Optional[List[Dict]]`
- + `save_klines` · function · L152-L189 — `def save_klines( symbol: str, period: str, klines: List[Dict], source: str = "" ) -> None`
- + `cache_status` · function · L192-L206 — `def cache_status(symbol: str, period: str) -> Optional[Dict]`
- + `save_annotation` · function · L213-L226 — `def save_annotation(anno_id: str, symbol: str, kind: str, data: dict, source: str = "") -> None`
- + `save_annotations_batch` · function · L229-L248 — `def save_annotations_batch(symbol: str, kind: str, items: List[dict], source: str = "") -> None`
- + `get_annotations` · function · L251-L283 — `def get_annotations(symbol: str, kind: Optional[str] = None) -> List[dict]`
- + `clear_annotations` · function · L286-L304 — `def clear_annotations(symbol: str, kind: Optional[str] = None, source: Optional[str] = None) -> int`

### stage_one/backend/desktop_main.py

共 9 个符号 · 被依赖 0 · 依赖外部 0

-   `_console_available` · function · L30-L38 — `def _console_available() -> bool`
- + `setup_logging` · function · L41-L52 — `def setup_logging()`
- + `check_single_instance` · function · L55-L67 — `def check_single_instance() -> bool`
- + `start_backend_server` · function · L70-L79 — `def start_backend_server(port: int = 8000)`
- + `wait_for_backend` · function · L82-L91 — `def wait_for_backend(port: int, timeout: float = 30.0) -> bool`
- + `main` · function · L686-L798 — `def main()`
-   `_boot` · function · L717-L765 — `def _boot()`
-   `_on_restored` · function · L767-L771 — `def _on_restored()`
-   `_on_minimized` · function · L773-L777 — `def _on_minimized()`

### stage_one/backend/main.py

共 55 个符号 · 被依赖 4 · 依赖外部 37

- + `lifespan` · function · L61-L64 — `async def lifespan(app: FastAPI)`
- + `read_root` · function · L86-L91 — `def read_root()`
- + `health_check` · function · L95-L97 — `def health_check()`
- + `get_quote` · function · L105-L116 — `async def get_quote( symbols: str = Query(..., description="逗号分隔的带前缀代码, 如 usAAPL,BTC-USD"), )`
- + `quote_config` · function · L120-L145 — `async def quote_config()`
-   `_patch_latest_bar_with_quote` · function · L247-L284 — `async def _patch_latest_bar_with_quote(symbol: str, period: str, df: pd.DataFrame) -> pd.DataFrame`
- + `get_klines_df` · function · L287-L324 — `async def get_klines_df(symbol: str, period: str, full: bool = True, bypass_cache: bool = False)`
-   `_load_local_csv_fallback` · function · L327-L336 — `def _load_local_csv_fallback(norm_sym: str) -> Optional[pd.DataFrame]`
- + `prewarm_cache` · function · L339-L365 — `async def prewarm_cache()`
- + `KLinePoint` · class · L372-L378 — `class KLinePoint(BaseModel)`
- + `AnalysisRequest` · class · L381-L385 — `class AnalysisRequest(BaseModel)`
- + `WatchGroupModel` · class · L388-L391 — `class WatchGroupModel(BaseModel)`
- + `WatchlistGroupsRequest` · class · L394-L395 — `class WatchlistGroupsRequest(BaseModel)`
- + `SRLevel` · class · L398-L403 — `class SRLevel(BaseModel)`
- + `RangeStat` · class · L406-L409 — `class RangeStat(BaseModel)`
- + `AnalysisResponse` · class · L412-L416 — `class AnalysisResponse(BaseModel)`
-   `_score_stock` · function · L423-L477 — `def _score_stock(kw: str, stock: dict) -> int`
- + `search_stocks` · function · L481-L542 — `async def search_stocks( keyword: Optional[str] = Query(None, description="搜索股票名称、英文名称、代码或拼音缩写（全市场范围内）"), )`
-   `_tencent_security_search` · function · L545-L616 — `async def _tencent_security_search(kw: str) -> list`
-   `_parse_search_code` · function · L547-L557 — `def _parse_search_code(code: str) -> Optional[str]`
-   `_pool_item` · function · L559-L579 — `def _pool_item(code: str, name: str, pinyin: str = "", type_: str = "") -> Optional[dict]`
- + `get_klines` · function · L620-L643 — `async def get_klines( symbol: str = Query(..., description="股票代码，如 usAAPL"), period: str = Query("1d", description="K线周期"), full: bool = Query(True, description="是否拉取上市以来全部历史"), fresh: bool = Query(False, description="是否跳过缓存强制拉取最新数据"), )`
- + `analyze_stock` · function · L647-L663 — `async def analyze_stock(request: AnalysisRequest)`
- + `get_supported_periods` · function · L667-L683 — `async def get_supported_periods()`
-   `_default_groups` · function · L694-L695 — `def _default_groups() -> List[dict]`
-   `_load_groups` · function · L698-L714 — `def _load_groups() -> List[dict]`
-   `_save_groups` · function · L717-L733 — `def _save_groups(groups: List[dict]) -> List[dict]`
- + `get_watchlist` · function · L737-L738 — `async def get_watchlist()`
- + `save_watchlist` · function · L742-L748 — `async def save_watchlist(req: WatchlistGroupsRequest)`
- + `WSManager` · class · L755-L777 — `class WSManager`
-   `__init__` · method · L756-L758 — `def __init__(self)`
- + `connect` · method · L760-L762 — `async def connect(self, ws: WebSocket)`
- + `disconnect` · method · L764-L766 — `def disconnect(self, ws: WebSocket)`
- + `broadcast` · method · L768-L773 — `async def broadcast(self, data: dict)`
- + `resolve_capture` · method · L775-L777 — `def resolve_capture(self, request_id: str, image_base64: str)`
- + `websocket_control` · function · L791-L815 — `async def websocket_control(websocket: WebSocket)`
- + `OpenChartRequest` · class · L818-L820 — `class OpenChartRequest(BaseModel)`
- + `MarkerItem` · class · L823-L829 — `class MarkerItem(BaseModel)`
- + `AddMarkersRequest` · class · L832-L835 — `class AddMarkersRequest(BaseModel)`
- + `LineItem` · class · L838-L844 — `class LineItem(BaseModel)`
- + `DrawLinesRequest` · class · L847-L850 — `class DrawLinesRequest(BaseModel)`
- + `BoxItem` · class · L853-L861 — `class BoxItem(BaseModel)`
- + `DrawBoxesRequest` · class · L864-L867 — `class DrawBoxesRequest(BaseModel)`
- + `RunStrategyRequest` · class · L870-L875 — `class RunStrategyRequest(BaseModel)`
- + `ClearAnnotationsRequest` · class · L878-L881 — `class ClearAnnotationsRequest(BaseModel)`
- + `control_open` · function · L885-L897 — `async def control_open(req: OpenChartRequest)`
- + `control_get_state` · function · L901-L909 — `async def control_get_state()`
- + `control_add_markers` · function · L913-L922 — `async def control_add_markers(req: AddMarkersRequest)`
- + `control_draw_lines` · function · L926-L935 — `async def control_draw_lines(req: DrawLinesRequest)`
- + `control_draw_boxes` · function · L939-L948 — `async def control_draw_boxes(req: DrawBoxesRequest)`
- + `control_run_strategy` · function · L952-L1012 — `async def control_run_strategy(req: RunStrategyRequest)`
- + `get_strategy_chart_html` · function · L1016-L1031 — `async def get_strategy_chart_html(symbol: str, period: str = "1d")`
- + `control_clear_annotations` · function · L1035-L1043 — `async def control_clear_annotations(req: ClearAnnotationsRequest)`
- + `control_get_annotations` · function · L1047-L1052 — `async def control_get_annotations( symbol: str = Query(..., description="股票代码"), kind: Optional[str] = Query(None, description="标注类型: marker / line / box"), )`
- + `control_capture_chart` · function · L1056-L1098 — `async def control_capture_chart()`

### stage_one/backend/mcp_server.py

共 22 个符号 · 被依赖 2 · 依赖外部 0

-   `_ToolInfo` · class · L22-L24 — `class _ToolInfo`
-   `__init__` · method · L23-L24 — `def __init__(self, name)`
-   `_DummyToolManager` · class · L26-L31 — `class _DummyToolManager`
-   `__init__` · method · L27-L28 — `def __init__(self)`
- + `list_tools` · method · L30-L31 — `def list_tools(self)`
-   `_DummyServer` · class · L33-L44 — `class _DummyServer`
-   `__init__` · method · L34-L35 — `def __init__(self)`
- + `tool` · method · L37-L41 — `def tool(self, *args, **kwargs)`
- + `decorator` · function · L38-L40 — `def decorator(f)`
- + `run` · method · L43-L44 — `def run(self, *args, **kwargs)`
- + `stock_get_state` · function · L53-L55 — `def stock_get_state() -> Dict[str, Any]`
- + `stock_open_chart` · function · L59-L61 — `def stock_open_chart(symbol: str, period: str = "1d") -> Dict[str, Any]`
- + `stock_add_markers` · function · L65-L67 — `def stock_add_markers(symbol: str, markers: List[Dict[str, Any]]) -> Dict[str, Any]`
- + `stock_draw_price_lines` · function · L71-L73 — `def stock_draw_price_lines(symbol: str, lines: List[Dict[str, Any]]) -> Dict[str, Any]`
- + `stock_draw_boxes` · function · L77-L79 — `def stock_draw_boxes(symbol: str, boxes: List[Dict[str, Any]]) -> Dict[str, Any]`
- + `stock_run_pa_strategy` · function · L83-L87 — `def stock_run_pa_strategy( symbol: str, mode: str = "swing", draw_on_chart: bool = True ) -> Dict[str, Any]`
- + `stock_capture_chart` · function · L91-L93 — `def stock_capture_chart() -> Dict[str, Any]`
- + `stock_clear_annotations` · function · L97-L99 — `def stock_clear_annotations(symbol: str, source: Optional[str] = None) -> Dict[str, Any]`
- + `stock_get_watchlist` · function · L103-L105 — `def stock_get_watchlist() -> Dict[str, Any]`
- + `stock_update_watchlist` · function · L109-L118 — `def stock_update_watchlist( action: str, symbol: str, group_name: Optional[str] = None ) -> Dict[str, Any]`
- + `stock_search_symbols` · function · L122-L124 — `def stock_search_symbols(keyword: str, limit: int = 10) -> Dict[str, Any]`
- + `main` · function · L127-L128 — `def main()`

### stage_one/backend/quote_config.py

共 2 个符号 · 被依赖 11 · 依赖外部 1

- + `market_of` · function · L60-L62 — `def market_of(symbol: str) -> Optional[str]`
- + `get_market_cfg` · function · L65-L67 — `def get_market_cfg(market: Optional[str]) -> dict`

### stage_one/backend/quote_provider.py

共 30 个符号 · 被依赖 7 · 依赖外部 8

- + `QuoteRateLimiter` · class · L38-L98 — `class QuoteRateLimiter`
-   `__init__` · method · L41-L48 — `def __init__(self) -> None`
- + `allow` · method · L50-L71 — `async def allow(self, market: str, symbol: str) -> Tuple[bool, str]`
- + `record_symbol` · method · L73-L74 — `def record_symbol(self, symbol: str) -> None`
- + `record_http_call` · method · L76-L78 — `def record_http_call(self) -> None`
- + `on_rate_limited` · method · L80-L84 — `def on_rate_limited(self) -> None`
- + `on_symbol_empty` · method · L86-L88 — `def on_symbol_empty(self, symbol: str) -> None`
- + `status` · method · L90-L98 — `def status(self) -> Dict`
-   `_get_direct_client` · function · L104-L121 — `async def _get_direct_client() -> httpx.AsyncClient`
-   `_get_proxy_client` · function · L126-L143 — `async def _get_proxy_client() -> httpx.AsyncClient`
- + `YahooCryptoQuoteProvider` · class · L145-L223 — `class YahooCryptoQuoteProvider`
-   `__init__` · method · L148-L149 — `def __init__(self) -> None`
- + `get_quotes` · method · L151-L223 — `async def get_quotes(self, symbols: List[str]) -> List[dict]`
- + `TencentQuoteProvider` · class · L225-L442 — `class TencentQuoteProvider`
-   `__init__` · method · L228-L233 — `def __init__(self) -> None`
-   `_resolve_us_ext_session` · method · L235-L263 — `def _resolve_us_ext_session(self, symbol: str, ext_price: float) -> Tuple[Optional[float], str]`
-   `_fetch_yahoo_premarket` · method · L265-L294 — `async def _fetch_yahoo_premarket(self, us_symbols: List[str]) -> Dict[str, float]`
-   `_one` · function · L272-L291 — `async def _one(sym: str)`
- + `get_quotes` · method · L296-L322 — `async def get_quotes(self, symbols: List[str]) -> List[dict]`
-   `_get_tencent_quotes` · method · L324-L373 — `async def _get_tencent_quotes(self, symbols: List[str]) -> List[dict]`
-   `_fetch_raw` · method · L375-L389 — `async def _fetch_raw(self, symbols: List[str]) -> str`
-   `_parse` · method · L391-L442 — `def _parse(self, text: str, symbols: List[str]) -> Dict[str, Optional[dict]]`
-   `_to_float` · function · L444-L455 — `def _to_float(s) -> Optional[float]`
-   `_format_update_time` · function · L457-L461 — `def _format_update_time(raw: str) -> str`
-   `_error_item` · function · L463-L483 — `def _error_item(symbol: str, status: str, msg: str) -> dict`
- + `SinaFuturesQuoteProvider` · class · L493-L624 — `class SinaFuturesQuoteProvider`
-   `__init__` · method · L496-L499 — `def __init__(self) -> None`
- + `get_quotes` · method · L501-L546 — `async def get_quotes(self, symbols: List[str]) -> List[dict]`
-   `_fetch` · method · L548-L582 — `async def _fetch(self, symbols: List[str]) -> Dict[str, Optional[dict]]`
-   `_parse_line` · method · L585-L624 — `def _parse_line(line: str) -> Optional[dict]`

### stage_one/backend/strategy_adapter.py

共 14 个符号 · 被依赖 38 · 依赖外部 7

-   `_get_modules` · function · L21-L41 — `def _get_modules() -> Dict[str, Any]`
-   `_normalize_df` · function · L44-L93 — `def _normalize_df(df: Any) -> Any`
-   `_prepare_strategy_df` · function · L96-L108 — `def _prepare_strategy_df(symbol: str, df: Optional[Any]) -> Any`
-   `_evaluate_market_structure` · function · L111-L249 — `def _evaluate_market_structure( pa: Any, df_clean: Any, current_price: float, is_intraday: bool, is_crypto: bool = False ) -> Dict[str, Any]`
-   `_verify_us_market_dow` · function · L255-L361 — `def _verify_us_market_dow( pa: Any, spy_df: Optional[Any] = None, qqq_df: Optional[Any] = None, iwm_df: Optional[Any] = None, force_refresh: bool = False, ) -> Dict[str, Any]`
-   `_eval_index` · function · L289-L316 — `def _eval_index(df: Any) -> Tuple[str, bool, bool, float, float]`
-   `_build_trade_plan` · function · L364-L1409 — `def _build_trade_plan( pa: Any, df_clean: Any, current_price: float, struct: Dict[str, Any], turn_windows_res: Dict[str, Any], is_crypto: bool = False, is_us: bool = True, dow_market_ver: Optional[Dict[str, Any]] = None, ) -> Dict[str, Any]`
-   `_get_pt_p` · function · L446-L451 — `def _get_pt_p(key: Any) -> Optional[float]`
-   `_build_chart_annotations` · function · L1412-L1856 — `def _build_chart_annotations( pa: Any, df_clean: Any, current_price: float, is_intraday: bool, struct: Dict[str, Any], trade_plan: Dict[str, Any], turn_windows_res: Dict[str, Any], ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]`
-   `_format_time_str` · function · L1432-L1444 — `def _format_time_str(val: Any) -> str`
-   `_resolve_pt_time` · function · L1446-L1450 — `def _resolve_pt_time(pt: Dict[str, Any], idx: int) -> str`
-   `_generate_depth_diagnosis` · function · L1859-L1923 — `def _generate_depth_diagnosis( struct: Dict[str, Any], trade_plan: Dict[str, Any], turn_windows_res: Dict[str, Any], current_price: float, dow_market_ver: Optional[Dict[str, Any]] = None, ) -> str`
- + `run_strategy_analysis` · function · L1926-L2090 — `def run_strategy_analysis( symbol: str, period: str = "1d", mode: str = "swing", df: Optional[Any] = None, market: Optional[str] = None, spy_df: Optional[Any] = None, qqq_df: Optional[Any] = None, iwm_df: Optional[Any] = None, ) -> Dict[str, Any]`
- + `generate_wave_chart_html` · function · L2093-L2136 — `def generate_wave_chart_html(symbol: str, period: str = "1d", df: Optional[Any] = None) -> str`

### stage_one/backend/strategy_core/__init__.py

共 0 个符号 · 被依赖 0 · 依赖外部 0

- （该文件无可提取符号）

### stage_one/backend/strategy_core/pa_engine.py

共 50 个符号 · 被依赖 0 · 依赖外部 0

- + `DataUnavailable` · class · L67-L68 — `class DataUnavailable(RuntimeError)`
- + `reset_fetch_state` · function · L76-L81 — `def reset_fetch_state() -> None`
- + `median_bar_range` · function · L84-L93 — `def median_bar_range(df: pd.DataFrame, n: int = 14) -> float`
- + `fetch_klines` · function · L114-L170 — `def fetch_klines(ticker: str, interval: str, period: str, prepost: bool = False, retries: int = FETCH_RETRIES) -> pd.DataFrame`
- + `extract_swings` · function · L177-L271 — `def extract_swings(df: pd.DataFrame, order: int = 5, confirmed_only: bool = True, min_swing_k: float = 1.5) -> list`
-   `_prune` · function · L224-L241 — `def _prune(min_k: float) -> list`
-   `_split_swings` · function · L274-L280 — `def _split_swings(df: pd.DataFrame, order: int)`
-   `_fmt_pending` · function · L283-L289 — `def _fmt_pending(pend: list) -> str`
-   `_determine_dow_phase` · function · L292-L309 — `def _determine_dow_phase(swings: list) -> str`
- + `detect_mss` · function · L316-L434 — `def detect_mss(swings: list, df: pd.DataFrame = None, buffer_k: float = 0.0, vol_mult: float = 1.2) -> list`
- + `detect_consolidation_box` · function · L441-L585 — `def detect_consolidation_box(df: pd.DataFrame, swings: list = None, lookback_bars: int = 40, min_bars: int = 15, height_pct_min: float = 0.03, height_pct_max: float = 0.35, containment_pct: float = 0.70, buffer_k: float = 0.0) -> dict`
- + `detect_price_channel` · function · L588-L727 — `def detect_price_channel(df: pd.DataFrame, swings: list = None, lookback_bars: int = 30, std_mult: float = 2.0) -> dict`
-   `_fmt_price` · function · L734-L736 — `def _fmt_price(value) -> str`
- + `check_dow_indices` · function · L739-L769 — `def check_dow_indices(mode: str, indices: list = None) -> dict`
-   `_to_exchange_tz` · function · L776-L788 — `def _to_exchange_tz(df: pd.DataFrame)`
-   `_infer_bar_minutes` · function · L791-L799 — `def _infer_bar_minutes(df: pd.DataFrame) -> int`
-   `_prev_session_bar` · function · L802-L813 — `def _prev_session_bar(df_daily: pd.DataFrame, df_intraday: pd.DataFrame)`
- + `calc_fibonacci_and_levels` · function · L816-L900 — `def calc_fibonacci_and_levels(swings: list, df_daily: pd.DataFrame = None, df_intraday: pd.DataFrame = None) -> dict`
-   `_match_fib_ratio` · function · L907-L923 — `def _match_fib_ratio(ratio: float) -> str`
- + `calc_multi_leg_fib` · function · L926-L1006 — `def calc_multi_leg_fib(swings: list, tolerance_pct: float = 0.01) -> dict`
-   `_flush` · function · L973-L987 — `def _flush(group)`
-   `_resolve_swing_idx` · function · L1017-L1033 — `def _resolve_swing_idx(swing: dict, df: pd.DataFrame = None) -> int | None`
-   `_detect_wave5_variants_and_volume` · function · L1036-L1081 — `def _detect_wave5_variants_and_volume(cand: list, direction: int, df: pd.DataFrame = None, rule1_passed: bool = True, rule2_passed: bool = True, rule3_passed: bool = True) -> dict`
- + `classify_wave_pattern` · function · L1084-L1569 — `def classify_wave_pattern(swings: list, df: pd.DataFrame = None, allow_shallow_w4: bool = False) -> dict`
-   `_check_impulse_5` · function · L1106-L1362 — `def _check_impulse_5(cand)`
- + `evaluate_wave_position` · function · L1572-L1744 — `def evaluate_wave_position(swings: list, df: pd.DataFrame = None, current_price: float = None, allow_shallow_w4: bool = False) -> dict`
- + `classify_corrective_subtypes` · function · L1747-L1893 — `def classify_corrective_subtypes(swings: list) -> dict`
- + `calc_time_windows` · function · L1896-L1961 — `def calc_time_windows(swings: list, df: pd.DataFrame) -> dict`
-   `_match_seq` · function · L1916-L1921 — `def _match_seq(val: int, seq: tuple) -> int | None`
- + `calc_elliott_channel` · function · L1964-L2067 — `def calc_elliott_channel(swings: list, df: pd.DataFrame, wp: dict = None, use_log: bool = True) -> dict`
-   `_project_line` · function · L1984-L1992 — `def _project_line(i1: int, p1: float, i2: int, p2: float, target_i: int) -> float | None`
-   `_project_parallel` · function · L1994-L2001 — `def _project_parallel(i1: int, p1: float, i2: int, p2: float, i_anchor: int, p_anchor: float, target_i: int) -> float | None`
- + `generate_wave_counts` · function · L2070-L2129 — `def generate_wave_counts(swings: list, df: pd.DataFrame = None, wp: dict = None) -> dict`
- + `detect_gaps` · function · L2136-L2189 — `def detect_gaps(df: pd.DataFrame, min_gap_pct: float = 0.008) -> list`
- + `scan_price_action` · function · L2196-L2339 — `def scan_price_action(df: pd.DataFrame, key_levels: list = None, bar_rng: float = None, require_location: bool = True, sweep_min_tier: int = TIER_MIN_FOR_SWEEP) -> list`
- + `gate_ok` · function · L2264-L2270 — `def gate_ok(price_probe)`
- + `analyze_volume` · function · L2346-L2392 — `def analyze_volume(df: pd.DataFrame, lookback: int = 20, recent: int = 5) -> dict`
- + `analyze_dow_volume` · function · L2395-L2506 — `def analyze_dow_volume(df: pd.DataFrame, dow_bias: int = 0, lookback: int = 20) -> dict`
- + `dow_bias_count` · function · L2513-L2525 — `def dow_bias_count(swings: list) -> int`
- + `dow_bias` · function · L2528-L2600 — `def dow_bias(swings: list, df: pd.DataFrame = None, buffer_k: float = 0.0) -> int`
- + `build_key_levels` · function · L2604-L2659 — `def build_key_levels(levels: dict, swings_mtf: list, swings_ltf: list, gaps: list, clusters: list, bar_rng: float) -> list`
- + `add` · function · L2615-L2621 — `def add(price, kind, src)`
-   `_is_last_bar_open` · function · L2662-L2676 — `def _is_last_bar_open(df: pd.DataFrame, now=None) -> bool`
- + `build_trade_plan` · function · L2679-L2967 — `def build_trade_plan(mode: str, price: float, swings_mtf: list, swings_ltf: list, key_levels: list, levels: dict, bar_rng: float, bias_htf: int, bias_mtf: int, equity: float = None, risk_pct: float = DEFAULT_RISK_PCT, min_rr: float = MIN_RR, market_dow: dict = None, df_mtf: pd.DataFrame = None, target_symbol: str = None, target_sector: str = None, allow_decoupling: bool = False, micro_conviction: str = None, use_trend_gate: bool = False) -> dict`
-   `_print_trade_plan` · function · L2970-L3044 — `def _print_trade_plan(plan: dict) -> None`
- + `side_cn` · function · L2972-L2973 — `def side_cn(s)`
-   `_write_json` · function · L3047-L3056 — `def _write_json(path: str, payload: dict) -> bool`
- + `analyze_single_ticker` · function · L3063-L3362 — `def analyze_single_ticker(ticker: str, mode: str, market_dow: dict = None, is_watchlist: bool = False, json_out: str = None, equity: float = None, risk_pct: float = DEFAULT_RISK_PCT)`
-   `_print_run_summary` · function · L3365-L3389 — `def _print_run_summary(results: dict) -> int`
- + `main` · function · L3392-L3470 — `def main() -> int`

### stage_one/backend/strategy_core/plot_wave_chart.py

共 7 个符号 · 被依赖 1 · 依赖外部 0

- + `load_ohlcv` · function · L36-L48 — `def load_ohlcv(csv_path: Path) -> pd.DataFrame`
-   `_resolve_wave_annotations` · function · L51-L113 — `def _resolve_wave_annotations( sub: pd.DataFrame, swings: list[dict], wave_pattern: dict, ) -> list[dict]`
-   `_future_bar_timestamp` · function · L116-L120 — `def _future_bar_timestamp(last_dt: pd.Timestamp, offset_bars: int, has_weekends: bool) -> pd.Timestamp`
-   `_add_structure_and_sr_overlays` · function · L123-L252 — `def _add_structure_and_sr_overlays( fig: go.Figure, sub: pd.DataFrame, swings: list[dict], x_end: pd.Timestamp, ) -> tuple[dict, dict, list[dict], list[dict]]`
-   `_build_summary_lines` · function · L255-L319 — `def _build_summary_lines( wave_pattern: dict, result: dict, ema_last: float, current_price: float, bars_since: int, next_lucas: int | None, next_fib: int | None, chan: dict | None = None, gaps: list[dict] | None = None, fib_levels: dict | None = None, ) -> list[str]`
- + `plot_wave_chart` · function · L322-L676 — `def plot_wave_chart( ticker: str = "GOOGL", csv_path: Path | None = None, output_path: Path | None = None, lookback_bars: int = 120, include_plotlyjs: str | bool = "cdn", ) -> Path`
- + `main` · function · L679-L696 — `def main() -> None`

### stage_one/backend/strategy_core/strategy_crypto.py

共 10 个符号 · 被依赖 0 · 依赖外部 0

- + `is_crypto_black_swan` · function · L72-L87 — `def is_crypto_black_swan(date_val) -> bool`
- + `trade_overlaps_black_swan` · function · L90-L104 — `def trade_overlaps_black_swan(entry_date, exit_date) -> bool`
- + `is_crypto_asset` · function · L107-L139 — `def is_crypto_asset(ticker: str) -> bool`
- + `extract_crypto_levels` · function · L146-L249 — `def extract_crypto_levels(df: pd.DataFrame, t: int, side: int, swings: list, buffer_k: float = CRYPTO_STOP_BUFFER_K) -> dict`
- + `detect_crypto_trigger_on_bar` · function · L256-L352 — `def detect_crypto_trigger_on_bar(df: pd.DataFrame, k: int, side: int, key_level: float, bar_rng: float, tol_k: float = 0.6) -> dict`
- + `check_recent_crypto_2b_sweep` · function · L355-L415 — `def check_recent_crypto_2b_sweep(df: pd.DataFrame, side: int, swings: list, bar_rng: float = None, lookback: int = 5) -> dict`
-   `_weekly_prefix` · function · L422-L429 — `def _weekly_prefix(df: pd.DataFrame, t: int) -> pd.DataFrame`
- + `check_crypto_primary_trend` · function · L432-L466 — `def check_crypto_primary_trend(df: pd.DataFrame, t: int, side: int, weekly_df: pd.DataFrame = None) -> dict`
- + `simulate_crypto_trigger_entry` · function · L469-L536 — `def simulate_crypto_trigger_entry(df: pd.DataFrame, t: int, side: int, key_level: float, bar_rng: float, structural_stop: float, max_wait_bars: int = CRYPTO_MAX_WAIT_BARS, use_trend_gate: bool = True, disallow_short_engulfing: bool = True, weekly_df: pd.DataFrame = None) -> dict`
- + `simulate_crypto_trade` · function · L543-L840 — `def simulate_crypto_trade(df: pd.DataFrame, entry_t: int, entry_price: float, side: int, stop_price: float, tp1_price: float = None, tp2_price: float = None, impulse_leg: float = None, max_hold_bars: int = CRYPTO_MAX_HOLD_BARS, min_rr: float = CRYPTO_MIN_RR) -> dict`

### stage_one/backend/strategy_core/strategy_day.py

共 11 个符号 · 被依赖 0 · 依赖外部 0

- + `normalize_intraday_tz` · function · L53-L71 — `def normalize_intraday_tz(df: pd.DataFrame) -> pd.DataFrame`
- + `split_intraday_sessions` · function · L74-L86 — `def split_intraday_sessions(df: pd.DataFrame) -> dict`
- + `extract_session_key_levels` · function · L93-L142 — `def extract_session_key_levels(df_session: pd.DataFrame, prev_session_df: pd.DataFrame = None) -> dict`
- + `detect_intraday_2b_sweep` · function · L149-L228 — `def detect_intraday_2b_sweep(df: pd.DataFrame, k: int, level: float, level_name: str, bar_rng: float, buffer_k: float = DEFAULT_DAY_STOP_BUFFER_K, level_type: str = "auto") -> dict`
- + `detect_orb_breakout_retest` · function · L231-L280 — `def detect_orb_breakout_retest(df: pd.DataFrame, k: int, orh: float, orl: float, bar_rng: float, buffer_k: float = DEFAULT_DAY_STOP_BUFFER_K) -> dict`
- + `simulate_day_trade` · function · L287-L545 — `def simulate_day_trade(df: pd.DataFrame, entry_t: int, entry_price: float, side: int, stop_price: float, tp_price: float, tp2_price: float = None, min_rr: float = DEFAULT_DAY_MIN_RR, slippage_bps: float = DEFAULT_SLIPPAGE_BPS, commission_bps: float = DEFAULT_COMMISSION_BPS, use_be_at_1_5r: bool = True, eod_exit_time: dtime = DAY_EOD_EXIT_TIME, max_hold_bars: int = 78, pattern: str = None, htf_bias: int = None, market_dow: dict = None, **kwargs) -> dict`
- + `extract_intraday_htf_bias` · function · L548-L579 — `def extract_intraday_htf_bias(df_5m: pd.DataFrame, cutoff_ts: pd.Timestamp = None) -> int`
- + `enumerate_day_events` · function · L586-L801 — `def enumerate_day_events(df: pd.DataFrame, strategy_type: str = "day_combined", min_rr: float = DEFAULT_DAY_MIN_RR, buffer_k: float = DEFAULT_DAY_STOP_BUFFER_K, avoid_overlap: bool = True, use_htf_filter: bool = True, slippage_bps: float = DEFAULT_SLIPPAGE_BPS, commission_bps: float = DEFAULT_COMMISSION_BPS, market_data: dict = None, df_1h: pd.DataFrame = None, **kwargs) -> list`
- + `synthetic_intraday_days` · function · L808-L864 — `def synthetic_intraday_days(n_days: int = 15, seed: int = 42, base_price: float = 150.0) -> pd.DataFrame`
- + `summarize_day_trades` · function · L871-L948 — `def summarize_day_trades(trades: list, label: str = "") -> dict`
- + `sub_stats` · function · L912-L924 — `def sub_stats(sub_df)`

### stage_one/backend/strategy_core/strategy_layer.py

共 13 个符号 · 被依赖 0 · 依赖外部 0

- + `is_stock_black_swan` · function · L71-L87 — `def is_stock_black_swan(date_val) -> bool`
- + `trade_overlaps_stock_black_swan` · function · L90-L106 — `def trade_overlaps_stock_black_swan(entry_date, exit_date) -> bool`
- + `extract_breakout_levels` · function · L113-L190 — `def extract_breakout_levels(df: pd.DataFrame, t: int, side: int, swings: list, buffer_k: float = 0.0) -> dict`
- + `verify_primary_trend_gate` · function · L226-L316 — `def verify_primary_trend_gate(df: pd.DataFrame, side: int, ema_period: int = 200, t: int = None, ema_series: pd.Series = None) -> dict`
- + `verify_market_dow_gate` · function · L319-L622 — `def verify_market_dow_gate(market_dow: dict = None, target_symbol_or_side = None, target_sector: str = None, side: int = None, allow_decoupling: bool = False, micro_conviction: str = None, target_symbol: str = None, market_data: dict = None, **kwargs) -> dict`
- + `verify_macro_short_gate` · function · L625-L692 — `def verify_macro_short_gate(market_dow: dict = None, df: pd.DataFrame = None, t: int = None, micro_conviction: str = None, allow_decoupling: bool = False, target_symbol: str = None, ema_series: pd.Series = None, **kwargs) -> dict`
- + `verify_box_gate` · function · L695-L738 — `def verify_box_gate(df: pd.DataFrame, t: int, side: int, swings: list = None) -> dict`
- + `verify_channel_gate` · function · L741-L784 — `def verify_channel_gate(df: pd.DataFrame, t: int, side: int, swings: list = None) -> dict`
- + `simulate_limit_order` · function · L791-L931 — `def simulate_limit_order(df: pd.DataFrame, t: int, side: int, limit_price: float, stop_price: float, max_wait_bars: int = DEFAULT_MAX_WAIT_BARS, volume_filter: bool = False) -> dict`
- + `detect_trigger_on_bar` · function · L938-L1019 — `def detect_trigger_on_bar(df: pd.DataFrame, k: int, side: int, key_level: float, bar_rng: float, tol_k: float = 0.5) -> dict`
- + `simulate_trigger_entry` · function · L1022-L1070 — `def simulate_trigger_entry(df: pd.DataFrame, t: int, side: int, key_level: float, bar_rng: float, structural_stop: float, max_wait_bars: int = DEFAULT_MAX_WAIT_BARS) -> dict`
- + `simulate_strategy_trade` · function · L1077-L1515 — `def simulate_strategy_trade(df: pd.DataFrame, entry_t: int, entry_price: float, side: int, stop_price: float, tp_price: float, max_hold_bars: int = DEFAULT_MAX_HOLD_BARS, min_rr: float = DEFAULT_MIN_RR, market_dow: dict = None, wave_status: str = None, box_gate: dict = None, channel_gate: dict = None, use_channel_tp: bool = False, channel_info: dict = None, use_tiered_tp: bool = False, tp2_price: float = None, impulse_leg: float = None, trend_gate: dict = None, use_trend_gate: bool = False, target_symbol: str = None, target_sector: str = None, allow_decoupling: bool = False, micro_conviction: str = None, ema_series: pd.Series = None) -> dict`
- + `calc_entry_horizon_stats` · function · L1522-L1547 — `def calc_entry_horizon_stats(df: pd.DataFrame, entry_t: int, entry_price: float, side: int, h: int) -> dict`

### stage_one/backend/symbols.py

共 5 个符号 · 被依赖 28 · 依赖外部 0

- + `norm_market_prefix` · function · L23-L29 — `def norm_market_prefix(sym: str) -> str`
-   `_strip_crypto_us_prefix` · function · L32-L39 — `def _strip_crypto_us_prefix(clean: str) -> str`
- + `normalize_symbol` · function · L42-L85 — `def normalize_symbol(raw: str, market: Optional[str] = None) -> Optional[str]`
- + `market_of` · function · L88-L120 — `def market_of(symbol: str, default_us: bool = False) -> Optional[str]`
- + `strip_prefix` · function · L123-L129 — `def strip_prefix(symbol: str) -> str`

### stage_one/backend/test_adjustment.py

共 1 个符号 · 被依赖 0 · 依赖外部 2

- + `check` · function · L13-L20 — `def check(name, cond)`

### stage_one/backend/test_crypto_features.py

共 22 个符号 · 被依赖 0 · 依赖外部 20

- + `TestCryptoFeatures` · class · L23-L345 — `class TestCryptoFeatures(unittest.TestCase)`
- + `setUp` · method · L25-L26 — `def setUp(self)`
- + `test_to_yahoo_ticker_crypto_variants` · method · L31-L66 — `def test_to_yahoo_ticker_crypto_variants(self)`
- + `test_to_yahoo_ticker_non_crypto` · method · L68-L71 — `def test_to_yahoo_ticker_non_crypto(self)`
- + `test_normalize_symbol_crypto` · method · L76-L113 — `def test_normalize_symbol_crypto(self)`
- + `test_normalize_symbol_stocks_and_futures` · method · L115-L118 — `def test_normalize_symbol_stocks_and_futures(self)`
- + `test_market_of_crypto` · method · L120-L133 — `def test_market_of_crypto(self)`
- + `test_market_labels_and_config` · method · L135-L142 — `def test_market_labels_and_config(self)`
- + `test_search_crypto_aliases` · method · L147-L175 — `def test_search_crypto_aliases(self)`
- + `test_us_stock_prefix_not_colliding_with_crypto` · method · L177-L182 — `def test_us_stock_prefix_not_colliding_with_crypto(self)`
- + `test_data_provider_manager_crypto_routes_only_yahoo` · method · L187-L216 — `def test_data_provider_manager_crypto_routes_only_yahoo(self)`
- + `test_yahoo_crypto_quote_provider_parsing` · method · L221-L269 — `def test_yahoo_crypto_quote_provider_parsing(self)`
- + `test_tencent_quote_provider_routes_crypto` · method · L274-L291 — `def test_tencent_quote_provider_routes_crypto(self)`
- + `test_yahoo_crypto_daily_uses_10y_range` · method · L296-L332 — `def test_yahoo_crypto_daily_uses_10y_range(self)`
- + `test_live_get_klines_btc_usdt_daily` · method · L334-L345 — `def test_live_get_klines_btc_usdt_daily(self)`
- + `TestCryptoDowntrendAndRRGates` · class · L348-L548 — `class TestCryptoDowntrendAndRRGates(unittest.TestCase)`
- + `setUp` · method · L360-L380 — `def setUp(self)`
- + `test_btc_downtrend_stop_loss_not_taking_ancient_high` · method · L382-L404 — `def test_btc_downtrend_stop_loss_not_taking_ancient_high(self)`
- + `test_btc_downtrend_tp1_uses_forward_fibonacci_projection` · method · L406-L426 — `def test_btc_downtrend_tp1_uses_forward_fibonacci_projection(self)`
- + `test_btc_downtrend_rr_calculation_accuracy` · method · L428-L454 — `def test_btc_downtrend_rr_calculation_accuracy(self)`
- + `test_rr_gate_consistency_no_poor_playbook_exposed` · method · L456-L515 — `def test_rr_gate_consistency_no_poor_playbook_exposed(self)`
- + `test_anti_chase_and_honest_structural_targets` · method · L517-L548 — `def test_anti_chase_and_honest_structural_targets(self)`

### stage_one/backend/test_dow_elliott_refactor.py

共 9 个符号 · 被依赖 0 · 依赖外部 6

- + `TestDowElliottStrategyRefactor` · class · L19-L172 — `class TestDowElliottStrategyRefactor(unittest.TestCase)`
- + `setUp` · method · L20-L45 — `def setUp(self): # 构造标准的 60 根多头波浪走势数据`
- + `test_structured_fields_presence` · method · L47-L60 — `def test_structured_fields_presence(self)`
- + `test_multi_tier_stop_loss_anchor_pool` · method · L62-L77 — `def test_multi_tier_stop_loss_anchor_pool(self)`
- + `test_take_profit_separates_unconfirmed_realtime_extremes` · method · L79-L96 — `def test_take_profit_separates_unconfirmed_realtime_extremes(self)`
- + `test_condition_playbook_tight_retracement_and_rr_gate` · method · L98-L113 — `def test_condition_playbook_tight_retracement_and_rr_gate(self)`
- + `test_crypto_routing_and_atr_anti_wick_buffer` · method · L115-L133 — `def test_crypto_routing_and_atr_anti_wick_buffer(self)`
- + `test_crypto_shallow_wave4_piercing_tolerance` · method · L135-L154 — `def test_crypto_shallow_wave4_piercing_tolerance(self)`
- + `test_dow_volume_status_analysis` · method · L156-L172 — `def test_dow_volume_status_analysis(self)`

### stage_one/backend/test_dow_elliott_us_strategy.py

共 12 个符号 · 被依赖 0 · 依赖外部 11

- + `TestDowElliottUSStrategy` · class · L18-L345 — `class TestDowElliottUSStrategy(unittest.TestCase)`
- + `setUp` · method · L19-L82 — `def setUp(self): # 基础测试日期序列`
- + `test_dow_macro_filter_mutual_verification_pass` · method · L84-L100 — `def test_dow_macro_filter_mutual_verification_pass(self)`
- + `test_dow_macro_filter_divergence_blocks_long` · method · L102-L123 — `def test_dow_macro_filter_divergence_blocks_long(self)`
- + `test_wave2_buy_point_setup_and_iron_rule` · method · L125-L154 — `def test_wave2_buy_point_setup_and_iron_rule(self)`
- + `test_wave4_buy_point_setup_and_rule` · method · L156-L181 — `def test_wave4_buy_point_setup_and_rule(self)`
- + `test_sell_stages_high_selling_ladder` · method · L183-L211 — `def test_sell_stages_high_selling_ladder(self)`
- + `test_condition_playbook_wave_setups` · method · L213-L234 — `def test_condition_playbook_wave_setups(self)`
- + `test_us_bear_market_defense` · method · L236-L259 — `def test_us_bear_market_defense(self)`
- + `test_cn_stock_skips_us_dow_macro_filter` · method · L261-L274 — `def test_cn_stock_skips_us_dow_macro_filter(self)`
- + `test_channel_2_4_breakdown_triggers_escape_and_blocks_long` · method · L276-L306 — `def test_channel_2_4_breakdown_triggers_escape_and_blocks_long(self)`
- + `test_wave4_conditional_playbook_fib_levels` · method · L308-L345 — `def test_wave4_conditional_playbook_fib_levels(self)`

### stage_one/backend/test_endpoints.py

共 16 个符号 · 被依赖 0 · 依赖外部 12

- + `TestStockBackend` · class · L25-L275 — `class TestStockBackend(unittest.TestCase)`
- + `setUp` · method · L27-L45 — `def setUp(self)`
- + `test_search_endpoint_pool` · method · L47-L51 — `def test_search_endpoint_pool(self)`
- + `test_search_endpoint_by_keyword` · method · L53-L62 — `def test_search_endpoint_by_keyword(self)`
- + `test_search_endpoint_custom_code` · method · L64-L74 — `def test_search_endpoint_custom_code(self)`
- + `test_periods_endpoint` · method · L76-L84 — `def test_periods_endpoint(self)`
- + `test_klines_endpoint` · method · L86-L96 — `def test_klines_endpoint(self)`
- + `test_klines_multi_period` · method · L98-L113 — `def test_klines_multi_period(self)`
- + `test_klines_invalid_period` · method · L115-L118 — `def test_klines_invalid_period(self)`
- + `test_analysis_endpoint` · method · L120-L138 — `def test_analysis_endpoint(self)`
- + `test_analysis_multi_period` · method · L140-L155 — `def test_analysis_multi_period(self)`
- + `test_range_stats_calculation` · method · L157-L172 — `def test_range_stats_calculation(self)`
- + `test_sr_levels_multi_period` · method · L174-L211 — `def test_sr_levels_multi_period(self)`
- + `test_data_provider_manager` · method · L213-L218 — `def test_data_provider_manager(self)`
- + `test_ash_and_hk_disabled` · method · L220-L275 — `def test_ash_and_hk_disabled(self)`
- + `np_sin` · function · L278-L281 — `def np_sin(x)`

### stage_one/backend/test_optimization_and_refactor.py

共 18 个符号 · 被依赖 0 · 依赖外部 6

- + `TestOptimizationAndRefactor` · class · L22-L349 — `class TestOptimizationAndRefactor(unittest.TestCase)`
- + `test_extract_swings_anti_noise_filter` · method · L24-L49 — `def test_extract_swings_anti_noise_filter(self)`
- + `test_extract_swings_outside_bar_order` · method · L51-L75 — `def test_extract_swings_outside_bar_order(self)`
- + `test_extract_swings_dow_label_no_forced_ll` · method · L77-L103 — `def test_extract_swings_dow_label_no_forced_ll(self)`
- + `test_detect_mss_indentation_historical_events` · method · L105-L124 — `def test_detect_mss_indentation_historical_events(self)`
- + `test_detect_gaps_vectorized` · method · L126-L141 — `def test_detect_gaps_vectorized(self)`
- + `test_calculate_sr_levels_optimized` · method · L143-L164 — `def test_calculate_sr_levels_optimized(self)`
- + `test_verify_primary_trend_gate_ema_series_equivalence` · method · L166-L185 — `def test_verify_primary_trend_gate_ema_series_equivalence(self)`
- + `test_sr_levels_edge_cases` · method · L187-L192 — `def test_sr_levels_edge_cases(self)`
- + `test_strategy_crypto_weekly_precomputed` · method · L194-L207 — `def test_strategy_crypto_weekly_precomputed(self)`
- + `test_calc_elliott_channel_log_vs_linear` · method · L209-L237 — `def test_calc_elliott_channel_log_vs_linear(self)`
- + `test_detect_wave5_variants_truncated` · method · L239-L255 — `def test_detect_wave5_variants_truncated(self)`
- + `test_detect_wave5_variants_ending_diagonal` · method · L257-L273 — `def test_detect_wave5_variants_ending_diagonal(self)`
- + `test_detect_wave5_volume_divergence` · method · L275-L293 — `def test_detect_wave5_volume_divergence(self)`
- + `test_classify_corrective_running_flat_warning` · method · L295-L306 — `def test_classify_corrective_running_flat_warning(self)`
- + `test_dow_market_iwm_breadth_divergence` · method · L308-L321 — `def test_dow_market_iwm_breadth_divergence(self)`
- + `test_weekly_daily_fractal_resonance` · method · L323-L338 — `def test_weekly_daily_fractal_resonance(self)`
- + `test_main_ws_broadcast_channels` · method · L340-L349 — `def test_main_ws_broadcast_channels(self)`

### stage_one/backend/test_pagination.py

共 1 个符号 · 被依赖 0 · 依赖外部 0

- + `fetch_page` · function · L10-L26 — `def fetch_page(end: str, count: int = 2000)`

### stage_one/backend/test_resample.py

共 6 个符号 · 被依赖 0 · 依赖外部 7

-   `_make_daily` · function · L15-L36 — `def _make_daily(start_year=2020, n_years=3, base=100.0, drift=0.0)`
- + `test_resample_quarterly` · function · L39-L49 — `def test_resample_quarterly()`
- + `test_resample_semiannual` · function · L52-L56 — `def test_resample_semiannual()`
- + `test_resample_yearly` · function · L59-L65 — `def test_resample_yearly()`
- + `test_forward_adjust_before_resample_continuous` · function · L68-L91 — `def test_forward_adjust_before_resample_continuous()`
- + `test_validate_rejects_aggregated_as_daily` · function · L94-L106 — `def test_validate_rejects_aggregated_as_daily()`

### stage_one/backend/test_strategy_wave_channel.py

共 8 个符号 · 被依赖 0 · 依赖外部 5

- + `TestWaveAndChannelAnnotations` · class · L14-L144 — `class TestWaveAndChannelAnnotations(unittest.TestCase)`
- + `setUp` · method · L15-L32 — `def setUp(self)`
- + `test_run_strategy_analysis_returns_wave_and_channel` · method · L34-L82 — `def test_run_strategy_analysis_returns_wave_and_channel(self)`
- + `test_api_control_strategy_endpoint` · method · L84-L98 — `def test_api_control_strategy_endpoint(self)`
- + `test_api_strategy_html_endpoint` · method · L100-L106 — `def test_api_strategy_html_endpoint(self)`
- + `test_edge_cases_empty_or_small_df` · method · L108-L113 — `def test_edge_cases_empty_or_small_df(self)`
- + `test_control_strategy_with_frontend_klines` · method · L115-L133 — `def test_control_strategy_with_frontend_klines(self)`
- + `test_normalize_df_with_records_list` · method · L135-L144 — `def test_normalize_df_with_records_list(self)`

### stage_one/backend/test_transformation_new.py

共 7 个符号 · 被依赖 0 · 依赖外部 4

- + `TestStockVisionTransformation` · class · L21-L192 — `class TestStockVisionTransformation(unittest.TestCase)`
- + `setUpClass` · method · L23-L24 — `def setUpClass(cls)`
- + `test_supported_periods_expansion` · method · L26-L30 — `def test_supported_periods_expansion(self)`
- + `test_fuzzy_search_matching_and_no_phantom_tickers` · method · L32-L57 — `def test_fuzzy_search_matching_and_no_phantom_tickers(self)`
- + `test_strategy_adapter_pa_matrix` · method · L59-L123 — `def test_strategy_adapter_pa_matrix(self)`
- + `test_control_endpoints_crud` · method · L125-L176 — `def test_control_endpoints_crud(self)`
- + `test_mcp_server_tools_registered` · method · L178-L192 — `def test_mcp_server_tools_registered(self)`

### stage_one/backend/test_triggers_and_turning_dates.py

共 4 个符号 · 被依赖 0 · 依赖外部 3

- + `TestTriggersAndTurningDates` · class · L13-L104 — `class TestTriggersAndTurningDates(unittest.TestCase)`
- + `setUp` · method · L14-L43 — `def setUp(self)`
- + `test_bear_market_triggers_and_direction` · method · L45-L88 — `def test_bear_market_triggers_and_direction(self)`
- + `test_bull_market_triggers` · method · L90-L104 — `def test_bull_market_triggers(self)`

### stage_one/backend/test_validate.py

共 8 个符号 · 被依赖 0 · 依赖外部 2

- + `make_df` · function · L12-L20 — `def make_df(dates)`
- + `quarterly_dates` · function · L23-L34 — `def quarterly_dates(n=60, start=date(2010, 1, 1))`
- + `daily_dates` · function · L37-L45 — `def daily_dates(n=400, start=date(2023, 1, 2))`
- + `weekly_dates` · function · L48-L56 — `def weekly_dates(n=200, start=date(2015, 1, 2))`
- + `monthly_dates` · function · L59-L75 — `def monthly_dates(n=150, start=date(2010, 1, 31))`
- + `semiannual_dates` · function · L78-L85 — `def semiannual_dates(n=10, start=date(2010, 1, 1))`
- + `annual_dates` · function · L88-L95 — `def annual_dates(n=10, start=date(2010, 1, 1))`
- + `check` · function · L98-L101 — `def check(name, got, expect)`

### stage_one/backend/time_window.py

共 5 个符号 · 被依赖 2 · 依赖外部 0

- + `add_period_offset` · function · L16-L39 — `def add_period_offset(start_date_str: str, bars_offset: int, period: str = "1d", is_crypto: bool = False) -> str`
- + `add_calendar_offset` · function · L42-L53 — `def add_calendar_offset(start_date_str: str, days_offset: int, is_crypto: bool = False) -> str`
- + `trading_days_between` · function · L56-L71 — `def trading_days_between(d1_str: str, d2_str: str, is_crypto: bool = False) -> int`
- + `predict_turn_windows` · function · L74-L334 — `def predict_turn_windows( df: pd.DataFrame, swings: List[Dict[str, Any]], wave_points: Optional[Dict[str, Any]] = None, period: str = "1d", lookahead_bars: int = 45, lookback_bars: int = 3, is_crypto: bool = False, ) -> Dict[str, Any]`
-   `_get_bar_date` · function · L97-L103 — `def _get_bar_date(idx: int) -> str`

### stage_one/frontend/postcss.config.js

共 0 个符号 · 被依赖 0 · 依赖外部 0

- （该文件无可提取符号）

### stage_one/frontend/src/App.vue

共 48 个符号 · 被依赖 1 · 依赖外部 60

-   `value` · method · L844-L844 — `get value()`
-   `selectWatchlist` · function · L866-L874 — `selectWatchlist = (sym: string)`
-   `navBack` · function · L911-L917 — `navBack = ()`
-   `navForward` · function · L919-L925 — `navForward = ()`
-   `refreshCurrent` · function · L927-L931 — `refreshCurrent = ()`
-   `selectSuggestion` · function · L933-L936 — `selectSuggestion = (symbol: string)`
-   `resolveSymbol` · function · L938-L947 — `async function resolveSymbol(raw: string): Promise<string>`
-   `handleSearch` · function · L949-L955 — `handleSearch = async ()`
-   `changePeriod` · function · L957-L970 — `changePeriod = (period: Period)`
-   `detectBackend` · function · L975-L996 — `async function detectBackend(): Promise<boolean>`
-   `retryConnection` · function · L998-L1007 — `async function retryConnection()`
-   `handleRunStrategy` · function · L1010-L1054 — `handleRunStrategy = async (mode: string = 'swing', isManual: boolean = false)`
-   `handleClearStrategy` · function · L1056-L1068 — `handleClearStrategy = ()`
-   `onOpenChart` · method · L1072-L1079 — `onOpenChart(symbol, period)`
-   `onAddMarkers` · method · L1080-L1083 — `onAddMarkers(markers, sym)`
-   `onDrawLines` · method · L1084-L1087 — `onDrawLines(lines, sym)`
-   `onDrawBoxes` · method · L1088-L1091 — `onDrawBoxes(boxes, sym)`
-   `onDrawChannelLines` · method · L1092-L1095 — `onDrawChannelLines(channelLines, sym)`
-   `onDrawWaveLines` · method · L1096-L1099 — `onDrawWaveLines(waveLines, sym)`
-   `onDrawTimeLines` · method · L1100-L1103 — `onDrawTimeLines(timeLines, sym)`
-   `onDrawFibLines` · method · L1104-L1107 — `onDrawFibLines(fibLines, sym)`
-   `onDrawGapBoxes` · method · L1108-L1111 — `onDrawGapBoxes(gapBoxes, sym)`
-   `onDrawEma200` · method · L1112-L1115 — `onDrawEma200(ema200Data, sym)`
-   `onClearAnnotations` · method · L1116-L1128 — `onClearAnnotations(kind, sym)`
-   `onCaptureChart` · method · L1130-L1139 — `onCaptureChart()`
-   `toChartTime` · function · L1143-L1143 — `toChartTime = (timeStr: any): any`
-   `applyChartTheme` · function · L1145-L1165 — `applyChartTheme = (isDark: boolean)`
-   `toggleDarkMode` · function · L1167-L1172 — `toggleDarkMode = ()`
-   `initDarkMode` · function · L1174-L1179 — `initDarkMode = ()`
-   `triggerCreateGroup` · function · L1194-L1198 — `triggerCreateGroup = ()`
-   `triggerManageGroups` · function · L1200-L1203 — `triggerManageGroups = ()`
-   `handleCreateGroupSubmit` · function · L1205-L1209 — `handleCreateGroupSubmit = ()`
-   `confirmRename` · function · L1211-L1215 — `confirmRename = (id: string)`
-   `handleModalSearchInput` · function · L1218-L1236 — `handleModalSearchInput = ()`
-   `handleModalSearchSelect` · function · L1238-L1244 — `handleModalSearchSelect = (sym: string)`
-   `toggleLeftSidebar` · function · L1250-L1258 — `toggleLeftSidebar = ()`
-   `toggleRightSidebar` · function · L1260-L1268 — `toggleRightSidebar = ()`
-   `syncChartSize` · function · L1275-L1279 — `syncChartSize = ()`
-   `createColumnResizer` · function · L1281-L1318 — `createColumnResizer = (getStartWidth: () => number, setWidth: (w: number) => void, sign: 1 | -1)`
-   `handleMouseMove` · function · L1291-L1302 — `handleMouseMove = (moveEvent: MouseEvent)`
-   `cleanup` · function · L1304-L1313 — `cleanup = ()`
-   `formatVolumeNum` · function · L1341-L1346 — `formatVolumeNum = (vol: number): string`
-   `findPrevClose` · function · L1348-L1359 — `findPrevClose = (time: any): number | null`
-   `formatDate` · function · L1361-L1370 — `formatDate = (input: Date | string): string`
-   `updateTooltipPosition` · function · L1372-L1379 — `updateTooltipPosition = (relX: number)`
-   `initChart` · function · L1382-L1426 — `initChart = ()`
-   `handleClickOutside` · function · L1450-L1453 — `handleClickOutside = (e: MouseEvent)`
-   `handleGlobalKeydown` · function · L1466-L1521 — `handleGlobalKeydown = (e: KeyboardEvent)`

### stage_one/frontend/src/components/DateRangePicker.vue

共 9 个符号 · 被依赖 0 · 依赖外部 0

-   `parseYMD` · function · L36-L38 — `function parseYMD(s: string): Date`
-   `openPicker` · function · L40-L47 — `function openPicker(field: 'start' | 'end')`
-   `close` · function · L49-L51 — `function close()`
-   `onYearChange` · function · L61-L63 — `function onYearChange(e: Event)`
-   `onMonthChange` · function · L64-L66 — `function onMonthChange(e: Event)`
-   `prevMonth` · function · L67-L74 — `function prevMonth()`
-   `nextMonth` · function · L75-L82 — `function nextMonth()`
-   `selectDate` · function · L106-L117 — `function selectDate(cell: { day: number; dateStr: string; disabled: boolean })`
-   `clearActive` · function · L119-L122 — `function clearActive()`

### stage_one/frontend/src/components/GlobalSecuritySearch.vue

共 14 个符号 · 被依赖 1 · 依赖外部 4

-   `openPanel` · function · L197-L200 — `function openPanel()`
-   `focusInput` · function · L202-L207 — `function focusInput()`
-   `onInput` · function · L213-L234 — `function onInput()`
-   `choose` · function · L236-L242 — `function choose(r: StockInfo)`
-   `close` · function · L244-L246 — `function close()`
-   `addToRecent` · function · L249-L260 — `function addToRecent(r: StockInfo)`
-   `removeFromRecent` · function · L262-L269 — `function removeFromRecent(symbol: string)`
-   `clearAllRecent` · function · L271-L275 — `function clearAllRecent()`
-   `isFavored` · function · L278-L282 — `function isFavored(symbol: string): boolean`
-   `toggleFav` · function · L285-L287 — `function toggleFav(symbol: string)`
-   `fetchDefaultRecommend` · function · L290-L298 — `async function fetchDefaultRecommend()`
-   `onKeydown` · function · L301-L319 — `function onKeydown(e: KeyboardEvent)`
-   `onGlobalKey` · function · L322-L328 — `function onGlobalKey(e: KeyboardEvent)`
-   `badge` · function · L330-L333 — `function badge(symbol: string): string`

### stage_one/frontend/src/components/StrategyPanel.vue

共 2 个符号 · 被依赖 1 · 依赖外部 3

-   `formatWavePattern` · function · L530-L533 — `function formatWavePattern(pattern?: string): string`
-   `copyReviewMarkdown` · function · L774-L813 — `function copyReviewMarkdown()`

### stage_one/frontend/src/components/ThemeToggle.vue

共 16 个符号 · 被依赖 1 · 依赖外部 0

-   `PixelDot` · interface · L97-L102 — `interface PixelDot`
-   `MorphParticle` · interface · L104-L118 — `interface MorphParticle`
-   `createParticles` · function · L167-L197 — `function createParticles(): MorphParticle[]`
-   `rnd` · function · L169-L172 — `rnd = ()`
-   `easeInOutCubic` · function · L201-L204 — `function easeInOutCubic(t: number): number`
-   `renderCanvas` · function · L231-L274 — `function renderCanvas(t: number, now = performance.now())`
-   `idleLoop` · function · L281-L288 — `function idleLoop(now: number)`
-   `startIdleLoopIfNeeded` · function · L290-L294 — `function startIdleLoopIfNeeded()`
-   `stopIdleLoop` · function · L296-L301 — `function stopIdleLoop()`
-   `animateTo` · function · L304-L346 — `function animateTo(targetP: number, duration = 480)`
-   `step` · function · L326-L343 — `function step(now: number)`
-   `onPointerDown` · function · L354-L374 — `function onPointerDown(e: PointerEvent)`
-   `onPointerMove` · function · L376-L391 — `function onPointerMove(e: PointerEvent)`
-   `onPointerUp` · function · L393-L418 — `function onPointerUp(e: PointerEvent)`
-   `onPointerCancel` · function · L420-L434 — `function onPointerCancel(e: PointerEvent)`
-   `handleClick` · function · L437-L447 — `function handleClick()`

### stage_one/frontend/src/composables/useChartAnnotations.ts

共 51 个符号 · 被依赖 5 · 依赖外部 0

- + `ChartMarkerItem` · interface · L15-L22 — `interface ChartMarkerItem`
- + `ChartPriceLineItem` · interface · L24-L31 — `interface ChartPriceLineItem`
- + `ChartBoxItem` · interface · L33-L42 — `interface ChartBoxItem`
- + `ChartChannelLineItem` · interface · L44-L54 — `interface ChartChannelLineItem`
- + `WavePointItem` · interface · L56-L64 — `interface WavePointItem`
- + `ChartWaveLinesItem` · interface · L66-L77 — `interface ChartWaveLinesItem`
- + `FibLineItem` · interface · L79-L87 — `interface FibLineItem`
- + `GapBoxItem` · interface · L89-L97 — `interface GapBoxItem`
- + `EmaPointItem` · interface · L99-L102 — `interface EmaPointItem`
- + `TimeLineItem` · interface · L104-L115 — `interface TimeLineItem`
- + `toChartTime` · function · L120-L152 — `function toChartTime(t: string | number): any`
- + `getTimeCoordinate` · function · L157-L219 — `function getTimeCoordinate(timeScale: any, rawTime: string | number): number | null`
-   `AnnotationOverlayPrimitive` · class · L225-L801 — `class AnnotationOverlayPrimitive implements ISeriesPrimitive<any>`
-   `constructor` · method · L239-L696 — `constructor()`
-   `draw` · method · L252-L683 — `draw(target: any)`
-   `zOrder` · method · L688-L690 — `zOrder()`
-   `renderer` · method · L691-L693 — `renderer()`
-   `setDarkMode` · method · L698-L701 — `public setDarkMode(isDark: boolean)`
-   `setBoxes` · method · L703-L706 — `public setBoxes(boxes: ChartBoxItem[])`
-   `setChannelLines` · method · L708-L711 — `public setChannelLines(channelLines: ChartChannelLineItem[])`
-   `setWaveLines` · method · L713-L716 — `public setWaveLines(waveLines: ChartWaveLinesItem | null)`
-   `setTimeLines` · method · L718-L721 — `public setTimeLines(timeLines: TimeLineItem[])`
-   `setFibLines` · method · L723-L726 — `public setFibLines(fibLines: FibLineItem[])`
-   `setGapBoxes` · method · L728-L731 — `public setGapBoxes(gapBoxes: GapBoxItem[])`
-   `setEma200Data` · method · L733-L739 — `public setEma200Data(data: EmaPointItem[])`
-   `setBatch` · method · L741-L763 — `public setBatch(payload: { boxes?: ChartBoxItem[]; channelLines?: ChartChannelLineItem[]; waveLines?: ChartWaveLinesItem | null; timeLines?: TimeLineItem[]; fibLines?: FibLineItem[]; gapBoxes?: GapBoxItem[]; ema200Data?: EmaPointItem[]; })`
-   `setHighlightedTime` · method · L765-L768 — `public setHighlightedTime(timeStr: string | null)`
-   `clear` · method · L770-L780 — `public clear()`
-   `requestUpdate` · method · L782-L786 — `private requestUpdate()`
-   `attached` · method · L788-L790 — `public attached(param: any)`
-   `detached` · method · L792-L794 — `public detached()`
-   `updateAllViews` · method · L796-L796 — `public updateAllViews()`
-   `paneViews` · method · L798-L800 — `public paneViews(): readonly IPrimitivePaneView[]`
- + `useChartAnnotations` · function · L803-L1111 — `function useChartAnnotations()`
- + `init` · function · L819-L840 — `function init(chart: IChartApi, series: ISeriesApi<any>, existingMarkersPlugin?: any)`
- + `setMarkers` · function · L842-L869 — `function setMarkers(markers: ChartMarkerItem[])`
- + `setPriceLines` · function · L871-L939 — `function setPriceLines(lines: ChartPriceLineItem[])`
- + `getLinePriority` · function · L885-L894 — `function getLinePriority(item: ChartPriceLineItem): number`
- + `setBoxes` · function · L941-L945 — `function setBoxes(boxes: ChartBoxItem[])`
- + `setChannelLines` · function · L947-L951 — `function setChannelLines(channelLines: ChartChannelLineItem[])`
- + `setWaveLines` · function · L953-L957 — `function setWaveLines(waveLines: ChartWaveLinesItem | null)`
- + `setTimeLines` · function · L959-L963 — `function setTimeLines(lines: TimeLineItem[])`
- + `setFibLines` · function · L965-L969 — `function setFibLines(fibLines: FibLineItem[])`
- + `setGapBoxes` · function · L971-L975 — `function setGapBoxes(gapBoxes: GapBoxItem[])`
- + `setEma200Data` · function · L977-L980 — `function setEma200Data(data: EmaPointItem[])`
- + `highlightTimeLine` · function · L982-L985 — `function highlightTimeLine(dateStr: string | null)`
- + `setDarkMode` · function · L987-L990 — `function setDarkMode(isDark: boolean)`
- + `setBatch` · function · L992-L1011 — `function setBatch(payload: { boxes?: ChartBoxItem[]; channelLines?: ChartChannelLineItem[]; waveLines?: ChartWaveLinesItem | null; timeLines?: TimeLineItem[]; fibLines?: FibLineItem[]; gapBoxes?: GapBoxItem[]; ema200Data?: EmaPointItem[]; })`
- + `setAllAnnotations` · function · L1013-L1041 — `function setAllAnnotations(anno: { markers?: ChartMarkerItem[]; lines?: ChartPriceLineItem[]; boxes?: ChartBoxItem[]; channel_lines?: ChartChannelLineItem[]; channelLines?: ChartChannelLineItem[]; wave_lines?: ChartWaveLinesItem | null; waveLines?: ChartWaveLinesItem | null; time_lines?: TimeLineItem[]; timeLines?: TimeLineItem[]; fib_lines?: FibLineItem[]; fibLines?: FibLineItem[]; gap_boxes?: GapBoxItem[]; gapBoxes?: GapBoxItem[]; ema200_data?: EmaPointItem[]; ema200Data?: EmaPointItem[]; })`
- + `clearAnnotations` · function · L1043-L1056 — `function clearAnnotations()`
- + `dispose` · function · L1058-L1083 — `function dispose()`

### stage_one/frontend/src/composables/useChartCore.ts

共 6 个符号 · 被依赖 3 · 依赖外部 2

- + `UseChartCoreOptions` · interface · L14-L19 — `interface UseChartCoreOptions`
- + `useChartCore` · function · L21-L163 — `function useChartCore(options?: UseChartCoreOptions)`
- + `initChart` · function · L31-L88 — `function initChart( container: HTMLElement, cfg?: { isDark?: boolean; onRangeChange?: (range: any) => void; onCrosshairMove?: (param: any) => void; } )`
- + `observeChartArea` · function · L90-L110 — `function observeChartArea(areaEl?: HTMLElement | null)`
- + `syncChartSize` · function · L112-L123 — `function syncChartSize(areaEl?: HTMLElement | null)`
- + `dispose` · function · L125-L146 — `function dispose()`

### stage_one/frontend/src/composables/useChartIndicators.ts

共 5 个符号 · 被依赖 6 · 依赖外部 2

- + `useChartIndicators` · function · L6-L149 — `function useChartIndicators()`
- + `calcEMA` · function · L19-L27 — `function calcEMA(data: KLinePoint[], span: number)`
- + `calcVWAP` · function · L29-L46 — `function calcVWAP(data: KLinePoint[])`
- + `initIndicators` · function · L48-L78 — `function initIndicators(chart: IChartApi)`
- + `updateIndicators` · function · L80-L146 — `function updateIndicators(data: KLinePoint[], force = false)`

### stage_one/frontend/src/composables/useChartViewport.ts

共 22 个符号 · 被依赖 11 · 依赖外部 10

- + `generateFutureWhitespace` · function · L18-L83 — `function generateFutureWhitespace( lastTimeStr: string, period: Period, symbol: string, count: number = 24 ): { time: any }[]`
-   `toLocalDateStr` · function · L85-L90 — `toLocalDateStr = (d: Date): string`
- + `useChartViewport` · function · L92-L958 — `function useChartViewport(options: { isDarkMode: Ref<boolean>; currentSymbol: Ref<string>; currentPeriod: Ref<Period>; getChartInstance: () => IChartApi | null; getCandlestickSeries: () => any; getVolumeSeries: () => any; getMarkersPlugin: () => any; clearChartAnnotations: () => void; updateIndicators: (data: KLinePoint[]) => void; onBeforeLoad: () => void; onLoadSuccess: () => void; onLoadError: () => void; })`
- + `cacheKey` · function · L124-L124 — `cacheKey = (symbol: string, period: Period)`
- + `getFromCache` · function · L126-L132 — `getFromCache = (key: string): KLinePoint[] | undefined`
- + `SRPriceLineItem` · interface · L146-L151 — `interface SRPriceLineItem`
- + `setSuppressRangeEvents` · function · L175-L177 — `setSuppressRangeEvents = (v: boolean)`
- + `updateCache` · function · L179-L190 — `updateCache = (sym: string, period: Period, data: KLinePoint[])`
- + `stopFlashing` · function · L192-L212 — `stopFlashing = ()`
- + `clearOverlays` · function · L214-L244 — `clearOverlays = ()`
- + `animatePriceRange` · function · L246-L276 — `animatePriceRange = ( priceScale: any, startFrom: number, startTo: number, targetFrom: number, targetTo: number, duration = 240 )`
- + `step` · function · L259-L274 — `step = (now: number)`
- + `onVisibleLogicalRangeChanged` · function · L278-L287 — `onVisibleLogicalRangeChanged = (range: any)`
- + `setTimeRange` · function · L289-L349 — `setTimeRange = (range: string)`
- + `selectTimeRange` · function · L351-L354 — `selectTimeRange = (range: string)`
- + `highlightSRLevel` · function · L356-L401 — `highlightSRLevel = (idx: number, isHover: boolean, level?: SRLevel)`
- + `scrollToSRLevel` · function · L403-L654 — `scrollToSRLevel = (level: SRLevel, idx?: number)`
- + `animatePulse` · function · L495-L528 — `animatePulse = (now: number)`
- + `renderSRLevels` · function · L656-L695 — `renderSRLevels = (levels?: SRLevel[], summary?: any)`
- + `loadKlineData` · function · L697-L798 — `loadKlineData = async (targetSymbol: string, targetPeriod: Period)`
- + `patchTailBar` · function · L800-L816 — `patchTailBar = (updatedBar: KLinePoint, isNewBar: boolean)`
- + `setKlineDataSilently` · function · L818-L823 — `setKlineDataSilently = (freshData: KLinePoint[], preserveRange?: { from: number; to: number } | null)`

### stage_one/frontend/src/composables/useLiveQuoteSync.ts

共 9 个符号 · 被依赖 6 · 依赖外部 10

- + `resolveBarBucketTime` · function · L8-L33 — `function resolveBarBucketTime(updateTime: string, period: Period, lastBarTime: string): string`
- + `useLiveQuoteSync` · function · L35-L324 — `function useLiveQuoteSync(options: { currentSymbol: Ref<string>; currentPeriod: Ref<Period>; klineData: Ref<KLinePoint[]>; latestPrice: Ref<number | null>; latestChange: Ref<number>; watchlist: Ref<string[]>; getChartInstance: () => IChartApi | null; getCandlestickSeries: () => any; setSuppressRangeEvents: (v: boolean) => void; onCacheUpdate: (sym: string, period: Period, data: KLinePoint[]) => void; onIndicatorsUpdate: (data: KLinePoint[]) => void; onPatchTailBar?: (updatedBar: KLinePoint, isNewBar: boolean) => void; onSetKlineDataSilently?: (freshData: KLinePoint[], preserveRange?: { from: number; to: number } | null) => void; })`
- + `refreshEngineSymbols` · function · L129-L135 — `function refreshEngineSymbols()`
- + `syncLatestBarsSilently` · function · L137-L165 — `async function syncLatestBarsSilently(sym: string, period: Period)`
- + `applyLiveQuoteToChart` · function · L167-L235 — `function applyLiveQuoteToChart(q: Quote)`
- + `startQuoteEngine` · function · L237-L261 — `async function startQuoteEngine()`
- + `pauseQuoteEngine` · function · L263-L265 — `function pauseQuoteEngine()`
- + `resumeQuoteEngine` · function · L268-L280 — `function resumeQuoteEngine()`
- + `stopQuoteEngine` · function · L291-L294 — `function stopQuoteEngine()`

### stage_one/frontend/src/composables/useSmartThrottling.ts

共 7 个符号 · 被依赖 2 · 依赖外部 0

- + `useSmartThrottling` · function · L5-L103 — `function useSmartThrottling()`
- + `Poller` · type · L9-L13 — `type Poller = { fn: () => void | Promise<void>; intervalMs: number; timerId: any; };`
- + `handleVisibilityChange` · function · L16-L20 — `function handleVisibilityChange()`
- + `handleFocus` · function · L22-L25 — `function handleFocus()`
- + `handleBlur` · function · L27-L33 — `function handleBlur()`
- + `updateActiveState` · function · L35-L57 — `function updateActiveState()`
- + `registerPoll` · function · L62-L80 — `function registerPoll(fn: () => void | Promise<void>, intervalMs: number)`

### stage_one/frontend/src/composables/useWatchlist.ts

共 32 个符号 · 被依赖 10 · 依赖外部 11

- + `MarketTabKey` · type · L14-L14 — `type MarketTabKey = 'all' | 'us' | 'futures';`
- + `SortKey` · type · L15-L15 — `type SortKey = 'name' | 'price' | 'change';`
- + `WatchlistPriceInfo` · interface · L17-L21 — `interface WatchlistPriceInfo`
- + `WatchlistRowInfo` · interface · L23-L38 — `interface WatchlistRowInfo`
- + `canonSym` · function · L52-L56 — `canonSym = (s: string): string`
- + `currencyOf` · function · L58-L58 — `currencyOf = (_sym: string): string`
- + `useWatchlist` · function · L60-L518 — `function useWatchlist(options: { liveQuoteMap: Ref<Record<string, Quote>>; quoteConfig: Ref<QuoteConfig | null>; currentSymbol: Ref<string>; onSelectSymbol: (sym: string) => void; onSymbolsChanged: () => void; })`
- + `genGroupId` · function · L69-L72 — `genGroupId = (): string`
- + `defaultGroups` · function · L74-L76 — `defaultGroups = (): WatchGroup[]`
- + `getInitialGroups` · function · L78-L95 — `function getInitialGroups(): WatchGroup[]`
- + `getStockName` · function · L130-L133 — `getStockName = (sym: string): string`
- + `delayFullOf` · function · L135-L138 — `delayFullOf = (sym: string): string`
- + `loadStockNameMap` · function · L140-L158 — `async function loadStockNameMap()`
- + `watchPriceInfo` · function · L160-L209 — `function watchPriceInfo(item: string): { price: number | null; change: number | null; loading: boolean; extendedPrice: number | null; extendedLabel: string; prevClose: number | null; status?: string; reason?: string; }`
- + `secondaryLineInfo` · function · L211-L237 — `function secondaryLineInfo(item: string): { price: number | null; changePct: number | null; label: string; } | null`
- + `updateWatchlistPrices` · function · L265-L267 — `async function updateWatchlistPrices()`
- + `persistWatchlistLocal` · function · L269-L271 — `persistWatchlistLocal = ()`
- + `persistWatchlist` · function · L273-L276 — `persistWatchlist = ()`
- + `loadWatchlist` · function · L278-L328 — `loadWatchlist = async ()`
- + `isWatchlisted` · function · L330-L333 — `isWatchlisted = (sym: string): boolean`
- + `removeFromWatchlist` · function · L335-L346 — `removeFromWatchlist = (sym: string, groupId?: string)`
- + `toggleWatchlist` · function · L348-L366 — `toggleWatchlist = (sym: string)`
- + `addToActiveGroup` · function · L368-L384 — `addToActiveGroup = (sym: string)`
- + `createGroup` · function · L386-L393 — `createGroup = (rawName: string)`
- + `renameGroup` · function · L395-L401 — `renameGroup = (id: string, name: string)`
- + `deleteGroup` · function · L403-L413 — `deleteGroup = (id: string)`
- + `selectGroup` · function · L415-L418 — `selectGroup = (id: string)`
- + `toggleGroupDropdown` · function · L420-L422 — `toggleGroupDropdown = ()`
- + `setSort` · function · L424-L431 — `setSort = (key: SortKey)`
- + `matchMarketTab` · function · L433-L441 — `matchMarketTab = (sym: string, tab: MarketTabKey): boolean`
- + `clearWatchlistCache` · function · L475-L477 — `clearWatchlistCache = ()`
- + `markAllLoadingFailed` · function · L479-L483 — `markAllLoadingFailed = ()`

### stage_one/frontend/src/composables/useWebSocketControl.ts

共 4 个符号 · 被依赖 2 · 依赖外部 0

- + `WSControlMessage` · interface · L5-L36 — `interface WSControlMessage`
- + `useWebSocketControl` · function · L38-L174 — `function useWebSocketControl(handlers: { onOpenChart?: (symbol: string, period?: string) => void; onAddMarkers?: (markers: any[], symbol?: string) => void; onDrawLines?: (lines: any[], symbol?: string) => void; onDrawBoxes?: (boxes: any[], symbol?: string) => void; onDrawChannelLines?: (channelLines: any[], symbol?: string) => void; onDrawWaveLines?: (waveLines: any, symbol?: string) => void; onDrawTimeLines?: (timeLines: any[], symbol?: string) => void; onDrawFibLines?: (fibLines: any[], symbol?: string) => void; onDrawGapBoxes?: (gapBoxes: any[], symbol?: string) => void; onDrawEma200?: (ema200Data: any[], symbol?: string) => void; onClearAnnotations?: (kind?: string, symbol?: string) => void; onRunStrategy?: (mode?: string, symbol?: string) => void; onCaptureChart?: (requestId?: string) => Promise<string | null> | (string | null); onRefreshWatchlist?: () => void; })`
- + `connect` · function · L61-L147 — `function connect()`
- + `sendState` · function · L149-L153 — `function sendState(state: { symbol: string; period: string; current_price?: number })`

### stage_one/frontend/src/main.ts

共 0 个符号 · 被依赖 0 · 依赖外部 1

- （该文件无可提取符号）

### stage_one/frontend/src/utils/api.ts

共 11 个符号 · 被依赖 18 · 依赖外部 3

- + `Period` · type · L24-L24 — `type Period = (typeof SUPPORTED_PERIODS)[number];`
- + `StockInfo` · interface · L39-L43 — `interface StockInfo`
- + `WatchGroup` · interface · L45-L49 — `interface WatchGroup`
- + `AnalysisResponse` · interface · L51-L54 — `interface AnalysisResponse`
- + `LeveragePairInfo` · interface · L56-L60 — `interface LeveragePairInfo`
- + `searchStocks` · function · L75-L87 — `async function searchStocks(keyword: string): Promise<StockInfo[]>`
- + `getKLines` · function · L90-L110 — `async function getKLines( symbol: string, period: Period = '1d', full: boolean = false, fresh: boolean = false, signal?: AbortSignal ): Promise<KLinePoint[]>`
- + `getStockAnalysis` · function · L113-L149 — `async function getStockAnalysis( symbol: string, startDate: string, endDate: string, klineCache?: KLinePoint[], period: Period = '1d' ): Promise<AnalysisResponse | null>`
- + `getWatchlist` · function · L152-L162 — `async function getWatchlist(): Promise<WatchGroup[]>`
- + `saveWatchlist` · function · L164-L172 — `async function saveWatchlist(groups: WatchGroup[]): Promise<void>`
- + `runPAStrategy` · function · L175-L197 — `async function runPAStrategy( symbol: string, period: string = '1d', mode: string = 'swing', klines?: KLinePoint[], signal?: AbortSignal ): Promise<any>`

### stage_one/frontend/src/utils/chartUtils.ts

共 1 个符号 · 被依赖 4 · 依赖外部 0

- + `getChartOptions` · function · L4-L97 — `getChartOptions = (isDark: boolean = false): DeepPartial<ChartOptions>`

### stage_one/frontend/src/utils/mockEngine.ts

共 8 个符号 · 被依赖 5 · 依赖外部 0

- + `KLinePoint` · interface · L3-L10 — `interface KLinePoint`
- + `SRLevel` · interface · L12-L18 — `interface SRLevel`
- + `RangeStatPoint` · interface · L20-L24 — `interface RangeStatPoint`
- + `RangeStats` · interface · L26-L34 — `interface RangeStats`
-   `findExtrema` · function · L50-L63 — `function findExtrema(data: KLinePoint[], windowSize: number = 5)`
-   `median` · function · L79-L84 — `function median(values: number[]): number`
- + `calculateSRLevels` · function · L90-L182 — `function calculateSRLevels(data: KLinePoint[], windowSize: number = 5, period: string = '1d'): SRLevel[]`
- + `calculateRangeStats` · function · L187-L250 — `function calculateRangeStats(data: KLinePoint[], sDate: string, eDate: string): RangeStats | null`

### stage_one/frontend/src/utils/quote.ts

共 33 个符号 · 被依赖 4 · 依赖外部 4

- + `QuoteStatus` · type · L4-L11 — `type QuoteStatus = | 'ok' | 'cooling' | 'rate_limited' | 'ip_overload' | 'empty' | 'error' | 'loading';`
- + `toCanonSym` · function · L13-L17 — `function toCanonSym(s: string): string`
- + `USExtendedSessionLabel` · type · L19-L19 — `type USExtendedSessionLabel = '夜盘' | '盘前' | '盘后' | '';`
- + `getCurrentUSExtendedSession` · function · L25-L48 — `function getCurrentUSExtendedSession(now: Date = new Date()): USExtendedSessionLabel`
- + `Quote` · interface · L50-L67 — `interface Quote`
- + `MarketCfg` · interface · L69-L77 — `interface MarketCfg`
- + `QuoteConfig` · interface · L79-L87 — `interface QuoteConfig`
- + `USSession` · type · L129-L129 — `type USSession = 'pre' | 'regular' | 'post';`
- + `SymbolMeta` · interface · L131-L138 — `interface SymbolMeta`
-   `Listener` · type · L140-L140 — `type Listener = (symbol: string, quote: Quote) => void;`
-   `BatchListener` · type · L141-L141 — `type BatchListener = (batch: Record<string, Quote>) => void;`
-   `QuoteEngine` · class · L145-L669 — `class QuoteEngine`
-   `constructor` · method · L162-L164 — `constructor()`
-   `loadQuotesCache` · method · L168-L185 — `private loadQuotesCache(): void`
-   `saveQuotesCache` · method · L187-L197 — `private saveQuotesCache(): void`
-   `setActiveSymbol` · method · L199-L208 — `setActiveSymbol(sym: string): void`
-   `loadConfig` · method · L210-L217 — `async loadConfig(): Promise<void>`
-   `setSymbols` · method · L219-L243 — `setSymbols(syms: string[]): void`
-   `subscribe` · method · L245-L256 — `subscribe(cb: Listener): () => void`
-   `subscribeBatch` · method · L258-L269 — `subscribeBatch(cb: BatchListener): () => void`
-   `onTick` · method · L271-L274 — `onTick(cb: () => void): () => void`
-   `snapshotMetas` · method · L276-L280 — `snapshotMetas(): Record<string, SymbolMeta>`
-   `start` · method · L283-L288 — `start(): void`
-   `resume` · method · L291-L318 — `resume(): void`
-   `stop` · method · L321-L327 — `stop(): void`
-   `getQuote` · method · L329-L339 — `getQuote(symbol: string): Quote | null`
-   `getAllQuotes` · method · L341-L347 — `getAllQuotes(): Record<string, Quote>`
-   `getMeta` · method · L349-L351 — `getMeta(symbol: string): SymbolMeta | null`
-   `getEngineStatus` · method · L353-L358 — `getEngineStatus(): { cooling: boolean; reason: string }`
-   `getMinInterval` · method · L360-L368 — `private getMinInterval(market: Market | null): number`
-   `detectUSSession` · method · L370-L375 — `private detectUSSession(): USSession`
-   `tick` · method · L377-L434 — `private async tick(): Promise<void>`
-   `fetchMarketBatch` · method · L436-L668 — `private async fetchMarketBatch(market: string, due: string[], now: number): Promise<void>`

### stage_one/frontend/src/utils/srUtils.ts

共 2 个符号 · 被依赖 4 · 依赖外部 1

- + `EnrichedSRLevel` · interface · L5-L7 — `interface EnrichedSRLevel extends SRLevel`
- + `enrichSRLevels` · function · L13-L48 — `function enrichSRLevels(levels: SRLevel[], summary?: any): EnrichedSRLevel[]`

### stage_one/frontend/src/utils/symbols.ts

共 6 个符号 · 被依赖 27 · 依赖外部 0

- + `Market` · type · L3-L3 — `type Market = 'us' | 'ash' | 'asz' | 'hk' | 'futures' | 'crypto';`
-   `stripCryptoUsPrefix` · function · L25-L40 — `function stripCryptoUsPrefix(clean: string): string`
- + `marketOf` · function · L43-L70 — `function marketOf(sym: string): Market | null`
- + `stripPrefix` · function · L73-L79 — `function stripPrefix(sym: string): string`
- + `formatSymbol` · function · L82-L84 — `function formatSymbol(sym: string): string`
- + `normalizeSymbol` · function · L87-L136 — `function normalizeSymbol(raw: string, market?: Market): string`

### stage_one/frontend/tailwind.config.js

共 0 个符号 · 被依赖 0 · 依赖外部 0

- （该文件无可提取符号）

### stage_one/frontend/vite.config.ts

共 0 个符号 · 被依赖 0 · 依赖外部 0

- （该文件无可提取符号）

## 6. 使用说明（给阅读者）

1. **定位**：先看第 3 节确认改动目标的影响面，再在第 5 节拿到 `文件:行号`。
2. **不完整之处**：本文件无函数体、无全局状态、无运行时配置，逻辑与业务规则需结合源码。
3. **符号重名**：前后端存在同义映射（如 `normalize_symbol` 与 `normalizeSymbol`），按路径区分。
4. **范围**：仅 `stage_one/` 下的受版本控制源码，已排除 `node_modules/`、`.venv/`、构建产物。
