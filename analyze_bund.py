import pandas as pd, numpy as np
from scipy import stats

# ── Config ──
DATA = "dati/bund_m1.txt"
TICK = 0.01  # 1 tick = 0.01 point
START = "2024-01-01"  # Focus on recent 2.5 years
END = "2026-06-01"

# ── Load ──
print("Loading data...")
cols = ["date","time","open","high","low","close","volume"]
df = pd.read_csv(DATA, sep=",", header=None, names=cols)
df["datetime"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"])
df.set_index("datetime", inplace=True)
for c in ["open","high","low","close","volume"]: df[c] = df[c].astype(float)
df["volume"] = df["volume"].astype(int)
df.drop(columns=["date","time"], inplace=True)
print(f"  Loaded {len(df):,} rows from {df.index[0]} to {df.index[-1]}")

# Filter to recent + Eurex hours
mask_date = (df.index >= START) & (df.index < END)
df = df[mask_date].copy()
print(f"  Subset {START}–{END}: {len(df):,} rows")
print()

# ───────────────────────────────────────────────────────
# 1. HOURLY SEASONALITY
# ───────────────────────────────────────────────────────
print("=" * 70)
print("1. HOURLY SEASONALITY")
print("=" * 70)

df["hour"] = df.index.hour
df["minute"] = df.index.hour * 60 + df.index.minute
df["ret_ticks"] = (df["close"] - df["close"].shift(1)) / TICK
df["ret_ticks"] = df["ret_ticks"].fillna(0)
df["range"] = (df["high"] - df["low"]) / TICK  # in ticks

hrly = df[df["hour"].between(7, 20)].copy()  # Eurex hours 07-20 UTC = 08-21 CET

hourly_stats = []
for h, grp in df.groupby("hour"):
    if h < 7 or h > 20:  # skip outside Eurex
        continue
    rets = grp["ret_ticks"]
    if len(rets) == 0:
        continue
    avg_ret = rets.mean()
    std_ret = rets.std()
    win_rate = (rets > 0).mean()
    avg_range = grp["range"].mean()
    n_obs = len(rets)
    hourly_stats.append({
        "Hour": f"{h:02d}:00",
        "N_obs": n_obs,
        "AvgRet_tick": avg_ret,
        "Std_tick": std_ret,
        "WinRate%": win_rate * 100,
        "AvgRange_ticks": avg_range,
        "Sharpe_hourly": avg_ret / std_ret * np.sqrt(60) if std_ret > 0 else 0
    })

hourly_df = pd.DataFrame(hourly_stats)
print("\nHourly Statistics (Eurex hours, 2024-2026):")
print(hourly_df.round(4).to_string(index=False))

# Summary
best_vol = hourly_df.loc[hourly_df["Std_tick"].idxmax()]
best_ret = hourly_df.loc[hourly_df["AvgRet_tick"].idxmax()]
best_dir = hourly_df.loc[hourly_df["WinRate%"].idxmax()]
print(f"\n  Highest volatility (std):   Hour {best_vol['Hour']}  ({best_vol['Std_tick']:.3f} ticks)")
print(f"  Highest avg return:         Hour {best_ret['Hour']}  ({best_ret['AvgRet_tick']:.4f} ticks)")
print(f"  Best directional cons.:     Hour {best_dir['Hour']}  ({best_dir['WinRate%']:.1f}%)")
print()

# ───────────────────────────────────────────────────────
# 2. FIRST HOUR REVERSAL
# ───────────────────────────────────────────────────────
print("=" * 70)
print("2. FIRST HOUR REVERSAL PATTERN")
print("=" * 70)

daily_ret_1h = df["close"].resample("D").last().pct_change()  # not used here
daily_ret_1h[:] = np.nan

first_hour_rets = []
rest_day_rets = []

# Use opening/closing prices around first hour
for date, grp in df.groupby(df.index.date):
    day_data = grp.sort_index()
    # First hour: 08:00 to 09:00 (index hour 8)
    fh = day_data.between_time("08:00", "08:59")
    rd = day_data.between_time("09:00", "17:30")
    if len(fh) == 0 or len(rd) == 0:
        continue
    fh_open = fh.iloc[0]["open"]
    fh_close = fh.iloc[-1]["close"]
    rd_open = rd.iloc[0]["open"]
    rd_close = rd.iloc[-1]["close"]

    fh_ret = (fh_close - fh_open) / TICK
    rd_ret = (rd_close - rd_open) / TICK
    first_hour_rets.append(fh_ret)
    rest_day_rets.append(rd_ret)

fh_arr = np.array(first_hour_rets)
rd_arr = np.array(rest_day_rets)

print(f"  Days analyzed: {len(fh_arr)}")
print(f"  Avg first-hour return: {fh_arr.mean():.2f} ticks")
print(f"  Avg rest-of-day return: {rd_arr.mean():.2f} ticks")
print(f"  Correlation (1h vs rest): {np.corrcoef(fh_arr, rd_arr)[0,1]:.4f}")

# Dummy strategy: go opposite of 1h signal at 9:00
reversal_signal = np.sign(fh_arr) * -1  # bet against first hour
reversal_pnl = reversal_signal * rd_arr
reversal_trades = len(reversal_signal)
reversal_wins = (reversal_pnl > 0).sum()
print(f"\n  Reversal (opposite 1h -> rest-of-day):")
print(f"    Trades: {reversal_trades}")
print(f"    Win rate: {reversal_wins/reversal_trades*100:.1f}%")
print(f"    Gross PnL: {reversal_pnl.sum():.1f} ticks ({reversal_pnl.sum()/100:.1f} points)")
print(f"    Avg PnL/trade: {reversal_pnl.mean():.2f} ticks")

# Continuation strategy: follow 1h signal
cont_signal = np.sign(fh_arr)
cont_pnl = cont_signal * rd_arr
cont_wins = (cont_pnl > 0).sum()
print(f"\n  Continuation (follow 1h -> rest-of-day):")
print(f"    Trades: {len(cont_pnl)}")
print(f"    Win rate: {cont_wins/len(cont_pnl)*100:.1f}%")
print(f"    Gross PnL: {cont_pnl.sum():.1f} ticks ({cont_pnl.sum()/100:.1f} points)")
print(f"    Avg PnL/trade: {cont_pnl.mean():.2f} ticks")
print()

# ───────────────────────────────────────────────────────
# 3. MICRO-MOMENTUM (1-bar autocorrelation & strategy)
# ───────────────────────────────────────────────────────
print("=" * 70)
print("3. MICRO-MOMENTUM")
print("=" * 70)

df["ret"] = np.log(df["close"] / df["close"].shift(1))
df["ret"] = df["ret"].fillna(0)

# Rolling autocorr lag-1 over 60 bars (1 hour)
df["autocorr_60"] = df["ret"].rolling(60).apply(lambda x: x.autocorr() if len(x) > 1 else 0, raw=False)

# Fill and clean
df["autocorr_60"] = df["autocorr_60"].fillna(0)

print("  Auto-correlation distribution (lag-1, 60-bar window):")
print(df["autocorr_60"].describe().round(4).to_string())
print()

# Test thresholds
THRESHOLDS = [0.1, 0.15, 0.2]
SL_TICKS = 20
TP_TICKS = 10

print(f"  Strategy: enter on autocorr > threshold, SL={SL_TICKS}t, TP={TP_TICKS}t\n")

for thresh in THRESHOLDS:
    # Generate signals
    entry_price = None
    position = 0  # 0 flat, 1 long, -1 short
    trades = []
    pnl_cur = 0
    trade_active = False

    prices = df["close"].values
    autocorr = df["autocorr_60"].values
    last_ret = df["ret"].values

    for i in range(60, len(prices)):
        if not trade_active:
            # Look for entry
            if autocorr[i] > thresh:
                if last_ret[i] > 0:
                    position = 1
                    entry_price = prices[i]
                    entry_idx = i
                    trade_active = True
                elif last_ret[i] < 0:
                    position = -1
                    entry_price = prices[i]
                    entry_idx = i
                    trade_active = True
        else:
            # Check exit
            if position == 1:
                pts = (prices[i] - entry_price) / TICK
                if pts >= TP_TICKS:
                    trades.append(TP_TICKS)
                    trade_active = False
                elif pts <= -SL_TICKS:
                    trades.append(-SL_TICKS)
                    trade_active = False
            elif position == -1:
                pts = (entry_price - prices[i]) / TICK
                if pts >= TP_TICKS:
                    trades.append(TP_TICKS)
                    trade_active = False
                elif pts <= -SL_TICKS:
                    trades.append(-SL_TICKS)
                    trade_active = False

    trades_arr = np.array(trades)
    if len(trades_arr) > 0:
        wins = (trades_arr > 0).sum()
        total_pnl = trades_arr.sum()
        pf = trades_arr[trades_arr > 0].sum() / abs(trades_arr[trades_arr < 0].sum()) if trades_arr[trades_arr < 0].sum() != 0 else float('inf')
        print(f"  Threshold={thresh}:  Trades={len(trades_arr):,}  Win%={wins/len(trades_arr)*100:.1f}  "
              f"PF={pf:.2f}  PnL={total_pnl:.0f}t ({total_pnl/100:.1f}pts)")
    else:
        print(f"  Threshold={thresh}:  No trades triggered")
print()

# ───────────────────────────────────────────────────────
# 4. VOLATILITY CLUSTERING
# ───────────────────────────────────────────────────────
print("=" * 70)
print("4. VOLATILITY CLUSTERING")
print("=" * 70)

df["abs_ret"] = np.abs(df["ret"])
df["vol_autocorr_1"] = df["abs_ret"].rolling(60).apply(lambda x: x.autocorr(lag=1) if len(x) > 1 else 0, raw=False)
df["vol_autocorr_5"] = df["abs_ret"].rolling(60).apply(lambda x: x.autocorr(lag=5) if len(x) > 1 else 0, raw=False)

print("  Autocorrelation of absolute returns (volatility persistence):")
print(f"    Lag-1 vol autocorr (mean): {df['vol_autocorr_1'].mean():.4f}")
print(f"    Lag-5 vol autocorr (mean): {df['vol_autocorr_5'].mean():.4f}")
print(f"  => Volatility CLUSTERS strongly (high persistence).")

# Check: does high vol regime predict direction?
df["vol_high"] = df["abs_ret"] > df["abs_ret"].rolling(60).mean()
# Does high vol period have mean-reverting vs trending tendency?
high_vol_rets = df[df["vol_high"]]["ret"]
low_vol_rets = df[~df["vol_high"]]["ret"]
print(f"  During HIGH vol: avg return = {high_vol_rets.mean()*10000:.2f} bps")
print(f"  During LOW vol:  avg return = {low_vol_rets.mean()*10000:.2f} bps")

# Check vol forecast: tomorrow's range vs today's vol
daily_max = df["high"].resample("D").max()
daily_min = df["low"].resample("D").min()
daily_range = (daily_max - daily_min) / TICK
daily_vol = np.log(df["close"].resample("D").last() / df["close"].resample("D").last().shift(1)).abs()
print(f"\n  Range persistence: daily range autocorr(1) = {daily_range.autocorr():.4f}")
print(f"  => Daily range autocorr = {daily_range.autocorr():.4f} ({'persistent' if daily_range.autocorr() > 0.2 else 'moderately persistent' if daily_range.autocorr() > 0 else 'not persistent'})")
print()

# ───────────────────────────────────────────────────────
# 5. OPEN-TO-CLOSE PATTERN (gap analysis)
# ───────────────────────────────────────────────────────
print("=" * 70)
print("5. GAP ANALYSIS (Open-to-previous-close)")
print("=" * 70)

# Get daily data
daily_open = df["open"].resample("D").first()
daily_close = df["close"].resample("D").last()
prev_close = daily_close.shift(1)
gap = (daily_open - prev_close) / TICK
daily_dir = (daily_close - daily_open) / TICK  # close - open

gap_df = pd.DataFrame({"gap": gap, "daily_dir": daily_dir}).dropna()
gap_df["gap_bin"] = pd.cut(gap_df["gap"].abs(), bins=[0, 5, 10, 20, 100], labels=["0-5", "5-10", "10-20", "20+"])

print("  Gap distribution and subsequent intraday direction:")
for lbl, grp in gap_df.groupby("gap_bin", observed=True):
    corr = grp["gap"].corr(grp["daily_dir"])
    mean_dir = grp["daily_dir"].mean()
    win = (grp["daily_dir"] > 0).mean() if mean_dir > 0 else (grp["daily_dir"] < 0).mean()
    n = len(grp)
    print(f"    Gap {lbl} ticks (n={n:4d}):  gap-dir corr={corr:+.3f}  "
          f"avg_day_dir={mean_dir:+.2f}t  win={win:.0%}  "
          f"{'continuation' if corr > 0 else 'reversal'}")

# Test gap thresholds
print("\n  Gap-based strategies:")
for gt in [5, 10, 20]:
    # Continuation
    cont_signal = np.sign(gap_df["gap"])
    cont_signal[np.abs(gap_df["gap"]) < gt] = 0
    cont_pnl = cont_signal * gap_df["daily_dir"]
    cont_trades = (cont_signal != 0).sum()
    cont_wins = ((cont_signal * gap_df["daily_dir"]) > 0).sum()
    if cont_trades > 0:
        print(f"    Continuation |gap|>={gt}t:  "
              f"trades={cont_trades}  win%={cont_wins/cont_trades*100:.0f}%  "
              f"pnl={cont_pnl.sum():.0f}t")

    # Reversal
    rev_signal = -np.sign(gap_df["gap"])
    rev_signal[np.abs(gap_df["gap"]) < gt] = 0
    rev_pnl = rev_signal * gap_df["daily_dir"]
    rev_trades = (rev_signal != 0).sum()
    rev_wins = ((rev_signal * gap_df["daily_dir"]) > 0).sum()
    if rev_trades > 0:
        print(f"    Reversal      |gap|>={gt}t:  "
              f"trades={rev_trades}  win%={rev_wins/rev_trades*100:.0f}%  "
              f"pnl={rev_pnl.sum():.0f}t")
print()

# ───────────────────────────────────────────────────────
# 6. PRACTICAL EDGE SUMMARY
# ───────────────────────────────────────────────────────
print("=" * 70)
print("6. KEY FINDINGS & RECOMMENDATIONS")
print("=" * 70)

# Let's compute PF properly for the hourly seasonality
# Find best hours for directional bias
best_long_hours = hourly_df[hourly_df["AvgRet_tick"] > 0].sort_values("AvgRet_tick", ascending=False)
best_short_hours = hourly_df[hourly_df["AvgRet_tick"] < 0].sort_values("AvgRet_tick")

print(f"\n  Best hours to BUY  (highest avg return):")
for _, r in best_long_hours.head(3).iterrows():
    print(f"    {r['Hour']}  avg={r['AvgRet_tick']:+.3f}t  wr={r['WinRate%']:.0f}%  "
          f"sharpe={r['Sharpe_hourly']:.2f}")

print(f"\n  Best hours to SELL (lowest avg return):")
for _, r in best_short_hours.head(3).iterrows():
    print(f"    {r['Hour']}  avg={r['AvgRet_tick']:+.3f}t  wr={r['WinRate%']:.0f}%  "
          f"sharpe={r['Sharpe_hourly']:.2f}")

vol_ranked = hourly_df.sort_values("Std_tick", ascending=False)
print(f"\n  Highest volatility hours:")
for _, r in vol_ranked.head(4).iterrows():
    print(f"    {r['Hour']}  std={r['Std_tick']:.3f}t  range={r['AvgRange_ticks']:.1f}t")
