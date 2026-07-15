# StockVision（智能股票技术分析平台）

> 基于 Web 的多市场（美股/A股/港股）技术分析平台，自动计算支撑阻力位、识别技术形态。

## 技术栈
Vue3, TypeScript, Vite, FastAPI, pandas, scipy, lightweight-charts v5

## 核心模块
- 数据获取层：腾讯(主,全市场)+Yahoo(美股全量优先) 故障转移 + 本地 SQLite 缓存
- 实时行情层：腾讯 qt.gtimg.cn/q= 多市场行情，分层刷新+限流护盾（配置集中在 quote_config.py）
- 技术分析层：支撑阻力位 + 区间统计（多周期自适应，前后端 1:1 同步）
- 前端展示层：K线图/搜索/自选分组/实时行情引擎(utils/quote.ts)

## 关键约束
- 代码在 stage_one/；前后端算法必须 1:1 同步
- 实时行情合规红线（全在 quote_config.py，前端只读取）：单标的≥100ms、A股≥2s/批量≥3s、港股≥2s、美股≥10s、盘前盘后≥30s、限流冷却≥30s
- 统一代码格式（大写前缀 canonical：USAAPL/SH600519/HK00700）；后端 norm_market_prefix 在腾讯边界转小写（大写会404）；名称/拼音走 normalize_symbol 自动识别
- 非美股数据源仅腾讯；演示/实时由 /api/health 自动探测（无手动开关）
- 自选栏价/涨跌基于日线末根，与图表周期/区间解耦；季半年年K 前复权须在聚合重采样前完成

## 详细文档
- 完整结构：智能股票技术分析平台_项目结构梳理.md
- 已知陷阱：技术债与已知陷阱.md
- 功能进展：项目进展与功能清单.md
