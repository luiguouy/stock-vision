import { ref, computed, nextTick, type Ref } from 'vue';
import type { IChartApi } from 'lightweight-charts';
import { getKLines, marketOf, type KLinePoint, type Period } from '../utils/api';
import { quoteEngine, type Quote, type SymbolMeta, type QuoteConfig } from '../utils/quote';
import { toChartTime } from './useChartAnnotations';
import { canonSym } from './useWatchlist';

export function resolveBarBucketTime(updateTime: string, period: Period, lastBarTime: string): string {
  if (!updateTime || updateTime.length < 10) return lastBarTime;
  const datePart = updateTime.slice(0, 10);
  const timePart = updateTime.length >= 16 ? updateTime.slice(11, 16) : '00:00';

  if (period === '1d') return datePart >= lastBarTime ? datePart : lastBarTime;
  if (['1w', '1M', '3M', '6M', '1Y'].includes(period)) return lastBarTime;

  const [hhStr, mmStr] = timePart.split(':');
  const hh = parseInt(hhStr || '0', 10);
  const mm = parseInt(mmStr || '0', 10);
  if (isNaN(hh) || isNaN(mm)) return lastBarTime;

  let bucketH = hh;
  let bucketM = 0;
  if (period === '5m') bucketM = Math.floor(mm / 5) * 5;
  else if (period === '15m') bucketM = Math.floor(mm / 15) * 15;
  else if (period === '1h') bucketM = 0;
  else if (period === '4h') {
    bucketH = Math.floor(hh / 4) * 4;
    bucketM = 0;
  }

  const formatted = `${datePart} ${String(bucketH).padStart(2, '0')}:${String(bucketM).padStart(2, '0')}`;
  return formatted >= lastBarTime ? formatted : lastBarTime;
}

export function useLiveQuoteSync(options: {
  useMockData: Ref<boolean>;
  currentSymbol: Ref<string>;
  currentPeriod: Ref<Period>;
  klineData: Ref<KLinePoint[]>;
  latestPrice: Ref<number | null>;
  latestChange: Ref<number>;
  watchlist: Ref<string[]>;
  getChartInstance: () => IChartApi | null;
  getCandlestickSeries: () => any;
  setSuppressRangeEvents: (v: boolean) => void;
  onCacheUpdate: (sym: string, period: Period, data: KLinePoint[]) => void;
  onIndicatorsUpdate: (data: KLinePoint[]) => void;
}) {
  const {
    useMockData,
    currentSymbol,
    currentPeriod,
    klineData,
    latestPrice,
    latestChange,
    watchlist,
    getChartInstance,
    getCandlestickSeries,
    setSuppressRangeEvents,
    onCacheUpdate,
    onIndicatorsUpdate,
  } = options;

  const quoteConfig = ref<QuoteConfig | null>(null);
  const liveQuoteMap = ref<Record<string, Quote>>({});
  const liveMetaMap = ref<Record<string, SymbolMeta>>({});
  const engineCooling = ref(false);

  let quoteWired = false;
  let isSyncingTail = false;

  const displayPrice = computed<number | null>(() => {
    if (useMockData.value) return latestPrice.value;
    const q = currentSymbol.value ? liveQuoteMap.value[currentSymbol.value] : null;
    return q && q.price != null ? q.price : latestPrice.value;
  });

  const displayChange = computed<number>(() => {
    if (useMockData.value) return latestChange.value;
    const q = currentSymbol.value ? liveQuoteMap.value[currentSymbol.value] : null;
    return q && q.changePct != null ? q.changePct : latestChange.value;
  });

  const displayExtendedInfo = computed(() => {
    if (useMockData.value || !currentSymbol.value) return null;
    const q = liveQuoteMap.value[currentSymbol.value];
    if (!q || !q.extendedPrice || !q.prevClose || q.prevClose <= 0) return null;
    if (q.price != null && Math.abs(q.extendedPrice - q.price) < 0.01) return null;
    const chgPct = ((q.extendedPrice - q.prevClose) / q.prevClose) * 100;
    return {
      label: q.extendedLabel || '盘后',
      price: q.extendedPrice,
      changePct: chgPct,
    };
  });

  const currentRefreshCycle = computed<number>(() => {
    const meta = currentSymbol.value ? liveMetaMap.value[currentSymbol.value] : null;
    const base = marketOf(currentSymbol.value) === 'us' ? 10 : 2;
    const min = quoteConfig.value?.markets[marketOf(currentSymbol.value) || 'us']?.minInterval ?? base;
    return Math.max(1, Math.round(min * (meta?.intervalMul ?? 1)));
  });

  const quoteEngineStatus = computed<{ cooling: boolean; reason: string }>(() => ({
    cooling: engineCooling.value,
    reason: engineCooling.value ? 'cooling' : '',
  }));

  function refreshEngineSymbols() {
    if (currentSymbol.value) {
      quoteEngine.setActiveSymbol(currentSymbol.value);
    }
    const syms = [currentSymbol.value, ...watchlist.value].filter(Boolean);
    quoteEngine.setSymbols(syms);
  }

  async function syncLatestBarsSilently(sym: string, period: Period) {
    if (useMockData.value || isSyncingTail || !sym) return;
    isSyncingTail = true;
    try {
      const freshData = await getKLines(sym, period, true, true);
      if (!freshData || !freshData.length) return;
      if (currentSymbol.value !== sym || currentPeriod.value !== period) return;
      onCacheUpdate(sym, period, freshData);

      const chart = getChartInstance();
      const prevRange = chart?.timeScale().getVisibleLogicalRange();
      klineData.value = freshData;
      if (prevRange && chart) {
        nextTick(() => {
          setSuppressRangeEvents(true);
          chart.timeScale().setVisibleLogicalRange(prevRange);
          setSuppressRangeEvents(false);
        });
      }
    } catch {
      // 静默忽略
    } finally {
      isSyncingTail = false;
    }
  }

  function applyLiveQuoteToChart(q: Quote) {
    const series = getCandlestickSeries();
    if (useMockData.value || !series || !klineData.value.length) return;

    const isIntraday = ['5m', '15m', '1h', '4h'].includes(currentPeriod.value);
    const activePrice = isIntraday && q.extendedPrice && q.extendedPrice > 0 ? q.extendedPrice : q.price;
    if (q.status !== 'ok' || activePrice == null || activePrice <= 0) return;

    const arr = klineData.value;
    const lastBar = arr[arr.length - 1];
    const bucketTime = resolveBarBucketTime(q.updateTime, currentPeriod.value, lastBar.time);

    if (bucketTime === lastBar.time) {
      const updatedBar: KLinePoint = {
        ...lastBar,
        close: activePrice,
        high: Math.max(lastBar.high, activePrice, currentPeriod.value === '1d' && q.high ? q.high : activePrice),
        low: Math.min(lastBar.low, activePrice, currentPeriod.value === '1d' && q.low ? q.low : activePrice),
      };
      arr[arr.length - 1] = updatedBar;
      series.update({
        time: toChartTime(updatedBar.time),
        open: updatedBar.open,
        high: updatedBar.high,
        low: updatedBar.low,
        close: updatedBar.close,
      });
      try {
        onIndicatorsUpdate(klineData.value);
      } catch {}
    } else if (bucketTime > lastBar.time) {
      const openPrice = currentPeriod.value === '1d' && q.open ? q.open : activePrice;
      const newBar: KLinePoint = {
        time: bucketTime,
        open: openPrice,
        high: Math.max(openPrice, activePrice),
        low: Math.min(openPrice, activePrice),
        close: activePrice,
        volume: 0,
      };
      arr.push(newBar);
      series.update({
        time: toChartTime(newBar.time),
        open: newBar.open,
        high: newBar.high,
        low: newBar.low,
        close: newBar.close,
      });
      try {
        onIndicatorsUpdate(klineData.value);
      } catch {}
      setTimeout(() => {
        syncLatestBarsSilently(currentSymbol.value, currentPeriod.value);
      }, 1500);
    }
  }

  async function startQuoteEngine() {
    await quoteEngine.loadConfig();
    quoteConfig.value = quoteEngine.config;
    if (!quoteWired) {
      quoteEngine.subscribe((sym, q) => {
        liveQuoteMap.value = { ...liveQuoteMap.value, [sym]: q };
        if (currentSymbol.value && canonSym(sym) === canonSym(currentSymbol.value)) {
          applyLiveQuoteToChart(q);
        }
      });
      quoteEngine.onTick(() => {
        liveMetaMap.value = quoteEngine.snapshotMetas();
        engineCooling.value = quoteEngine.getEngineStatus().cooling;
      });
      quoteWired = true;
    }
    refreshEngineSymbols();
    quoteEngine.start();
  }

  function stopQuoteEngine() {
    quoteEngine.stop();
    liveQuoteMap.value = {};
    liveMetaMap.value = {};
    engineCooling.value = false;
  }

  return {
    quoteConfig,
    liveQuoteMap,
    liveMetaMap,
    engineCooling,
    displayPrice,
    displayChange,
    displayExtendedInfo,
    currentRefreshCycle,
    quoteEngineStatus,
    refreshEngineSymbols,
    startQuoteEngine,
    stopQuoteEngine,
  };
}
