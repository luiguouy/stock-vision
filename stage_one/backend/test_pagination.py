"""验证腾讯日线能否用 end 参数分页回溯到上市日。"""
import httpx
import json
from datetime import datetime

SYMBOL = "usAAPL.OQ"
BASE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def fetch_page(end: str, count: int = 2000):
    param = f"{SYMBOL},day,{''},{end},{count},qfq" if end else f"{SYMBOL},day,,,{count},qfq"
    url = f"{BASE}?param={param}"
    with httpx.Client(timeout=15.0, follow_redirects=True) as c:
        r = c.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        d = r.json()
        k = d.get("data", {}).get(SYMBOL, {})
        arr = k.get("day") or k.get("qfqday")
        if not arr:
            return []
        out = []
        for it in arr:
            if len(it) >= 6:
                out.append((it[0], float(it[1]), float(it[2]), float(it[3]), float(it[4]), float(it[5])))
        return out


all_bars = {}
prev_earliest = None
end = None  # 第一页不传 end
pages = 0
while pages < 20:
    bars = fetch_page(end)
    if not bars:
        print(f"page {pages}: empty -> stop")
        break
    pages += 1
    # 去重按日期
    added = 0
    for b in bars:
        if b[0] not in all_bars:
            all_bars[b[0]] = b
            added += 1
    dates = sorted(all_bars.keys())
    print(f"page {pages}: got={len(bars)} new={added} first={bars[0][0]} last={bars[-1][0]} total_unique={len(all_bars)}")
    # 下一页 end = 当前最早日期
    earliest = dates[0]
    if earliest == prev_earliest:
        print("no earlier progress -> stop")
        break
    prev_earliest = earliest
    end = earliest
    if len(bars) < 2000:
        print("last page < 2000 -> reached earliest available")
        break

dates = sorted(all_bars.keys())
print("\n=== RESULT ===")
print(f"total unique daily bars: {len(all_bars)}")
print(f"earliest: {dates[0]}")
print(f"latest:   {dates[-1]}")
# 检测缺口: 相邻日期差 > 7 天视为可能有缺
gaps = []
for i in range(1, len(dates)):
    a = datetime.strptime(dates[i-1], "%Y-%m-%d")
    b = datetime.strptime(dates[i], "%Y-%m-%d")
    diff = (b - a).days
    if diff > 7:
        gaps.append((dates[i-1], dates[i], diff))
print(f"gaps>7days: {len(gaps)}")
for g in gaps[:10]:
    print("  gap", g)
