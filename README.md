# 📈 StockVision - 智能股票技术分析平台

基于 **Vue 3 + FastAPI** 的多市场（美股 / A股 / 港股）智能股票技术分析平台，提供日/分/周/月/年多周期 K 线图表、多市场实时行情轮询、支撑阻力位识别、区间统计分析，以及价格行为、动态价格通道与艾略特波浪理论高精度主图标注。

## ✨ 功能特性

- **全局证券搜索（命令面板）** - 支持美股、A股、港股多市场，支持代码、中英文名称、拼音缩写模糊匹配与键盘快速导航（快捷键 `Ctrl+K` / `⌘K`）
- **多市场实时行情** - 接入腾讯全市场行情源，具备分层轮询、冷门标的自适应降频、美股盘前/盘中/盘后智能调度与服务端防封限流护盾
- **多周期 K 线图表** - 5m / 15m / 1h / 4h / 日K / 周K / 月K / 季K / 半年K / 年K，基于 TradingView Lightweight Charts v5
- **全量历史 + 前复权** - 上市至今完整历史自动前复权（拆股复权），本地 SQLite 缓存与预热加速
- **支撑阻力位分析** - 多周期自适应极值聚类算法，自动识别关键支撑与阻力水平
- **区间涨跌统计** - 运行峰值/谷值算法，计算指定日期区间内的最大连续上涨与最大连续下跌波段
- **价格行为与动态通道/波浪标注（PA Strategy）** - 接入 `Investment_Assistant` 算法内核：
  - 最小二乘一元线性拟合三轨动态通道（LRC，上轨/中轴/下轨）
  - 艾略特波浪形态（推动浪 0..5 / 调整浪 0..ABC）关键拐点定位与现价延伸虚线
  - 200 EMA 宏观门禁与盘整箱体识别
  - Lightweight Charts v5 自定义 Canvas Overlay Primitive 矢量图层高性能渲染与原子防竞态清屏
  - 一键生成并查看独立的 Plotly 高保真交互式单文件 HTML 报表
- **自选股分组管理** - 专业终端式分组管理（支持分组建组、重命名、删除与拖拽），后端持久化保留

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3.5 + TypeScript + Vite + Tailwind CSS 4 |
| **图表** | Lightweight Charts v5 (TradingView) + 自定义 Canvas Overlay Primitive |
| **后端** | FastAPI (Python 3.10+) + Uvicorn + WebSockets |
| **数据与算法** | Pandas + NumPy + SciPy + Plotly + Investment_Assistant 价格行为内核 |
| **存储缓存** | SQLite (本地 K 线缓存与预热) + JSON 持久化 (自选股分组) |

## 📁 项目结构

```
stock_trading_platform/
├── stage_one/                  # 第一阶段 MVP
│   ├── backend/                # FastAPI 后端
│   │   ├── main.py             # 主入口 & API 路由
│   │   ├── analysis.py         # 技术分析算法
│   │   ├── test_endpoints.py   # 接口测试
│   │   └── requirements.txt    # Python 依赖
│   └── frontend/               # Vue 3 前端
│       ├── src/
│       │   ├── App.vue         # 主应用组件
│       │   ├── main.ts         # 入口文件
│       │   └── style.css       # 全局样式
│       ├── index.html
│       ├── package.json
│       └── vite.config.ts
└── .gitignore
```

## 🚀 快速开始

### 前置要求

- **Node.js** >= 18
- **Python** >= 3.10

### 后端启动

```bash
cd stage_one/backend

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境 (Windows)
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 启动服务 (默认 http://localhost:8000)
uvicorn main:app --reload
```

### 前端启动

```bash
cd stage_one/frontend

# 安装依赖
npm install

# 启动开发服务器 (默认 http://localhost:5173)
npm run dev
```

### API 文档

后端启动后，访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看 Swagger 交互式 API 文档。

## 📝 更新日志

每次版本更新的新增功能、Bug 修复与改进都记录在 [CHANGELOG.md](./CHANGELOG.md)。

## 📜 License

MIT
