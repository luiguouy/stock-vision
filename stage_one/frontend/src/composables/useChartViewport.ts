import { ref, computed, watch, type Ref } from 'vue';
import type { IChartApi } from 'lightweight-charts';
import { getKLines, generateMockKLines, stripPrefix, marketOf, type KLinePoint, type SRLevel, type Period } from '../utils/api';
import { calculateSRLevels, resampleMockKLines } from '../utils/mockEngine';
import { toChartTime } from './useChartAnnotations';

export const TIME_RANGES = [
  { label: '近1月', value: 'r1m' },
  { label: '近3月', value: 'r3m' },
  { label: '近6月', value: 'r6m' },
  { label: '近1年', value: 'r1y' },
  { label: '全部', value: 'ALL' },
];

const MIN_SKELETON_MS = 700;

export function generateFutureWhitespace(
  lastTimeStr: string,
  period: Period,
  symbol: string,
  count: number = 24
): { time: any }[] {
  const whitespace: { time: any }[] = [];
  if (!lastTimeStr) return whitespace;

  const isCrypto = marketOf(symbol) === 'crypto';

  if (['5m', '15m', '1h', '4h'].includes(period)) {
    const startSec = toChartTime(lastTimeStr);
    if (typeof startSec === 'number' && !isNaN(startSec)) {
      const stepSecMap: Record<string, number> = {
        '5m': 5 * 60,
        '15m': 15 * 60,
        '1h': 60 * 60,
        '4h': 4 * 60 * 60,
      };
      const stepSec = stepSecMap[period] || 300;
      let currSec = startSec;
      let added = 0;
      while (added < count) {
        currSec += stepSec;
        if (!isCrypto) {
          const d = new Date(currSec * 1000);
          const day = d.getUTCDay();
          if (day === 0 || day === 6) continue;
        }
        whitespace.push({ time: currSec });
        added++;
      }
    }
    return whitespace;
  }

  const dateOnly = lastTimeStr.slice(0, 10);
  const curr = new Date(`${dateOnly}T00:00:00`);
  if (isNaN(curr.getTime())) return whitespace;

  const stepDaysMap: Record<string, number> = {
    '1d': 1,
    '1w': 7,
    '1M': 30,
    '3M': 90,
    '6M': 180,
    '1Y': 365,
  };
  const stepDays = stepDaysMap[period] || 1;

  let added = 0;
  while (added < count) {
    curr.setDate(curr.getDate() + stepDays);
    if (period === '1d' && !isCrypto) {
      const day = curr.getDay();
      if (day === 0 || day === 6) continue;
    }
    const y = curr.getFullYear();
    const m = String(curr.getMonth() + 1).padStart(2, '0');
    const d = String(curr.getDate()).padStart(2, '0');
    whitespace.push({ time: `${y}-${m}-${d}` });
    added++;
  }
  return whitespace;
}

const toLocalDateStr = (d: Date): string => {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
};

export function useChartViewport(options: {
  useMockData: Ref<boolean>;
  isDarkMode: Ref<boolean>;
  currentSymbol: Ref<string>;
  currentPeriod: Ref<Period>;
  getChartInstance: () => IChartApi | null;
  getCandlestickSeries: () => any;
  getVolumeSeries: () => any;
  getMarkersPlugin: () => any;
  clearChartAnnotations: () => void;
  updateIndicators: (data: KLinePoint[]) => void;
  onBeforeLoad: () => void;
  onLoadSuccess: () => void;
  onLoadError: () => void;
}) {
  const {
    useMockData,
    isDarkMode,
    currentSymbol,
    currentPeriod,
    getChartInstance,
    getCandlestickSeries,
    getVolumeSeries,
    getMarkersPlugin,
    clearChartAnnotations,
    updateIndicators,
    onBeforeLoad,
    onLoadSuccess,
    onLoadError,
  } = options;

  const klineData = ref<KLinePoint[]>([]);
  const klineCache = new Map<string, KLinePoint[]>();
  const cacheKey = (symbol: string, period: Period) => `${symbol}_${period}`;

  const isLoading = ref(false);
  const errorMsg = ref('');
  const dataWarning = ref('');
  const srLevels = ref<SRLevel[]>([]);
  const highlightedSR = ref<number | null>(null);
  const activeTimeRange = ref('ALL');
  const showTimeRangeMenu = ref(false);

  const zoomMemoryByPeriod = new Map<Period, { fromFrac: number; toFrac: number }>();
  let suppressRangeEvents = false;
  let priceLines: any[] = [];
  let activeKlineReqId = 0;
  let activeKlineAbortController: AbortController | null = null;

  const latestPrice = computed(() => {
    if (klineData.value.length === 0) return null;
    return klineData.value[klineData.value.length - 1].close;
  });

  const latestChange = computed(() => {
    if (klineData.value.length < 2) return 0;
    const current = klineData.value[klineData.value.length - 1].close;
    const previous = klineData.value[klineData.value.length - 2].close;
    return ((current - previous) / previous) * 100;
  });

  const setSuppressRangeEvents = (v: boolean) => {
    suppressRangeEvents = v;
  };

  const updateCache = (sym: string, period: Period, data: KLinePoint[]) => {
    klineCache.set(cacheKey(sym, period), data);
  };

  const clearOverlays = () => {
    const series = getCandlestickSeries();
    priceLines.forEach((line) => series?.removePriceLine(line));
    priceLines = [];
    getMarkersPlugin()?.setMarkers([]);
    clearChartAnnotations();
  };

  const onVisibleLogicalRangeChanged = (range: any) => {
    if (suppressRangeEvents || !range) return;
    const n = klineData.value.length;
    if (n < 2) return;
    const fromFrac = range.from / n;
    const toFrac = range.to / n;
    if (!isFinite(fromFrac) || !isFinite(toFrac)) return;
    if (toFrac - fromFrac < 0.0005) return;
    zoomMemoryByPeriod.set(currentPeriod.value, { fromFrac, toFrac });
  };

  const setTimeRange = (range: string) => {
    const chart = getChartInstance();
    if (!chart || !klineData.value.length) return;

    activeTimeRange.value = range;
    const data = klineData.value;
    const n = data.length;
    const lastDate = new Date(data[n - 1].time);
    let startDate: Date;

    switch (range) {
      case 'r1m':
        startDate = new Date(lastDate);
        startDate.setMonth(startDate.getMonth() - 1);
        break;
      case 'r3m':
        startDate = new Date(lastDate);
        startDate.setMonth(startDate.getMonth() - 3);
        break;
      case 'r6m':
        startDate = new Date(lastDate);
        startDate.setMonth(startDate.getMonth() - 6);
        break;
      case 'r1y':
        startDate = new Date(lastDate);
        startDate.setFullYear(startDate.getFullYear() - 1);
        break;
      case 'ALL':
      default:
        zoomMemoryByPeriod.delete(currentPeriod.value);
        chart.timeScale().fitContent();
        return;
    }

    const startStr = toLocalDateStr(startDate);
    let fromIndex = n - 1;
    for (let i = n - 1; i >= 0; i--) {
      if (data[i].time <= startStr) {
        fromIndex = i;
        break;
      }
    }

    const toIndex = n - 1;
    if (toIndex - fromIndex >= 1) {
      suppressRangeEvents = true;
      zoomMemoryByPeriod.set(currentPeriod.value, {
        fromFrac: fromIndex / n,
        toFrac: toIndex / n,
      });
      chart.timeScale().setVisibleLogicalRange({ from: fromIndex, to: toIndex });
      suppressRangeEvents = false;
    } else {
      zoomMemoryByPeriod.delete(currentPeriod.value);
      chart.timeScale().fitContent();
    }
  };

  const selectTimeRange = (range: string) => {
    showTimeRangeMenu.value = false;
    setTimeRange(range);
  };

  const highlightSRLevel = (idx: number, isHover: boolean) => {
    highlightedSR.value = isHover ? idx : null;
    if (priceLines[idx]) {
      priceLines[idx].applyOptions({
        lineWidth: isHover ? 3 : 1.5,
        lineStyle: isHover ? 0 : 2,
      });
    }
  };

  const scrollToSRLevel = (level: SRLevel) => {
    const chart = getChartInstance();
    if (!chart) return;
    const currentRange = chart.timeScale().getVisibleLogicalRange();
    if (currentRange) {
      const idx = srLevels.value.indexOf(level);
      if (idx >= 0) {
        highlightedSR.value = idx;
        setTimeout(() => {
          highlightedSR.value = null;
        }, 1000);
      }
    }
  };

  const loadKlineData = async (targetSymbol: string, targetPeriod: Period) => {
    if (!targetSymbol) return;
    const reqId = ++activeKlineReqId;

    if (activeKlineAbortController) {
      activeKlineAbortController.abort();
      activeKlineAbortController = null;
    }
    activeKlineAbortController = new AbortController();
    const signal = activeKlineAbortController.signal;

    const isSymbolChanged = currentSymbol.value !== targetSymbol;
    currentSymbol.value = targetSymbol;
    currentPeriod.value = targetPeriod;

    if (isSymbolChanged) {
      klineData.value = [];
    }

    isLoading.value = true;
    errorMsg.value = '';
    srLevels.value = [];
    activeTimeRange.value = 'ALL';

    onBeforeLoad();
    clearOverlays();

    const startedAt = performance.now();

    try {
      let klines: KLinePoint[];

      if (useMockData.value) {
        const basePriceMap: Record<string, number> = {
          AAPL: 180,
          NVDA: 450,
          TSLA: 250,
          MSFT: 370,
          GOOGL: 140,
          AMZN: 175,
          META: 480,
          AMD: 160,
          MU: 130,
          SNDK: 95,
        };
        const basePrice = basePriceMap[stripPrefix(targetSymbol)] || 150;
        klines = generateMockKLines(stripPrefix(targetSymbol), 4500, basePrice);
        klines = resampleMockKLines(klines, targetPeriod);
      } else {
        const key = cacheKey(targetSymbol, targetPeriod);
        if (klineCache.has(key)) {
          klines = klineCache.get(key)!;
        } else {
          klines = await getKLines(targetSymbol, targetPeriod, true, false, signal);
          if (klines.length > 0) klineCache.set(key, klines);
        }
      }

      if (reqId !== activeKlineReqId) return;

      if (!klines || klines.length === 0) {
        throw new Error('未获取到有效的K线行情数据');
      }

      klineData.value = klines;

      if (!useMockData.value && klines.length > 0) {
        const p = targetPeriod;
        const n = klines.length;
        if (p === '1d' && n < 400) {
          dataWarning.value = `⚠️ 当前仅返回 ${n} 根日K线，可能不是该股票的完整历史（数据源被限流或网络异常时会发生）。请稍后重试，或确认后端数据源可用。`;
        } else if ((p === '3M' && n < 4) || (p === '6M' && n < 2) || (p === '1Y' && n < 2)) {
          const labels: Record<string, string> = { '3M': '季K', '6M': '半年K', '1Y': '年K' };
          dataWarning.value = `⚠️ 该股票历史数据较短，当前仅 ${n} 根${labels[p] || p}（可能是退市/新上市股票）。建议切换到更短周期（如日K）查看更多细节。`;
        } else {
          dataWarning.value = '';
        }
      } else {
        dataWarning.value = '';
      }

      clearOverlays();

      if (klines.length > 0) {
        srLevels.value = calculateSRLevels(klines, 5, targetPeriod);
        const series = getCandlestickSeries();
        srLevels.value.forEach((lvl) => {
          const isSupport = lvl.type === 'support';
          const lineColor = isSupport
            ? isDarkMode.value
              ? '#34d399'
              : '#10b981'
            : isDarkMode.value
              ? '#fb7185'
              : '#f43f5e';
          const line = series?.createPriceLine({
            price: lvl.price,
            color: lineColor,
            lineWidth: 1.5,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `${isSupport ? '支撑' : '阻力'}: ${lvl.price.toFixed(2)} [${lvl.level}]`,
          });
          if (line) priceLines.push(line);
        });
      }

      onLoadSuccess();
    } catch (err: any) {
      if (err.name === 'AbortError' || signal.aborted) {
        if (reqId === activeKlineReqId) {
          klineData.value = [];
        }
        return;
      }
      if (reqId !== activeKlineReqId) return;

      errorMsg.value = err.message || '网络连接失败，无法加载行情图';
      klineData.value = [];
      currentSymbol.value = '';
      clearOverlays();
      onLoadError();
    } finally {
      if (reqId === activeKlineReqId) {
        const elapsed = performance.now() - startedAt;
        const remain = Math.max(0, MIN_SKELETON_MS - elapsed);
        if (remain > 0) {
          setTimeout(() => {
            if (reqId === activeKlineReqId) isLoading.value = false;
          }, remain);
        } else {
          isLoading.value = false;
        }
      }
    }
  };

  watch(klineData, (newData) => {
    const candleSeries = getCandlestickSeries();
    const volSeries = getVolumeSeries();
    const chart = getChartInstance();
    if (!candleSeries || !volSeries) return;

    if (!newData || newData.length === 0) {
      try {
        candleSeries.setData([]);
        volSeries.setData([]);
      } catch {}
      return;
    }

    try {
      const sorted = [...newData].sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
      const seen = new Set<string>();
      const clean = sorted.filter((d) => {
        if (seen.has(d.time)) return false;
        seen.add(d.time);
        return true;
      });

      const candlePoints = clean
        .map((d) => ({
          time: toChartTime(d.time),
          open: d.open,
          close: d.close,
          high: d.high,
          low: d.low,
        }))
        .filter((p) => p.time !== '' && p.time !== undefined && p.time !== null);

      const lastBar = clean[clean.length - 1];
      const futureWhitespace = generateFutureWhitespace(
        lastBar.time,
        currentPeriod.value,
        currentSymbol.value,
        24
      );
      const whitespacePoints = futureWhitespace
        .map((w) => ({ time: toChartTime(w.time) }))
        .filter((p) => p.time !== '' && p.time !== undefined && p.time !== null);

      candleSeries.setData([...candlePoints, ...whitespacePoints]);

      const upVol = isDarkMode.value ? 'rgba(52, 211, 153, 0.35)' : 'rgba(16, 185, 129, 0.25)';
      const downVol = isDarkMode.value ? 'rgba(251, 113, 133, 0.35)' : 'rgba(244, 63, 94, 0.25)';
      volSeries.setData(
        clean
          .map((d) => ({
            time: toChartTime(d.time),
            value: d.volume,
            color: d.close >= d.open ? upVol : downVol,
          }))
          .filter((p) => p.time !== '' && p.time !== undefined && p.time !== null)
      );

      updateIndicators(clean);

      const n = clean.length;
      const mem = zoomMemoryByPeriod.get(currentPeriod.value);
      if (mem && n > 10) {
        const from = Math.max(0, Math.min(n, mem.fromFrac * n));
        const to = Math.max(0, Math.min(n, mem.toFrac * n));
        if (to - from >= 1) {
          suppressRangeEvents = true;
          chart?.timeScale().setVisibleLogicalRange({ from, to });
          suppressRangeEvents = false;
        } else {
          chart?.timeScale().fitContent();
        }
      } else if (n > 140) {
        suppressRangeEvents = true;
        chart?.timeScale().setVisibleLogicalRange({ from: n - 140, to: n + 12 });
        suppressRangeEvents = false;
      } else {
        chart?.timeScale().fitContent();
      }
    } catch (err) {
      console.error('Error rendering chart data:', err);
    }
  });

  return {
    klineData,
    isLoading,
    errorMsg,
    dataWarning,
    srLevels,
    highlightedSR,
    activeTimeRange,
    showTimeRangeMenu,
    latestPrice,
    latestChange,
    setSuppressRangeEvents,
    updateCache,
    clearOverlays,
    onVisibleLogicalRangeChanged,
    setTimeRange,
    selectTimeRange,
    highlightSRLevel,
    scrollToSRLevel,
    loadKlineData,
  };
}
