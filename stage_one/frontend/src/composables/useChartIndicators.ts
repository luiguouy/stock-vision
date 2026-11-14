import { ref } from 'vue';
import { LineSeries, type IChartApi, type ISeriesApi } from 'lightweight-charts';
import type { KLinePoint } from '../utils/api';
import { toChartTime } from './useChartAnnotations';

export function useChartIndicators() {
  const showEMA = ref(false);
  const showVWAP = ref(false);

  let ema20Series: ISeriesApi<'Line'> | null = null;
  let ema50Series: ISeriesApi<'Line'> | null = null;
  let ema200Series: ISeriesApi<'Line'> | null = null;
  let vwapSeries: ISeriesApi<'Line'> | null = null;

  function calcEMA(data: KLinePoint[], span: number) {
    if (!data.length) return [];
    const k = 2 / (span + 1);
    let ema = data[0].close;
    return data.map((d, idx) => {
      if (idx > 0) ema = d.close * k + ema * (1 - k);
      return { time: toChartTime(d.time), value: Number(ema.toFixed(3)) };
    });
  }

  function calcVWAP(data: KLinePoint[]) {
    let cumPV = 0;
    let cumVol = 0;
    let currentDay = '';
    return data.map((d) => {
      const day = d.time.slice(0, 10);
      if (day !== currentDay) {
        currentDay = day;
        cumPV = 0;
        cumVol = 0;
      }
      const typicalPrice = (d.high + d.low + d.close) / 3;
      const vol = d.volume || 1;
      cumPV += typicalPrice * vol;
      cumVol += vol;
      return { time: toChartTime(d.time), value: Number((cumPV / cumVol).toFixed(3)) };
    });
  }

  function initIndicators(chart: IChartApi) {
    ema20Series = chart.addSeries(LineSeries, {
      color: '#38bdf8',
      lineWidth: 1,
      title: 'EMA20',
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ema50Series = chart.addSeries(LineSeries, {
      color: '#f59e0b',
      lineWidth: 1,
      title: 'EMA50',
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ema200Series = chart.addSeries(LineSeries, {
      color: '#a855f7',
      lineWidth: 2,
      title: 'EMA200',
      priceLineVisible: false,
      lastValueVisible: false,
    });
    vwapSeries = chart.addSeries(LineSeries, {
      color: '#ec4899',
      lineWidth: 1,
      lineStyle: 2,
      title: 'VWAP',
      priceLineVisible: false,
      lastValueVisible: false,
    });
  }

  function updateIndicators(data: KLinePoint[]) {
    if (!ema20Series || !ema50Series || !ema200Series || !vwapSeries) return;
    if (!data || !data.length) {
      ema20Series.setData([]);
      ema50Series.setData([]);
      ema200Series.setData([]);
      vwapSeries.setData([]);
      return;
    }
    const sorted = [...data].sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
    const seen = new Set<string>();
    const clean = sorted.filter((d) => {
      if (seen.has(d.time)) return false;
      seen.add(d.time);
      return true;
    });

    ema20Series.setData(showEMA.value ? calcEMA(clean, 20) : []);
    ema50Series.setData(showEMA.value ? calcEMA(clean, 50) : []);
    ema200Series.setData(showEMA.value ? calcEMA(clean, 200) : []);
    vwapSeries.setData(showVWAP.value ? calcVWAP(clean) : []);
  }

  return { showEMA, showVWAP, initIndicators, updateIndicators };
}
