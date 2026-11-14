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

（精简版已省略逐符号明细。需要时运行 `python .workbuddy/tools/gen_project_map.py` 生成完整版。）

## 6. 使用说明（给阅读者）

1. **定位**：先看第 3 节确认改动目标的影响面，再在第 5 节拿到 `文件:行号`。
2. **不完整之处**：本文件无函数体、无全局状态、无运行时配置，逻辑与业务规则需结合源码。
3. **符号重名**：前后端存在同义映射（如 `normalize_symbol` 与 `normalizeSymbol`），按路径区分。
4. **范围**：仅 `stage_one/` 下的受版本控制源码，已排除 `node_modules/`、`.venv/`、构建产物。
