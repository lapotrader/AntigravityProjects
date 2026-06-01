import pandas as pd
import numpy as np
from itertools import product
import warnings
warnings.filterwarnings('ignore')
pd.set_option('display.max_columns', 20)
pd.set_option('display.width', 200)

# ============ DATA ============
df = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
df.columns = ["data","open","high","low","close","volume"]
df["dt"] = pd.to_datetime(df["data"])
df.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: df[c] = df[c].astype(float)

ndf = pd.read_csv("dati/27 febbraio.txt", sep="\t", header=None, decimal=",")
ndf.columns = ["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: ndf[c] = ndf[c].astype(float)
ndf["dt"] = pd.to_datetime(ndf["data"], dayfirst=True)
ndf.sort_values("dt", inplace=True)
ndf.set_index("dt", inplace=True)

# ============ INDICATORS ============
def compute_atr(high, low, close, period=14):
    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - close.shift(1)),
                               np.abs(low - close.shift(1))))
    atr = tr.rolling(period, min_periods=period).mean()
    return atr

def compute_bb(close, period, std_mult):
    ma = close.rolling(period, min_periods=period).mean()
    std = close.rolling(period, min_periods=period).std(ddof=0)
    return ma + std_mult * std, ma - std_mult * std

# ============ STRATEGY ============
def run_strategy(df, bb_periods, bb_std, min_sig, sl_mult, tp_mult, use_filter=False, filter_days=90):
    n = len(df)
    idx = df.index
    o, h, l, c = df['open'].values, df['high'].values, df['low'].values, df['close'].values

    atr = compute_atr(df['high'], df['low'], df['close']).values

    bb_lower_sh = {}
    bb_upper_sh = {}
    for p in bb_periods:
        upper, lower = compute_bb(df['close'], p, bb_std)
        bb_upper_sh[p] = upper.shift(1).values
        bb_lower_sh[p] = lower.shift(1).values

    c_prev = np.concatenate([[np.nan], c[:-1]])
    long_votes = np.zeros((n, len(bb_periods)))
    short_votes = np.zeros((n, len(bb_periods)))
    for j, p in enumerate(bb_periods):
        long_votes[:, j] = (c_prev < bb_lower_sh[p]).astype(int)
        short_votes[:, j] = (c_prev > bb_upper_sh[p]).astype(int)
    sig = long_votes.sum(axis=1) - short_votes.sum(axis=1)
    long_entry = sig >= min_sig
    short_entry = sig <= -min_sig

    trades = []
    in_trade = False
    entry_bar = -1; direction = 0; entry_px = 0; sl = 0; tp = 0; bars = 0
    trade_pnl_at_close = np.zeros(n)

    for i in range(max(50, max(bb_periods)), n):
        if in_trade:
            bars += 1
            exit_px = None; reason = ''
            if direction == 1:
                if l[i] <= sl:
                    exit_px = sl; reason = 'SL'
                elif h[i] >= tp:
                    exit_px = tp; reason = 'TP'
            else:
                if h[i] >= sl:
                    exit_px = sl; reason = 'SL'
                elif l[i] <= tp:
                    exit_px = tp; reason = 'TP'
            if exit_px is None and bars >= 40:
                exit_px = c[i]; reason = 'Timeout'
            if exit_px is not None:
                pnl = (exit_px - entry_px) * direction
                trades.append(dict(entry_bar=entry_bar, exit_bar=i, direction=direction,
                                   entry_px=entry_px, exit_px=exit_px, sl=sl, tp=tp,
                                   pnl=pnl, bars=bars, reason=reason,
                                   entry_dt=idx[entry_bar], exit_dt=idx[i]))
                trade_pnl_at_close[i] = pnl
                in_trade = False; bars = 0

        if not in_trade:
            enter = False; dir_ = 0
            if long_entry[i]:
                if not use_filter:
                    enter, dir_ = True, 1
                else:
                    cutoff = idx[i] - pd.Timedelta(days=filter_days)
                    mask = idx[:i] >= cutoff
                    if trade_pnl_at_close[:i][mask].sum() >= 0:
                        enter, dir_ = True, 1
            if not enter and short_entry[i]:
                if not use_filter:
                    enter, dir_ = True, -1
                else:
                    cutoff = idx[i] - pd.Timedelta(days=filter_days)
                    mask = idx[:i] >= cutoff
                    if trade_pnl_at_close[:i][mask].sum() >= 0:
                        enter, dir_ = True, -1
            if enter:
                in_trade = True; direction = dir_; entry_bar = i
                entry_px = o[i]; bars = 0
                curr_atr = atr[i-1] if not np.isnan(atr[i-1]) else atr[max(0,i-2)]
                if dir_ == 1:
                    swing_l = l[max(0,i-5):i].min()
                    sl_swing = swing_l - 0.5 * curr_atr
                    sl_atr = entry_px - curr_atr * sl_mult
                    sl = max(sl_swing, sl_atr)
                    tp = entry_px + curr_atr * tp_mult
                else:
                    swing_h = h[max(0,i-5):i].max()
                    sl_swing = swing_h + 0.5 * curr_atr
                    sl_atr = entry_px + curr_atr * sl_mult
                    sl = min(sl_swing, sl_atr)
                    tp = entry_px - curr_atr * tp_mult

    return trades, sig

def metrics(trades):
    if len(trades) < 5:
        return None
    pnls = np.array([t['pnl'] for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    n = len(pnls)
    wr = len(wins) / n
    pf = wins.sum() / abs(losses.sum()) if len(losses) > 0 and losses.sum() != 0 else (np.inf if len(wins) > 0 else 0)
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = losses.mean() if len(losses) > 0 else 0
    tot = pnls.sum()
    cum = pnls.cumsum()
    dd = (np.maximum.accumulate(cum) - cum).max()
    return dict(n=n, pf=pf, wr=wr, avg_win=avg_win, avg_loss=avg_loss, tot_pnl=tot,
                max_dd=dd, all_wins=(len(losses)==0), all_losses=(len(wins)==0))

def fmt_metrics(m):
    if m is None: return "INSUFFICIENT TRADES"
    return (f"n={m['n']:3d}  PF={m['pf']:6.2f}  WR={m['wr']:.0%}  "
            f"AvgW={m['avg_win']:7.2f}  AvgL={m['avg_loss']:7.2f}  "
            f"Tot={m['tot_pnl']:8.2f}  MaxDD={m['max_dd']:7.2f}")

# ============ PARAM GRID ============
bb_opts = [[10, 20], [20, 50], [10, 20, 50]]
std_opts = [1.5, 2.0, 2.5]
min_sig_opts = [1, 2]
sl_opts = [1.5, 2.0, 3.0]
tp_opts = [2.0, 3.0, 4.0]

# Split IS / OOS
mid = len(df) // 2
df_is = df.iloc[:mid].copy()
df_oos = df.iloc[mid:].copy()
print(f"Total bars: {len(df)}, IS: {len(df_is)}, OOS: {len(df_oos)}")

print("\n========== PARAM GRID OPTIMIZATION (IS) ==========")
results = []
total_combos = len(bb_opts)*len(std_opts)*len(min_sig_opts)*len(sl_opts)*len(tp_opts)
count = 0
for bp, std, ms, slm, tpm in product(bb_opts, std_opts, min_sig_opts, sl_opts, tp_opts):
    count += 1
    trades, _ = run_strategy(df_is, bp, std, ms, slm, tpm)
    m = metrics(trades)
    if m is not None and not m['all_wins'] and not m['all_losses']:
        results.append(dict(bb=str(bp), std=std, min_sig=ms, sl_mult=slm, tp_mult=tpm, **m))
    if count % 20 == 0:
        print(f"  Progress: {count}/{total_combos}", end='\r')

print(f"\n  Complete: {count}/{total_combos}, valid: {len(results)}")

if results:
    rdf = pd.DataFrame(results).sort_values('pf', ascending=False)
    print(f"\nTop 15 by PF (IS):")
    cols = ['bb','std','min_sig','sl_mult','tp_mult','n','pf','wr','tot_pnl','max_dd']
    print(rdf[cols].head(15).to_string(index=False))

    # Summary by BB period group
    print(f"\nParameter influence (avg PF by group):")
    print(f"  BB periods: {rdf.groupby('bb')['pf'].agg(['mean','std','count']).to_string()}")
    print(f"  Std:        {rdf.groupby('std')['pf'].agg(['mean','std','count']).to_string()}")
    print(f"  Min_sig:    {rdf.groupby('min_sig')['pf'].agg(['mean','std','count']).to_string()}")
    print(f"  sl_mult:    {rdf.groupby('sl_mult')['pf'].agg(['mean','std','count']).to_string()}")
    print(f"  tp_mult:    {rdf.groupby('tp_mult')['pf'].agg(['mean','std','count']).to_string()}")

    best = rdf.iloc[0]
    print(f"\n========== BEST IS PARAMS ==========")
    print(f"  BB periods: {best['bb']}, std={best['std']}, min_sig={best['min_sig']}, "
          f"sl_mult={best['sl_mult']}, tp_mult={best['tp_mult']}")
    print(f"  IS: {fmt_metrics(best.to_dict())}")

    print(f"\n========== OOS (BEST PARAMS) ==========")
    bp_best = eval(best['bb']) if isinstance(best['bb'], str) else best['bb']
    trades_oos, sig_oos = run_strategy(df_oos, bp_best, best['std'], best['min_sig'],
                                        best['sl_mult'], best['tp_mult'])
    moos = metrics(trades_oos)
    print(f"  OOS: {fmt_metrics(moos)}" if moos else "  OOS: INSUFFICIENT TRADES")

    print(f"\nTop 5 IS params -> OOS performance:")
    for idx in range(min(5, len(rdf))):
        row = rdf.iloc[idx]
        bp_ = eval(row['bb']) if isinstance(row['bb'], str) else row['bb']
        to, _ = run_strategy(df_oos, bp_, row['std'], row['min_sig'], row['sl_mult'], row['tp_mult'])
        mo = metrics(to)
        print(f"  Rank {idx+1}: BB={row['bb']}, std={row['std']}, ms={row['min_sig']}, "
              f"sl={row['sl_mult']}, tp={row['tp_mult']}")
        print(f"    IS: {fmt_metrics(row.to_dict())}")
        print(f"    OOS: {fmt_metrics(mo)}" if mo else f"    OOS: INSUFFICIENT TRADES")

# ============ FIXED PARAMS ============
print(f"\n========== FIXED PARAMS TEST ==========")
print(f"  BB[10,20], std=2.0, min_sig=1, sl_mult=2.0, tp_mult=3.0")
trades_fixed_is, _ = run_strategy(df_is, [10,20], 2.0, 1, 2.0, 3.0)
mf_is = metrics(trades_fixed_is)
print(f"  IS: {fmt_metrics(mf_is)}")
trades_fixed_oos, _ = run_strategy(df_oos, [10,20], 2.0, 1, 2.0, 3.0)
mf_oos = metrics(trades_fixed_oos)
print(f"  OOS: {fmt_metrics(mf_oos)}")

# ============ ON/OFF FILTER ============
print(f"\n========== ON/OFF FILTER COMPARISON (FIXED PARAMS) ==========")
# OFF (already done above)
# ON
trades_on_is, _ = run_strategy(df_is, [10,20], 2.0, 1, 2.0, 3.0, use_filter=True)
mon_is = metrics(trades_on_is)
print(f"  IS OFF: {fmt_metrics(mf_is)}")
print(f"  IS ON:  {fmt_metrics(mon_is)}")

trades_on_oos, _ = run_strategy(df_oos, [10,20], 2.0, 1, 2.0, 3.0, use_filter=True)
mon_oos = metrics(trades_on_oos)
print(f"  OOS OFF: {fmt_metrics(mf_oos)}")
print(f"  OOS ON:  {fmt_metrics(mon_oos)}")

# ============ NEW DATA FILE ============
print(f"\n========== NEW DATA: 27 FEBBRAIO ==========")
print(f"  Bars: {len(ndf)}")
# Run fixed params on full new data
trades_ndf, _ = run_strategy(ndf, [10,20], 2.0, 1, 2.0, 3.0)
mndf = metrics(trades_ndf)
print(f"  Fixed params: {fmt_metrics(mndf)}")

if results:
    # Best IS params on new data
    trades_ndf_best, _ = run_strategy(ndf, bp_best, best['std'], best['min_sig'],
                                       best['sl_mult'], best['tp_mult'])
    mndf_best = metrics(trades_ndf_best)
    print(f"  Best IS params: {fmt_metrics(mndf_best)}")

print(f"\nDone.")
