import pandas as pd
import numpy as np
import warnings
from itertools import product
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
# INDICATORS (no look-ahead: all shifted by 1)
# ============================================================
def add_indicators(df: pd.DataFrame, fast: int, slow: int, signal: int):
    close = df["close"]
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - sig_line

    df["macd"] = macd_line.shift(1)
    df["sig"] = sig_line.shift(1)
    df["hist"] = hist.shift(1)
    df["macd_p"] = macd_line.shift(2)
    df["sig_p"] = sig_line.shift(2)
    df["hist_p"] = hist.shift(2)

    high_low = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, hc, lc], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    df["atr"] = atr.shift(1)

    df["sl5"] = df["low"].rolling(5, min_periods=1).min().shift(1)
    df["sh5"] = df["high"].rolling(5, min_periods=1).max().shift(1)

# ============================================================
# BACKTEST
# ============================================================
def run_backtest(df: pd.DataFrame, fast: int, slow: int, signal: int,
                 hist_confirm: bool, tp_mult: float, sl_atr: float = 2.0,
                 timeout: int = 40, use_filter: bool = False,
                 filter_lookback: int = 756) -> pd.DataFrame:
    df = df.copy()
    add_indicators(df, fast, slow, signal)

    crossover = (df["macd"] > df["sig"]) & (df["macd_p"] <= df["sig_p"])
    crossunder = (df["macd"] < df["sig"]) & (df["macd_p"] >= df["sig_p"])

    if hist_confirm:
        crossover = crossover & (df["hist"] > 0)
        crossunder = crossunder & (df["hist"] < 0)

    df["sig_raw"] = np.where(crossover, 1, np.where(crossunder, -1, 0))

    # ---- ON/OFF filter ----
    if use_filter:
        raw = np.zeros(len(df))
        for i in range(1, len(df)):
            s = df["sig_raw"].iloc[i]
            if s != 0:
                ex = df["close"].iloc[min(i+1, len(df)-1)]
                raw[i] = (ex / df["open"].iloc[i] - 1) * s
        df["raw_pnl"] = raw
        rp = pd.Series(raw, index=df.index).rolling(filter_lookback, min_periods=filter_lookback).sum()
        df["filter_on"] = rp > 0
        df["filter_on"] = df["filter_on"].shift(1).fillna(False)
        df["signal"] = df["sig_raw"] * df["filter_on"].astype(int)
    else:
        df["signal"] = df["sig_raw"]

    # ---- Trade loop ----
    pos = 0; ep = 0.0; ebar = 0; sl = 0.0; tp = 0.0
    trades = []

    for i in range(1, len(df)):
        idx = df.index[i]
        if pos == 0:
            s = df["signal"].iloc[i]
            atr_v = df["atr"].iloc[i]
            if s != 0 and not np.isnan(atr_v) and atr_v > 0:
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
                trades.append((idx, ret, reason))
                pos = 0

    if pos != 0:
        ret = (df["close"].iloc[-1] - ep) / ep * pos
        trades.append((df.index[-1], ret, "end"))

    return pd.DataFrame(trades, columns=["exit_time","return","reason"])

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
FAST = [5, 8, 12]
SLOW = [13, 21, 26]
SIG = [3, 5, 9]
HIST = [True, False]
TP = [2.0, 3.0, 4.0]
SL_ATR = 2.0
TIMEOUT = 40

ALL_PARAMS = list(product(FAST, SLOW, SIG, HIST, TP))

FIXED = dict(fast=12, slow=26, signal=9, hist_confirm=False, tp_mult=3.0)

def grid_search(df_is, df_oos, params_list, filter_lookback=756):
    rows = []
    for f, s, sg, h, tp in params_list:
        tr = run_backtest(df_is, fast=f, slow=s, signal=sg, hist_confirm=h, tp_mult=tp)
        m = compute_metrics(tr)
        if m["n_trades"] >= 5 and not m["all_wins"] and m["profit_factor"] > 0:
            tr_oos = run_backtest(df_oos, fast=f, slow=s, signal=sg, hist_confirm=h, tp_mult=tp)
            m_oos = compute_metrics(tr_oos)
            rows.append((f, s, sg, h, tp, m["n_trades"], m["profit_factor"],
                         m["total_return"], m["sharpe"], m["max_dd"],
                         m_oos["n_trades"], m_oos["profit_factor"],
                         m_oos["total_return"], m_oos["sharpe"]))
    cols = ["fast","slow","sig","hist","tp","IS_n","IS_PF","IS_Ret","IS_Sharpe","IS_DD",
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

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 72)
    print("MACD STRATEGY BACKTEST - BTP 1h")
    print("=" * 72)

    df_full = load_btp_full()
    df_new = load_27feb()
    print(f"\nFull data: {len(df_full)} bars  {df_full.index[0]} - {df_full.index[-1]}")
    print(f"\nNew data:  {len(df_new)} bars  {df_new.index[0]} - {df_new.index[-1]}")

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
        print(f"  {'fast':>4} {'slow':>4} {'sig':>3} {'hist':>4} {'tp':>3} | "
              f"{'IS_n':>3} {'IS_PF':>5} {'IS_Ret':>6} {'IS_SR':>5} {'IS_DD':>5} | "
              f"{'OOS_n':>3} {'OOS_PF':>5} {'OOS_Ret':>6} {'OOS_SR':>5}")
        print("  " + "-"*78)
        for _, r in grid.head(10).iterrows():
            print(f"  {r['fast']:4d} {r['slow']:4d} {r['sig']:3d} {str(r['hist']):>4} {r['tp']:3.0f} | "
                  f"{r['IS_n']:3d} {r['IS_PF']:5.2f} {r['IS_Ret']:+.1%} {r['IS_Sharpe']:5.2f} {r['IS_DD']:5.2%} | "
                  f"{r['OOS_n']:3d} {r['OOS_PF']:5.2f} {r['OOS_Ret']:+.1%} {r['OOS_Sharpe']:5.2f}")
    else:
        print("  No valid combos found.")

    # ================================================================
    # 2. BEST PARAMS -> OOS
    # ================================================================
    print()
    print("-" * 72)
    print("BEST IS PARAMS -> Performance")
    print("-" * 72)
    if len(grid):
        best = grid.iloc[0]
        bp = dict(fast=int(best["fast"]), slow=int(best["slow"]), signal=int(best["sig"]),
                  hist_confirm=bool(best["hist"]), tp_mult=float(best["tp"]))
        print(f"\n  Best IS params: MACD({bp['fast']},{bp['slow']},{bp['signal']}) "
              f"hist={bp['hist_confirm']} tp={bp['tp_mult']}x")
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
    print("FIXED PARAMS  MACD(12,26,9) hist=F  tp=3.0x")
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

    for label, p in [("Best IS params", bp), ("Fixed MACD(12,26,9)", FIXED)]:
        tr_no = run_backtest(df_full, **p)
        m_no = compute_metrics(tr_no)
        tr_yes = run_backtest(df_full, use_filter=True, filter_lookback=756, **p)
        m_yes = compute_metrics(tr_yes)
        print(f"\n  {label}")
        pprint("  Without filter", m_no)
        pprint("  With filter", m_yes)

    # ================================================================
    # 5. NEW DATA (27 febbraio.txt)
    # ================================================================
    print()
    print("-" * 72)
    print("NEW DATA  (27 Feb - 1 Jun 2026)")
    print("-" * 72)
    for label, p in [("Best IS params", bp if len(grid) else None), ("Fixed MACD(12,26,9)", FIXED)]:
        if p is None:
            continue
        tr = run_backtest(df_new, **p)
        m = compute_metrics(tr)
        pprint(label, m)
        tr_f = run_backtest(df_new, use_filter=True, filter_lookback=168, **p)
        m_f = compute_metrics(tr_f)
        pprint(label + " +filter", m_f)

    # ================================================================
    # 6. MONTHLY PnL (Full dataset)
    # ================================================================
    print()
    print("-" * 72)
    print("MONTHLY PnL  (full dataset)")
    print("-" * 72)

    for label, p in [("Best IS params", bp if len(grid) else None), ("Fixed MACD(12,26,9)", FIXED)]:
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

    print("\nDone.")

if __name__ == "__main__":
    main()
