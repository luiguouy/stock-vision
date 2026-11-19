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

（精简版已省略逐符号明细。需要时运行 `python .workbuddy/tools/gen_project_map.py` 生成完整版。）

## 6. 使用说明（给阅读者）

1. **定位**：先看第 3 节确认改动目标的影响面，再在第 5 节拿到 `文件:行号`。
2. **不完整之处**：本文件无函数体、无全局状态、无运行时配置，逻辑与业务规则需结合源码。
3. **符号重名**：前后端存在同义映射（如 `normalize_symbol` 与 `normalizeSymbol`），按路径区分。
4. **范围**：仅 `stage_one/` 下的受版本控制源码，已排除 `node_modules/`、`.venv/`、构建产物。
