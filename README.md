# 📈 StockVision - 智能股票技术分析平台

一个基于 **Vue 3 + FastAPI** 的美股智能技术分析平台，提供日 K 线图表展示、支撑阻力位识别以及区间统计分析等功能。

## ✨ 功能特性

- **股票搜索** - 支持代码、中文名、拼音缩写模糊匹配（如 `AAPL`、`苹果`、`pg`）
- **日 K 线图表** - 基于 TradingView Lightweight Charts 的专业级 K 线展示
- **支撑阻力位分析** - 自动识别关键价格支撑与阻力水平
- **区间统计** - 提供价格区间的统计分析

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| **前端** | Vue 3 + TypeScript + Vite |
| **样式** | Tailwind CSS 4 |
| **图表** | Lightweight Charts (TradingView) |
| **后端** | FastAPI (Python) |
| **数据分析** | Pandas + NumPy + SciPy |

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

## 📜 License

MIT
