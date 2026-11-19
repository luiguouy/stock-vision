import { ref, computed, type Ref } from 'vue';
import {
  getWatchlist,
  saveWatchlist,
  BASE_URL,
  normalizeSymbol,
  stripPrefix,
  marketOf,
  formatSymbol,
  type WatchGroup,
} from '../utils/api';
import { quoteEngine, type Quote, type QuoteConfig } from '../utils/quote';

export type MarketTabKey = 'all' | 'us' | 'futures';
export type SortKey = 'name' | 'price' | 'change';

export interface WatchlistPriceInfo {
  price: number | null;
  change: number | null;
  loading: boolean;
}

export interface WatchlistRowInfo {
  price: number | null;
  change: number | null;
  formattedPrice: string;
  formattedChange: string;
  isUp: boolean;
  secondary: {
    price: string;
    changePct: number | null;
    formattedChange: string | null;
    label: string;
    isUp: boolean;
  } | null;
  status?: string;
  reason?: string;
}

export const MARKET_TABS: { key: MarketTabKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'us', label: '美股' },
  { key: 'futures', label: '期货' },
];

const DELAY_LABEL_FALLBACK: Record<string, { label: string; full: string }> = {
  us: { label: '15m 延迟', full: '美股 公开数据源 (15分钟延迟)' },
  futures: { label: '实时快照', full: '期货 CME 连续合约实时快照' },
  crypto: { label: '实时行情', full: '加密货币 Yahoo 实时行情' },
};

export const canonSym = (s: string): string => {
  const n = normalizeSymbol(s);
  if (!n) return n;
  return n.replace(/^(US|SH|SZ|HK)/i, (m) => m.toLowerCase());
};

export const currencyOf = (_sym: string): string => '$';

export function useWatchlist(options: {
  liveQuoteMap: Ref<Record<string, Quote>>;
  quoteConfig: Ref<QuoteConfig | null>;
  currentSymbol: Ref<string>;
  onSelectSymbol: (sym: string) => void;
  onSymbolsChanged: () => void;
}) {
  const { liveQuoteMap, quoteConfig, currentSymbol, onSelectSymbol, onSymbolsChanged } = options;

  const genGroupId = (): string =>
    typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `g${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`;

  const defaultGroups = (): WatchGroup[] => [
    { id: genGroupId(), name: '我的自选', stocks: ['usAAPL', 'usNVDA', 'usAMD', 'usTSLA', 'usQQQ'] },
  ];

  function getInitialGroups(): WatchGroup[] {
    try {
      const local = localStorage.getItem('stock_watchlist');
      if (local) {
        const parsed = JSON.parse(local);
        if (Array.isArray(parsed) && parsed.length) {
          return [{ id: genGroupId(), name: '我的自选', stocks: parsed.map((s: string) => canonSym(s) || s) }];
        } else if (parsed && Array.isArray(parsed.groups) && parsed.groups.length) {
          return (parsed.groups as WatchGroup[]).map((g) => ({
            id: g.id || genGroupId(),
            name: g.name || '未命名分组',
            stocks: (g.stocks || []).map((s: string) => canonSym(s) || s),
          }));
        }
      }
    } catch {}
    return defaultGroups();
  }

  const watchGroups = ref<WatchGroup[]>(getInitialGroups());
  const watchlistPriceMap = ref<Record<string, WatchlistPriceInfo>>({});
  const stockNameMap = ref<Record<string, string>>({});

  const activeMarketTab = ref<MarketTabKey>('all');
  const activeGroupId = ref<string>('all');
  const showGroupDropdown = ref(false);
  const sortBy = ref<SortKey | null>(null);
  const sortDir = ref<'asc' | 'desc'>('desc');

  const watchlist = computed<string[]>(() => {
    const set = new Set<string>();
    for (const g of watchGroups.value) {
      for (const s of g.stocks) {
        const n = canonSym(s);
        if (n) set.add(n);
      }
    }
    return [...set];
  });

  const activeGroupName = computed(() => {
    if (activeGroupId.value === 'all') return '选择分组';
    const g = watchGroups.value.find((x) => x.id === activeGroupId.value);
    return g ? g.name : '选择分组';
  });

  const isCurrentGroupEmpty = computed(() => {
    if (activeGroupId.value === 'all') return false;
    const g = watchGroups.value.find((x) => x.id === activeGroupId.value);
    return g ? g.stocks.length === 0 : false;
  });

  const getStockName = (sym: string): string => {
    const normalized = canonSym(sym);
    return stockNameMap.value[normalized] || stockNameMap.value[sym] || formatSymbol(sym);
  };

  const delayFullOf = (sym: string): string => {
    const m = marketOf(sym) || 'us';
    return quoteConfig.value?.markets[m]?.delayFull ?? DELAY_LABEL_FALLBACK[m]?.full ?? DELAY_LABEL_FALLBACK.us.full;
  };

  async function loadStockNameMap() {
    try {
      const res = await fetch(`${BASE_URL}/search`, { cache: 'no-store' });
      if (res.ok) {
        const pool = await res.json();
        if (Array.isArray(pool)) {
          const map: Record<string, string> = {};
          for (const s of pool) {
            if (s.symbol && s.name) {
              map[canonSym(s.symbol)] = s.name;
            }
          }
          stockNameMap.value = { ...stockNameMap.value, ...map };
        }
      }
    } catch {
      // 后端不可用时静默回退代码显示
    }
  }

  function watchPriceInfo(item: string): {
    price: number | null;
    change: number | null;
    loading: boolean;
    extendedPrice: number | null;
    extendedLabel: string;
    prevClose: number | null;
    status?: string;
    reason?: string;
  } {
    const c = canonSym(item) || item;
    const itemUpper = (item || '').toUpperCase();
    const itemLower = (item || '').toLowerCase();
    const cleanSym = stripPrefix(item);

    const q =
      liveQuoteMap.value[c] ||
      liveQuoteMap.value[item] ||
      liveQuoteMap.value[itemUpper] ||
      liveQuoteMap.value[itemLower] ||
      liveQuoteMap.value[cleanSym] ||
      quoteEngine.getQuote(c) ||
      quoteEngine.getQuote(item) ||
      quoteEngine.getQuote(itemUpper);

    // 优先：无论当前处于 mock 还是 live 模式，只要引擎或本地缓存中有价格，零延迟直接退出骨架屏展示价格
    if (q && q.price != null) {
      return {
        price: q.price,
        change: q.changePct ?? 0,
        loading: false,
        extendedPrice: q.extendedPrice ?? null,
        extendedLabel: q.extendedLabel ?? '',
        prevClose: q.prevClose ?? null,
        status: q.status,
        reason: q.message,
      };
    }

    return {
      price: null,
      change: null,
      loading: false,
      extendedPrice: null,
      extendedLabel: '',
      prevClose: q?.prevClose ?? null,
      status: q ? q.status : 'loading',
      reason: q?.message,
    };
  }

  function secondaryLineInfo(item: string): {
    price: number | null;
    changePct: number | null;
    label: string;
  } | null {
    const info = watchPriceInfo(item);
    if (info.price == null) return null;

    if (info.extendedPrice != null && info.prevClose != null && info.prevClose > 0) {
      if (Math.abs(info.extendedPrice - info.price) >= 0.01) {
        const chg = ((info.extendedPrice - info.prevClose) / info.prevClose) * 100;
        return { price: info.extendedPrice, changePct: chg, label: info.extendedLabel || '盘后' };
      }
    }

    if (info.prevClose != null && info.prevClose > 0) {
      return { price: info.prevClose, changePct: null, label: '昨收' };
    }
    return null;
  }

  const rowInfoMap = computed<Record<string, WatchlistRowInfo>>(() => {
    const map: Record<string, WatchlistRowInfo> = {};
    for (const item of watchlist.value) {
      const info = watchPriceInfo(item);
      const sec = secondaryLineInfo(item);
      const isUp = (info.change ?? 0) >= 0;
      map[item] = {
        price: info.price,
        change: info.change,
        formattedPrice: info.price != null ? info.price.toFixed(2) : '--',
        formattedChange: info.change != null ? `${isUp ? '+' : ''}${info.change.toFixed(2)}%` : '',
        isUp,
        secondary: sec && sec.price != null ? {
          price: sec.price.toFixed(2),
          changePct: sec.changePct,
          formattedChange: sec.changePct != null ? `${sec.changePct >= 0 ? '+' : ''}${sec.changePct.toFixed(2)}%` : null,
          label: sec.label,
          isUp: (sec.changePct ?? 0) >= 0,
        } : null,
        status: info.status,
        reason: info.reason,
      };
    }
    return map;
  });

  async function updateWatchlistPrices() {
    onSymbolsChanged();
  }

  const persistWatchlistLocal = () => {
    localStorage.setItem('stock_watchlist', JSON.stringify({ groups: watchGroups.value }));
  };

  const persistWatchlist = () => {
    persistWatchlistLocal();
    saveWatchlist(watchGroups.value);
  };

  const loadWatchlist = async () => {
    try {
      const remote = await getWatchlist();
      if (Array.isArray(remote) && remote.length) {
        watchGroups.value = remote.map((g: WatchGroup) => ({
          id: g.id || genGroupId(),
          name: g.name || '未命名分组',
          stocks: g.stocks.map((s: string) => canonSym(s) || s),
        }));
        persistWatchlistLocal();
      }
    } catch {
      // 回退本地
    }

    if (!watchGroups.value.length) {
      const local = localStorage.getItem('stock_watchlist');
      if (local) {
        try {
          const parsed = JSON.parse(local);
          if (Array.isArray(parsed)) {
            watchGroups.value = [{ id: genGroupId(), name: '我的自选', stocks: parsed.map((s: string) => canonSym(s) || s) }];
          } else if (parsed && Array.isArray(parsed.groups)) {
            watchGroups.value = parsed.groups as WatchGroup[];
          } else {
            watchGroups.value = defaultGroups();
          }
        } catch {
          watchGroups.value = defaultGroups();
        }
      } else {
        watchGroups.value = defaultGroups();
        persistWatchlistLocal();
      }
    }

    const initMap: Record<string, WatchlistPriceInfo> = {};
    for (const s of watchlist.value) {
      const prev = watchlistPriceMap.value[s];
      initMap[s] = prev ?? { price: null, change: null, loading: false };
    }
    watchlistPriceMap.value = initMap;

    onSymbolsChanged();

    if (!currentSymbol.value && watchlist.value.length) {
      onSelectSymbol(watchlist.value[0]);
    } else if (currentSymbol.value) {
      updateWatchlistPrices();
    }
  };

  const isWatchlisted = (sym: string): boolean => {
    const target = canonSym(sym);
    return watchGroups.value.some((g) => g.stocks.some((s) => canonSym(s) === target));
  };

  const removeFromWatchlist = (sym: string, groupId?: string) => {
    const target = canonSym(sym);
    for (const g of watchGroups.value) {
      if (groupId && g.id !== groupId) continue;
      const idx = g.stocks.findIndex((s) => canonSym(s) === target);
      if (idx > -1) g.stocks.splice(idx, 1);
    }
    const stillAny = watchGroups.value.some((g) => g.stocks.some((s) => canonSym(s) === target));
    if (!stillAny) delete watchlistPriceMap.value[target];
    persistWatchlist();
    onSymbolsChanged();
  };

  const toggleWatchlist = (sym: string) => {
    if (!sym) return;
    const target = canonSym(sym);

    if (isWatchlisted(target)) {
      removeFromWatchlist(target);
    } else {
      if (!watchGroups.value.length) watchGroups.value = defaultGroups();
      const targetGroupId = activeGroupId.value !== 'all' ? activeGroupId.value : watchGroups.value[0].id;
      const targetGroup = watchGroups.value.find((g) => g.id === targetGroupId) || watchGroups.value[0];
      if (!targetGroup.stocks.some((s) => canonSym(s) === target)) {
        targetGroup.stocks.push(target);
        watchlistPriceMap.value[target] = { price: null, change: null, loading: true };
      }
      persistWatchlist();
      onSymbolsChanged();
    }
    updateWatchlistPrices();
  };

  const addToActiveGroup = (sym: string) => {
    const target = canonSym(sym);
    if (!watchGroups.value.length) watchGroups.value = defaultGroups();
    const currentGroup = watchGroups.value.find((g) => g.id === activeGroupId.value) || watchGroups.value[0];
    if (currentGroup) {
      if (!currentGroup.stocks.some((s) => canonSym(s) === target)) {
        currentGroup.stocks.push(target);
      }
      if (!watchlistPriceMap.value[target]) {
        watchlistPriceMap.value[target] = { price: null, change: null, loading: true };
      }
      persistWatchlist();
      updateWatchlistPrices();
      onSymbolsChanged();
    }
    return target;
  };

  const createGroup = (rawName: string) => {
    const name = (rawName || '').trim();
    if (!name) return;
    const newId = genGroupId();
    watchGroups.value.push({ id: newId, name, stocks: [] });
    persistWatchlist();
    activeGroupId.value = newId;
  };

  const renameGroup = (id: string, name: string) => {
    const g = watchGroups.value.find((x) => x.id === id);
    if (g) {
      g.name = (name || '').trim() || g.name;
      persistWatchlist();
    }
  };

  const deleteGroup = (id: string) => {
    const i = watchGroups.value.findIndex((x) => x.id === id);
    if (i > -1) {
      watchGroups.value.splice(i, 1);
      if (activeGroupId.value === id) {
        activeGroupId.value = 'all';
      }
      persistWatchlist();
      onSymbolsChanged();
    }
  };

  const selectGroup = (id: string) => {
    activeGroupId.value = id;
    showGroupDropdown.value = false;
  };

  const toggleGroupDropdown = () => {
    showGroupDropdown.value = !showGroupDropdown.value;
  };

  const setSort = (key: SortKey) => {
    if (sortBy.value === key) {
      sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
    } else {
      sortBy.value = key;
      sortDir.value = key === 'name' ? 'asc' : 'desc';
    }
  };

  const matchMarketTab = (sym: string, tab: MarketTabKey): boolean => {
    if (tab === 'all') {
      const m = marketOf(sym);
      return m === 'us' || m === 'crypto' || sym.toLowerCase().endsWith('main');
    }
    if (tab === 'futures') return sym.toLowerCase().endsWith('main');
    if (tab === 'us') return marketOf(sym) === 'us';
    return false;
  };

  const filteredWatchlist = computed<string[]>(() => {
    const gid = activeGroupId.value;
    return watchlist.value.filter((sym) => {
      const okMarket = matchMarketTab(sym, activeMarketTab.value);
      let okGroup = true;
      if (gid !== 'all') {
        const g = watchGroups.value.find((x) => x.id === gid);
        okGroup = g ? g.stocks.some((s) => canonSym(s) === canonSym(sym)) : false;
      }
      return okMarket && okGroup;
    });
  });

  const sortedFilteredWatchlist = computed<string[]>(() => {
    const arr = filteredWatchlist.value.slice();
    if (!sortBy.value) return arr;
    const dir = sortDir.value === 'asc' ? 1 : -1;
    const k = sortBy.value;
    arr.sort((a, b) => {
      if (k === 'name') return a.localeCompare(b) * dir;
      const va = k === 'price' ? watchPriceInfo(a).price : watchPriceInfo(a).change;
      const vb = k === 'price' ? watchPriceInfo(b).price : watchPriceInfo(b).change;
      const na = va == null;
      const nb = vb == null;
      if (na && nb) return 0;
      if (na) return 1;
      if (nb) return -1;
      return (va - vb) * dir;
    });
    return arr;
  });

  const clearWatchlistCache = () => {
    watchlistPriceMap.value = {};
  };

  const markAllLoadingFailed = () => {
    for (const s of watchlist.value) {
      if (watchlistPriceMap.value[s]) watchlistPriceMap.value[s].loading = false;
    }
  };

  return {
    watchGroups,
    watchlist,
    activeMarketTab,
    activeGroupId,
    showGroupDropdown,
    sortBy,
    sortDir,
    filteredWatchlist,
    sortedFilteredWatchlist,
    activeGroupName,
    isCurrentGroupEmpty,
    getStockName,
    delayFullOf,
    loadStockNameMap,
    watchPriceInfo,
    secondaryLineInfo,
    rowInfoMap,
    updateWatchlistPrices,
    loadWatchlist,
    isWatchlisted,
    toggleWatchlist,
    removeFromWatchlist,
    addToActiveGroup,
    createGroup,
    renameGroup,
    deleteGroup,
    selectGroup,
    toggleGroupDropdown,
    setSort,
    clearWatchlistCache,
    markAllLoadingFailed,
  };
}
