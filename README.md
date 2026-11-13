# 📈 StockVision

> **全市场跨周期智能股票技术分析平台**  
> 基于 **Vue 3 + Vite + Tailwind CSS** 前端与 **FastAPI + WebSockets** 后端构建，支持美股、A股、港股多市场实时行情、全周期前复权 K 线聚合分析、自适应支撑阻力识别，以及价格行为、动态价格通道与艾略特波浪高精度图表标注。

---

## ✨ 核心特性

- **🔍 全局证券搜索（命令面板）**
  - 支持快捷键呼出（`Ctrl+K` / `⌘K`）。
  - 覆盖美股、A股（沪深）、港股，支持代码、中英文名称及拼音缩写模糊检索。

- **⚡ 多市场实时行情与智能调度**
  - 毫秒级多源实时行情分层轮询机制。
  - 冷门标的自适应降频与防封限流护盾。
  - 美股盘前 / 盘中 / 盘后智能会话状态自适应切换。

- **📊 全周期前复权 K 线图表**
  - 基于 **TradingView Lightweight Charts v5** 构建，流畅支持超大数据量渲染。
  - 支持 **5m / 15m / 1h / 4h / 日K / 周K / 月K / 季K / 半年K / 年K** 多粒度周期自由聚合。
  - 上市至今全量历史数据自动拆股前复权（QFQ），本地 SQLite 高速缓存。

- **🎯 关键位识别与区间统计分析**
  - 自适应极值聚类算法，自动标定各周期关键支撑位与阻力位（Support & Resistance）。
  - 极值峰谷波段算法，精准统计指定起止区间内的最大连续上涨与连续下跌波段。

- **🧠 价格行为（PA）与艾略特波浪 / 动态通道标注**
  - **动态线性回归通道（LRC）**：三轨（上轨、中轴、下轨）最小二乘拟合与突破判定。
  - **艾略特波浪形态识别**：推动浪（0..5）与调整浪（0..ABC）自动拐点定位，附带当前价格延伸虚线。
  - **200 EMA 宏观门禁与盘整箱体识别**：结构化生成交易计划（Entry、SL、TP1、盈亏比）。
  - **Canvas Overlay Primitive**：自定义矢量叠加层高效渲染与原子级防竞态清屏。
  - **独立交互式报表**：一键生成并直接查看 Plotly 高保真独立单文件交互式 HTML 策略报告。

- **💼 终端级自选股管理**
  - 支持多分组创建、重命名、排序及标的拖拽管理，后端持久化跨设备同步。

---

## 🛠️ 技术架构

```
stock-vision/
├── stage_one/
│   ├── backend/                # FastAPI 后端服务
│   │   ├── main.py             # 核心 RESTful & WebSocket API
│   │   ├── analysis.py         # 支撑阻力位与区间统计算法
│   │   ├── strategy_adapter.py # 价格行为、通道拟合与波浪算法适配
│   │   ├── data_provider.py    # 历史 K 线获取与聚合（腾讯/雅虎源）
│   │   ├── quote_provider.py   # 实时行情分层轮询与缓存调度
│   │   ├── mcp_server.py       # MCP (Model Context Protocol) 接口
│   │   ├── desktop_main.py     # 桌面内嵌 Webview 运行入口
│   │   └── requirements.txt    # 后端 Python 依赖
│   └── frontend/               # Vue 3 前端工程
│       ├── src/
│       │   ├── components/     # 全局搜索、策略面板、日期选择器等
│       │   ├── composables/    # 图表标注、防抖节流与 WebSocket 逻辑
│       │   ├── utils/          # 轻量级图表工具库与 API 封装
│       │   └── App.vue         # 主工作台视图
│       ├── package.json
│       └── vite.config.ts
├── start_platform.bat          # 浏览器平台一键启动脚本
├── start_desktop.bat           # 独立桌面应用一键启动脚本
├── stockvision.cmd             # CLI 启动命令
└── sv.cmd                      # 快速启动入口
```

---

## 🚀 快速上手

### 1. 环境准备
- **Node.js**: >= 18.x
- **Python**: >= 3.10

### 2. 后端安装与启动
```bash
cd stage_one/backend

# 创建并激活虚拟环境 (可选)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动 FastAPI 服务 (默认运行在 http://127.0.0.1:8000)
python -m uvicorn main:app --reload --port 8000
```

### 3. 前端安装与启动
```bash
cd stage_one/frontend

# 安装依赖
npm install

# 启动开发服务器 (默认运行在 http://localhost:5173)
npm run dev
```

### 4. 一键启动（Windows）
在根目录下直接双击运行：
- **`start_platform.bat`**：自动启动后端与前端开发服务并在默认浏览器中打开。
- **`start_desktop.bat`**：以原生独立桌面窗口运行 StockVision。

---

## 📜 许可证

本项目基于 [MIT License](LICENSE) 开源发布。
