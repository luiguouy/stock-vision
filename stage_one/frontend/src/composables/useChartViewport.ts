import { ref, shallowRef, computed, watch, onUnmounted, type Ref } from 'vue';
import type { IChartApi } from 'lightweight-charts';
import { getKLines, marketOf, type KLinePoint, type SRLevel, type Period } from '../utils/api';
import { calculateSRLevels } from '../utils/mockEngine';
import { enrichSRLevels } from '../utils/srUtils';
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

  const klineData = shallowRef<KLinePoint[]>([]);
  const MAX_CACHE_ENTRIES = 30;
  const klineCache = new Map<string, KLinePoint[]>();
  const cacheKey = (symbol: string, period: Period) => `${symbol}_${period}`;

  const getFromCache = (key: string): KLinePoint[] | undefined => {
    if (!klineCache.has(key)) return undefined;
    const val = klineCache.get(key)!;
    klineCache.delete(key);
    klineCache.set(key, val);
    return val;
  };

  const isLoading = ref(false);
  const errorMsg = ref('');
  const dataWarning = ref('');
  const srLevels = ref<SRLevel[]>([]);
  const highlightedSR = ref<number | null>(null);
  const activeTimeRange = ref('ALL');
  const showTimeRangeMenu = ref(false);

  const zoomMemoryByPeriod = new Map<Period, { fromFrac: number; toFrac: number }>();
  let suppressRangeEvents = false;
  let isTailPatching = false;
  let pendingPreserveRange: { from: number; to: number } | null = null;
  interface SRPriceLineItem {
    price: number;
    type: 'support' | 'resistance';
    line: any;
    defaultColor: string;
  }
  let priceLines: SRPriceLineItem[] = [];
  let activePulseRaf: number | null = null;
  let activeRangeRaf: number | null = null;
  let activeFlashTimer: any = null;
  let activeFlashingLine: { line: any; defaultColor: string } | null = null;
  let activeLocatingIdx: number | null = null;
  let activeLocatingLine: { line: any; defaultColor: string; title: string } | null = null;
  let locatingResetTimer: any = null;
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
    const key = cacheKey(sym, period);
    if (klineCache.has(key)) {
      klineCache.delete(key);
    } else if (klineCache.size >= MAX_CACHE_ENTRIES) {
      const oldest = klineCache.keys().next().value;
      if (oldest !== undefined) {
        klineCache.delete(oldest);
      }
    }
    klineCache.set(key, data);
  };

  const stopFlashing = () => {
    if (activePulseRaf !== null) {
      cancelAnimationFrame(activePulseRaf);
      activePulseRaf = null;
    }
    if (activeFlashTimer) {
      clearInterval(activeFlashTimer);
      activeFlashTimer = null;
    }
    if (activeFlashingLine && activeFlashingLine.line) {
      try {
        activeFlashingLine.line.applyOptions({
          lineWidth: 1.5,
          lineStyle: 2,
          color: activeFlashingLine.defaultColor,
          axisLabelVisible: true,
        });
      } catch {}
      activeFlashingLine = null;
    }
  };

  const clearOverlays = () => {
    stopFlashing();
    if (activeRangeRaf !== null) {
      cancelAnimationFrame(activeRangeRaf);
      activeRangeRaf = null;
    }
    if (locatingResetTimer) {
      clearTimeout(locatingResetTimer);
      locatingResetTimer = null;
    }
    if (activeLocatingLine && activeLocatingLine.line) {
      try {
        activeLocatingLine.line.applyOptions({
          lineWidth: 1.5,
          lineStyle: 2,
          color: activeLocatingLine.defaultColor,
        });
      } catch {}
      activeLocatingLine = null;
    }
    activeLocatingIdx = null;
    highlightedSR.value = null;
    const series = getCandlestickSeries();
    priceLines.forEach((item) => series?.removePriceLine(item.line));
    priceLines = [];
    getMarkersPlugin()?.setMarkers([]);
    clearChartAnnotations();
    try {
      getChartInstance()?.priceScale('right').setAutoScale(true);
    } catch {}
  };

  const animatePriceRange = (
    priceScale: any,
    startFrom: number,
    startTo: number,
    targetFrom: number,
    targetTo: number,
    duration = 240
  ) => {
    if (activeRangeRaf !== null) {
      cancelAnimationFrame(activeRangeRaf);
      activeRangeRaf = null;
    }
    const startTime = performance.now();
    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      // 240ms easeOutCubic view range animation
      const ease = 1 - Math.pow(1 - progress, 3);
      const currentFrom = startFrom + (targetFrom - startFrom) * ease;
      const currentTo = startTo + (targetTo - startTo) * ease;
      try {
        priceScale.setVisibleRange({ from: currentFrom, to: currentTo });
      } catch {}
      if (progress < 1) {
        activeRangeRaf = requestAnimationFrame(step);
      } else {
        activeRangeRaf = null;
      }
    };
    activeRangeRaf = requestAnimationFrame(step);
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

    try {
      chart.priceScale('right').setAutoScale(true);
    } catch {}

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

  const highlightSRLevel = (idx: number, isHover: boolean, level?: SRLevel) => {
    // 若当前正在执行该项的点击定位且未超时，移出鼠标时不清除高亮状态
    if (!isHover && activeLocatingIdx !== null && activeLocatingIdx === idx) {
      return;
    }

    highlightedSR.value = isHover ? idx : (activeLocatingIdx !== null ? activeLocatingIdx : null);

    let target: SRPriceLineItem | null = null;
    if (level && level.price !== undefined) {
      const targetPrice = Number(level.price);
      target = priceLines.find((p) => Math.abs(p.price - targetPrice) < 0.05 || Math.abs(p.price - targetPrice) / Math.max(1, targetPrice) < 0.005) || null;
    }
    if (!target && idx >= 0 && idx < priceLines.length) {
      if (!level || Math.abs(priceLines[idx].price - Number(level.price)) / Math.max(1, Number(level.price)) < 0.02) {
        target = priceLines[idx];
      }
    }

    if (target && target.line) {
      if (activeFlashingLine && activeFlashingLine.line === target.line && !isHover) {
        return;
      }
      const isSupport = target.type === 'support';
      const basisText = (level as any)?.basis || (level as any)?.desc;
      const titleText = `${isSupport ? '支撑' : '阻力'}: ${target.price.toFixed(2)}${basisText ? ` [${basisText}]` : ''}`;

      if (isHover) {
        target.line.applyOptions({
          lineWidth: 3,
          lineStyle: 0,
          axisLabelVisible: true,
          title: titleText,
        });
      } else {
        const isCurrentlyLocating = activeLocatingIdx !== null && (activeLocatingLine?.line === target.line || (activeLocatingIdx < priceLines.length && priceLines[activeLocatingIdx]?.line === target.line));
        target.line.applyOptions({
          lineWidth: isCurrentlyLocating ? 2.5 : 1.5,
          lineStyle: isCurrentlyLocating ? 0 : 2,
          color: target.defaultColor,
          axisLabelVisible: true,
          title: titleText,
        });
      }
    }
  };

  const scrollToSRLevel = (level: SRLevel, idx?: number) => {
    const chart = getChartInstance();
    const series = getCandlestickSeries();
    if (!chart || !series) return;

    const targetPrice = Number(level.price);
    if (isNaN(targetPrice)) return;

    // 清理之前的闪烁与定位常驻状态
    stopFlashing();
    if (locatingResetTimer) {
      clearTimeout(locatingResetTimer);
      locatingResetTimer = null;
    }
    if (activeLocatingLine && activeLocatingLine.line) {
      try {
        activeLocatingLine.line.applyOptions({
          lineWidth: 1.5,
          lineStyle: 2,
          color: activeLocatingLine.defaultColor,
          axisLabelVisible: true,
          title: activeLocatingLine.title,
        });
      } catch {}
      activeLocatingLine = null;
    }

    // 1. 确定在 srLevels 中的对应索引并高亮面板项
    let targetIdx = typeof idx === 'number' && idx >= 0 ? idx : -1;
    if (targetIdx < 0 || targetIdx >= srLevels.value.length) {
      targetIdx = srLevels.value.findIndex(
        (lvl) => Math.abs(Number(lvl.price) - targetPrice) < 0.05 || Math.abs(Number(lvl.price) - targetPrice) / Math.max(1, targetPrice) < 0.005
      );
    }

    if (targetIdx >= 0) {
      activeLocatingIdx = targetIdx;
      highlightedSR.value = targetIdx;
    }

    // 2. 找到对应的图表 PriceLine（容差匹配 + 接近度校验 + 缺失自愈重建）
    let targetLineItem: SRPriceLineItem | null =
      priceLines.find((p) => Math.abs(p.price - targetPrice) < 0.05 || Math.abs(p.price - targetPrice) / Math.max(1, targetPrice) < 0.005) || null;
    if (!targetLineItem && targetIdx >= 0 && targetIdx < priceLines.length) {
      const candidate = priceLines[targetIdx];
      if (Math.abs(candidate.price - targetPrice) / Math.max(1, targetPrice) < 0.02) {
        targetLineItem = candidate;
      }
    }

    const isSupport = level.type === 'support';
    const basisText = (level as any)?.basis || (level as any)?.desc;
    const titleText = `${isSupport ? '支撑' : '阻力'}: ${targetPrice.toFixed(2)}${basisText ? ` [${basisText}]` : ` [${level?.level || ''}]`}`;

    if (!targetLineItem) {
      const lineColor = isSupport
        ? isDarkMode.value
          ? '#34d399'
          : '#10b981'
        : isDarkMode.value
          ? '#fb7185'
          : '#f43f5e';
      const line = series.createPriceLine({
        price: targetPrice,
        color: lineColor,
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: titleText,
      });
      if (line) {
        targetLineItem = {
          price: targetPrice,
          type: level.type,
          line,
          defaultColor: lineColor,
        };
        priceLines.push(targetLineItem);
      }
    }

    // 3. 执行图表价格线 60fps rAF 脉冲动效 (wave = 0.5 - 0.5 * cos(t * pi * 4))
    if (targetLineItem && targetLineItem.line) {
      const origColor = targetLineItem.defaultColor;
      const flashColor = isDarkMode.value ? '#818cf8' : '#4f46e5';

      activeFlashingLine = { line: targetLineItem.line, defaultColor: origColor };
      activeLocatingLine = { line: targetLineItem.line, defaultColor: origColor, title: titleText };

      const animDuration = 1000;
      const startTime = performance.now();

      const animatePulse = (now: number) => {
        const elapsed = now - startTime;
        const t = Math.min(1, elapsed / animDuration);
        const wave = 0.5 - 0.5 * Math.cos(t * Math.PI * 4);

        if (targetLineItem && targetLineItem.line) {
          try {
            targetLineItem.line.applyOptions({
              lineWidth: 1.5 + wave * 2.0,
              lineStyle: 0,
              color: wave > 0.35 ? flashColor : origColor,
              axisLabelVisible: true,
              title: titleText,
            });
          } catch {}
        }

        if (t < 1) {
          activePulseRaf = requestAnimationFrame(animatePulse);
        } else {
          activePulseRaf = null;
          if (targetLineItem && targetLineItem.line) {
            try {
              targetLineItem.line.applyOptions({
                lineWidth: 2.5,
                lineStyle: 0,
                color: origColor,
                axisLabelVisible: true,
                title: titleText,
              });
            } catch {}
          }
        }
      };

      if (activePulseRaf !== null) {
        cancelAnimationFrame(activePulseRaf);
      }
      activePulseRaf = requestAnimationFrame(animatePulse);

      locatingResetTimer = setTimeout(() => {
        if (activeLocatingIdx === targetIdx) {
          activeLocatingIdx = null;
          if (highlightedSR.value === targetIdx) {
            highlightedSR.value = null;
          }
          if (activeLocatingLine && activeLocatingLine.line) {
            try {
              activeLocatingLine.line.applyOptions({
                lineWidth: 1.5,
                lineStyle: 2,
                color: activeLocatingLine.defaultColor,
                axisLabelVisible: true,
                title: activeLocatingLine.title,
              });
            } catch {}
            activeLocatingLine = null;
          }
        }
      }, 3000);
    }

    // 4. 定位图表视口：确保价格线在 Y 轴可见区域内（自适应获取当前价格范围并居中/留舒适边距）
    try {
      const priceScale = chart.priceScale('right');
      const timeScale = chart.timeScale();
      const logicalRange = timeScale?.getVisibleLogicalRange?.();

      let topPrice: number | null = null;
      let bottomPrice: number | null = null;

      // 4.1 优先通过 series.coordinateToPrice 获取精确可视价格区间
      if (typeof series.coordinateToPrice === 'function') {
        let paneHeight = 500;
        try {
          if (typeof chart.paneSize === 'function') {
            const size = chart.paneSize(0) || (chart as any).paneSize();
            if (size && size.height > 0) paneHeight = size.height;
          }
        } catch {}
        const pTop = series.coordinateToPrice(0);
        const pBottom = series.coordinateToPrice(paneHeight);
        if (pTop !== null && pBottom !== null && !isNaN(Number(pTop)) && !isNaN(Number(pBottom))) {
          topPrice = Math.max(Number(pTop), Number(pBottom));
          bottomPrice = Math.min(Number(pTop), Number(pBottom));
        }
      }

      // 4.2 若未获取到，通过可视 logicalRange 范围内的 K 线极值推算
      if ((topPrice === null || bottomPrice === null) && logicalRange && klineData.value.length > 0) {
        const fromIdx = Math.max(0, Math.floor(logicalRange.from));
        const toIdx = Math.min(klineData.value.length - 1, Math.ceil(logicalRange.to));
        let minL = Infinity;
        let maxH = -Infinity;
        for (let i = fromIdx; i <= toIdx; i++) {
          const bar = klineData.value[i];
          if (bar.low < minL) minL = bar.low;
          if (bar.high > maxH) maxH = bar.high;
        }
        if (minL < Infinity && maxH > -Infinity) {
          bottomPrice = minL;
          topPrice = maxH;
        }
      }

      // 4.3 兜底推算
      if (topPrice === null || bottomPrice === null) {
        if (klineData.value.length > 0) {
          const lastBars = klineData.value.slice(-60);
          bottomPrice = Math.min(...lastBars.map((b) => b.low));
          topPrice = Math.max(...lastBars.map((b) => b.high));
        } else {
          bottomPrice = targetPrice * 0.95;
          topPrice = targetPrice * 1.05;
        }
      }

      const span = Math.max(topPrice - bottomPrice, 1);
      const margin = Math.max(span * 0.15, targetPrice * 0.015);
      let newFrom = bottomPrice;
      let newTo = topPrice;
      let needsAdjust = false;

      if (targetPrice < bottomPrice + margin) {
        newFrom = targetPrice - margin;
        needsAdjust = true;
      }
      if (targetPrice > topPrice - margin) {
        newTo = targetPrice + margin;
        needsAdjust = true;
      }

      if (needsAdjust) {
        const curRange = typeof priceScale.getVisibleRange === 'function' ? priceScale.getVisibleRange() : null;
        const startFrom = curRange && Number.isFinite(curRange.from) ? curRange.from : bottomPrice;
        const startTo = curRange && Number.isFinite(curRange.to) ? curRange.to : topPrice;
        animatePriceRange(priceScale, startFrom, startTo, newFrom, newTo, 240);
      }
    } catch (e) {
      console.warn('Adjust price scale visible range error:', e);
    }

    // 5. 确保时间轴对准最新K线区域，便于直观观察右侧价格标签
    try {
      const timeScale = chart.timeScale();
      const logicalRange = timeScale?.getVisibleLogicalRange?.();
      if (logicalRange && klineData.value.length > 0) {
        const lastBarIdx = klineData.value.length - 1;
        if (logicalRange.to < lastBarIdx - 30 || logicalRange.from > lastBarIdx) {
          if (typeof timeScale.scrollToRealTime === 'function') {
            timeScale.scrollToRealTime();
          } else if (typeof timeScale.scrollToPosition === 'function') {
            timeScale.scrollToPosition(12, true);
          }
        }
      }
    } catch (e) {
      console.warn('Adjust time scale position error:', e);
    }
  };

  const renderSRLevels = (levels?: SRLevel[], summary?: any) => {
    stopFlashing();
    const series = getCandlestickSeries();
    priceLines.forEach((item) => series?.removePriceLine(item.line));
    priceLines = [];

    const rawList = levels || (klineData.value.length > 0 ? calculateSRLevels(klineData.value, 5, currentPeriod.value) : []);
    const enriched = enrichSRLevels(rawList, summary);
    srLevels.value = enriched;

    if (!series) return;

    enriched.forEach((lvl) => {
      const isSupport = lvl.type === 'support';
      const lineColor = isSupport
        ? isDarkMode.value
          ? '#34d399'
          : '#10b981'
        : isDarkMode.value
          ? '#fb7185'
          : '#f43f5e';
      const basisStr = lvl.basis ? ` [${lvl.basis}]` : ` [${lvl.level}]`;
      const line = series.createPriceLine({
        price: lvl.price,
        color: lineColor,
        lineWidth: 1.5,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `${isSupport ? '支撑' : '阻力'}: ${Number(lvl.price).toFixed(2)}${basisStr}`,
      });
      if (line) {
        priceLines.push({
          price: Number(lvl.price),
          type: lvl.type,
          line,
          defaultColor: lineColor,
        });
      }
    });
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
    try {
      getChartInstance()?.priceScale('right').setAutoScale(true);
    } catch {}

    const startedAt = performance.now();

    try {
      let klines: KLinePoint[];

      const key = cacheKey(targetSymbol, targetPeriod);
      const cached = getFromCache(key);
      if (cached) {
        klines = cached;
      } else {
        klines = await getKLines(targetSymbol, targetPeriod, true, false, signal);
        if (klines.length > 0) updateCache(targetSymbol, targetPeriod, klines);
      }

      if (reqId !== activeKlineReqId) return;

      if (!klines || klines.length === 0) {
        throw new Error('未获取到有效的K线行情数据，请确认标的代码或网络');
      }

      klineData.value = klines;

      if (klines.length > 0) {
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
        renderSRLevels();
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

  const patchTailBar = (updatedBar: KLinePoint, isNewBar: boolean) => {
    const arr = klineData.value;
    if (!arr.length) return;
    isTailPatching = true;
    try {
      if (isNewBar) {
        arr.push(updatedBar);
      } else {
        arr[arr.length - 1] = updatedBar;
      }
      // 仅更新指标线与缓存，绝不触发 candleSeries.setData() 和视口重置
      updateIndicators(arr);
      updateCache(currentSymbol.value, currentPeriod.value, arr);
    } finally {
      isTailPatching = false;
    }
  };

  const setKlineDataSilently = (freshData: KLinePoint[], preserveRange?: { from: number; to: number } | null) => {
    if (preserveRange) {
      pendingPreserveRange = preserveRange;
    }
    klineData.value = freshData;
  };

  watch(klineData, (newData) => {
    if (isTailPatching) return;
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

      if (pendingPreserveRange) {
        suppressRangeEvents = true;
        chart?.timeScale().setVisibleLogicalRange(pendingPreserveRange);
        suppressRangeEvents = false;
        pendingPreserveRange = null;
      } else {
        const n = clean.length;
        const mem = zoomMemoryByPeriod.get(currentPeriod.value);
        if (mem && n > 10) {
          const from = Math.max(-50, mem.fromFrac * n);
          const to = Math.min(n + 50, mem.toFrac * n);
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
      }
    } catch (err) {
      console.error('Error rendering chart data:', err);
    }
  });

  onUnmounted(() => {
    stopFlashing();
    if (activePulseRaf !== null) {
      cancelAnimationFrame(activePulseRaf);
      activePulseRaf = null;
    }
    if (activeRangeRaf !== null) {
      cancelAnimationFrame(activeRangeRaf);
      activeRangeRaf = null;
    }
    if (activeKlineAbortController) {
      activeKlineAbortController.abort();
      activeKlineAbortController = null;
    }
    clearOverlays();
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
    renderSRLevels,
    loadKlineData,
    patchTailBar,
    setKlineDataSilently,
  };
}
