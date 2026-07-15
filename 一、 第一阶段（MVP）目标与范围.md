为了稳步推进项目，第一阶段（MVP，最小可行性产品）的设计应聚焦于**“数据通路打通”**与**“基础可视化”**。此阶段的目标是实现一个端到端的闭环：用户搜索股票 -> 获取腾讯行情 -> 展示 K 线 -> 计算并绘制支撑/阻力位 -> 展示区间统计。

以下是第一阶段的具体落地实施方案。

---

## 一、 第一阶段（MVP）目标与范围

| 功能模块      | MVP 实现范围                                          | 暂不实现（留至后续阶段）                     |
| :------------ | :---------------------------------------------------- | :------------------------------------------- |
| **股票搜索**  | 支持精确代码输入（如 `MU`, `SNDK`）及基础本地匹配     | 模糊拼音搜索、智能联想输入、最近搜索记录     |
| **数据获取**  | 获取日K线历史数据（最近100-200根K线）                 | 周/月K、分钟级别K线、实时Tick推送            |
| **K线展示**   | 基础 K 线图 + 成交量图 + 十字光标                     | 缩放状态保存、多图表联动、指标切换（MACD等） |
| **支撑/阻力** | 基于局部极值（Local Extrema）聚类算法计算并绘制水平线 | 复杂的成交量密集区分析、突破失败次数评分     |
| **区间统计**  | 允许用户输入/选择两个日期，计算该区间内的最大涨跌幅   | 图形化鼠标框选统计                           |

---

## 二、 核心技术实现方案

### 1. 后端数据源获取（Python + FastAPI）

由于腾讯证券的非官方接口存在不稳定性，建议在后端使用 `requests` 或 `httpx` 直接抓取，或使用开源库 `AkShare` 作为数据提取的基础。

#### 腾讯日K线接口参考（公开接口，免Key）：
```text
https://web.ifzq.gtimg.cn/appzone/newstrend/new_chart/query?code={symbol}&type=qfqk
```
*注：`qfqk` 表示前复权日K线。支持的代码格式如 `sh600519`（沪市）、`sz000002`（深市）、`hk00700`（港股）。*

#### 基础数据获取代码示例（FastAPI 路由）：
```python
import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List

app = FastAPI()

class KLinePoint(BaseModel):
    time: str     # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float

@app.get("/api/klines", response_model=List[KLinePoint])
async def get_klines(symbol: str = Query(..., description="例如 sh600519")):
    url = f"https://web.ifzq.gtimg.cn/appzone/newstrend/new_chart/query?code={symbol}&type=qfqk"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=10.0)
            if response.status_code != 200:
                raise HTTPException(status_code=502, detail="无法连接到行情源")
            
            data = response.json()
            # 腾讯接口返回的数据结构解析（根据实际返回格式微调）
            raw_klines = data.get("data", {}).get(symbol, {}).get("qfqk", [])
            
            result = []
            for item in raw_klines:
                # 假设返回格式为 ["2023-10-27", "1800.00", "1810.00", ...]
                result.append(KLinePoint(
                    time=item[0],
                    open=float(item[1]),
                    high=float(item[3]),
                    low=float(item[4]),
                    close=float(item[2]),
                    volume=float(item[5])
                ))
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"数据解析失败: {str(e)}")
```

---

### 2. 支撑位/阻力位简易算法（Python + Pandas/SciPy）

在 MVP 阶段，采用基于**局部价格极值 + 密度聚类**的算法，既直观又易于实现。

#### 算法步骤：
1. **寻找局部极点**：使用滑动窗口（如左右各5根 K 线），找出局部最高点（Resistance 候选）和局部最低点（Support 候选）。
2. **聚类分组**：将相近的价格归为一类（可以使用简单的阈值分组或 `scipy.cluster.vq.kmeans`）。
3. **计算权重**：统计每个价格区间内极点落入的次数。次数越多的区间，其作为支撑/阻力位的强度越高。

#### 核心计算代码示例：
```python
import numpy as np
import pandas as pd
from scipy.signal import argrelextrema

def calculate_sr_levels(df: pd.DataFrame, window: int = 5, distance_pct: float = 0.015):
    """
    df 包含 high, low 列
    distance_pct: 聚类合并的阈值，例如价格相差 1.5% 以内合并
    """
    # 1. 寻找局部极大值和极小值
    df['loc_max'] = df.iloc[argrelextrema(df['high'].values, np.greater_equal, order=window)[0]]['high']
    df['loc_min'] = df.iloc[argrelextrema(df['low'].values, np.less_equal, order=window)[0]]['low']
    
    highs = df['loc_max'].dropna().values
    lows = df['loc_min'].dropna().values
    
    # 2. 简易聚类（以阻力位为例）
    resistance_levels = []
    for h in sorted(highs):
        # 检查是否可以与已有的级别合并
        merged = False
        for r in resistance_levels:
            if abs(r['price'] - h) / r['price'] < distance_pct:
                # 更新平均价格和触碰次数
                r['price'] = (r['price'] * r['count'] + h) / (r['count'] + 1)
                r['count'] += 1
                merged = True
                break
        if not merged:
            resistance_levels.append({'price': h, 'count': 1, 'type': 'resistance'})
            
    # 支撑位同理
    support_levels = []
    for l in sorted(lows):
        merged = False
        for s in support_levels:
            if abs(s['price'] - l) / s['price'] < distance_pct:
                s['price'] = (s['price'] * s['count'] + l) / (s['count'] + 1)
                s['count'] += 1
                merged = True
                break
        if not merged:
            support_levels.append({'price': l, 'count': 1, 'type': 'support'})
            
    # 按触碰次数排序，取前 3 个
    top_resistance = sorted(resistance_levels, key=lambda x: x['count'], reverse=True)[:3]
    top_support = sorted(support_levels, key=lambda x: x['count'], reverse=True)[:3]
    
    return top_resistance + top_support
```

---

### 3. 区间统计逻辑

用户选择 `start_date` 和 `end_date` 后，后端通过切片数据计算区间极值。

```python
def calculate_range_stats(df: pd.DataFrame, start_date: str, end_date: str):
    # 筛选区间数据
    mask = (df['date'] >= start_date) & (df['date'] <= end_date)
    sub_df = df.loc[mask].reset_index(drop=True)
    
    if sub_df.empty:
        return {}
        
    # 最大上涨：寻找区间内的最低点，以及该最低点之后的最高点
    min_idx = sub_df['low'].idxmin()
    after_min_df = sub_df.loc[min_idx:]
    if not after_min_df.empty:
        max_after_min_idx = after_min_df['high'].idxmax()
        max_up_pct = (sub_df.loc[max_after_min_idx]['high'] - sub_df.loc[min_idx]['low']) / sub_df.loc[min_idx]['low'] * 100
        up_start = sub_df.loc[min_idx]['date']
        up_end = sub_df.loc[max_after_min_idx]['date']
    else:
        max_up_pct, up_start, up_end = 0.0, "", ""

    # 最大下跌：寻找区间内的最高点，以及该最高点之后的最低点
    max_idx = sub_df['high'].idxmax()
    after_max_df = sub_df.loc[max_idx:]
    if not after_max_df.empty:
        min_after_max_idx = after_max_df['low'].idxmin()
        max_down_pct = (sub_df.loc[min_after_max_idx]['low'] - sub_df.loc[max_idx]['high']) / sub_df.loc[max_idx]['high'] * 100
        down_start = sub_df.loc[max_idx]['date']
        down_end = sub_df.loc[min_after_max_idx]['date']
    else:
        max_down_pct, down_start, down_end = 0.0, "", ""

    return {
        "max_rise": {"pct": round(max_up_pct, 2), "start": up_start, "end": up_end},
        "max_fall": {"pct": round(max_down_pct, 2), "start": down_start, "end": down_end}
    }
```

---

### 4. 前端 K 线图与支撑阻力绘制（Vue3 + TS）

MVP 阶段使用 **TradingView Lightweight Charts** 绘制日K和成交量，并使用其内置的 `createPriceLine` 接口绘制水平支撑位和阻力位。

#### 前端组件基础代码结构：
```vue
<template>
  <div class="chart-container">
    <div ref="chartContainer" class="chart-canvas"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch, onUnmounted } from 'vue';
import { createChart, IChartApi, ISeriesApi } from 'lightweight-charts';

const props = defineProps<{
  klineData: any[];
  srLevels: any[]; // 后端返回的支撑阻力位数据
}>();

const chartContainer = ref<HTMLElement | null>(null);
let chart: IChartApi | null = null;
let candlestickSeries: ISeriesApi<'Candlestick'> | null = null;
let priceLines: any[] = []; // 保存画线引用以便重置

const initChart = () => {
  if (!chartContainer.value) return;

  chart = createChart(chartContainer.value, {
    width: chartContainer.value.clientWidth,
    height: 500,
    layout: { backgroundColor: '#131722', textColor: '#d1d4dc' },
    grid: { vertLines: { color: '#2b2e3a' }, horzLines: { color: '#2b2e3a' } },
  });

  candlestickSeries = chart.addCandlestickSeries({
    upColor: '#26a69a',
    downColor: '#ef5350',
    borderVisible: false,
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350',
  });
};

const renderChartData = () => {
  if (!candlestickSeries || !props.klineData.length) return;
  
  // 填充K线数据
  candlestickSeries.setData(props.klineData);

  // 清除旧线
  priceLines.forEach(line => candlestickSeries?.removePriceLine(line));
  priceLines = [];

  // 绘制新的支撑阻力线
  props.srLevels.forEach(level => {
    const isSupport = level.type === 'support';
    const line = candlestickSeries!.createPriceLine({
      price: level.price,
      color: isSupport ? '#26a69a' : '#ef5350',
      lineWidth: 2,
      lineStyle: 2, // 虚线
      axisLabelVisible: true,
      title: `${isSupport ? '支撑' : '阻力'} (次数:${level.count})`,
    });
    priceLines.push(line);
  });
  
  chart?.timeScale().fitContent();
};

watch(() => [props.klineData, props.srLevels], () => {
  renderChartData();
}, { deep: true });

onMounted(() => {
  initChart();
  renderChartData();
});

onUnmounted(() => {
  if (chart) chart.remove();
});
</script>

<style scoped>
.chart-container { width: 100%; height: 500px; }
.chart-canvas { width: 100%; height: 100%; }
</style>
```

---

## 三、 第一阶段（MVP）API 契约

后端提供三个核心接口即可支撑前端基本运行：

1. **`GET /api/search`**
   * 参数：`keyword` (如 "600519" 或 "AAPL")
   * 返回：`[{ "symbol": "sh600519", "name": "贵州茅台" }]`（支持模糊解析与转换）
2. **`GET /api/klines`**
   * 参数：`symbol` (如 "sh600519")
   * 返回：日K基础数据列表
3. **`POST /api/analysis`**
   * 请求体：`{ "symbol": "sh600519", "start_date": "2023-01-01", "end_date": "2023-12-31" }`
   * 返回：
     ```json
     {
       "sr_levels": [
         { "price": 1800.5, "count": 5, "type": "resistance" },
         { "price": 1650.0, "count": 4, "type": "support" }
       ],
       "statistics": {
         "max_rise": { "pct": 15.2, "start": "2023-05-10", "end": "2023-07-12" },
         "max_fall": { "pct": -8.5, "start": "2023-02-01", "end": "2023-03-15" }
       }
     }
     ```

---

## 四、 第一阶段开发顺序建议

为了高效交付，建议按以下步骤进行开发：

1. **第 1 步：数据与分析层（Backend）**
   * 实现从腾讯（或备用源）获取日K数据。
   * 编写支撑/阻力位聚类算法，利用本地数据模拟测试，调整滑动窗口和距离阈值参数。
   * 编写区间统计逻辑。
2. **第 2 步：基础前端环境（Frontend）**
   * 使用 Vite 创建 Vue3 + TS 项目，安装 `lightweight-charts`。
   * 完成 K 线图基础配置，确保缩放、拖拽和时间轴显示正常。
3. **第 3 步：前后端连调**
   * 实现前端请求后端数据，并正确呈递 K 线图。
   * 在 K 线图上调用 `createPriceLine` API 将后端计算的支撑位、阻力位绘制出来。
4. **第 4 步：界面优化与统计面板**
   * 在前端添加简单的查询卡片（支持输入代码、选择日期区间）。
   * 显示区间最大涨跌幅的文字统计面板。