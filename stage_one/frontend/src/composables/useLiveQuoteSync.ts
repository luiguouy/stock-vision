import { ref, computed, nextTick, onUnmounted, type Ref } from 'vue';
import type { IChartApi } from 'lightweight-charts';
import { getKLines, marketOf, type KLinePoint, type Period } from '../utils/api';
import { quoteEngine, getCurrentUSExtendedSession, type Quote, type SymbolMeta, type QuoteConfig } from '../utils/quote';
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
  onPatchTailBar?: (updatedBar: KLinePoint, isNewBar: boolean) => void;
  onSetKlineDataSilently?: (freshData: KLinePoint[], preserveRange?: { from: number; to: number } | null) => void;
}) {
  const {
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
    onPatchTailBar,
    onSetKlineDataSilently,
  } = options;

  const quoteConfig = ref<QuoteConfig | null>(quoteEngine.config);
  const liveQuoteMap = ref<Record<string, Quote>>(quoteEngine.getAllQuotes());
  const liveMetaMap = ref<Record<string, SymbolMeta>>({});
  const engineCooling = ref(false);

  let quoteWired = false;
  let isSyncingTail = false;
  let tailSyncTimer: ReturnType<typeof setTimeout> | null = null;

  const displayPrice = computed<number | null>(() => {
    const sym = currentSymbol.value;
    if (!sym) return latestPrice.value;
    const c = canonSym(sym) || sym;
    const q = liveQuoteMap.value[c] || liveQuoteMap.value[sym] || quoteEngine.getQuote(c);
    return q && q.price != null ? q.price : latestPrice.value;
  });

  const displayChange = computed<number>(() => {
    const sym = currentSymbol.value;
    if (!sym) return latestChange.value;
    const c = canonSym(sym) || sym;
    const q = liveQuoteMap.value[c] || liveQuoteMap.value[sym] || quoteEngine.getQuote(c);
    return q && q.changePct != null ? q.changePct : latestChange.value;
  });

  const displayExtendedInfo = computed(() => {
    if (!currentSymbol.value) return null;
    const sym = currentSymbol.value;
    if (marketOf(sym) !== 'us') return null;

    const c = canonSym(sym) || sym;
    const q = liveQuoteMap.value[c] || liveQuoteMap.value[sym] || quoteEngine.getQuote(c);
    if (!q || !q.extendedPrice || q.extendedPrice <= 0) return null;

    const label = q.extendedLabel || getCurrentUSExtendedSession();
    if (!label) return null; // 常规盘中 (09:30-16:00 ET) 不显示

    // 修正：腾讯/Yahoo接口中，盘前时段 q.price 已经是昨日正常盘收盘价，盘后/夜盘 q.price 是今日正常盘收盘价
    // 因此所有扩展时段均统一以 q.price 为基准计算涨跌幅
    const basePrice = q.price && q.price > 0 ? q.price : q.prevClose;
    if (!basePrice || basePrice <= 0) return null;
    if (Math.abs(q.extendedPrice - basePrice) < 0.01 && label === '盘后') return null;

    const chgPct = ((q.extendedPrice - basePrice) / basePrice) * 100;
    return {
      label,
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
    if (isSyncingTail || !sym) return;
    isSyncingTail = true;
    try {
      const freshData = await getKLines(sym, period, true, true);
      if (!freshData || !freshData.length) return;
      if (currentSymbol.value !== sym || currentPeriod.value !== period) return;
      onCacheUpdate(sym, period, freshData);

      const chart = getChartInstance();
      const prevRange = chart?.timeScale().getVisibleLogicalRange();
      if (onSetKlineDataSilently) {
        onSetKlineDataSilently(freshData, prevRange || null);
      } else {
        klineData.value = freshData;
        if (prevRange && chart) {
          nextTick(() => {
            setSuppressRangeEvents(true);
            chart.timeScale().setVisibleLogicalRange(prevRange);
            setSuppressRangeEvents(false);
          });
        }
      }
    } catch {
      // 静默忽略
    } finally {
      isSyncingTail = false;
    }
  }

  function applyLiveQuoteToChart(q: Quote) {
    const series = getCandlestickSeries();
    if (!series || !klineData.value.length) return;

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
      series.update({
        time: toChartTime(updatedBar.time),
        open: updatedBar.open,
        high: updatedBar.high,
        low: updatedBar.low,
        close: updatedBar.close,
      });
      if (onPatchTailBar) {
        onPatchTailBar(updatedBar, false);
      } else {
        arr[arr.length - 1] = updatedBar;
        try {
          onIndicatorsUpdate(klineData.value);
        } catch {}
      }
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
      series.update({
        time: toChartTime(newBar.time),
        open: newBar.open,
        high: newBar.high,
        low: newBar.low,
        close: newBar.close,
      });
      if (onPatchTailBar) {
        onPatchTailBar(newBar, true);
      } else {
        arr.push(newBar);
        try {
          onIndicatorsUpdate(klineData.value);
        } catch {}
      }
      if (tailSyncTimer) {
        clearTimeout(tailSyncTimer);
        tailSyncTimer = null;
      }
      tailSyncTimer = setTimeout(() => {
        tailSyncTimer = null;
        syncLatestBarsSilently(currentSymbol.value, currentPeriod.value);
      }, 1500);
    }
  }

  async function startQuoteEngine() {
    quoteConfig.value = quoteEngine.config;
    if (!quoteWired) {
      quoteEngine.subscribeBatch((batch) => {
        liveQuoteMap.value = { ...liveQuoteMap.value, ...batch };
        if (currentSymbol.value) {
          const activeCanon = canonSym(currentSymbol.value);
          const q = batch[activeCanon] || batch[currentSymbol.value];
          if (q) applyLiveQuoteToChart(q);
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

    // 核心优化：配置在后台异步拉取，首屏启动 0 毫秒立即启动轮询，绝不等待 loadConfig 网络往返
    void quoteEngine.loadConfig().then(() => {
      quoteConfig.value = quoteEngine.config;
    });
  }

  function pauseQuoteEngine() {
    quoteEngine.stop();
  }

  let lastResumeCall = 0;
  function resumeQuoteEngine() {
    const now = Date.now();
    if (now - lastResumeCall < 200) return;
    lastResumeCall = now;

    // 恢复时首先同步注入现有全部缓存行情，杜绝切回瞬间闪烁骨架屏
    const cached = quoteEngine.getAllQuotes();
    if (Object.keys(cached).length > 0) {
      liveQuoteMap.value = { ...liveQuoteMap.value, ...cached };
    }
    refreshEngineSymbols();
    quoteEngine.resume();
  }

  if (typeof window !== 'undefined') {
    (window as any).__onDesktopWindowRestored = () => {
      resumeQuoteEngine();
    };
    (window as any).__onDesktopWindowMinimized = () => {
      pauseQuoteEngine();
    };
  }

  function stopQuoteEngine() {
    quoteEngine.stop();
    engineCooling.value = false;
  }

  onUnmounted(() => {
    if (tailSyncTimer) {
      clearTimeout(tailSyncTimer);
      tailSyncTimer = null;
    }
    if (typeof window !== 'undefined') {
      delete (window as any).__onDesktopWindowRestored;
      delete (window as any).__onDesktopWindowMinimized;
    }
    stopQuoteEngine();
  });

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
    pauseQuoteEngine,
    resumeQuoteEngine,
    stopQuoteEngine,
  };
}
