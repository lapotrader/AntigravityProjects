import pandas as pd
import numpy as np
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
# INDICATORS (no look-ahead)
# ============================================================
def add_atr(df: pd.DataFrame, period: int = 14):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift(1)).abs()
    low_close = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    df["atr"] = atr.shift(1)  # ATR[i] = ATR from bars 0..i-1

def add_rolling_extremes(df: pd.DataFrame, lookback: int = 5):
    df["hh5"] = df["high"].rolling(window=lookback, min_periods=1).max().shift(1)
    df["ll5"] = df["low"].rolling(window=lookback, min_periods=1).min().shift(1)

def create_sl_tp_series(df: pd.DataFrame):
    """Precompute SL/TP levels at entry time to avoid lookahead."""
    df["sl_long"] = np.nan
    df["tp_long"] = np.nan
    df["sl_short"] = np.nan
    df["tp_short"] = np.nan

# ============================================================
# STRATEGY 1: ATR-channel breakout
# Fix: close[i-1] vs high[i-2]/low[i-2] (can't beat high/low of same bar)
# ============================================================
def run_atr_breakout(df: pd.DataFrame, k: float, tp_atr: float, sl_atr: float = 2.0,
                     timeout: int = 30, use_filter: bool = False, filter_lookback: int = 756) -> pd.DataFrame:
    df = df.copy()
    add_atr(df, 14)
    add_rolling_extremes(df, 5)

    # Signal generation at bar i (enter at open[i])
    # Long: close[i-1] > high[i-2] + k * ATR[i]   (close breaks above 2-bars-ago high)
    # Short: close[i-1] < low[i-2] - k * ATR[i]
    # ATR[i] uses data up to bar i-1 => no lookahead
    long_sig = df["close"].shift(1) > df["high"].shift(2) + k * df["atr"]
    short_sig = df["close"].shift(1) < df["low"].shift(2) - k * df["atr"]
    df["signal"] = np.where(long_sig, 1, np.where(short_sig, -1, 0))

    # ON/OFF rolling PnL filter (3 months ~ 756 bars on 1h)
    if use_filter:
        df["raw_pnl"] = 0.0
        for i in range(1, len(df)):
            if df["signal"].iloc[i-1] != 0:
                entry = df["open"].iloc[i]
                ideal_exit = df["close"].iloc[i] if i+1 < len(df) else df["close"].iloc[i]
                ret = (ideal_exit - entry) / entry * df["signal"].iloc[i-1]
                df.loc[df.index[i], "raw_pnl"] = ret
        df["rolling_pnl"] = df["raw_pnl"].rolling(window=filter_lookback, min_periods=filter_lookback).sum()
        df["filter_on"] = df["rolling_pnl"] > 0
        df["filter_on"] = df["filter_on"].shift(1).fillna(False)
        df["signal"] = df["signal"] * (df["filter_on"].astype(int))

    # Backtest
    pos = 0; entry_p = 0.0; entry_bar = 0
    sl_price = 0.0; tp_price = 0.0
    trades = []  # list of (exit_idx, return)

    for i in range(1, len(df)):
        idx = df.index[i]
        if pos == 0:
            sig = df["signal"].iloc[i]
            if sig != 0 and not np.isnan(df["atr"].iloc[i]) and df["atr"].iloc[i] > 0:
                pos = sig
                entry_p = df["open"].iloc[i]
                entry_bar = i
                atr_val = df["atr"].iloc[i]
                if pos == 1:
                    sl_price = df["ll5"].iloc[i] if df["ll5"].iloc[i] < entry_p else entry_p - sl_atr * atr_val
                    tp_price = entry_p + tp_atr * atr_val
                else:
                    sl_price = df["hh5"].iloc[i] if df["hh5"].iloc[i] > entry_p else entry_p + sl_atr * atr_val
                    tp_price = entry_p - tp_atr * atr_val
        else:
            bars = i - entry_bar
            h, l, c = df["high"].iloc[i], df["low"].iloc[i], df["close"].iloc[i]
            exit_reason = None; exit_price = None
            if pos == 1:
                if l <= sl_price: exit_price, exit_reason = sl_price, "sl"
                elif h >= tp_price: exit_price, exit_reason = tp_price, "tp"
            else:
                if h >= sl_price: exit_price, exit_reason = sl_price, "sl"
                elif l <= tp_price: exit_price, exit_reason = tp_price, "tp"
            if exit_reason is None and bars >= timeout:
                exit_price, exit_reason = c, "timeout"
            if exit_reason is not None:
                ret = (exit_price - entry_p) / entry_p * pos
                trades.append((idx, ret))
                pos = 0; entry_p = 0.0

    # Close any open position at end
    if pos != 0:
        ret = (df["close"].iloc[-1] - entry_p) / entry_p * pos
        trades.append((df.index[-1], ret))

    return pd.DataFrame(trades, columns=["exit_time", "return"]) if trades else pd.DataFrame(columns=["exit_time", "return"])

# ============================================================
# STRATEGY 2: Gap continuation (daily)
# ============================================================
def run_gap_continuation(df: pd.DataFrame, gap_min: int, gap_max: int,
                         tp_atr: float = 1.0, sl_atr: float = 2.0,
                         timeout_days: int = 5, use_filter: bool = False,
                         filter_lookback: int = 63) -> pd.DataFrame:
    tick = 0.01
    daily = df.resample("D").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    add_atr(daily, 14)
    daily["close_prev"] = daily["close"].shift(1)
    daily["gap"] = daily["open"] - daily["close_prev"]
    daily["gap_abs"] = daily["gap"].abs()

    daily["signal"] = 0
    cond = (daily["gap_abs"] >= gap_min * tick) & (daily["gap_abs"] <= gap_max * tick)
    daily["signal"] = np.where(cond, np.sign(daily["gap"]), 0)

    # Filter
    if use_filter:
        daily["raw_pnl"] = 0.0
        for i in range(1, len(daily)):
            if daily["signal"].iloc[i-1] != 0:
                ret = (daily["close"].iloc[i] / daily["open"].iloc[i] - 1) * daily["signal"].iloc[i-1]
                daily.loc[daily.index[i], "raw_pnl"] = ret
        daily["rolling_pnl"] = daily["raw_pnl"].rolling(window=filter_lookback, min_periods=filter_lookback).sum()
        daily["filter_on"] = daily["rolling_pnl"] > 0
        daily["filter_on"] = daily["filter_on"].shift(1).fillna(False)
        daily["signal"] = daily["signal"] * daily["filter_on"].astype(int)

    # Backtest
    pos = 0; entry_p = 0.0; entry_bar = 0
    sl_price = 0.0; tp_price = 0.0
    trades = []

    for i in range(1, len(daily)):
        if pos == 0:
            sig = daily["signal"].iloc[i]
            if sig != 0 and not np.isnan(daily["atr"].iloc[i]) and daily["atr"].iloc[i] > 0:
                pos = sig
                entry_p = daily["open"].iloc[i]
                entry_bar = i
                atr_val = daily["atr"].iloc[i]
                gap_val = daily["gap"].iloc[i]
                sl_price = entry_p - sl_atr * atr_val if pos == 1 else entry_p + sl_atr * atr_val
                tp_price = entry_p + abs(gap_val) + tp_atr * atr_val if pos == 1 else entry_p - abs(gap_val) - tp_atr * atr_val
        else:
            bars = i - entry_bar
            h, l, c = daily["high"].iloc[i], daily["low"].iloc[i], daily["close"].iloc[i]
            exit_reason = None; exit_price = None
            if pos == 1:
                if l <= sl_price: exit_price, exit_reason = sl_price, "sl"
                elif h >= tp_price: exit_price, exit_reason = tp_price, "tp"
            else:
                if h >= sl_price: exit_price, exit_reason = sl_price, "sl"
                elif l <= tp_price: exit_price, exit_reason = tp_price, "tp"
            if exit_reason is None and bars >= timeout_days:
                exit_price, exit_reason = c, "timeout"
            if exit_reason is not None:
                ret = (exit_price - entry_p) / entry_p * pos
                trades.append((daily.index[i], ret))
                pos = 0; entry_p = 0.0

    if pos != 0:
        ret = (daily["close"].iloc[-1] - entry_p) / entry_p * pos
        trades.append((daily.index[-1], ret))

    return pd.DataFrame(trades, columns=["exit_time", "return"]) if trades else pd.DataFrame(columns=["exit_time", "return"])

# ============================================================
# METRICS
# ============================================================
def compute_metrics(trades_df: pd.DataFrame) -> dict:
    rets = trades_df["return"].values
    if len(rets) < 2:
        return {"total_return": 0, "n_trades": len(rets), "win_rate": 0,
                "avg_ret": float(np.mean(rets)) if len(rets) > 0 else 0,
                "sharpe": 0, "max_dd": 0, "profit_factor": 0}

    total_ret = float(np.prod(1 + rets) - 1)
    n_trades = len(rets)
    wins = rets[rets > 0]
    losses = rets[rets < 0]
    win_rate = len(wins) / n_trades
    avg_ret = float(np.mean(rets))
    std_ret = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0.001
    sharpe = avg_ret / std_ret * np.sqrt(252) if std_ret > 1e-10 else 0

    cum = np.cumprod(1 + rets)
    running_max = np.maximum.accumulate(cum)
    drawdown = (cum - running_max) / running_max
    max_dd = float(np.min(drawdown))

    total_wins = float(np.sum(wins)) if len(wins) > 0 else 0
    total_losses = float(np.abs(np.sum(losses))) if len(losses) > 0 else 1e-10
    profit_factor = total_wins / total_losses if total_losses > 1e-10 else np.inf

    return {"total_return": total_ret, "n_trades": n_trades, "win_rate": win_rate,
            "avg_ret": avg_ret, "sharpe": sharpe, "max_dd": max_dd, "profit_factor": profit_factor}

def print_metrics(label: str, m: dict):
    print(f"  {label:20s} | trades={m['n_trades']:3d} WR={m['win_rate']:.1%} "
          f"ret={m['total_return']:.4f} Sharpe={m['sharpe']:.2f} "
          f"DD={m['max_dd']:.2%} PF={m['profit_factor']:.2f}")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 80)
    print("BTP STRATEGY BACKTEST")
    print("=" * 80)

    df_full = load_btp_full()
    df_27feb = load_27feb()
    print(f"\nBTP full data: {len(df_full)} rows, {df_full.index[0]} to {df_full.index[-1]}")
    print(f"27 Feb data: {len(df_27feb)} rows, {df_27feb.index[0]} to {df_27feb.index[-1]}")

    n = len(df_full)
    split_idx = n // 2
    df_is = df_full.iloc[:split_idx].copy()
    df_oos = df_full.iloc[split_idx:].copy()
    print(f"\nIS: {len(df_is)} rows ({df_is.index[0]} to {df_is.index[-1]})")
    print(f"OOS: {len(df_oos)} rows ({df_oos.index[0]} to {df_oos.index[-1]})")

    # ============================================================
    # STRATEGY 1: ATR-channel breakout
    # ============================================================
    print("\n" + "=" * 80)
    print("STRATEGY 1: ATR-CHANNEL BREAKOUT")
    print("=" * 80)

    ks = [0.5, 1.0, 1.5, 2.0]
    tps = [2, 3, 4]

    best_sharpe = -np.inf
    best_params = None
    best_metrics = None

    print("\n--- Optimization on IS ---")
    for k in ks:
        for tp in tps:
            trades = run_atr_breakout(df_is, k=k, tp_atr=tp, sl_atr=2.0, timeout=30)
            if len(trades) < 3:
                continue
            m = compute_metrics(trades)
            print_metrics(f"k={k:.1f} TP={tp}atr", m)
            if m["sharpe"] > best_sharpe:
                best_sharpe = m["sharpe"]
                best_params = (k, tp)
                best_metrics = m

    if best_params is not None:
        print(f"\n>> Best IS: k={best_params[0]}, TP={best_params[1]}atr (Sharpe={best_sharpe:.2f})")
        print(f"\n--- OOS with best params ---")
        trades_oos = run_atr_breakout(df_oos, k=best_params[0], tp_atr=best_params[1], sl_atr=2.0, timeout=30)
        m_oos = compute_metrics(trades_oos)
        print_metrics(f"OOS (best)", m_oos)

        print(f"\n--- OOS with best params + SL swing ---")
        trades_oos2 = run_atr_breakout(df_oos, k=best_params[0], tp_atr=best_params[1], sl_atr=2.0, timeout=30)
        m_oos2 = compute_metrics(trades_oos2)
        print_metrics(f"OOS (best)", m_oos2)

    # Fixed params: k=1.0, TP=3atr
    print(f"\n--- Fixed params (k=1.0, TP=3atr) ---")
    for name, d in [("IS", df_is), ("OOS", df_oos), ("Full", df_full)]:
        trades = run_atr_breakout(d, k=1.0, tp_atr=3.0, sl_atr=2.0, timeout=30)
        m = compute_metrics(trades)
        print_metrics(name, m)

    # Fixed params WITH ON/OFF filter
    print(f"\n--- Fixed params WITH ON/OFF filter ---")
    for name, d in [("IS", df_is), ("OOS", df_oos), ("Full", df_full)]:
        trades = run_atr_breakout(d, k=1.0, tp_atr=3.0, sl_atr=2.0, timeout=30,
                                  use_filter=True, filter_lookback=756)
        m = compute_metrics(trades)
        print_metrics(name, m)

    # ============================================================
    # STRATEGY 2: Gap continuation
    # ============================================================
    print("\n" + "=" * 80)
    print("STRATEGY 2: GAP CONTINUATION")
    print("=" * 80)

    gap_ranges = [(5, 10), (10, 20), (20, 50)]

    best_sharpe_g = -np.inf
    best_params_g = None
    best_metrics_g = None

    print("\n--- Optimization on IS ---")
    for gmin, gmax in gap_ranges:
        trades = run_gap_continuation(df_is, gap_min=gmin, gap_max=gmax, tp_atr=1.0, sl_atr=2.0, timeout_days=5)
        if len(trades) < 2:
            print(f"  gap [{gmin:2d},{gmax:2d}] ticks: no trades")
            continue
        m = compute_metrics(trades)
        print_metrics(f"gap [{gmin},{gmax}]", m)
        if m["sharpe"] > best_sharpe_g:
            best_sharpe_g = m["sharpe"]
            best_params_g = (gmin, gmax)
            best_metrics_g = m

    if best_params_g is not None:
        print(f"\n>> Best IS: gap [{best_params_g[0]}, {best_params_g[1]}] ticks (Sharpe={best_sharpe_g:.2f})")
        print(f"\n--- OOS with best gap params ---")
        trades = run_gap_continuation(df_oos, gap_min=best_params_g[0], gap_max=best_params_g[1],
                                      tp_atr=1.0, sl_atr=2.0, timeout_days=5)
        print_metrics("OOS (best)", compute_metrics(trades))

    # Fixed gap [10,20]
    print(f"\n--- Fixed gap [10,20] ticks ---")
    for name, d in [("IS", df_is), ("OOS", df_oos), ("Full", df_full)]:
        trades = run_gap_continuation(d, gap_min=10, gap_max=20, tp_atr=1.0, sl_atr=2.0, timeout_days=5)
        print_metrics(name, compute_metrics(trades))

    # Gap WITH filter
    print(f"\n--- Gap [10,20] WITH ON/OFF filter ---")
    for name, d in [("IS", df_is), ("OOS", df_oos), ("Full", df_full)]:
        trades = run_gap_continuation(d, gap_min=10, gap_max=20, tp_atr=1.0, sl_atr=2.0, timeout_days=5,
                                      use_filter=True, filter_lookback=63)
        print_metrics(name, compute_metrics(trades))

    # ============================================================
    # TEST ON 27 FEBBRAIO
    # ============================================================
    print("\n" + "=" * 80)
    print("TEST ON 27 FEBBRAIO DATA")
    print("=" * 80)

    print(f"\n27 Feb: {len(df_27feb)} rows, {df_27feb.index[0]} to {df_27feb.index[-1]}")

    print(f"\n--- S1: Fixed (k=1.0, TP=3atr) ---")
    print_metrics("27 Feb", compute_metrics(run_atr_breakout(df_27feb, k=1.0, tp_atr=3.0, sl_atr=2.0, timeout=30)))

    print(f"\n--- S1: Fixed WITH filter ---")
    print_metrics("27 Feb", compute_metrics(run_atr_breakout(df_27feb, k=1.0, tp_atr=3.0, sl_atr=2.0, timeout=30,
                                                             use_filter=True, filter_lookback=168)))

    print(f"\n--- S2: Gap [10,20] ticks ---")
    print_metrics("27 Feb", compute_metrics(run_gap_continuation(df_27feb, gap_min=10, gap_max=20,
                                                                  tp_atr=1.0, sl_atr=2.0, timeout_days=5)))

    print(f"\n--- S2: Gap [10,20] WITH filter ---")
    print_metrics("27 Feb", compute_metrics(run_gap_continuation(df_27feb, gap_min=10, gap_max=20,
                                                                  tp_atr=1.0, sl_atr=2.0, timeout_days=5,
                                                                  use_filter=True, filter_lookback=20)))
    print("\nDone.")

if __name__ == "__main__":
    main()
