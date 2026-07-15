// 实时行情引擎（多市场：美股 / A股 / 港股）
// ============================================================
// 职责：在「真实模式」下，按后端下发的各市场刷新间隔，分层刷新实时行情：
//   1) 本地定时器（tick）按各市场「最低合规间隔」触发请求 —— 这是"请求频率"；
//   2) 服务端真实数据更新后，仅当价格/涨跌幅「发生变化」才通知前端刷新渲染 ——
//      无新行情则不去重、不重渲染，降低开销（需求要求的"分层刷新控制"）。
// 此外实现：
//   - 自适应：连续多次无新行情的冷门标的，自动放大轮询间隔；
//   - 美股盘前/盘中/盘后三套刷新配置；
//   - 异常防护：后端返回限流/冷却状态时，前端进入冷却、不再高频重试。
//
// 所有间隔/阈值均来自后端 /api/quote_config，前端不硬编码合规数值。

import { BASE_URL, marketOf, type Market } from './api';

// ===================== 类型定义 =====================

/** 行情状态（ok=正常；其余为异常/冷却） */
export type QuoteStatus =
  | 'ok'
  | 'cooling'      // 后端全局冷却中
  | 'rate_limited' // 触发限流(403/429)
  | 'ip_overload'  // 单 IP 窗口请求过多
  | 'empty'        // 接口返回但无行情
  | 'error'        // 网络/解析异常
  | 'loading';     // 尚未取到首值

/** 单只标的的实时行情 */
export interface Quote {
  symbol: string;
  name: string;
  price: number | null;
  prevClose: number | null;
  open: number | null;
  change: number | null;      // 涨跌额
  changePct: number | null;   // 涨跌幅 %
  updateTime: string;         // 服务端更新时间（已格式化）
  market: Market | null;
  delayLabel: string;         // 行情延迟标注（如"无延迟 LV1"）
  status: QuoteStatus;
  message?: string;
  extendedPrice: number | null;   // 扩展交易时段价格（盘后/夜盘）
  extendedLabel: string;          // 时段标签（"盘后"/"夜盘"）
}

/** 后端下发的引擎/市场配置 */
export interface MarketCfg {
  name: string;
  minInterval: number;                 // 本地最低轮询间隔（秒，合规下限）
  batchInterval: number;               // 批量查询最低间隔（秒）
  serverUpdate: [number, number];      // 服务端有效更新频率区间（秒）
  delayLabel: string;                  // 精简延迟标注
  delayFull: string;                   // 完整延迟提示语
  sessions?: Record<USSession, { label: string; minInterval: number; maxInterval: number }>;
}
export interface QuoteConfig {
  tickMs: number;                      // 前端本地定时器粒度（毫秒）
  absoluteMinInterval: number;         // 单标的轮询绝对红线（秒，0.1=100ms）
  rateLimitCooldown: number;           // 冷却时长（秒）
  ipMaxRequests: number;               // 单 IP 窗口最大请求数
  ipWindow: number;                    // 滑动窗口（秒）
  adaptive: { coldThreshold: number; coldFactor: number; maxFactor: number };
  markets: Record<string, MarketCfg>;
}
export type USSession = 'pre' | 'regular' | 'post';

/** 引擎健康状态（后端返回） */
export interface EngineStatus {
  cooling: boolean;
  reason: string;
  cooldownRemaining: number;
  slowdown: number;
  windowRequests: number;
}

/** 前端维护的每只标的轮询元数据（用于 UI 展示刷新周期/上次请求时间） */
export interface SymbolMeta {
  nextAllowed: number;      // 下次允许请求的时间戳(ms)
  lastRequest: number;      // 上次发起请求的时间戳(ms)（本地定时器触发）
  lastUpdate: number;       // 上次价格实际变化的时间戳(ms)（服务端真有新行情）
  noChange: number;         // 连续无新行情次数（自适应计数）
  intervalMul: number;      // 当前间隔放大倍率（自适应）
  status: QuoteStatus;
}

// ===================== 实时行情引擎 =====================

type Listener = (symbol: string, quote: Quote) => void;

class QuoteEngine {
  config: QuoteConfig | null = null;

  // 去重后的最新行情（仅价格/涨跌幅变化时才更新）
  private quotes = new Map<string, Quote>();
  // 每只标的的轮询元数据
  private meta = new Map<string, SymbolMeta>();
  // 当前需要轮询的标的集合（当前股票 + 自选股）
  private symbols: string[] = [];
  // 前端本地定时器
  private timer: number | null = null;
  // 订阅者（行情变化时回调）
  private listeners = new Set<Listener>();
  // 每轮 tick 结束后的回调（用于 UI 刷新状态面板，即使价格未变也触发）
  private tickListeners = new Set<() => void>();
  // 后端冷却截止时间戳（ms）
  private coolingUntil = 0;
  // 上一批请求发送时间（ms），用于保证批量查询最低间隔
  private lastBatchAt = 0;
  // 单批最多请求标的数（避免一次性过大）
  private readonly BATCH_MAX = 20;

  /** 启动时从后端拉取配置（刷新间隔/延迟标注/阈值） */
  async loadConfig(): Promise<void> {
    try {
      const res = await fetch(`${BASE_URL}/quote_config`, { cache: 'no-store' });
      if (res.ok) this.config = (await res.json()) as QuoteConfig;
    } catch {
      this.config = null; // 取不到则用兜底默认值（见 getMinInterval）
    }
  }

  /** 设置需要轮询的标的集合（当前股票 + 自选股），增量更新元数据 */
  setSymbols(syms: string[]): void {
    const next = syms.filter(Boolean);
    this.symbols = next;
    for (const s of next) {
      if (!this.meta.has(s)) {
        this.meta.set(s, {
          nextAllowed: 0,         // 立即可请求首值
          lastRequest: 0,
          lastUpdate: 0,
          noChange: 0,
          intervalMul: 1,
          status: 'loading',
        });
      }
    }
    // 清理已不在集合中的标的元数据
    for (const s of [...this.meta.keys()]) {
      if (!next.includes(s)) this.meta.delete(s);
    }
  }

  /** 订阅行情变化（返回取消订阅函数） */
  subscribe(cb: Listener): () => void {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  /** 订阅每轮 tick（即使价格未变也触发，用于刷新状态面板） */
  onTick(cb: () => void): () => void {
    this.tickListeners.add(cb);
    return () => this.tickListeners.delete(cb);
  }

  /** 导出所有标的的轮询元数据快照（供 UI 展示刷新周期/上次请求时间） */
  snapshotMetas(): Record<string, SymbolMeta> {
    const out: Record<string, SymbolMeta> = {};
    for (const [k, v] of this.meta.entries()) out[k] = { ...v };
    return out;
  }

  /** 启动本地定时器（仅在真实模式调用） */
  start(): void {
    if (this.timer != null) return;
    const tick = this.config?.tickMs ?? 1000;
    this.timer = window.setInterval(() => void this.tick(), tick);
  }

  /** 停止并清空（切换回演示模式时调用） */
  stop(): void {
    if (this.timer != null) {
      clearInterval(this.timer);
      this.timer = null;
    }
    this.quotes.clear();
    this.meta.clear();
    this.symbols = [];
    this.coolingUntil = 0;
  }

  /** 读取某标的当前行情（去重后） */
  getQuote(symbol: string): Quote | null {
    return this.quotes.get(symbol) ?? null;
  }

  /** 读取某标的轮询元数据（供 UI 展示刷新周期/上次请求时间） */
  getMeta(symbol: string): SymbolMeta | null {
    return this.meta.get(symbol) ?? null;
  }

  /** 后端冷却状态（限流/异常） */
  getEngineStatus(): { cooling: boolean; reason: string } {
    return {
      cooling: Date.now() < this.coolingUntil,
      reason: Date.now() < this.coolingUntil ? 'cooling' : '',
    };
  }

  // ---------- 内部逻辑 ----------

  /** 取得某标的当前应使用的最小刷新间隔（秒），含美股盘前/盘中/盘后判断 */
  private getMinInterval(market: Market | null): number {
    const cfg = this.config;
    if (!cfg) return market === 'us' ? 10 : 2; // 兜底：美股10s，其余2s
    if (market === 'us' && cfg.markets.us.sessions) {
      const sess = this.detectUSSession();
      return cfg.markets.us.sessions[sess].minInterval;
    }
    return cfg.markets[market ?? 'us']?.minInterval ?? 2;
  }

  /** 检测美股当前交易时段（美东时间） */
  private detectUSSession(): USSession {
    const now = new Date();
    // 把当前时刻转换为美东时间对应的本地 Date 对象
    const etStr = now.toLocaleString('en-US', { timeZone: 'America/New_York' });
    const et = new Date(etStr);
    const day = et.getDay(); // 0=周日, 6=周六
    const mins = et.getHours() * 60 + et.getMinutes();
    if (day === 0 || day === 6) return 'post';       // 周末视为盘后（无交易）
    if (mins < 9 * 60 + 30) return 'pre';             // 盘前 4:00-9:30 ET
    if (mins < 16 * 60) return 'regular';             // 盘中 9:30-16:00 ET
    return 'post';                                    // 盘后 16:00-20:00 ET
  }

  /** 定时器回调：分层刷新核心 */
  private async tick(): Promise<void> {
    try {
    if (!this.config) return;
    const now = Date.now();

    // 全局冷却中：标记到期标的为 cooling，不再发起请求（避免高频重试触发封禁）
    if (now < this.coolingUntil) {
      for (const s of this.symbols) {
        const m = this.meta.get(s);
        if (m) m.status = 'cooling';
      }
      return;
    }

    // 计算本 tick 到期的标的（满足各自市场最低间隔 + 未曾在本 tick 内请求过）
    const due: string[] = [];
    for (const s of this.symbols) {
      const m = this.meta.get(s);
      if (!m) continue;
      const eligible = now >= m.nextAllowed && now - m.lastRequest >= this.config.tickMs;
      if (eligible && due.length < this.BATCH_MAX) due.push(s);
    }
    if (due.length === 0) return;

    // 批量查询最低间隔：任意标的所在市场的 batchInterval 取最大值，
    // 保证「连续两批请求」间隔不低于该值（如 A股批量 ≥3s），避免批量高频触发封禁。
    const batchIntervalMs = Math.max(
      ...due.map((s) => {
        const mk = marketOf(s) ?? 'us';
        const cfg = this.config!.markets[mk];
        return (cfg?.batchInterval ?? cfg?.minInterval ?? 3) * 1000;
      })
    );
    if (now - this.lastBatchAt < batchIntervalMs) return; // 本 tick 暂不发包，下轮再试

    try {
      this.lastBatchAt = now; // 记录本批发送时间（用于下批间隔判定）
      const url = `${BASE_URL}/quote?symbols=${encodeURIComponent(due.join(','))}`;
      const res = await fetch(url, { cache: 'no-store' });
      if (!res.ok) {
        // 后端 429/5xx：标记冷却，停止重试一段时间
        for (const s of due) {
          const m = this.meta.get(s);
          if (m) m.status = 'rate_limited';
        }
        this.coolingUntil = now + (this.config.rateLimitCooldown ?? 30) * 1000;
        return;
      }
      const data = await res.json();
      // 后端引擎若处于冷却，本地同步冷却，避免空转
      if (data.engine && data.engine.cooling) {
        this.coolingUntil = now + (data.engine.cooldownRemaining ?? 30) * 1000;
      }
      // 注意：后端下发的是 snake_case（price/prev_close/change_pct/update_time/delay_label），
      // 而前端 Quote 类型是 camelCase，必须在此做一次字段映射，否则 changePct 等永远为 undefined，
      // 会导致实时模式下自选栏/顶部一直显示加载骨架而非真实价格。
      const map = new Map<string, Quote>(
        (data.quotes as any[]).map((r) => [
          r.symbol,
          {
            symbol: r.symbol,
            name: r.name,
            price: r.price ?? null,
            prevClose: r.prev_close ?? null,
            open: r.open ?? null,
            change: r.change ?? null,
            changePct: r.change_pct ?? null,
            updateTime: r.update_time ?? '',
            market: (r.market as Market | null) ?? null,
            delayLabel: r.delay_label ?? '',
            status: r.status as QuoteStatus,
            message: r.message,
            extendedPrice: r.extended_price ?? null,
            extendedLabel: r.extended_price ? '盘后' : '',
          } as Quote,
        ] as [string, Quote])
      );

      for (const s of due) {
        const m = this.meta.get(s)!;
        m.lastRequest = now;                 // 本地定时器已发起请求
        const q = map.get(s);
        if (!q || q.status !== 'ok') {
          m.status = (q?.status as QuoteStatus) || 'error';
          // 异常标的按其市场最低间隔等待后再重试，避免空转触发限流
          const minMs = this.getMinInterval(marketOf(s)) * 1000;
          m.nextAllowed = now + minMs;
          continue;
        }
        // 去重：价格与涨跌幅均未变化 → 不通知、不重渲染
        const prev = this.quotes.get(s);
        const changed = !prev || prev.price !== q.price || prev.changePct !== q.changePct;
        m.status = 'ok';
        m.lastUpdate = now;                  // 服务端真有新行情
        if (changed) {
          m.noChange = 0;
          m.intervalMul = 1;                 // 有变化 → 复位为基准间隔
          this.quotes.set(s, q);
          this.listeners.forEach((cb) => cb(s, q)); // 仅变化时通知 UI 刷新
        } else {
          m.noChange += 1;
          // 冷门：连续无变化达阈值 → 间隔放大（自适应），但不超上限
          if (m.noChange >= this.config.adaptive.coldThreshold) {
            m.intervalMul = Math.min(
              this.config.adaptive.maxFactor,
              m.intervalMul * this.config.adaptive.coldFactor
            );
          }
        }
        const nextMin = this.getMinInterval(marketOf(s)) * 1000 * m.intervalMul;
        m.nextAllowed = now + nextMin;
      }
    } catch {
      // 网络异常：标记 error，等待下一 tick（后端护盾也会冷却）
      for (const s of due) {
        const m = this.meta.get(s);
        if (m) m.status = 'error';
      }
    }
    } finally {
      // 每轮 tick 结束都通知 UI（用于刷新状态面板，不受价格是否变化影响）
      this.tickListeners.forEach((cb) => cb());
    }
  }
}

/** 全局单例（跨组件共享同一套轮询与限流状态） */
export const quoteEngine = new QuoteEngine();
