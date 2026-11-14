// 统一证券代码归一与市场识别模块（与后端 stage_one/backend/symbols.py 规则对齐）

export type Market = 'us' | 'ash' | 'asz' | 'hk' | 'futures' | 'crypto';

export const MARKETS: { key: Market; label: string; hint: string }[] = [
  { key: 'us', label: '美股', hint: '如 AAPL' },
  // 暂时停用 A股 与 港股，保留注释以备后用:
  // { key: 'ash', label: '沪A',  hint: '如 600519' },
  // { key: 'asz', label: '深A',  hint: '如 000001' },
  // { key: 'hk',  label: '港股', hint: '如 00700' },
];

export const MARKET_LABEL: Record<Market, string> = {
  us: '美股',
  ash: '沪A',
  asz: '深A',
  hk: '港股',
  futures: '期货',
  crypto: '加密',
};

const SUPPORTED_CRYPTO_BASES = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'BNB'] as const;
const PREFIXES = ['US'] as const;

function stripCryptoUsPrefix(clean: string): string {
  if (
    clean.startsWith('US') &&
    SUPPORTED_CRYPTO_BASES.some(
      (b) =>
        clean.slice(2) === b ||
        clean.slice(2) === `${b}-USD` ||
        clean.slice(2) === `${b}-USDT` ||
        clean.slice(2) === `${b}USD` ||
        clean.slice(2) === `${b}USDT`
    )
  ) {
    return clean.slice(2);
  }
  return clean;
}

/** 识别代码所属市场 */
export function marketOf(sym: string): Market | null {
  const s = (sym || '').toUpperCase();
  if (!s) return null;

  const cryptoNorm = s.replace(/\//g, '-').replace(/_/g, '-');
  const cleanNoUs = stripCryptoUsPrefix(cryptoNorm);

  if (
    cryptoNorm.endsWith('-USD') ||
    cryptoNorm.endsWith('-USDT') ||
    cryptoNorm.endsWith('USDT') ||
    (SUPPORTED_CRYPTO_BASES as readonly string[]).includes(cryptoNorm) ||
    (SUPPORTED_CRYPTO_BASES as readonly string[]).includes(cleanNoUs) ||
    cleanNoUs.endsWith('-USD') ||
    cleanNoUs.endsWith('-USDT') ||
    cleanNoUs.endsWith('USDT') ||
    SUPPORTED_CRYPTO_BASES.some((b) => cleanNoUs === `${b}USD` || cleanNoUs === `${b}USDT`)
  ) {
    return 'crypto';
  }

  if (s.endsWith('MAIN')) return 'futures';
  if (s.startsWith('US')) return 'us';
  if (s.startsWith('SH')) return 'ash';
  if (s.startsWith('SZ')) return 'asz';
  if (s.startsWith('HK')) return 'hk';
  return null;
}

/** 去掉市场前缀，返回纯净代码 (usAAPL -> AAPL) */
export function stripPrefix(sym: string): string {
  const s = sym.toUpperCase();
  for (const p of PREFIXES) {
    if (s.startsWith(p)) return s.slice(p.length);
  }
  return s;
}

/** 展示用：直接返回去前缀后的代码 */
export function formatSymbol(sym: string): string {
  return stripPrefix(sym);
}

/** 把用户输入归一化为带市场前缀的统一代码 */
export function normalizeSymbol(raw: string, market?: Market): string {
  const s = (raw || '').trim().toUpperCase();
  if (!s) return s;

  const cryptoNorm = s.replace(/\//g, '-').replace(/_/g, '-');
  const cleanNoUs = stripCryptoUsPrefix(cryptoNorm);

  if (
    (SUPPORTED_CRYPTO_BASES as readonly string[]).includes(cryptoNorm) ||
    cryptoNorm.endsWith('-USD') ||
    cryptoNorm.endsWith('-USDT')
  ) {
    const base = cryptoNorm.split('-')[0].replace(/^US/, '');
    return `${base}-USD`;
  }

  for (const base of SUPPORTED_CRYPTO_BASES) {
    if (
      cryptoNorm === `${base}USDT` ||
      cryptoNorm === `${base}USD` ||
      cryptoNorm === `US${base}` ||
      cleanNoUs === base ||
      cleanNoUs === `${base}USDT` ||
      cleanNoUs === `${base}USD` ||
      cleanNoUs === `${base}-USD` ||
      cleanNoUs === `${base}-USDT`
    ) {
      return `${base}-USD`;
    }
  }

  if (cleanNoUs.endsWith('-USDT')) {
    return `${cleanNoUs.slice(0, -5).replace(/^US/, '')}-USD`;
  }
  if (cleanNoUs.endsWith('USDT') && cleanNoUs.length > 4) {
    return `${cleanNoUs.slice(0, -4).replace(/^US/, '')}-USD`;
  }
  if (cleanNoUs.endsWith('-USD')) {
    return cleanNoUs;
  }
  if (cleanNoUs.endsWith('USD') && cleanNoUs.length > 3) {
    return `${cleanNoUs.slice(0, -3).replace(/^US/, '')}-USD`;
  }

  if (PREFIXES.some((p) => s.startsWith(p))) return s;
  if (s.endsWith('MAIN')) return s.slice(0, -4) + 'main';
  if (market === 'us') return 'US' + s;

  return 'US' + s;
}
