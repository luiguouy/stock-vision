# StockVision — 项目结构图谱

> 本文件由 graft 结构层自动导出，是对代码库的**索引**，不是实现说明。
> 每条记录都带 `文件:行号`，用于精确定位；这里**不含函数体**，需要实现细节时应另行取源码。
> 生成时间：2026-11-14 21:03

## 1. 概览

| 指标 | 数值 |
|---|---|
| 源文件 | 42 |
| 语言 | javascript, python, typescript, vue |
| 符号总数 | 504（不含 42 个文件节点） |
| 符号构成 | function 304 / method 133 / file 42 / class 35 / interface 24 / type 8 |
| 依赖边 | 199（跨文件调用、导入、继承） |

后端为 FastAPI + WebSockets（Python），前端为 Vue 3 + Vite + Tailwind（TypeScript/Vue）。

## 2. 模块分布

| 目录 | 文件数 | 符号数 | 被依赖 | 依赖外部 |
|---|---|---|---|---|
| `stage_one/backend/` | 21 | 265 | 103 | 103 |
| `stage_one/frontend/` | 3 | 0 | 0 | 0 |
| `stage_one/frontend/src/` | 2 | 44 | 1 | 54 |
| `stage_one/frontend/src/components/` | 4 | 40 | 3 | 5 |
| `stage_one/frontend/src/composables/` | 7 | 103 | 36 | 32 |
| `stage_one/frontend/src/utils/` | 5 | 52 | 56 | 5 |

## 3. 核心枢纽

按**被调用次数**排序。改动这些符号的影响面最大，属于优先理解对象。

| 符号 | 位置 | 被调用 | 签名 |
|---|---|---|---|
| `normalize_symbol` | `stage_one/backend/symbols.py:L42-L85` | 13 | `def normalize_symbol(raw: str, market: Optional[str] = None) -> Optional[str]` |
| `canonSym` | `stage_one/frontend/src/composables/useWatchlist.ts:L51-L55` | 11 | `canonSym = (s: string): string` |
| `normalizeSymbol` | `stage_one/frontend/src/utils/symbols.ts:L87-L136` | 10 | `function normalizeSymbol(raw: string, market?: Market): string` |
| `validate_klines` | `stage_one/backend/data_provider.py:L86-L116` | 8 | `def validate_klines(df: "pd.DataFrame", period: str) -> bool` |
| `_get_connection` | `stage_one/backend/db_cache.py:L68-L80` | 8 | `def _get_connection() -> sqlite3.Connection` |
| `broadcast` | `stage_one/backend/main.py:L752-L757` | 8 | `async def broadcast(self, data: dict)` |
| `_post` | `stage_one/backend/control_client.py:L58-L64` | 7 | `def _post(path: str, payload: Optional[Dict[str, Any]] = None, err_prefix: str = "请求失败"...` |
| `resample_to_period` | `stage_one/backend/data_provider.py:L193-L218` | 7 | `def resample_to_period(df: pd.DataFrame, rule: str) -> pd.DataFrame` |
| `get_market_cfg` | `stage_one/backend/quote_config.py:L65-L67` | 6 | `def get_market_cfg(market: Optional[str]) -> dict` |
| `loadKlineData` | `stage_one/frontend/src/composables/useChartViewport.ts:L267-L402` | 6 | `loadKlineData = async (targetSymbol: string, targetPeriod: Period)` |
| `marketOf` | `stage_one/frontend/src/utils/symbols.ts:L43-L70` | 6 | `function marketOf(sym: string): Market \| null` |
| `requestUpdate` | `stage_one/frontend/src/composables/useChartAnnotations.ts:L519-L523` | 6 | `private requestUpdate()` |
| `persistWatchlist` | `stage_one/frontend/src/composables/useWatchlist.ts:L256-L259` | 6 | `persistWatchlist = ()` |
| `ensure_app_running` | `stage_one/backend/control_client.py:L25-L49` | 5 | `def ensure_app_running() -> bool` |
| `strip_prefix` | `stage_one/backend/symbols.py:L123-L129` | 5 | `def strip_prefix(symbol: str) -> str` |

## 4. 文件级依赖

只列**项目内跨文件**关系，同文件内的包含关系与标准库导入已剔除。括号内为关系类型与出现次数。

- **stage_one/backend/control_client.py** → `stage_one/backend/symbols.py` (calls ×2, imports)
- **stage_one/backend/data_provider.py** → `stage_one/backend/symbols.py` (calls, imports)
- **stage_one/backend/db_cache.py** → `stage_one/backend/data_provider.py` (calls, imports)
- **stage_one/backend/main.py** → `stage_one/backend/analysis.py` (calls ×2, imports), `stage_one/backend/data_provider.py` (imports), `stage_one/backend/db_cache.py` (calls ×10, imports), `stage_one/backend/quote_config.py` (imports), `stage_one/backend/quote_provider.py` (imports), `stage_one/backend/strategy_adapter.py` (calls ×2, imports), `stage_one/backend/symbols.py` (calls ×16, imports)
- **stage_one/backend/quote_config.py** → `stage_one/backend/symbols.py` (imports)
- **stage_one/backend/quote_provider.py** → `stage_one/backend/data_provider.py` (imports), `stage_one/backend/quote_config.py` (calls ×5, imports)
- **stage_one/backend/strategy_adapter.py** → `stage_one/backend/symbols.py` (calls ×2, imports), `stage_one/backend/time_window.py` (calls, imports)
- **stage_one/backend/test_adjustment.py** → `stage_one/backend/data_provider.py` (calls, imports)
- **stage_one/backend/test_crypto_features.py** → `stage_one/backend/data_provider.py` (calls ×5, imports), `stage_one/backend/main.py` (imports), `stage_one/backend/quote_config.py` (calls, imports), `stage_one/backend/quote_provider.py` (calls ×4, imports)
- **stage_one/backend/test_endpoints.py** → `stage_one/backend/analysis.py` (calls ×2, imports), `stage_one/backend/data_provider.py` (calls ×3, imports), `stage_one/backend/main.py` (imports), `stage_one/backend/mcp_server.py` (imports), `stage_one/backend/quote_config.py` (imports), `stage_one/backend/quote_provider.py` (imports), `stage_one/backend/symbols.py` (calls)
- **stage_one/backend/test_resample.py** → `stage_one/backend/data_provider.py` (calls ×6, imports)
- **stage_one/backend/test_strategy_wave_channel.py** → `stage_one/backend/main.py` (imports), `stage_one/backend/strategy_adapter.py` (calls ×3, imports)
- **stage_one/backend/test_transformation_new.py** → `stage_one/backend/main.py` (imports), `stage_one/backend/mcp_server.py` (imports), `stage_one/backend/strategy_adapter.py` (calls, imports)
- **stage_one/backend/test_validate.py** → `stage_one/backend/data_provider.py` (calls, imports)
- **stage_one/frontend/src/App.vue** → `stage_one/frontend/src/components/GlobalSecuritySearch.vue` (imports), `stage_one/frontend/src/components/StrategyPanel.vue` (imports), `stage_one/frontend/src/components/ThemeToggle.vue` (imports), `stage_one/frontend/src/composables/useChartAnnotations.ts` (calls, imports), `stage_one/frontend/src/composables/useChartIndicators.ts` (calls ×3, imports), `stage_one/frontend/src/composables/useChartViewport.ts` (calls ×7, imports), `stage_one/frontend/src/composables/useLiveQuoteSync.ts` (calls ×3, imports), `stage_one/frontend/src/composables/useSmartThrottling.ts` (calls, imports), `stage_one/frontend/src/composables/useWatchlist.ts` (calls ×6, imports), `stage_one/frontend/src/composables/useWebSocketControl.ts` (calls, imports), `stage_one/frontend/src/utils/api.ts` (calls ×3, imports), `stage_one/frontend/src/utils/chartUtils.ts` (calls ×2, imports), `stage_one/frontend/src/utils/mockEngine.ts` (calls, imports), `stage_one/frontend/src/utils/symbols.ts` (calls ×12)
- **stage_one/frontend/src/components/GlobalSecuritySearch.vue** → `stage_one/frontend/src/utils/api.ts` (calls ×2, imports), `stage_one/frontend/src/utils/symbols.ts` (calls)
- **stage_one/frontend/src/components/StrategyPanel.vue** → `stage_one/frontend/src/utils/api.ts` (imports)
- **stage_one/frontend/src/composables/useChartIndicators.ts** → `stage_one/frontend/src/composables/useChartAnnotations.ts` (imports), `stage_one/frontend/src/utils/api.ts` (imports)
- **stage_one/frontend/src/composables/useChartViewport.ts** → `stage_one/frontend/src/composables/useChartAnnotations.ts` (imports), `stage_one/frontend/src/composables/useChartIndicators.ts` (calls), `stage_one/frontend/src/utils/api.ts` (calls, imports), `stage_one/frontend/src/utils/mockEngine.ts` (calls ×3, imports), `stage_one/frontend/src/utils/symbols.ts` (calls ×2)
- **stage_one/frontend/src/composables/useLiveQuoteSync.ts** → `stage_one/frontend/src/composables/useChartAnnotations.ts` (imports), `stage_one/frontend/src/composables/useChartViewport.ts` (calls), `stage_one/frontend/src/composables/useWatchlist.ts` (calls, imports), `stage_one/frontend/src/utils/api.ts` (calls, imports), `stage_one/frontend/src/utils/quote.ts` (imports), `stage_one/frontend/src/utils/symbols.ts` (calls)
- **stage_one/frontend/src/composables/useWatchlist.ts** → `stage_one/frontend/src/utils/api.ts` (calls ×3, imports), `stage_one/frontend/src/utils/mockEngine.ts` (calls), `stage_one/frontend/src/utils/quote.ts` (imports), `stage_one/frontend/src/utils/symbols.ts` (calls ×6)
- **stage_one/frontend/src/main.ts** → `stage_one/frontend/src/App.vue` (imports)
- **stage_one/frontend/src/utils/api.ts** → `stage_one/frontend/src/utils/mockEngine.ts` (calls ×2, imports)
- **stage_one/frontend/src/utils/quote.ts** → `stage_one/frontend/src/utils/api.ts` (imports), `stage_one/frontend/src/utils/symbols.ts` (calls)

### 外部依赖

项目外部模块（标准库 / 第三方包），仅列被导入者：

- **stage_one/backend/analysis.py**：typing
- **stage_one/backend/cli.py**：argparse, sys
- **stage_one/backend/control_client.py**：httpx, os, subprocess, sys, time, typing, uuid
- **stage_one/backend/data_provider.py**：asyncio, datetime, fastapi, httpx, json, re, typing, zoneinfo
- **stage_one/backend/db_cache.py**：datetime, json, os, sqlite3, typing
- **stage_one/backend/desktop_main.py**：ctypes, os, sys, threading, time, urllib.request, uvicorn, webview
- **stage_one/backend/main.py**：asyncio, base64, contextlib, datetime, difflib, fastapi, fastapi.middleware.cors, fastapi.responses, fastapi.staticfiles, httpx, json, os, pydantic, re, typing, uuid, uvicorn
- **stage_one/backend/mcp_server.py**：mcp.server.fastmcp, mcp.server.mcpserver, typing
- **stage_one/backend/quote_config.py**：typing
- **stage_one/backend/quote_provider.py**：asyncio, datetime, httpx, time, typing
- **stage_one/backend/strategy_adapter.py**：os, pa_engine, pathlib, plot_wave_chart, strategy_crypto, strategy_day, strategy_layer, sys, typing
- **stage_one/backend/symbols.py**：re, typing
- **stage_one/backend/test_adjustment.py**：os, sys
- **stage_one/backend/test_crypto_features.py**：asyncio, fastapi.testclient, httpx, unittest, unittest.mock
- **stage_one/backend/test_endpoints.py**：asyncio, fastapi, fastapi.testclient, math, os, sys, unittest
- **stage_one/backend/test_pagination.py**：datetime, httpx, json
- **stage_one/backend/test_resample.py**：os, sys
- **stage_one/backend/test_strategy_wave_channel.py**：fastapi.testclient, unittest
- **stage_one/backend/test_transformation_new.py**：fastapi.testclient, os, sys, unittest
- **stage_one/backend/test_validate.py**：datetime
- **stage_one/backend/time_window.py**：datetime, typing
- **stage_one/frontend/src/App.vue**：lightweight-charts, vue
- **stage_one/frontend/src/components/DateRangePicker.vue**：vue
- **stage_one/frontend/src/components/GlobalSecuritySearch.vue**：vue
- **stage_one/frontend/src/components/StrategyPanel.vue**：vue
- **stage_one/frontend/src/components/ThemeToggle.vue**：vue
- **stage_one/frontend/src/composables/useChartAnnotations.ts**：lightweight-charts, vue
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

共 3 个符号 · 被依赖 6 · 依赖外部 0

-   `_extract_ohlc` · function · L25-L31 — `def _extract_ohlc(df: pd.DataFrame) -> pd.DataFrame`
- + `calculate_sr_levels` · function · L34-L139 — `def calculate_sr_levels( df: pd.DataFrame, window: int = 5, distance_pct: float = 0.015, period: str = "1d", ) -> List[Dict[str, Any]]`
- + `calculate_range_stats` · function · L142-L244 — `def calculate_range_stats( df: pd.DataFrame, start_date: str, end_date: str ) -> Dict[str, Any]`

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

共 3 个符号 · 被依赖 0 · 依赖外部 0

- + `check_single_instance` · function · L28-L41 — `def check_single_instance() -> bool`
- + `start_backend_server` · function · L44-L55 — `def start_backend_server(port: int = 8000)`
- + `main` · function · L58-L94 — `def main()`

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
- + `prewarm_cache` · function · L339-L349 — `async def prewarm_cache()`
- + `KLinePoint` · class · L356-L362 — `class KLinePoint(BaseModel)`
- + `AnalysisRequest` · class · L365-L369 — `class AnalysisRequest(BaseModel)`
- + `WatchGroupModel` · class · L372-L375 — `class WatchGroupModel(BaseModel)`
- + `WatchlistGroupsRequest` · class · L378-L379 — `class WatchlistGroupsRequest(BaseModel)`
- + `SRLevel` · class · L382-L387 — `class SRLevel(BaseModel)`
- + `RangeStat` · class · L390-L393 — `class RangeStat(BaseModel)`
- + `AnalysisResponse` · class · L396-L400 — `class AnalysisResponse(BaseModel)`
-   `_score_stock` · function · L407-L461 — `def _score_stock(kw: str, stock: dict) -> int`
- + `search_stocks` · function · L465-L526 — `async def search_stocks( keyword: Optional[str] = Query(None, description="搜索股票名称、英文名称、代码或拼音缩写（全市场范围内）"), )`
-   `_tencent_security_search` · function · L529-L600 — `async def _tencent_security_search(kw: str) -> list`
-   `_parse_search_code` · function · L531-L541 — `def _parse_search_code(code: str) -> Optional[str]`
-   `_pool_item` · function · L543-L563 — `def _pool_item(code: str, name: str, pinyin: str = "", type_: str = "") -> Optional[dict]`
- + `get_klines` · function · L604-L627 — `async def get_klines( symbol: str = Query(..., description="股票代码，如 usAAPL"), period: str = Query("1d", description="K线周期"), full: bool = Query(True, description="是否拉取上市以来全部历史"), fresh: bool = Query(False, description="是否跳过缓存强制拉取最新数据"), )`
- + `analyze_stock` · function · L631-L647 — `async def analyze_stock(request: AnalysisRequest)`
- + `get_supported_periods` · function · L651-L667 — `async def get_supported_periods()`
-   `_default_groups` · function · L678-L679 — `def _default_groups() -> List[dict]`
-   `_load_groups` · function · L682-L698 — `def _load_groups() -> List[dict]`
-   `_save_groups` · function · L701-L717 — `def _save_groups(groups: List[dict]) -> List[dict]`
- + `get_watchlist` · function · L721-L722 — `async def get_watchlist()`
- + `save_watchlist` · function · L726-L732 — `async def save_watchlist(req: WatchlistGroupsRequest)`
- + `WSManager` · class · L739-L761 — `class WSManager`
-   `__init__` · method · L740-L742 — `def __init__(self)`
- + `connect` · method · L744-L746 — `async def connect(self, ws: WebSocket)`
- + `disconnect` · method · L748-L750 — `def disconnect(self, ws: WebSocket)`
- + `broadcast` · method · L752-L757 — `async def broadcast(self, data: dict)`
- + `resolve_capture` · method · L759-L761 — `def resolve_capture(self, request_id: str, image_base64: str)`
- + `websocket_control` · function · L775-L799 — `async def websocket_control(websocket: WebSocket)`
- + `OpenChartRequest` · class · L802-L804 — `class OpenChartRequest(BaseModel)`
- + `MarkerItem` · class · L807-L813 — `class MarkerItem(BaseModel)`
- + `AddMarkersRequest` · class · L816-L819 — `class AddMarkersRequest(BaseModel)`
- + `LineItem` · class · L822-L828 — `class LineItem(BaseModel)`
- + `DrawLinesRequest` · class · L831-L834 — `class DrawLinesRequest(BaseModel)`
- + `BoxItem` · class · L837-L845 — `class BoxItem(BaseModel)`
- + `DrawBoxesRequest` · class · L848-L851 — `class DrawBoxesRequest(BaseModel)`
- + `RunStrategyRequest` · class · L854-L859 — `class RunStrategyRequest(BaseModel)`
- + `ClearAnnotationsRequest` · class · L862-L865 — `class ClearAnnotationsRequest(BaseModel)`
- + `control_open` · function · L869-L881 — `async def control_open(req: OpenChartRequest)`
- + `control_get_state` · function · L885-L893 — `async def control_get_state()`
- + `control_add_markers` · function · L897-L906 — `async def control_add_markers(req: AddMarkersRequest)`
- + `control_draw_lines` · function · L910-L919 — `async def control_draw_lines(req: DrawLinesRequest)`
- + `control_draw_boxes` · function · L923-L932 — `async def control_draw_boxes(req: DrawBoxesRequest)`
- + `control_run_strategy` · function · L936-L993 — `async def control_run_strategy(req: RunStrategyRequest)`
- + `get_strategy_chart_html` · function · L997-L1012 — `async def get_strategy_chart_html(symbol: str, period: str = "1d")`
- + `control_clear_annotations` · function · L1016-L1024 — `async def control_clear_annotations(req: ClearAnnotationsRequest)`
- + `control_get_annotations` · function · L1028-L1033 — `async def control_get_annotations( symbol: str = Query(..., description="股票代码"), kind: Optional[str] = Query(None, description="标注类型: marker / line / box"), )`
- + `control_capture_chart` · function · L1037-L1079 — `async def control_capture_chart()`

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

共 2 个符号 · 被依赖 10 · 依赖外部 1

- + `market_of` · function · L60-L62 — `def market_of(symbol: str) -> Optional[str]`
- + `get_market_cfg` · function · L65-L67 — `def get_market_cfg(market: Optional[str]) -> dict`

### stage_one/backend/quote_provider.py

共 27 个符号 · 被依赖 7 · 依赖外部 7

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
- + `YahooCryptoQuoteProvider` · class · L145-L222 — `class YahooCryptoQuoteProvider`
-   `__init__` · method · L148-L149 — `def __init__(self) -> None`
- + `get_quotes` · method · L151-L222 — `async def get_quotes(self, symbols: List[str]) -> List[dict]`
- + `TencentQuoteProvider` · class · L224-L353 — `class TencentQuoteProvider`
-   `__init__` · method · L227-L231 — `def __init__(self) -> None`
- + `get_quotes` · method · L233-L248 — `async def get_quotes(self, symbols: List[str]) -> List[dict]`
-   `_get_tencent_quotes` · method · L250-L286 — `async def _get_tencent_quotes(self, symbols: List[str]) -> List[dict]`
-   `_fetch_raw` · method · L288-L302 — `async def _fetch_raw(self, symbols: List[str]) -> str`
-   `_parse` · method · L304-L353 — `def _parse(self, text: str, symbols: List[str]) -> Dict[str, Optional[dict]]`
-   `_to_float` · function · L355-L366 — `def _to_float(s) -> Optional[float]`
-   `_format_update_time` · function · L368-L372 — `def _format_update_time(raw: str) -> str`
-   `_error_item` · function · L374-L393 — `def _error_item(symbol: str, status: str, msg: str) -> dict`
- + `SinaFuturesQuoteProvider` · class · L403-L519 — `class SinaFuturesQuoteProvider`
-   `__init__` · method · L406-L408 — `def __init__(self) -> None`
- + `get_quotes` · method · L410-L442 — `async def get_quotes(self, symbols: List[str]) -> List[dict]`
-   `_fetch` · method · L444-L478 — `async def _fetch(self, symbols: List[str]) -> Dict[str, Optional[dict]]`
-   `_parse_line` · method · L481-L519 — `def _parse_line(line: str) -> Optional[dict]`

### stage_one/backend/strategy_adapter.py

共 10 个符号 · 被依赖 9 · 依赖外部 5

-   `_get_modules` · function · L27-L52 — `def _get_modules() -> Dict[str, Any]`
-   `_normalize_df` · function · L55-L104 — `def _normalize_df(df: Any) -> Any`
-   `_prepare_strategy_df` · function · L107-L119 — `def _prepare_strategy_df(symbol: str, df: Optional[Any]) -> Any`
-   `_evaluate_market_structure` · function · L122-L216 — `def _evaluate_market_structure( pa: Any, df_clean: Any, current_price: float, is_intraday: bool ) -> Dict[str, Any]`
-   `_build_trade_plan` · function · L219-L327 — `def _build_trade_plan( pa: Any, df_clean: Any, current_price: float, struct: Dict[str, Any], turn_windows_res: Dict[str, Any], ) -> Dict[str, Any]`
-   `_build_chart_annotations` · function · L330-L639 — `def _build_chart_annotations( pa: Any, df_clean: Any, current_price: float, is_intraday: bool, struct: Dict[str, Any], trade_plan: Dict[str, Any], turn_windows_res: Dict[str, Any], ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]`
-   `_format_time_str` · function · L349-L361 — `def _format_time_str(val: Any) -> str`
-   `_resolve_pt_time` · function · L363-L367 — `def _resolve_pt_time(pt: Dict[str, Any], idx: int) -> str`
- + `run_strategy_analysis` · function · L642-L703 — `def run_strategy_analysis( symbol: str, period: str = "1d", mode: str = "swing", df: Optional[Any] = None, ) -> Dict[str, Any]`
- + `generate_wave_chart_html` · function · L706-L748 — `def generate_wave_chart_html(symbol: str, period: str = "1d", df: Optional[Any] = None) -> str`

### stage_one/backend/symbols.py

共 5 个符号 · 被依赖 27 · 依赖外部 0

- + `norm_market_prefix` · function · L23-L29 — `def norm_market_prefix(sym: str) -> str`
-   `_strip_crypto_us_prefix` · function · L32-L39 — `def _strip_crypto_us_prefix(clean: str) -> str`
- + `normalize_symbol` · function · L42-L85 — `def normalize_symbol(raw: str, market: Optional[str] = None) -> Optional[str]`
- + `market_of` · function · L88-L120 — `def market_of(symbol: str, default_us: bool = False) -> Optional[str]`
- + `strip_prefix` · function · L123-L129 — `def strip_prefix(symbol: str) -> str`

### stage_one/backend/test_adjustment.py

共 1 个符号 · 被依赖 0 · 依赖外部 2

- + `check` · function · L13-L20 — `def check(name, cond)`

### stage_one/backend/test_crypto_features.py

共 15 个符号 · 被依赖 0 · 依赖外部 14

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

共 4 个符号 · 被依赖 2 · 依赖外部 0

- + `add_period_offset` · function · L16-L36 — `def add_period_offset(start_date_str: str, bars_offset: int, period: str = "1d") -> str`
- + `trading_days_between` · function · L39-L52 — `def trading_days_between(d1_str: str, d2_str: str) -> int`
- + `predict_turn_windows` · function · L55-L248 — `def predict_turn_windows( df: pd.DataFrame, swings: List[Dict[str, Any]], wave_points: Optional[Dict[str, Any]] = None, period: str = "1d", lookahead_bars: int = 25, lookback_bars: int = 3, ) -> Dict[str, Any]`
-   `_get_bar_date` · function · L76-L82 — `def _get_bar_date(idx: int) -> str`

### stage_one/frontend/postcss.config.js

共 0 个符号 · 被依赖 0 · 依赖外部 0

- （该文件无可提取符号）

### stage_one/frontend/src/App.vue

共 44 个符号 · 被依赖 1 · 依赖外部 53

-   `timeRangeLabel` · function · L772-L772 — `timeRangeLabel = (v: string): string`
-   `value` · method · L782-L782 — `get value()`
-   `selectWatchlist` · function · L803-L811 — `selectWatchlist = (sym: string)`
-   `navBack` · function · L850-L856 — `navBack = ()`
-   `navForward` · function · L858-L864 — `navForward = ()`
-   `refreshCurrent` · function · L866-L870 — `refreshCurrent = ()`
-   `selectSuggestion` · function · L872-L875 — `selectSuggestion = (symbol: string)`
-   `resolveSymbol` · function · L877-L886 — `async function resolveSymbol(raw: string): Promise<string>`
-   `handleSearch` · function · L888-L894 — `handleSearch = async ()`
-   `changePeriod` · function · L896-L905 — `changePeriod = (period: Period)`
-   `detectBackend` · function · L908-L925 — `async function detectBackend(): Promise<boolean>`
-   `retryConnection` · function · L927-L936 — `async function retryConnection()`
-   `handleRunStrategy` · function · L939-L971 — `handleRunStrategy = async (mode: string = 'swing', isManual: boolean = false)`
-   `handleClearStrategy` · function · L973-L977 — `handleClearStrategy = ()`
-   `onOpenChart` · method · L981-L988 — `onOpenChart(symbol, period)`
-   `onAddMarkers` · method · L989-L992 — `onAddMarkers(markers, sym)`
-   `onDrawLines` · method · L993-L996 — `onDrawLines(lines, sym)`
-   `onDrawBoxes` · method · L997-L1000 — `onDrawBoxes(boxes, sym)`
-   `onDrawChannelLines` · method · L1001-L1004 — `onDrawChannelLines(channelLines, sym)`
-   `onDrawWaveLines` · method · L1005-L1008 — `onDrawWaveLines(waveLines, sym)`
-   `onDrawTimeLines` · method · L1009-L1012 — `onDrawTimeLines(timeLines, sym)`
-   `onClearAnnotations` · method · L1013-L1022 — `onClearAnnotations(kind, sym)`
-   `onCaptureChart` · method · L1024-L1033 — `onCaptureChart()`
-   `toChartTime` · function · L1037-L1037 — `toChartTime = (timeStr: any): any`
-   `applyChartTheme` · function · L1039-L1058 — `applyChartTheme = (isDark: boolean)`
-   `toggleDarkMode` · function · L1060-L1065 — `toggleDarkMode = ()`
-   `initDarkMode` · function · L1067-L1072 — `initDarkMode = ()`
-   `triggerCreateGroup` · function · L1087-L1091 — `triggerCreateGroup = ()`
-   `triggerManageGroups` · function · L1093-L1096 — `triggerManageGroups = ()`
-   `handleCreateGroupSubmit` · function · L1098-L1102 — `handleCreateGroupSubmit = ()`
-   `confirmRename` · function · L1104-L1108 — `confirmRename = (id: string)`
-   `handleModalSearchInput` · function · L1111-L1129 — `handleModalSearchInput = ()`
-   `handleModalSearchSelect` · function · L1131-L1137 — `handleModalSearchSelect = (sym: string)`
-   `syncChartSize` · function · L1144-L1153 — `syncChartSize = ()`
-   `createColumnResizer` · function · L1155-L1192 — `createColumnResizer = (getStartWidth: () => number, setWidth: (w: number) => void, sign: 1 | -1)`
-   `handleMouseMove` · function · L1165-L1176 — `handleMouseMove = (moveEvent: MouseEvent)`
-   `cleanup` · function · L1178-L1187 — `cleanup = ()`
-   `formatVolumeNum` · function · L1215-L1220 — `formatVolumeNum = (vol: number): string`
-   `findPrevClose` · function · L1222-L1227 — `findPrevClose = (time: string): number | null`
-   `formatDate` · function · L1229-L1238 — `formatDate = (input: Date | string): string`
-   `updateTooltipPosition` · function · L1240-L1247 — `updateTooltipPosition = (relX: number)`
-   `initChart` · function · L1250-L1312 — `initChart = ()`
-   `handleClickOutside` · function · L1340-L1344 — `handleClickOutside = (e: MouseEvent)`
-   `handleGlobalKeydown` · function · L1357-L1392 — `handleGlobalKeydown = (e: KeyboardEvent)`

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

-   `openPanel` · function · L201-L204 — `function openPanel()`
-   `focusInput` · function · L206-L211 — `function focusInput()`
-   `onInput` · function · L217-L238 — `function onInput()`
-   `choose` · function · L240-L246 — `function choose(r: StockInfo)`
-   `close` · function · L248-L250 — `function close()`
-   `addToRecent` · function · L253-L264 — `function addToRecent(r: StockInfo)`
-   `removeFromRecent` · function · L266-L273 — `function removeFromRecent(symbol: string)`
-   `clearAllRecent` · function · L275-L279 — `function clearAllRecent()`
-   `isFavored` · function · L282-L286 — `function isFavored(symbol: string): boolean`
-   `toggleFav` · function · L289-L291 — `function toggleFav(symbol: string)`
-   `fetchDefaultRecommend` · function · L294-L302 — `async function fetchDefaultRecommend()`
-   `onKeydown` · function · L305-L323 — `function onKeydown(e: KeyboardEvent)`
-   `onGlobalKey` · function · L326-L332 — `function onGlobalKey(e: KeyboardEvent)`
-   `badge` · function · L334-L337 — `function badge(symbol: string): string`

### stage_one/frontend/src/components/StrategyPanel.vue

共 1 个符号 · 被依赖 1 · 依赖外部 1

-   `copyReviewMarkdown` · function · L327-L356 — `function copyReviewMarkdown()`

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

共 36 个符号 · 被依赖 5 · 依赖外部 0

- + `ChartMarkerItem` · interface · L15-L22 — `interface ChartMarkerItem`
- + `ChartPriceLineItem` · interface · L24-L31 — `interface ChartPriceLineItem`
- + `ChartBoxItem` · interface · L33-L42 — `interface ChartBoxItem`
- + `ChartChannelLineItem` · interface · L44-L54 — `interface ChartChannelLineItem`
- + `WavePointItem` · interface · L56-L62 — `interface WavePointItem`
- + `ChartWaveLinesItem` · interface · L64-L74 — `interface ChartWaveLinesItem`
- + `TimeLineItem` · interface · L76-L87 — `interface TimeLineItem`
- + `toChartTime` · function · L93-L125 — `function toChartTime(t: string | number): any`
- + `getTimeCoordinate` · function · L130-L193 — `function getTimeCoordinate(timeScale: any, rawTime: string | number): number | null`
-   `AnnotationOverlayPrimitive` · class · L199-L538 — `class AnnotationOverlayPrimitive implements ISeriesPrimitive<any>`
-   `constructor` · method · L209-L483 — `constructor()`
-   `draw` · method · L218-L470 — `draw(target: any)`
-   `zOrder` · method · L475-L477 — `zOrder()`
-   `renderer` · method · L478-L480 — `renderer()`
-   `setBoxes` · method · L485-L488 — `public setBoxes(boxes: ChartBoxItem[])`
-   `setChannelLines` · method · L490-L493 — `public setChannelLines(channelLines: ChartChannelLineItem[])`
-   `setWaveLines` · method · L495-L498 — `public setWaveLines(waveLines: ChartWaveLinesItem | null)`
-   `setTimeLines` · method · L500-L503 — `public setTimeLines(timeLines: TimeLineItem[])`
-   `setHighlightedTime` · method · L505-L508 — `public setHighlightedTime(timeStr: string | null)`
-   `clear` · method · L510-L517 — `public clear()`
-   `requestUpdate` · method · L519-L523 — `private requestUpdate()`
-   `attached` · method · L525-L527 — `public attached(param: any)`
-   `detached` · method · L529-L531 — `public detached()`
-   `updateAllViews` · method · L533-L533 — `public updateAllViews()`
-   `paneViews` · method · L535-L537 — `public paneViews(): readonly IPrimitivePaneView[]`
- + `useChartAnnotations` · function · L540-L719 — `function useChartAnnotations()`
- + `init` · function · L554-L577 — `function init(chart: IChartApi, series: ISeriesApi<any>, existingMarkersPlugin?: any)`
- + `setMarkers` · function · L579-L608 — `function setMarkers(markers: ChartMarkerItem[])`
- + `setPriceLines` · function · L610-L638 — `function setPriceLines(lines: ChartPriceLineItem[])`
- + `setBoxes` · function · L640-L644 — `function setBoxes(boxes: ChartBoxItem[])`
- + `setChannelLines` · function · L646-L650 — `function setChannelLines(channelLines: ChartChannelLineItem[])`
- + `setWaveLines` · function · L652-L656 — `function setWaveLines(waveLines: ChartWaveLinesItem | null)`
- + `setTimeLines` · function · L658-L662 — `function setTimeLines(lines: TimeLineItem[])`
- + `highlightTimeLine` · function · L664-L667 — `function highlightTimeLine(dateStr: string | null)`
- + `setAllAnnotations` · function · L669-L689 — `function setAllAnnotations(anno: { markers?: ChartMarkerItem[]; lines?: ChartPriceLineItem[]; boxes?: ChartBoxItem[]; channel_lines?: ChartChannelLineItem[]; channelLines?: ChartChannelLineItem[]; wave_lines?: ChartWaveLinesItem | null; waveLines?: ChartWaveLinesItem | null; time_lines?: TimeLineItem[]; timeLines?: TimeLineItem[]; })`
- + `clearAnnotations` · function · L691-L699 — `function clearAnnotations()`

### stage_one/frontend/src/composables/useChartIndicators.ts

共 5 个符号 · 被依赖 5 · 依赖外部 2

- + `useChartIndicators` · function · L6-L100 — `function useChartIndicators()`
- + `calcEMA` · function · L15-L23 — `function calcEMA(data: KLinePoint[], span: number)`
- + `calcVWAP` · function · L25-L42 — `function calcVWAP(data: KLinePoint[])`
- + `initIndicators` · function · L44-L74 — `function initIndicators(chart: IChartApi)`
- + `updateIndicators` · function · L76-L97 — `function updateIndicators(data: KLinePoint[])`

### stage_one/frontend/src/composables/useChartViewport.ts

共 13 个符号 · 被依赖 9 · 依赖外部 10

- + `generateFutureWhitespace` · function · L17-L82 — `function generateFutureWhitespace( lastTimeStr: string, period: Period, symbol: string, count: number = 24 ): { time: any }[]`
-   `toLocalDateStr` · function · L84-L89 — `toLocalDateStr = (d: Date): string`
- + `useChartViewport` · function · L91-L509 — `function useChartViewport(options: { useMockData: Ref<boolean>; isDarkMode: Ref<boolean>; currentSymbol: Ref<string>; currentPeriod: Ref<Period>; getChartInstance: () => IChartApi | null; getCandlestickSeries: () => any; getVolumeSeries: () => any; getMarkersPlugin: () => any; clearChartAnnotations: () => void; updateIndicators: (data: KLinePoint[]) => void; onBeforeLoad: () => void; onLoadSuccess: () => void; onLoadError: () => void; })`
- + `cacheKey` · function · L124-L124 — `cacheKey = (symbol: string, period: Period)`
- + `setSuppressRangeEvents` · function · L152-L154 — `setSuppressRangeEvents = (v: boolean)`
- + `updateCache` · function · L156-L158 — `updateCache = (sym: string, period: Period, data: KLinePoint[])`
- + `clearOverlays` · function · L160-L166 — `clearOverlays = ()`
- + `onVisibleLogicalRangeChanged` · function · L168-L177 — `onVisibleLogicalRangeChanged = (range: any)`
- + `setTimeRange` · function · L179-L235 — `setTimeRange = (range: string)`
- + `selectTimeRange` · function · L237-L240 — `selectTimeRange = (range: string)`
- + `highlightSRLevel` · function · L242-L250 — `highlightSRLevel = (idx: number, isHover: boolean)`
- + `scrollToSRLevel` · function · L252-L265 — `scrollToSRLevel = (level: SRLevel)`
- + `loadKlineData` · function · L267-L402 — `loadKlineData = async (targetSymbol: string, targetPeriod: Period)`

### stage_one/frontend/src/composables/useLiveQuoteSync.ts

共 7 个符号 · 被依赖 4 · 依赖外部 8

- + `resolveBarBucketTime` · function · L8-L33 — `function resolveBarBucketTime(updateTime: string, period: Period, lastBarTime: string): string`
- + `useLiveQuoteSync` · function · L35-L241 — `function useLiveQuoteSync(options: { useMockData: Ref<boolean>; currentSymbol: Ref<string>; currentPeriod: Ref<Period>; klineData: Ref<KLinePoint[]>; latestPrice: Ref<number | null>; latestChange: Ref<number>; watchlist: Ref<string[]>; getChartInstance: () => IChartApi | null; getCandlestickSeries: () => any; setSuppressRangeEvents: (v: boolean) => void; onCacheUpdate: (sym: string, period: Period, data: KLinePoint[]) => void; onIndicatorsUpdate: (data: KLinePoint[]) => void; })`
- + `refreshEngineSymbols` · function · L109-L115 — `function refreshEngineSymbols()`
- + `syncLatestBarsSilently` · function · L117-L141 — `async function syncLatestBarsSilently(sym: string, period: Period)`
- + `applyLiveQuoteToChart` · function · L143-L198 — `function applyLiveQuoteToChart(q: Quote)`
- + `startQuoteEngine` · function · L200-L218 — `async function startQuoteEngine()`
- + `stopQuoteEngine` · function · L220-L225 — `function stopQuoteEngine()`

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

共 31 个符号 · 被依赖 9 · 依赖外部 12

- + `MarketTabKey` · type · L17-L17 — `type MarketTabKey = 'all' | 'us' | 'futures';`
- + `SortKey` · type · L18-L18 — `type SortKey = 'name' | 'price' | 'change';`
- + `WatchlistPriceInfo` · interface · L20-L24 — `interface WatchlistPriceInfo`
- + `canonSym` · function · L51-L55 — `canonSym = (s: string): string`
- + `currencyOf` · function · L57-L57 — `currencyOf = (_sym: string): string`
-   `calcLatestPrice` · function · L59-L70 — `function calcLatestPrice(klines: KLinePoint[]): { price: number | null; change: number | null }`
- + `useWatchlist` · function · L72-L500 — `function useWatchlist(options: { useMockData: Ref<boolean>; liveQuoteMap: Ref<Record<string, Quote>>; quoteConfig: Ref<QuoteConfig | null>; currentSymbol: Ref<string>; onSelectSymbol: (sym: string) => void; onSymbolsChanged: () => void; })`
- + `genGroupId` · function · L93-L96 — `genGroupId = (): string`
- + `defaultGroups` · function · L98-L100 — `defaultGroups = (): WatchGroup[]`
- + `getStockName` · function · L125-L128 — `getStockName = (sym: string): string`
- + `delayFullOf` · function · L130-L133 — `delayFullOf = (sym: string): string`
- + `loadStockNameMap` · function · L135-L153 — `async function loadStockNameMap()`
- + `watchPriceInfo` · function · L155-L186 — `function watchPriceInfo(item: string): { price: number | null; change: number | null; loading: boolean; extendedPrice: number | null; extendedLabel: string; prevClose: number | null; }`
- + `secondaryLineInfo` · function · L188-L207 — `function secondaryLineInfo(item: string): { price: number | null; changePct: number | null; label: string; } | null`
- + `updateWatchlistPrices` · function · L209-L250 — `async function updateWatchlistPrices()`
- + `persistWatchlistLocal` · function · L252-L254 — `persistWatchlistLocal = ()`
- + `persistWatchlist` · function · L256-L259 — `persistWatchlist = ()`
- + `loadWatchlist` · function · L261-L310 — `loadWatchlist = async ()`
- + `isWatchlisted` · function · L312-L315 — `isWatchlisted = (sym: string): boolean`
- + `removeFromWatchlist` · function · L317-L328 — `removeFromWatchlist = (sym: string, groupId?: string)`
- + `toggleWatchlist` · function · L330-L348 — `toggleWatchlist = (sym: string)`
- + `addToActiveGroup` · function · L350-L366 — `addToActiveGroup = (sym: string)`
- + `createGroup` · function · L368-L375 — `createGroup = (rawName: string)`
- + `renameGroup` · function · L377-L383 — `renameGroup = (id: string, name: string)`
- + `deleteGroup` · function · L385-L395 — `deleteGroup = (id: string)`
- + `selectGroup` · function · L397-L400 — `selectGroup = (id: string)`
- + `toggleGroupDropdown` · function · L402-L404 — `toggleGroupDropdown = ()`
- + `setSort` · function · L406-L413 — `setSort = (key: SortKey)`
- + `matchMarketTab` · function · L415-L423 — `matchMarketTab = (sym: string, tab: MarketTabKey): boolean`
- + `clearWatchlistCache` · function · L457-L460 — `clearWatchlistCache = ()`
- + `markAllLoadingFailed` · function · L462-L466 — `markAllLoadingFailed = ()`

### stage_one/frontend/src/composables/useWebSocketControl.ts

共 4 个符号 · 被依赖 2 · 依赖外部 0

- + `WSControlMessage` · interface · L5-L30 — `interface WSControlMessage`
- + `useWebSocketControl` · function · L32-L150 — `function useWebSocketControl(handlers: { onOpenChart?: (symbol: string, period?: string) => void; onAddMarkers?: (markers: any[], symbol?: string) => void; onDrawLines?: (lines: any[], symbol?: string) => void; onDrawBoxes?: (boxes: any[], symbol?: string) => void; onDrawChannelLines?: (channelLines: any[], symbol?: string) => void; onDrawWaveLines?: (waveLines: any, symbol?: string) => void; onDrawTimeLines?: (timeLines: any[], symbol?: string) => void; onClearAnnotations?: (kind?: string, symbol?: string) => void; onRunStrategy?: (mode?: string, symbol?: string) => void; onCaptureChart?: (requestId?: string) => Promise<string | null> | (string | null); onRefreshWatchlist?: () => void; })`
- + `connect` · function · L50-L127 — `function connect()`
- + `sendState` · function · L129-L133 — `function sendState(state: { symbol: string; period: string; current_price?: number })`

### stage_one/frontend/src/main.ts

共 0 个符号 · 被依赖 0 · 依赖外部 1

- （该文件无可提取符号）

### stage_one/frontend/src/utils/api.ts

共 11 个符号 · 被依赖 18 · 依赖外部 3

- + `Period` · type · L26-L26 — `type Period = (typeof SUPPORTED_PERIODS)[number];`
- + `StockInfo` · interface · L41-L45 — `interface StockInfo`
- + `WatchGroup` · interface · L47-L51 — `interface WatchGroup`
- + `AnalysisResponse` · interface · L53-L56 — `interface AnalysisResponse`
- + `LeveragePairInfo` · interface · L58-L62 — `interface LeveragePairInfo`
- + `searchStocks` · function · L75-L87 — `async function searchStocks(keyword: string): Promise<StockInfo[]>`
- + `getKLines` · function · L90-L110 — `async function getKLines( symbol: string, period: Period = '1d', full: boolean = false, fresh: boolean = false, signal?: AbortSignal ): Promise<KLinePoint[]>`
- + `getStockAnalysis` · function · L113-L149 — `async function getStockAnalysis( symbol: string, startDate: string, endDate: string, klineCache?: KLinePoint[], period: Period = '1d' ): Promise<AnalysisResponse | null>`
- + `getWatchlist` · function · L152-L162 — `async function getWatchlist(): Promise<WatchGroup[]>`
- + `saveWatchlist` · function · L164-L172 — `async function saveWatchlist(groups: WatchGroup[]): Promise<void>`
- + `runPAStrategy` · function · L175-L195 — `async function runPAStrategy( symbol: string, period: string = '1d', mode: string = 'swing', klines?: KLinePoint[] ): Promise<any>`

### stage_one/frontend/src/utils/chartUtils.ts

共 1 个符号 · 被依赖 3 · 依赖外部 0

- + `getChartOptions` · function · L4-L90 — `getChartOptions = (isDark: boolean = false): DeepPartial<ChartOptions>`

### stage_one/frontend/src/utils/mockEngine.ts

共 11 个符号 · 被依赖 10 · 依赖外部 0

- + `KLinePoint` · interface · L3-L10 — `interface KLinePoint`
- + `SRLevel` · interface · L12-L18 — `interface SRLevel`
- + `RangeStatPoint` · interface · L20-L24 — `interface RangeStatPoint`
- + `RangeStats` · interface · L26-L34 — `interface RangeStats`
- + `generateMockKLines` · function · L53-L99 — `function generateMockKLines(symbol: string, days: number = 320, basePrice: number = 150): KLinePoint[]`
-   `parseYMD` · function · L101-L104 — `function parseYMD(t: string): [number, number, number]`
-   `bucketKey` · function · L106-L120 — `function bucketKey(t: string, period: string): string`
- + `resampleMockKLines` · function · L125-L146 — `function resampleMockKLines(daily: KLinePoint[], period: string): KLinePoint[]`
-   `findExtrema` · function · L148-L161 — `function findExtrema(data: KLinePoint[], windowSize: number = 5)`
- + `calculateSRLevels` · function · L166-L253 — `function calculateSRLevels(data: KLinePoint[], windowSize: number = 5, period: string = '1d'): SRLevel[]`
- + `calculateRangeStats` · function · L258-L321 — `function calculateRangeStats(data: KLinePoint[], sDate: string, eDate: string): RangeStats | null`

### stage_one/frontend/src/utils/quote.ts

共 23 个符号 · 被依赖 2 · 依赖外部 2

- + `QuoteStatus` · type · L19-L26 — `type QuoteStatus = | 'ok' | 'cooling' // 后端全局冷却中 | 'rate_limited' // 触发限流(403/429) | 'ip_overload' // 单 IP 窗口请求过多 | 'empty' // 接口返回但无行情 | 'error' // 网络/解析异常 | 'loading';`
- + `Quote` · interface · L29-L46 — `interface Quote`
- + `MarketCfg` · interface · L49-L57 — `interface MarketCfg`
- + `QuoteConfig` · interface · L58-L66 — `interface QuoteConfig`
- + `USSession` · type · L67-L67 — `type USSession = 'pre' | 'regular' | 'post';`
- + `EngineStatus` · interface · L70-L76 — `interface EngineStatus`
- + `SymbolMeta` · interface · L79-L86 — `interface SymbolMeta`
-   `Listener` · type · L90-L90 — `type Listener = (symbol: string, quote: Quote) => void;`
-   `QuoteEngine` · class · L92-L374 — `class QuoteEngine`
-   `setActiveSymbol` · method · L116-L125 — `setActiveSymbol(sym: string): void`
-   `loadConfig` · method · L128-L135 — `async loadConfig(): Promise<void>`
-   `setSymbols` · method · L138-L157 — `setSymbols(syms: string[]): void`
-   `subscribe` · method · L160-L163 — `subscribe(cb: Listener): () => void`
-   `onTick` · method · L166-L169 — `onTick(cb: () => void): () => void`
-   `snapshotMetas` · method · L172-L176 — `snapshotMetas(): Record<string, SymbolMeta>`
-   `start` · method · L179-L183 — `start(): void`
-   `stop` · method · L186-L195 — `stop(): void`
-   `getQuote` · method · L198-L200 — `getQuote(symbol: string): Quote | null`
-   `getMeta` · method · L203-L205 — `getMeta(symbol: string): SymbolMeta | null`
-   `getEngineStatus` · method · L208-L213 — `getEngineStatus(): { cooling: boolean; reason: string }`
-   `getMinInterval` · method · L218-L226 — `private getMinInterval(market: Market | null): number`
-   `detectUSSession` · method · L229-L240 — `private detectUSSession(): USSession`
-   `tick` · method · L243-L373 — `private async tick(): Promise<void>`

### stage_one/frontend/src/utils/symbols.ts

共 6 个符号 · 被依赖 23 · 依赖外部 0

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
