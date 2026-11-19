// 实时行情引擎（多市场：美股 / 期货 / 加密货币）
import { BASE_URL, marketOf, normalizeSymbol, type Market } from './api';

export type QuoteStatus =
  | 'ok'
  | 'cooling'
  | 'rate_limited'
  | 'ip_overload'
  | 'empty'
  | 'error'
  | 'loading';

export function toCanonSym(s: string): string {
  const n = normalizeSymbol(s || '');
  if (!n) return n;
  return n.replace(/^(US|SH|SZ|HK)/i, (m) => m.toLowerCase());
}

export type USExtendedSessionLabel = '夜盘' | '盘前' | '盘后' | '';

/**
 * 根据当前美东时间 (America/New_York) 判定美股所处的扩展交易时段
 * 返回 '' 表示正处于常规盘中 (09:30 - 16:00 ET)
 */
export function getCurrentUSExtendedSession(now: Date = new Date()): USExtendedSessionLabel {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(now);

  const weekday = parts.find((p) => p.type === 'weekday')?.value || '';
  const hour = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10);
  const minute = parseInt(parts.find((p) => p.type === 'minute')?.value || '0', 10);
  const mins = hour * 60 + minute;

  if (weekday === 'Sat') return '盘后';
  if (weekday === 'Sun') return mins >= 20 * 60 ? '夜盘' : '盘后';
  if (weekday === 'Fri' && mins >= 20 * 60) return '盘后';

  if (mins < 4 * 60) return '夜盘';
  if (mins < 9 * 60 + 30) return '盘前';
  if (mins < 16 * 60) return '';
  if (mins < 20 * 60) return '盘后';
  return '夜盘';
}

export interface Quote {
  symbol: string;
  name: string;
  price: number | null;
  prevClose: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  change: number | null;
  changePct: number | null;
  updateTime: string;
  market: Market | null;
  delayLabel: string;
  status: QuoteStatus;
  message?: string;
  extendedPrice: number | null;
  extendedLabel: string;
}

export interface MarketCfg {
  name: string;
  minInterval: number;
  batchInterval: number;
  serverUpdate: [number, number];
  delayLabel: string;
  delayFull: string;
  sessions?: Record<USSession, { label: string; minInterval: number; maxInterval: number }>;
}

export interface QuoteConfig {
  tickMs: number;
  absoluteMinInterval: number;
  rateLimitCooldown: number;
  ipMaxRequests: number;
  ipWindow: number;
  adaptive: { coldThreshold: number; coldFactor: number; maxFactor: number };
  markets: Record<string, MarketCfg>;
}

export const DEFAULT_QUOTE_CONFIG: QuoteConfig = {
  tickMs: 1000,
  absoluteMinInterval: 0.1,
  rateLimitCooldown: 20,
  ipMaxRequests: 120,
  ipWindow: 60,
  adaptive: { coldThreshold: 5, coldFactor: 1.5, maxFactor: 5 },
  markets: {
    us: {
      name: '美股',
      minInterval: 3,
      batchInterval: 3,
      serverUpdate: [3, 15],
      delayLabel: '实时轮询 (3s)',
      delayFull: '美股【免费公开数据源，盘中 3s 轮询】',
      sessions: {
        pre: { label: '盘前', minInterval: 6, maxInterval: 15 },
        regular: { label: '盘中', minInterval: 3, maxInterval: 5 },
        post: { label: '盘后', minInterval: 6, maxInterval: 15 },
      },
    },
    futures: {
      name: '期货',
      minInterval: 2,
      batchInterval: 2.5,
      serverUpdate: [2, 5],
      delayLabel: '实时快照 (2s)',
      delayFull: '期货【CME 连续合约实时快照】',
    },
    crypto: {
      name: '加密',
      minInterval: 3,
      batchInterval: 3,
      serverUpdate: [2, 5],
      delayLabel: '实时行情 (24/7)',
      delayFull: '加密货币【Yahoo 实时行情，24小时交易】',
    },
  },
};

export type USSession = 'pre' | 'regular' | 'post';

export interface SymbolMeta {
  nextAllowed: number;
  lastRequest: number;
  lastUpdate: number;
  noChange: number;
  intervalMul: number;
  status: QuoteStatus;
}

type Listener = (symbol: string, quote: Quote) => void;
type BatchListener = (batch: Record<string, Quote>) => void;

const QUOTE_CACHE_KEY = 'stock_quotes_cache';

class QuoteEngine {
  config: QuoteConfig = DEFAULT_QUOTE_CONFIG;

  private quotes = new Map<string, Quote>();
  private meta = new Map<string, SymbolMeta>();
  private symbols: string[] = [];
  private timer: number | null = null;
  private listeners = new Set<Listener>();
  private batchListeners = new Set<BatchListener>();
  private tickListeners = new Set<() => void>();
  private coolingUntil = 0;
  private lastBatchAt: Record<string, number> = {};
  private inFlightMarkets = new Set<string>();
  private readonly BATCH_MAX = 20;
  private activeSymbol: string = '';
  private deliveredSymbols = new Set<string>();

  constructor() {
    this.loadQuotesCache();
  }

  private lastResumeAt = 0;

  private loadQuotesCache(): void {
    try {
      const raw = localStorage.getItem(QUOTE_CACHE_KEY);
      if (raw) {
        const obj = JSON.parse(raw);
        for (const [k, v] of Object.entries(obj)) {
          if (v && typeof v === 'object' && (v as Quote).price != null) {
            const sym = toCanonSym(k) || k;
            const q = v as Quote;
            this.quotes.set(sym, q);
            this.quotes.set(k, q);
            this.quotes.set(k.toUpperCase(), q);
            this.quotes.set(k.toLowerCase(), q);
          }
        }
      }
    } catch {}
  }

  private saveQuotesCache(): void {
    try {
      const obj: Record<string, Quote> = {};
      for (const [k, v] of this.quotes.entries()) {
        if (v && v.status === 'ok' && v.price != null) {
          obj[k] = v;
        }
      }
      localStorage.setItem(QUOTE_CACHE_KEY, JSON.stringify(obj));
    } catch {}
  }

  setActiveSymbol(sym: string): void {
    const prev = this.activeSymbol;
    this.activeSymbol = sym;
    const m = this.meta.get(sym);
    if (m && prev !== sym) {
      m.intervalMul = 1;
      m.noChange = 0;
      m.nextAllowed = 0;
    }
  }

  async loadConfig(): Promise<void> {
    try {
      const res = await fetch(`${BASE_URL}/quote_config`, { cache: 'no-store' });
      if (res.ok) this.config = (await res.json()) as QuoteConfig;
    } catch {
      // 保持 DEFAULT_QUOTE_CONFIG 兜底
    }
  }

  setSymbols(syms: string[]): void {
    const next = [...new Set(syms.filter(Boolean))];
    this.symbols = next;
    let hasNew = false;
    for (const s of next) {
      if (!this.meta.has(s)) {
        hasNew = true;
        this.meta.set(s, {
          nextAllowed: 0,
          lastRequest: 0,
          lastUpdate: 0,
          noChange: 0,
          intervalMul: 1,
          status: 'loading',
        });
      }
    }
    for (const s of [...this.meta.keys()]) {
      if (!next.includes(s)) this.meta.delete(s);
    }
    // 新增标的时立即触发一次拉取，无需等待下个定时器周期
    if (hasNew && this.timer != null) {
      void this.tick();
    }
  }

  subscribe(cb: Listener): () => void {
    this.listeners.add(cb);
    // 立即向新订阅者回放当前内存/持久化中的全部有效行情，彻底消除开屏骨架屏闪烁
    for (const [sym, quote] of this.quotes.entries()) {
      try {
        cb(sym, quote);
      } catch (err) {
        console.error('Error emitting cached quote to subscriber:', err);
      }
    }
    return () => this.listeners.delete(cb);
  }

  subscribeBatch(cb: BatchListener): () => void {
    this.batchListeners.add(cb);
    const existing = this.getAllQuotes();
    if (Object.keys(existing).length > 0) {
      try {
        cb(existing);
      } catch (err) {
        console.error('Error emitting cached quotes batch to subscriber:', err);
      }
    }
    return () => this.batchListeners.delete(cb);
  }

  onTick(cb: () => void): () => void {
    this.tickListeners.add(cb);
    return () => this.tickListeners.delete(cb);
  }

  snapshotMetas(): Record<string, SymbolMeta> {
    const out: Record<string, SymbolMeta> = {};
    for (const [k, v] of this.meta.entries()) out[k] = { ...v };
    return out;
  }

  /** 启动定时器并立即执行首轮拉取 */
  start(): void {
    if (this.timer != null) return;
    const tick = this.config?.tickMs ?? 1000;
    void this.tick();
    this.timer = window.setInterval(() => void this.tick(), tick);
  }

  /** 恢复轮询并立即拉取一次（用于窗口由后台/最小化切回前台） */
  resume(): void {
    const now = Date.now();
    if (now - this.lastResumeAt < 200) {
      return; // 防抖保护：防止 pywebview 多事件并发瞬时唤醒导致并发竞争
    }
    this.lastResumeAt = now;

    this.inFlightMarkets.clear();
    this.deliveredSymbols.clear();
    for (const mk of Object.keys(this.lastBatchAt)) {
      this.lastBatchAt[mk] = 0;
    }
    for (const m of this.meta.values()) {
      m.nextAllowed = 0;
    }
    // 立即向 batchListeners 回放当前内存中的全部有效行情，确保切回前台瞬时恢复最新价显示
    const cached = this.getAllQuotes();
    if (Object.keys(cached).length > 0) {
      this.batchListeners.forEach((cb) => {
        try {
          cb(cached);
        } catch (err) {
          console.error('Error replaying cached quotes on resume:', err);
        }
      });
    }
    this.start();
  }

  /** 暂停轮询定时器（保留已有行情缓存，避免桌面失焦切回时闪烁骨架屏） */
  stop(): void {
    if (this.timer != null) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.inFlightMarkets.clear();
  }

  getQuote(symbol: string): Quote | null {
    if (!symbol) return null;
    const c = toCanonSym(symbol);
    return (
      this.quotes.get(c) ??
      this.quotes.get(symbol) ??
      this.quotes.get(symbol.toUpperCase()) ??
      this.quotes.get(symbol.toLowerCase()) ??
      null
    );
  }

  getAllQuotes(): Record<string, Quote> {
    const out: Record<string, Quote> = {};
    for (const [k, v] of this.quotes.entries()) {
      out[k] = v;
    }
    return out;
  }

  getMeta(symbol: string): SymbolMeta | null {
    return this.meta.get(symbol) ?? null;
  }

  getEngineStatus(): { cooling: boolean; reason: string } {
    return {
      cooling: Date.now() < this.coolingUntil,
      reason: Date.now() < this.coolingUntil ? 'cooling' : '',
    };
  }

  private getMinInterval(market: Market | null): number {
    const cfg = this.config;
    if (!cfg) return market === 'us' ? 5 : 2;
    if (market === 'us' && cfg.markets.us?.sessions) {
      const sess = this.detectUSSession();
      return cfg.markets.us.sessions[sess].minInterval;
    }
    return cfg.markets[market ?? 'us']?.minInterval ?? 2;
  }

  private detectUSSession(): USSession {
    const label = getCurrentUSExtendedSession();
    if (label === '盘前' || label === '夜盘') return 'pre';
    if (label === '') return 'regular';
    return 'post';
  }

  private async tick(): Promise<void> {
    try {
      if (!this.config) {
        await this.loadConfig();
        if (!this.config) return;
      }
      const now = Date.now();

      if (now < this.coolingUntil) {
        for (const s of this.symbols) {
          const m = this.meta.get(s);
          if (m && m.status === 'loading') m.status = 'cooling';
        }
        return;
      }

      const dueByMarket = new Map<string, string[]>();
      const initialMarkets = new Set<string>();

      for (const s of this.symbols) {
        const m = this.meta.get(s);
        if (!m) continue;
        const c = toCanonSym(s) || s;
        const hasValidPrice = (this.quotes.get(c)?.price != null) || (this.quotes.get(s)?.price != null);
        const isFirstLoad = m.lastRequest === 0 || !hasValidPrice;
        const eligible = isFirstLoad || (now >= m.nextAllowed && now - m.lastRequest >= this.config.tickMs);
        if (eligible) {
          const mk = marketOf(s) ?? 'us';
          if (isFirstLoad) initialMarkets.add(mk);
          if (!dueByMarket.has(mk)) dueByMarket.set(mk, []);
          const list = dueByMarket.get(mk)!;
          if (list.length < this.BATCH_MAX) {
            list.push(s);
          }
        }
      }

      if (dueByMarket.size === 0) return;

      const tasks: Promise<void>[] = [];
      for (const [mk, due] of dueByMarket.entries()) {
        if (due.length === 0 || this.inFlightMarkets.has(mk)) continue;
        const cfg = this.config.markets[mk];
        const batchIntervalMs = (cfg?.batchInterval ?? cfg?.minInterval ?? 2) * 1000;
        const lastAt = this.lastBatchAt[mk] || 0;
        // 含未初始化标的的市场批次直接放行，跳过 batchInterval 等待
        if (!initialMarkets.has(mk) && now - lastAt < batchIntervalMs) continue;

        tasks.push(this.fetchMarketBatch(mk, due, now));
      }

      if (tasks.length > 0) {
        await Promise.allSettled(tasks);
      }
    } finally {
      this.tickListeners.forEach((cb) => cb());
    }
  }

  private async fetchMarketBatch(market: string, due: string[], now: number): Promise<void> {
    this.inFlightMarkets.add(market);
    this.lastBatchAt[market] = now;
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 7000);

    try {
      const url = `${BASE_URL}/quote?symbols=${encodeURIComponent(due.join(','))}`;
      const res = await fetch(url, { cache: 'no-store', signal: ctrl.signal });
      if (!res.ok) {
        const errorBatch: Record<string, Quote> = {};
        for (const s of due) {
          const m = this.meta.get(s);
          if (m) {
            m.lastRequest = now;
            m.status = 'rate_limited';
            m.nextAllowed = now + 5000;
          }
          const c = toCanonSym(s) || s;
          const prev = this.quotes.get(c) ?? this.quotes.get(s);
          if (prev && prev.price != null) {
            continue;
          }
          const fallbackQ: Quote = {
            symbol: c,
            name: '',
            price: null,
            prevClose: null,
            open: null,
            high: null,
            low: null,
            change: null,
            changePct: null,
            updateTime: '',
            market: (marketOf(s) as Market | null) ?? null,
            delayLabel: '',
            status: 'rate_limited',
            extendedPrice: null,
            extendedLabel: '',
          };
          this.quotes.set(c, fallbackQ);
          this.quotes.set(s, fallbackQ);
          this.quotes.set(s.toUpperCase(), fallbackQ);
          this.listeners.forEach((cb) => cb(c, fallbackQ));
          errorBatch[c] = fallbackQ;
          errorBatch[s] = fallbackQ;
        }
        if (Object.keys(errorBatch).length > 0) {
          this.batchListeners.forEach((cb) => cb(errorBatch));
        }
        if (res.status === 429) {
          this.coolingUntil = now + (this.config?.rateLimitCooldown ?? 20) * 1000;
        }
        return;
      }

      const data = await res.json();
      if (data.engine && data.engine.cooling) {
        this.coolingUntil = now + (data.engine.cooldownRemaining ?? 20) * 1000;
      }

      const map = new Map<string, Quote>();
      for (const r of (data.quotes as any[] || [])) {
        const raw = r.symbol || '';
        const canon = toCanonSym(raw) || raw;
        const rawExtPrice = r.extended_price ?? null;
        // 优先采信后端返回标签；兼容旧缓存或缺省时用前端美东时段兜底
        const resolvedExtLabel = rawExtPrice
          ? (typeof r.extended_label === 'string' ? r.extended_label : getCurrentUSExtendedSession())
          : '';

        const q: Quote = {
          symbol: canon,
          name: r.name,
          price: r.price ?? null,
          prevClose: r.prev_close ?? null,
          open: r.open ?? null,
          high: r.high ?? null,
          low: r.low ?? null,
          change: r.change ?? null,
          changePct: r.change_pct ?? null,
          updateTime: r.update_time ?? '',
          market: (r.market as Market | null) ?? null,
          delayLabel: r.delay_label ?? '',
          status: (r.status as QuoteStatus) || 'empty',
          message: r.message,
          extendedPrice: resolvedExtLabel ? rawExtPrice : null,
          extendedLabel: resolvedExtLabel,
        };
        map.set(raw, q);
        map.set(canon, q);
        map.set(raw.toUpperCase(), q);
        map.set(raw.toLowerCase(), q);
        map.set(canon.toLowerCase(), q);
      }

      const batchToNotify: Record<string, Quote> = {};

      for (const s of due) {
        const m = this.meta.get(s);
        if (!m) continue;
        m.lastRequest = now;
        const c = toCanonSym(s) || s;
        const q = map.get(c) || map.get(s) || map.get(s.toUpperCase()) || map.get(s.toLowerCase());

        if (!q || q.status !== 'ok') {
          const status: QuoteStatus = q ? q.status : 'empty';
          m.status = status;
          m.nextAllowed = now + this.getMinInterval(marketOf(s)) * 1000;

          const prev = this.quotes.get(c) ?? this.quotes.get(s);
          // 核心保护：若已有末次有效报价（如收盘价/历史有效价），在非致命异常时绝不抹杀 price 导致闪烁骨架屏
          const fallbackPrice = prev?.price ?? q?.price ?? null;
          const fallbackQ: Quote = {
            symbol: c,
            name: q?.name || prev?.name || '',
            price: fallbackPrice,
            prevClose: q?.prevClose ?? prev?.prevClose ?? null,
            open: q?.open ?? prev?.open ?? null,
            high: q?.high ?? prev?.high ?? null,
            low: q?.low ?? prev?.low ?? null,
            change: q?.change ?? prev?.change ?? null,
            changePct: q?.changePct ?? prev?.changePct ?? null,
            updateTime: q?.updateTime || prev?.updateTime || '',
            market: (marketOf(s) as Market | null) ?? prev?.market ?? null,
            delayLabel: q?.delayLabel || prev?.delayLabel || '',
            status: fallbackPrice != null ? 'ok' : status,
            message: q?.message,
            extendedPrice: q?.extendedPrice ?? prev?.extendedPrice ?? null,
            extendedLabel: q?.extendedLabel ?? prev?.extendedLabel ?? '',
          };

          this.quotes.set(c, fallbackQ);
          this.quotes.set(s, fallbackQ);
          this.quotes.set(s.toUpperCase(), fallbackQ);
          this.deliveredSymbols.add(c);
          this.listeners.forEach((cb) => cb(c, fallbackQ));
          batchToNotify[c] = fallbackQ;
          batchToNotify[s] = fallbackQ;
          batchToNotify[s.toUpperCase()] = fallbackQ;
          continue;
        }

        const prev = this.quotes.get(c) ?? this.quotes.get(s);
        const changed =
          !prev ||
          prev.price !== q.price ||
          prev.changePct !== q.changePct ||
          prev.extendedPrice !== q.extendedPrice ||
          prev.updateTime !== q.updateTime ||
          prev.status !== q.status;

        m.status = 'ok';
        m.lastUpdate = now;
        this.quotes.set(c, q);
        this.quotes.set(s, q);
        this.quotes.set(s.toUpperCase(), q);
        this.quotes.set(c.toLowerCase(), q);

        if (changed || c === toCanonSym(this.activeSymbol)) {
          m.noChange = 0;
          m.intervalMul = 1;
        } else {
          m.noChange += 1;
          if (m.noChange >= this.config.adaptive.coldThreshold) {
            m.intervalMul = Math.min(
              this.config.adaptive.maxFactor,
              m.intervalMul * this.config.adaptive.coldFactor
            );
          }
        }
        m.nextAllowed = now + this.getMinInterval(marketOf(s)) * 1000 * m.intervalMul;

        this.deliveredSymbols.add(c);
        this.listeners.forEach((cb) => cb(c, q));
        batchToNotify[c] = q;
        batchToNotify[s] = q;
        batchToNotify[s.toUpperCase()] = q;
      }

      if (Object.keys(batchToNotify).length > 0) {
        this.batchListeners.forEach((cb) => cb(batchToNotify));
        this.saveQuotesCache();
      }
    } catch {
      const errorBatch: Record<string, Quote> = {};
      for (const s of due) {
        const m = this.meta.get(s);
        if (m) {
          m.lastRequest = now;
          m.status = 'error';
          m.nextAllowed = now + 3000;
        }
        const c = toCanonSym(s) || s;
        const prev = this.quotes.get(c) ?? this.quotes.get(s);
        if (prev && prev.price != null) {
          // 保留已有价格，避免闪烁
          continue;
        }
        if (!this.quotes.has(c)) {
          const fallbackQ: Quote = {
            symbol: c,
            name: '',
            price: null,
            prevClose: null,
            open: null,
            high: null,
            low: null,
            change: null,
            changePct: null,
            updateTime: '',
            market: (marketOf(s) as Market | null) ?? null,
            delayLabel: '',
            status: 'error',
            extendedPrice: null,
            extendedLabel: '',
          };
          this.quotes.set(c, fallbackQ);
          this.quotes.set(s, fallbackQ);
          this.quotes.set(s.toUpperCase(), fallbackQ);
          this.listeners.forEach((cb) => cb(c, fallbackQ));
          errorBatch[c] = fallbackQ;
          errorBatch[s] = fallbackQ;
        }
      }
      if (Object.keys(errorBatch).length > 0) {
        this.batchListeners.forEach((cb) => cb(errorBatch));
      }
    } finally {
      clearTimeout(timer);
      this.inFlightMarkets.delete(market);
    }
  }
}

export const quoteEngine = new QuoteEngine();
