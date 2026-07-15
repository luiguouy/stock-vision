# StockVision 智能股票技术分析平台
> 多市场(美股/A股/港股) K线行情浏览 + 技术分析(支撑阻力位/区间统计) + 实时行情看板

## 技术栈
Vue 3.5, TypeScript, Tailwind CSS 4, lightweight-charts, FastAPI, pandas, scipy, SQLite

## 核心模块
- **App.vue**：单文件前端主组件(~2700行)，含全部 UI/状态/图表/导航历史
- **实时行情引擎** (quote.ts + quote_provider.py)：多市场分层轮询 + 限流冷却保护
- **数据源层** (data_provider.py)：腾讯证券(主) + Yahoo Finance(备)，主备自动故障转移
- **技术分析** (analysis.py + mockEngine.ts)：SR 极点聚类 + 区间统计，前后端双实现
- **K线缓存** (db_cache.py)：SQLite 本地持久化，TTL 24h 过期

## 关键约束
- 涨跌配色用国际惯例(emerald 涨 / red 跌)，支撑阻力装饰色用 teal/rose，不可混淆
- App.vue 为单文件架构，修改时注意上下文窗口，优先定位精确区域再编辑
- 前端 mockEngine.ts 与后端 analysis.py 的 SR 算法必须保持 1:1 同步

## 详细文档
完整结构：项目结构与代码梳理.md | 已知陷阱：技术债与已知陷阱.md | 功能进展：项目进展与功能清单.md
