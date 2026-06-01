import pandas as pd
import numpy as np
from itertools import product
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# LOAD DATA
# ============================================================
def load_btp_full() -> pd.DataFrame:
    df = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
    df.columns = ["data","open","high","low","close","volume"]
    df["dt"] = pd.to_datetime(df["data"])
    df.set_index("dt", inplace=True)
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df.sort_index(inplace=True)
    return df

def load_27feb() -> pd.DataFrame:
    df = pd.read_csv("dati/27 febbraio.txt", sep="\t", decimal=",", header=None)
    df.columns = ["data","high","low","open","close","volume"]
    df["dt"] = pd.to_datetime(df["data"], dayfirst=True)
    df.set_index("dt", inplace=True)
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    df.sort_index(inplace=True)
    return df

# ============================================================
# INDICATORS (no look-ahead: all shifted)
# ============================================================
def add_indicators(df: pd.DataFrame, k: int, d: int, smooth: int):
    h = df["high"]
    l = df["low"]
    c = df["close"]

    ll = l.rolling(k, min_periods=k).min()
    hh = h.rolling(k, min_periods=k).max()
    stoch_raw = 100 * (c - ll) / (hh - ll)
    stoch_k = stoch_raw.rolling(smooth, min_periods=smooth).mean()
    stoch_d = stoch_k.rolling(d, min_periods=d).mean()

    df["stoch_k"] = stoch_k.shift(1)
    df["stoch_d"] = stoch_d.shift(1)
    df["stoch_k_p"] = stoch_k.shift(2)
    df["stoch_d_p"] = stoch_d.shift(2)

    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(14, min_periods=14).mean()
    df["atr"] = atr.shift(1)

    df["sl5"] = df["low"].rolling(5, min_periods=1).min().shift(1)
    df["sh5"] = df["high"].rolling(5, min_periods=1).max().shift(1)

    df["stoch_k_raw"] = stoch_raw

# ============================================================
# BACKTEST
# ============================================================
def run_backtest(df: pd.DataFrame, k: int, d: int, smooth: int,
                 oversold: float, overbought: float, tp_mult: float,
                 zone_filter: bool, sl_atr: float = 2.0,
                 timeout: int = 40) -> pd.DataFrame:
    df = df.copy()
    add_indicators(df, k, d, smooth)

    startup = max(k, d, smooth, 14, 5) + 5

    cross_above = (df["stoch_k"] > df["stoch_d"]) & (df["stoch_k_p"] <= df["stoch_d_p"])
    cross_below = (df["stoch_k"] < df["stoch_d"]) & (df["stoch_k_p"] >= df["stoch_d_p"])

    if zone_filter:
        if oversold is not None:
            k_raw = df["stoch_k_raw"].shift(1)
            was_oversold = k_raw.rolling(5, min_periods=1).min() < oversold
            cross_above = cross_above & was_oversold
        if overbought is not None:
            k_raw = df["stoch_k_raw"].shift(1)
            was_overbought = k_raw.rolling(5, min_periods=1).max() > overbought
            cross_below = cross_below & was_overbought

    df["signal"] = np.where(cross_above, 1, np.where(cross_below, -1, 0))

    pos = 0; ep = 0.0; ebar = 0; sl = 0.0; tp = 0.0
    trades = []

    for i in range(1, len(df)):
        idx = df.index[i]
        if pos == 0:
            s = df["signal"].iloc[i]
            atr_v = df["atr"].iloc[i]
            if s != 0 and not np.isnan(atr_v) and atr_v > 0 and i >= startup:
                pos = s
                ep = df["open"].iloc[i]
                ebar = i
                if pos == 1:
                    sl = df["sl5"].iloc[i]
                    if np.isnan(sl) or sl >= ep:
                        sl = ep - sl_atr * atr_v
                    tp = ep + tp_mult * atr_v
                else:
                    sl = df["sh5"].iloc[i]
                    if np.isnan(sl) or sl <= ep:
                        sl = ep + sl_atr * atr_v
                    tp = ep - tp_mult * atr_v
        else:
            bars = i - ebar
            h, l, c_ = df["high"].iloc[i], df["low"].iloc[i], df["close"].iloc[i]
            reason = None; xp = None
            if pos == 1:
                if l <= sl: xp, reason = sl, "sl"
                elif h >= tp: xp, reason = tp, "tp"
            else:
                if h >= sl: xp, reason = sl, "sl"
                elif l <= tp: xp, reason = tp, "tp"
            if reason is None and bars >= timeout:
                xp, reason = c_, "to"
            if reason is not None:
                ret = (xp - ep) / ep * pos
                trades.append((idx, ret, reason, ep, xp, pos, ebar))
                pos = 0

    if pos != 0:
        ret = (df["close"].iloc[-1] - ep) / ep * pos
        trades.append((df.index[-1], ret, "end", ep, df["close"].iloc[-1], pos, ebar))

    tdf = pd.DataFrame(trades, columns=["exit_time","return","reason","entry_p","exit_p","direction","entry_bar"])
    tdf["entry_time"] = tdf["exit_time"].shift(1)
    if len(tdf) > 0:
        tdf["entry_time"] = df.index[[t[6] for t in trades]]
    return tdf

# ============================================================
# METRICS
# ============================================================
def compute_metrics(trades_df: pd.DataFrame) -> dict:
    rets = trades_df["return"].values
    n = len(rets)
    if n < 2:
        return dict(total_return=0, n_trades=n, win_rate=0, avg_ret=float(np.mean(rets)) if n else 0,
                    sharpe=0, max_dd=0, profit_factor=0, all_wins=n>0)
    total = float(np.prod(1 + rets) - 1)
    wins = rets[rets > 0]; losses = rets[rets < 0]
    wr = len(wins) / n
    avg = float(np.mean(rets))
    std = float(np.std(rets, ddof=1)) if n > 1 else 0.001
    ann = avg / std * np.sqrt(2772) if std > 1e-10 else 0
    cum = np.cumprod(1 + rets)
    rm = np.maximum.accumulate(cum)
    dd = float(np.min((cum - rm) / rm))
    gw = float(np.sum(wins)) if len(wins) else 0
    gl = float(np.abs(np.sum(losses))) if len(losses) else 1e-10
    pf = gw / gl if gl > 1e-10 else (np.inf if gw > 0 else 0)
    return dict(total_return=total, n_trades=n, win_rate=wr, avg_ret=avg,
                sharpe=ann, max_dd=dd, profit_factor=pf, all_wins=len(losses)==0 and len(wins)>0)

def pprint(label, m):
    print(f"  {label:25s} | n={m['n_trades']:3d} WR={m['win_rate']:.1%} "
          f"Ret={m['total_return']:+.2%} AnnSharpe={m['sharpe']:.2f} "
          f"DD={m['max_dd']:.2%} PF={m['profit_factor']:.2f}")

# ============================================================
# PARAM GRID
# ============================================================
K = [10, 14, 21]
D = [3, 5]
SMOOTH = [3]
OVERSOLD = [20, 30, None]
OVERBOUGHT = [70, 80, None]
TP = [2.0, 3.0, 4.0]
ZONE = [True, False]

ALL_PARAMS = list(product(K, D, SMOOTH, OVERSOLD, OVERBOUGHT, TP, ZONE))

FIXED = dict(k=14, d=3, smooth=3, oversold=20, overbought=80, tp_mult=3.0, zone_filter=True)

def grid_search(df_is, df_oos, params_list):
    rows = []
    for k, d, sm, os, ob, tp, zf in params_list:
        if os is None and ob is None and zf:
            continue
        tr = run_backtest(df_is, k=k, d=d, smooth=sm, oversold=os, overbought=ob, tp_mult=tp, zone_filter=zf)
        m = compute_metrics(tr)
        if m["n_trades"] >= 5 and not m["all_wins"] and m["profit_factor"] > 0:
            tr_oos = run_backtest(df_oos, k=k, d=d, smooth=sm, oversold=os, overbought=ob, tp_mult=tp, zone_filter=zf)
            m_oos = compute_metrics(tr_oos)
            rows.append((k, d, sm, os, ob, tp, zf, m["n_trades"], m["profit_factor"],
                         m["total_return"], m["sharpe"], m["max_dd"],
                         m_oos["n_trades"], m_oos["profit_factor"],
                         m_oos["total_return"], m_oos["sharpe"]))
    cols = ["k","d","smooth","os","ob","tp","zone","IS_n","IS_PF","IS_Ret","IS_Sharpe","IS_DD",
            "OOS_n","OOS_PF","OOS_Ret","OOS_Sharpe"]
    res = pd.DataFrame(rows, columns=cols)
    if len(res):
        res = res.sort_values("IS_PF", ascending=False).reset_index(drop=True)
    return res

def monthly_pnl(df, params):
    tr = run_backtest(df, **params)
    if len(tr) == 0:
        return pd.Series(dtype=float)
    tr["month"] = tr["exit_time"].dt.to_period("M")
    monthly = tr.groupby("month")["return"].sum()
    return monthly

def monthly_pnl_table(df, params):
    tr = run_backtest(df, **params)
    if len(tr) == 0:
        return pd.DataFrame()
    tr["year"] = tr["exit_time"].dt.year
    tr["month"] = tr["exit_time"].dt.month
    pt = tr.pivot_table(index="year", columns="month", values="return", aggfunc="sum", fill_value=0)
    return pt

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 72)
    print("STOCHASTIC OSCILLATOR STRATEGY BACKTEST - BTP 1h")
    print("=" * 72)

    df_full = load_btp_full()
    df_new = load_27feb()
    print(f"\nFull data: {len(df_full)} bars  {df_full.index[0]} - {df_full.index[-1]}")
    print(f"New data:  {len(df_new)} bars  {df_new.index[0]} - {df_new.index[-1]}")

    n = len(df_full)
    split = n // 2
    df_is = df_full.iloc[:split].copy()
    df_oos = df_full.iloc[split:].copy()
    print(f"IS:  {len(df_is)} bars  {df_is.index[0]} - {df_is.index[-1]}")
    print(f"OOS: {len(df_oos)} bars  {df_oos.index[0]} - {df_oos.index[-1]}")
    print()

    # ================================================================
    # 1. FULL PARAM GRID
    # ================================================================
    print("-" * 72)
    print("GRID SEARCH - Top 10 by IS Profit Factor")
    print("-" * 72)
    grid = grid_search(df_is, df_oos, ALL_PARAMS)
    if len(grid):
        print(f"\n  Total valid combos (>=5 trades, not all wins): {len(grid)}")
        hdr = f"  {'k':>2} {'d':>2} {'sm':>2} {'os':>4} {'ob':>4} {'tp':>3} {'zone':>4} |"
        hdr += f" {'IS_n':>3} {'IS_PF':>5} {'IS_Ret':>6} {'IS_SR':>5} {'IS_DD':>5} |"
        hdr += f" {'OOS_n':>3} {'OOS_PF':>5} {'OOS_Ret':>6} {'OOS_SR':>5}"
        print(hdr)
        print("  " + "-"*96)
        for _, r in grid.head(10).iterrows():
            os_s = str(r['os']) if r['os'] is not None else 'None'
            ob_s = str(r['ob']) if r['ob'] is not None else 'None'
            print(f"  {r['k']:>2d} {r['d']:>2d} {r['smooth']:>2d} {os_s:>4s} {ob_s:>4s} {r['tp']:3.0f} {str(r['zone']):>4s} | "
                  f"{r['IS_n']:3d} {r['IS_PF']:5.2f} {r['IS_Ret']:+.1%} {r['IS_Sharpe']:5.2f} {r['IS_DD']:5.2%} | "
                  f"{r['OOS_n']:3d} {r['OOS_PF']:5.2f} {r['OOS_Ret']:+.1%} {r['OOS_Sharpe']:5.2f}")
    else:
        print("  No valid combos found.")

    # ================================================================
    # 2. BEST PARAMS -> Performance
    # ================================================================
    print()
    print("-" * 72)
    print("BEST IS PARAMS -> Performance")
    print("-" * 72)
    if len(grid):
        best = grid.iloc[0]
        bp = dict(k=int(best["k"]), d=int(best["d"]), smooth=int(best["smooth"]),
                  oversold=best["os"], overbought=best["ob"], tp_mult=float(best["tp"]),
                  zone_filter=bool(best["zone"]))
        print(f"\n  Best IS params: Stoch({bp['k']},{bp['d']},{bp['smooth']}) "
              f"os={bp['oversold']} ob={bp['overbought']} tp={bp['tp_mult']}x zone={bp['zone_filter']}")
        print()
        for label, d in [("IS", df_is), ("OOS", df_oos), ("Full", df_full)]:
            tr = run_backtest(d, **bp)
            m = compute_metrics(tr)
            pprint(label, m)

    # ================================================================
    # 3. FIXED PARAMS
    # ================================================================
    print()
    print("-" * 72)
    print("FIXED PARAMS  Stoch(14,3,3) os=20 ob=80 tp=3.0x zone=True")
    print("-" * 72)
    for label, d in [("IS", df_is), ("OOS", df_oos), ("Full", df_full)]:
        tr = run_backtest(d, **FIXED)
        m = compute_metrics(tr)
        pprint(label, m)

    # ================================================================
    # 4. ON/OFF FILTER COMPARISON (Full dataset)
    # ================================================================
    print()
    print("-" * 72)
    print("ON/OFF FILTER COMPARISON  (Full, rolling 3mo PnL)")
    print("-" * 72)

    for label, p in [("Best IS params", bp if len(grid) else None), ("Fixed Stoch(14,3,3)", FIXED)]:
        if p is None:
            continue
        tr = run_backtest(df_full, **p)
        if len(tr) == 0:
            print(f"\n  {label}: no trades")
            continue
        tr = tr.sort_values("exit_time").reset_index(drop=True)
        tr["entry_time"] = pd.to_datetime(tr["entry_time"])
        roll_pnl = []
        for j in range(len(tr)):
            t0 = tr.loc[j, "exit_time"]
            prior = tr[(tr["exit_time"] >= t0 - pd.DateOffset(months=3)) & (tr["exit_time"] < t0)]
            roll_pnl.append(prior["return"].sum())
        tr["roll_3m_pnl"] = roll_pnl

        print(f"\n  {label}")
        pprint("  Without filter", compute_metrics(tr))

        tr_f = tr[tr["roll_3m_pnl"] > 0].copy()
        m_f = compute_metrics(tr_f)
        pprint("  With filter", m_f)

    # ================================================================
    # 5. NEW DATA (27 febbraio.txt)
    # ================================================================
    print()
    print("-" * 72)
    print("NEW DATA  (27 Feb - 1 Jun 2026)")
    print("-" * 72)
    for label, p in [("Best IS params", bp if len(grid) else None), ("Fixed Stoch(14,3,3)", FIXED)]:
        if p is None:
            continue
        tr = run_backtest(df_new, **p)
        m = compute_metrics(tr)
        print(f"\n  {label}")
        pprint("  No filter", m)

        if len(tr) > 0:
            tr = tr.sort_values("exit_time").reset_index(drop=True)
            roll = []
            for j in range(len(tr)):
                t0 = tr.loc[j, "exit_time"]
                prior = tr[(tr["exit_time"] >= t0 - pd.DateOffset(months=3)) & (tr["exit_time"] < t0)]
                roll.append(prior["return"].sum())
            tr["roll_3m_pnl"] = roll
            tr_f = tr[tr["roll_3m_pnl"] > 0].copy()
            m_f = compute_metrics(tr_f)
            pprint("  With filter", m_f)

    # ================================================================
    # 6. MONTHLY PnL (Full dataset)
    # ================================================================
    print()
    print("-" * 72)
    print("MONTHLY PnL  (full dataset)")
    print("-" * 72)

    for label, p in [("Best IS params", bp if len(grid) else None), ("Fixed Stoch(14,3,3)", FIXED)]:
        if p is None:
            continue
        mon = monthly_pnl(df_full, p)
        print(f"\n  {label}")
        print(f"  {'Month':>8s}  {'PnL':>9s}")
        print(f"  {'-'*8}  {'-'*9}")
        for m_idx, val in mon.items():
            print(f"  {m_idx}  {val:+.4f}")
        print(f"  {'-'*8}  {'-'*9}")
        print(f"  {'Total':>8s}  {mon.sum():+.4f}")

    # Monthly table (year x month)
    for label, p in [("Best IS params", bp if len(grid) else None), ("Fixed Stoch(14,3,3)", FIXED)]:
        if p is None:
            continue
        pt = monthly_pnl_table(df_full, p)
        if len(pt):
            print(f"\n  Monthly PnL table - {label}")
            print(pt.to_string(float_format=lambda x: f"{x:+.4f}"))

    print("\nDone.")

if __name__ == "__main__":
    main()
