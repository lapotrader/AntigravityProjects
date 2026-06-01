"""
BUND 1h — ATR-channel breakout + Donchian breakout with IS/VAL/OOS + ON/OFF filter.

ATR-channel: close[i] > high[i-1]+k*ATR[i-1] -> LONG at open[i+1]
Donchian:    close[i] > HH(20)[i-1]          -> LONG at open[i+1]
"""
import pandas as pd, numpy as np, itertools

cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns=["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
cont.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: cont[c]=cont[c].astype(float)

is_df  = cont[cont.index < "2020-01-01"].copy()
val_df = cont[(cont.index >= "2020-01-01") & (cont.index < "2023-01-01")].copy()
oos_df = cont[cont.index >= "2023-01-01"].copy()
print(f"Data: {len(cont):,} bars | IS: {len(is_df):,} | VAL: {len(val_df):,} | OOS: {len(oos_df):,}")

# ── Indicators ─────────────────────────────────────────────────────────────
def compute_atr(h, l, c, period):
    n = len(h); tr = np.zeros(n); atr = np.zeros(n)
    tr[0] = h[0] - l[0]
    for i in range(1, n):
        tr[i] = max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1]))
    atr[0] = tr[0]; alpha = 2/(period+1)
    for i in range(1, n): atr[i] = atr[i-1] + alpha*(tr[i]-atr[i-1])
    return atr

def rolling_max(a, period):
    n = len(a); out = np.full(n, np.nan)
    for i in range(period-1, n): out[i] = np.max(a[i-period+1:i+1])
    return out

def rolling_min(a, period):
    n = len(a); out = np.full(n, np.nan)
    for i in range(period-1, n): out[i] = np.min(a[i-period+1:i+1])
    return out

# ── Strategy: ATR-channel ──────────────────────────────────────────────────
def run_atr_channel(df, k, tp_atr, sl_atr=2.0, period=20, timeout=30):
    n = len(df)
    op = df["open"].values; hi = df["high"].values; lo = df["low"].values; cl = df["close"].values

    atr = compute_atr(hi, lo, cl, period)

    # shift(1): atr_s[i] = atr[i-1], hi_s[i] = hi[i-1]
    atr_s = np.roll(atr, 1); atr_s[0] = np.nan
    hi_s = np.roll(hi, 1); hi_s[0] = np.nan
    lo_s = np.roll(lo, 1); lo_s[0] = np.nan

    # Signal at bar i: cl[i] > hi[i-1] + k*atr[i-1]  -> LONG
    # i.e. cl[i] > hi_s[i] + k*atr_s[i]
    # Entry at open[i+1]
    band_up = hi_s + k * atr_s
    band_dn = lo_s - k * atr_s

    trades = []; it = False; ep = 0; ei = 0; sd = ""; sp = 0; tpp = 0

    i = 0
    while i < n:
        if not it:
            if i < n - 1:
                sig_long = cl[i] > band_up[i]
                sig_short = cl[i] < band_dn[i]
            else:
                sig_long = False; sig_short = False

            if sig_long or sig_short:
                sd = "LONG" if sig_long else "SHORT"
                entry_bar = i + 1
                if entry_bar >= n: break
                ep = float(op[entry_bar]); ei = entry_bar
                atr_e = float(atr_s[i])
                if atr_e <= 0:
                    i += 1; continue
                if sd == "LONG":
                    sp = ep - sl_atr * atr_e
                    tpp = ep + tp_atr * atr_e
                else:
                    sp = ep + sl_atr * atr_e
                    tpp = ep - tp_atr * atr_e
                it = True
                i = entry_bar  # resume from entry bar
                continue
            i += 1
        else:
            lo_i = float(lo[i]); hi_i = float(hi[i]); ex = False; exp = 0
            if sd == "LONG":
                if lo_i <= sp: exp = sp; ex = True
                elif hi_i >= tpp: exp = tpp; ex = True
            else:
                if hi_i >= sp: exp = sp; ex = True
                elif lo_i <= tpp: exp = tpp; ex = True
            if not ex and (i - ei) >= timeout:
                exp = float(cl[i]); ex = True
            if ex:
                pnl = round(exp - ep, 2) if sd == "LONG" else round(ep - exp, 2)
                trades.append({"pnl": pnl, "dir": sd, "ix": ei, "exit_ix": i,
                               "ts": str(df.index[ei]), "exit_ts": str(df.index[i])})
                it = False
            i += 1
    return trades

# ── Strategy: ATR-channel with swing SL ────────────────────────────────────
def run_atr_channel_swing(df, k, tp_atr, sl_atr=2.0, period=20, timeout=30):
    n = len(df)
    op = df["open"].values; hi = df["high"].values; lo = df["low"].values; cl = df["close"].values

    atr = compute_atr(hi, lo, cl, period)
    atr_s = np.roll(atr, 1); atr_s[0] = np.nan
    hi_s = np.roll(hi, 1); hi_s[0] = np.nan
    lo_s = np.roll(lo, 1); lo_s[0] = np.nan

    band_up = hi_s + k * atr_s
    band_dn = lo_s - k * atr_s

    trades = []; it = False; ep = 0; ei = 0; sd = ""; sp = 0; tpp = 0

    i = 0
    while i < n:
        if not it:
            if i < n - 1:
                sig_long = not np.isnan(band_up[i]) and cl[i] > band_up[i]
                sig_short = not np.isnan(band_dn[i]) and cl[i] < band_dn[i]
            else:
                sig_long = False; sig_short = False

            if sig_long or sig_short:
                sd = "LONG" if sig_long else "SHORT"
                entry_bar = i + 1
                if entry_bar >= n: break
                ep = float(op[entry_bar]); ei = entry_bar
                atr_e = float(atr_s[i])
                if atr_e <= 0: i += 1; continue

                hh_swing = float(np.max(hi[max(0,entry_bar-5):entry_bar]))
                ll_swing = float(np.min(lo[max(0,entry_bar-5):entry_bar]))

                if sd == "LONG":
                    sp = ll_swing
                    if sp >= ep: sp = ep - sl_atr * atr_e
                    tpp = ep + tp_atr * atr_e
                else:
                    sp = hh_swing
                    if sp <= ep: sp = ep + sl_atr * atr_e
                    tpp = ep - tp_atr * atr_e
                it = True
                i = entry_bar
                continue
            i += 1
        else:
            lo_i = float(lo[i]); hi_i = float(hi[i]); ex = False; exp = 0
            if sd == "LONG":
                if lo_i <= sp: exp = sp; ex = True
                elif hi_i >= tpp: exp = tpp; ex = True
            else:
                if hi_i >= sp: exp = sp; ex = True
                elif lo_i <= tpp: exp = tpp; ex = True
            if not ex and (i - ei) >= timeout:
                exp = float(cl[i]); ex = True
            if ex:
                pnl = round(exp - ep, 2) if sd == "LONG" else round(ep - exp, 2)
                trades.append({"pnl": pnl, "dir": sd, "ix": ei, "exit_ix": i,
                               "ts": str(df.index[ei]), "exit_ts": str(df.index[i])})
                it = False
            i += 1
    return trades

# ── Strategy: Donchian ─────────────────────────────────────────────────────
def run_donchian(df, tp_atr, sl_atr=2.0, period=20, timeout=30):
    n = len(df)
    op = df["open"].values; hi = df["high"].values; lo = df["low"].values; cl = df["close"].values

    atr = compute_atr(hi, lo, cl, period)
    hh = rolling_max(hi, period)
    ll = rolling_min(lo, period)

    atr_s = np.roll(atr, 1); atr_s[0] = np.nan
    hh_s  = np.roll(hh, 1);  hh_s[0] = np.nan
    ll_s  = np.roll(ll, 1);  ll_s[0] = np.nan

    trades = []; it = False; ep = 0; ei = 0; sd = ""; sp = 0; tpp = 0

    i = period + 2
    while i < n:
        if not it:
            sig_long = not np.isnan(hh_s[i]) and cl[i] > hh_s[i]
            sig_short = not np.isnan(ll_s[i]) and cl[i] < ll_s[i]

            if sig_long or sig_short:
                sd = "LONG" if sig_long else "SHORT"
                entry_bar = i + 1
                if entry_bar >= n: break
                ep = float(op[entry_bar]); ei = entry_bar
                atr_e = float(atr_s[i])
                if atr_e <= 0: i += 1; continue

                if sd == "LONG":
                    sp = ll_s[i]
                    if sp >= ep: sp = ep - sl_atr * atr_e
                    tpp = ep + tp_atr * atr_e
                else:
                    sp = hh_s[i]
                    if sp <= ep: sp = ep + sl_atr * atr_e
                    tpp = ep - tp_atr * atr_e
                it = True
                i = entry_bar
                continue
            i += 1
        else:
            lo_i = float(lo[i]); hi_i = float(hi[i]); ex = False; exp = 0
            if sd == "LONG":
                if lo_i <= sp: exp = sp; ex = True
                elif hi_i >= tpp: exp = tpp; ex = True
            else:
                if hi_i >= sp: exp = sp; ex = True
                elif lo_i <= tpp: exp = tpp; ex = True
            if not ex and (i - ei) >= timeout:
                exp = float(cl[i]); ex = True
            if ex:
                pnl = round(exp - ep, 2) if sd == "LONG" else round(ep - exp, 2)
                trades.append({"pnl": pnl, "dir": sd, "ix": ei, "exit_ix": i,
                               "ts": str(df.index[ei]), "exit_ts": str(df.index[i])})
                it = False
            i += 1
    return trades

# ── Reporting ──────────────────────────────────────────────────────────────
def report(trades, label):
    total = len(trades)
    if total == 0:
        print(f"{label:<60}: 0 trades")
        return {"n": 0, "pf": 0, "pnl": 0}
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = total - wins
    gw = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gl = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    pf = gw / gl if gl else 999
    avg_w = gw/wins if wins else 0
    avg_l = gl/losses if losses else 0
    total_pnl = sum(t["pnl"] for t in trades)
    wr = wins/max(total,1)*100
    print(f"{label:<60}: {total:4d}tr  WR={wr:5.1f}%  PnL={total_pnl:+8.2f}  "
          f"PF={pf:6.3f}  AvgW={avg_w:6.2f}  AvgL={avg_l:6.2f}")
    return {"n": total, "wins": wins, "losses": losses, "gw": gw, "gl": gl,
            "pf": pf, "pnl": total_pnl, "avg_w": avg_w, "avg_l": avg_l}

def apply_onoff_pnl(trades, roll_months=3):
    if len(trades) == 0: return [], {}
    months = sorted(set(t["ts"][:7] for t in trades))
    monthly_pnl = {m: 0 for m in months}
    for t in trades: monthly_pnl[t["ts"][:7]] += t["pnl"]
    month_list = sorted(months)
    on_states = {}
    for i, m in enumerate(month_list):
        if i < roll_months:
            on_states[m] = True
        else:
            roll_sum = sum(monthly_pnl[month_list[j]] for j in range(i-roll_months, i))
            on_states[m] = roll_sum >= 0
    filtered = [t for t in trades if on_states.get(t["ts"][:7], True)]
    return filtered, on_states, monthly_pnl

def report_with_onoff(trades, label):
    r = report(trades, label)
    if r["n"] == 0:
        print(f"{'':60}  0 trades (filtered)")
        return r, {"pf": 0, "n": 0}
    ft, on_states, mpnl = apply_onoff_pnl(trades)
    fr = report(ft, label + " (filtered)")
    print(f"{'':60}  ON={sum(1 for v in on_states.values() if v)}/{len(on_states)} months")
    return r, fr


# ═══════════════════════════════════════════════════════════════════════════
#  ATR-CHANNEL BREAKOUT
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 100)
print("  ATR-CHANNEL BREAKOUT  (close > high[i-1]+k*ATR[i-1] -> LONG at open[i+1])")
print("=" * 100)

k_vals = [0.5, 1.0, 1.5, 2.0]
tp_vals = [2.0, 3.0, 4.0]

print("\n--- IS Parameter Scan (fixed SL=2atr) ---")
results = []
for k, tp in itertools.product(k_vals, tp_vals):
    trades = run_atr_channel(is_df, k=k, tp_atr=tp)
    tag = f"k={k:.1f} TP={tp:.0f}atr"
    r = report(trades, tag)
    results.append({"k": k, "tp": tp, **r})

valid = [r for r in results if r["n"] >= 10 and r["wins"] < r["n"]]
best_atr = max(valid, key=lambda x: x["pf"]) if valid else {}

print(f"\n>>> BEST IS: k={best_atr['k']:.1f}  TP={best_atr['tp']:.0f}atr  "
      f"PF={best_atr['pf']:.3f}  trades={best_atr['n']}") if best_atr else print("No valid")

print("\n--- VAL & OOS for BEST + Fixed ---")
if best_atr:
    for period, df_ in [("VAL", val_df), ("OOS", oos_df)]:
        t = run_atr_channel(df_, k=best_atr["k"], tp_atr=best_atr["tp"])
        report_with_onoff(t, f"BEST {period}")
else:
    print("No best params to test")

print("\n--- FIXED PARAMS (k=1.0 TP=3atr) ---")
for label, df_ in [("IS", is_df), ("VAL", val_df), ("OOS", oos_df)]:
    t = run_atr_channel(df_, k=1.0, tp_atr=3.0)
    report_with_onoff(t, f"FIXED {label}")

# ── Swing SL ───────────────────────────────────────────────────────────────
print("\n--- IS Parameter Scan (swing SL) ---")
results2 = []
for k, tp in itertools.product(k_vals, tp_vals):
    trades = run_atr_channel_swing(is_df, k=k, tp_atr=tp)
    tag = f"k={k:.1f} TP={tp:.0f}atr swingSL"
    r = report(trades, tag)
    results2.append({"k": k, "tp": tp, **r})

valid2 = [r for r in results2 if r["n"] >= 10 and r["wins"] < r["n"]]
best_atr_swing = max(valid2, key=lambda x: x["pf"]) if valid2 else {}

if best_atr_swing:
    print(f"\n>>> BEST IS (swing SL): k={best_atr_swing['k']:.1f} TP={best_atr_swing['tp']:.0f}atr  "
          f"PF={best_atr_swing['pf']:.3f}  trades={best_atr_swing['n']}")
    for period, df_ in [("VAL", val_df), ("OOS", oos_df)]:
        t = run_atr_channel_swing(df_, k=best_atr_swing["k"], tp_atr=best_atr_swing["tp"])
        report_with_onoff(t, f"BEST swing {period}")
else:
    print("No valid param set on IS (swing SL)")


# ═══════════════════════════════════════════════════════════════════════════
#  DONCHIAN BREAKOUT
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 100)
print("  DONCHIAN BREAKOUT")
print("=" * 100)

print("\n--- IS Parameter Scan ---")
d_results = []
for tp in [2.0, 3.0]:
    trades = run_donchian(is_df, tp_atr=tp)
    tag = f"Donchian TP={tp:.0f}atr"
    r = report(trades, tag)
    d_results.append({"tp": tp, **r})

valid_d = [r for r in d_results if r["n"] >= 10 and r["wins"] < r["n"]]
best_d = max(valid_d, key=lambda x: x["pf"]) if valid_d else {}

if best_d:
    print(f"\n>>> BEST IS: Donchian TP={best_d['tp']:.0f}atr  PF={best_d['pf']:.3f}  trades={best_d['n']}")
    for period, df_ in [("VAL", val_df), ("OOS", oos_df)]:
        t = run_donchian(df_, tp_atr=best_d["tp"])
        report_with_onoff(t, f"BEST Donchian {period}")
else:
    print("No valid param set on IS")


# ═══════════════════════════════════════════════════════════════════════════
#  CONSOLIDATED
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 100)
print("  CONSOLIDATED RESULTS")
print("=" * 100)

def pf_stats(tr):
    n = len(tr); wins = sum(1 for x in tr if x["pnl"] > 0)
    gw = sum(x["pnl"] for x in tr if x["pnl"] > 0)
    gl = abs(sum(x["pnl"] for x in tr if x["pnl"] <= 0))
    pf = gw/gl if gl else 999
    pnl = sum(x["pnl"] for x in tr)
    return n, pf, pnl

param_map = {"k": "k", "tp": "tp_atr"}
rows = []
confs = [
    ("ATR-CH (optim)", run_atr_channel, best_atr, ("k", "tp")),
    ("ATR-CH (fixed)", run_atr_channel, {"k": 1.0, "tp": 3.0}, ("k", "tp")),
    ("ATR-CH swing (optim)", run_atr_channel_swing, best_atr_swing, ("k", "tp")),
    ("Donchian (optim)", run_donchian, best_d, ("tp",)),
]

for name, fn, params, pnames in confs:
    if not params:
        for p in ["IS", "VAL", "OOS"]:
            rows.append((name, p, "0", "0", "0"))
        continue
    for p in ["IS", "VAL", "OOS"]:
        df_ = {"IS": is_df, "VAL": val_df, "OOS": oos_df}[p]
        kw = {param_map[k]: params[k] for k in pnames}
        t = fn(df_, **kw)
        n1, pf1, pnl1 = pf_stats(t)
        ft, _, _ = apply_onoff_pnl(t)
        n2, pf2, pnl2 = pf_stats(ft)
        rows.append((name, p, f"{n1}tr PnL={pnl1:+.1f} PF={pf1:.2f}",
                     f"{n2}tr PnL={pnl2:+.1f} PF={pf2:.2f}"))

print(f"\n{'Strategy':<30} {'Per':<6} {'No Filter':<28} {'Filtered':<28}")
print("-" * 92)
for name, period, nf, f in rows:
    print(f"{name:<30} {period:<6} {nf:<28} {f:<28}")
