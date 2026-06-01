import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# 1. LOAD DATA
# ============================================================
df = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
df.columns=["data","open","high","low","close","volume"]
df["dt"] = pd.to_datetime(df["data"])
df.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: df[c]=df[c].astype(float)

# New data file
btp_new = pd.read_csv("dati/27 febbraio.txt", sep="\t", header=None, decimal=",")
btp_new.columns=["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: btp_new[c]=btp_new[c].astype(float)
btp_new["dt"]=pd.to_datetime(btp_new["data"], dayfirst=True)
btp_new.sort_values("dt", inplace=True)
btp_new.set_index("dt", inplace=True)

# ============================================================
# 2. INDICATORS
# ============================================================
def compute_indicators(df):
    d = df.copy()
    delta = d["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss
    d["rsi"] = 100 - (100 / (1 + rs))
    d["vol_sma"] = d["volume"].rolling(20).mean()
    tr = pd.DataFrame({
        "hl": d["high"] - d["low"],
        "hc": (d["high"] - d["close"].shift(1)).abs(),
        "lc": (d["low"] - d["close"].shift(1)).abs()
    }).max(axis=1)
    d["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()
    d["vol_sma2"] = d["volume"].shift(1).rolling(20).mean()
    return d

df = compute_indicators(df)
btp_new = compute_indicators(btp_new)

print(f"Main BTP data: {df.index[0]} to {df.index[-1]}, {len(df)} bars")
print(f"New BTP data:  {btp_new.index[0]} to {btp_new.index[-1]}, {len(btp_new)} bars")
print()

# ============================================================
# 3. BACKTEST ENGINE
# ============================================================
def backtest(df, rsi_lower=20, rsi_upper=75, vol_mult=1.0, tp_mult=2.0, timeout=40,
              use_swing_sl=True, sl_atr_mult=2.0):
    n = len(df)
    trades = []
    in_trade = False
    entry_idx = None
    entry_price = 0
    sl_price = 0
    tp_price = 0
    direction = 0  # 1=long, -1=short
    bars_held = 0

    for i in range(timeout + 5, n):
        if not in_trade:
            # Check for entry at open[i] using data up to bar i-1
            rsi_val = df["rsi"].iloc[i-1]
            vol_val = df["volume"].iloc[i-1]
            vol_sma_val = df["vol_sma"].iloc[i-1]

            if pd.isna(rsi_val) or pd.isna(vol_sma_val):
                continue

            if rsi_val < rsi_lower and vol_val > vol_mult * vol_sma_val:
                direction = 1
                entry_price = df["open"].iloc[i]
                entry_idx = i
                # SL: swing low of last 5 bars
                swing_low = df["low"].iloc[i-5:i].min()
                sl_price = swing_low
                # TP
                atr_val = df["atr"].iloc[i-1]
                tp_price = entry_price + tp_mult * atr_val
                in_trade = True
                bars_held = 0

            elif rsi_val > rsi_upper and vol_val > vol_mult * vol_sma_val:
                direction = -1
                entry_price = df["open"].iloc[i]
                entry_idx = i
                swing_high = df["high"].iloc[i-5:i].max()
                sl_price = swing_high
                atr_val = df["atr"].iloc[i-1]
                tp_price = entry_price - tp_mult * atr_val
                in_trade = True
                bars_held = 0
        else:
            bars_held += 1
            # Check exits
            exit_price = None
            exit_reason = None

            # Timeout
            if bars_held >= timeout:
                exit_price = df["close"].iloc[i]
                exit_reason = "timeout"

            # Stop loss / take profit
            if direction == 1:
                if not np.isnan(df["low"].iloc[i]) and df["low"].iloc[i] <= sl_price:
                    exit_price = sl_price
                    exit_reason = "sl"
                elif not np.isnan(df["high"].iloc[i]) and df["high"].iloc[i] >= tp_price:
                    exit_price = tp_price
                    exit_reason = "tp"

                if exit_price is not None:
                    pnl = exit_price - entry_price
                    trades.append({
                        "entry_dt": df.index[entry_idx],
                        "exit_dt": df.index[i],
                        "direction": "LONG",
                        "entry": entry_price,
                        "exit": exit_price,
                        "pnl": pnl,
                        "pnl_pct": pnl / entry_price * 100,
                        "bars": bars_held,
                        "reason": exit_reason
                    })
                    in_trade = False
            elif direction == -1:
                if not np.isnan(df["high"].iloc[i]) and df["high"].iloc[i] >= sl_price:
                    exit_price = sl_price
                    exit_reason = "sl"
                elif not np.isnan(df["low"].iloc[i]) and df["low"].iloc[i] <= tp_price:
                    exit_price = tp_price
                    exit_reason = "tp"

                if exit_price is not None:
                    pnl = entry_price - exit_price
                    trades.append({
                        "entry_dt": df.index[entry_idx],
                        "exit_dt": df.index[i],
                        "direction": "SHORT",
                        "entry": entry_price,
                        "exit": exit_price,
                        "pnl": pnl,
                        "pnl_pct": pnl / entry_price * 100,
                        "bars": bars_held,
                        "reason": exit_reason
                    })
                    in_trade = False

    return trades


def compute_metrics(trades):
    if len(trades) == 0:
        return {"trades": 0, "pf": 0, "total_pnl": 0, "win_rate": 0, "avg_pnl": 0}
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = sum(1 for t in trades if t["pnl"] < 0)
    flat = sum(1 for t in trades if t["pnl"] == 0)
    pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)
    total_pnl = sum(t["pnl"] for t in trades)
    win_rate = wins / len(trades) if len(trades) > 0 else 0
    return {
        "trades": len(trades),
        "pf": round(pf, 4),
        "total_pnl": round(total_pnl, 4),
        "win_rate": round(win_rate, 4),
        "wins": wins,
        "losses": losses,
        "flat": flat,
        "avg_win": round(gross_profit / wins, 4) if wins > 0 else 0,
        "avg_loss": round(gross_loss / losses, 4) if losses > 0 else 0,
        "gross_profit": round(gross_profit, 4),
        "gross_loss": round(gross_loss, 4),
    }


# ============================================================
# 4. SPLIT: IS = first 50%, OOS = last 50%
# ============================================================
split = len(df) // 2
df_is = df.iloc[:split].copy()
df_oos = df.iloc[split:].copy()
print(f"IS:  {df_is.index[0]} to {df_is.index[-1]} ({len(df_is)} bars)")
print(f"OOS: {df_oos.index[0]} to {df_oos.index[-1]} ({len(df_oos)} bars)")
print()

# ============================================================
# 5. FULL PARAM GRID ON IS
# ============================================================
vol_mults = [1.0, 1.5, 2.0]
tp_mults = [1.5, 2.0, 3.0]
RSI_LOWER = 20
RSI_UPPER = 75
TIMEOUT = 40

print("=" * 100)
print("PARAM GRID - IN-SAMPLE RESULTS")
print("=" * 100)
print(f"{'vol_mult':>8} {'tp_mult':>8} {'trades':>7} {'PF':>8} {'Win%':>6} {'TotalPnL':>10} {'Wins':>5} {'Loss':>5} {'Flat':>5}")
print("-" * 100)

grid_results = []
for vm in vol_mults:
    for tp in tp_mults:
        trades = backtest(df_is, rsi_lower=RSI_LOWER, rsi_upper=RSI_UPPER,
                         vol_mult=vm, tp_mult=tp, timeout=TIMEOUT)
        m = compute_metrics(trades)
        grid_results.append({
            "vm": vm, "tp": tp, "trades": m["trades"],
            "pf": m["pf"], "total_pnl": m["total_pnl"],
            "win_rate": m["win_rate"], "wins": m["wins"],
            "losses": m["losses"], "flat": m["flat"],
            "all_wins": m["losses"] == 0 and m["wins"] > 0
        })
        print(f"{vm:>8.1f} {tp:>8.1f} {m['trades']:>7} {m['pf']:>8.4f} {m['win_rate']*100:>5.1f}% {m['total_pnl']:>10.4f} {m['wins']:>5} {m['losses']:>5} {m['flat']:>5}")

print()
print("=" * 100)
print("BEST PARAM COMBOS ON IS (PF, min 5 trades, not all wins)")
print("=" * 100)

valid = [r for r in grid_results if r["trades"] >= 5 and not r["all_wins"]]
valid.sort(key=lambda x: x["pf"], reverse=True)
best_combo = valid[0] if valid else None

if best_combo:
    print(f"Best IS: vol_mult={best_combo['vm']}, tp_mult={best_combo['tp']}, "
          f"PF={best_combo['pf']}, trades={best_combo['trades']}, "
          f"win_rate={best_combo['win_rate']*100:.1f}%, PnL={best_combo['total_pnl']:.4f}")

    # Top 5
    for i, r in enumerate(valid[:5]):
        print(f"  {i+1}. vol_mult={r['vm']}, tp_mult={r['tp']}, PF={r['pf']}, "
              f"trades={r['trades']}, WR={r['win_rate']*100:.1f}%, PnL={r['total_pnl']:.4f}")
else:
    print("No valid param combo found on IS!")

print()

# ============================================================
# 6. OOS RESULTS for best combo
# ============================================================
if best_combo:
    print("=" * 100)
    print(f"OOS RESULTS: vol_mult={best_combo['vm']}, tp_mult={best_combo['tp']}")
    print("=" * 100)
    trades_oos = backtest(df_oos, rsi_lower=RSI_LOWER, rsi_upper=RSI_UPPER,
                          vol_mult=best_combo["vm"], tp_mult=best_combo["tp"],
                          timeout=TIMEOUT)
    m_oos = compute_metrics(trades_oos)
    print(f"Trades: {m_oos['trades']}, PF: {m_oos['pf']}, Win%: {m_oos['win_rate']*100:.1f}%, "
          f"Total PnL: {m_oos['total_pnl']:.4f}")
    print(f"Wins: {m_oos['wins']}, Losses: {m_oos['losses']}, Flat: {m_oos['flat']}")
    print()

    # ============================================================
    # 7. ALL COMBOS ON OOS (for comparison)
    # ============================================================
    print("=" * 100)
    print("ALL COMBOS ON OOS")
    print("=" * 100)
    print(f"{'vol_mult':>8} {'tp_mult':>8} {'trades':>7} {'PF':>8} {'Win%':>6} {'TotalPnL':>10} {'Wins':>5} {'Loss':>5}")
    print("-" * 100)
    oos_results = []
    for vm in vol_mults:
        for tp in tp_mults:
            t = backtest(df_oos, vol_mult=vm, tp_mult=tp, timeout=TIMEOUT)
            m = compute_metrics(t)
            oos_results.append((vm, tp, m))
            print(f"{vm:>8.1f} {tp:>8.1f} {m['trades']:>7} {m['pf']:>8.4f} {m['win_rate']*100:>5.1f}% {m['total_pnl']:>10.4f} {m['wins']:>5} {m['losses']:>5}")
    print()

    # ============================================================
    # 8. FIXED PARAMS ON OOS (vol_mult=2.0, TP=2atr)
    # ============================================================
    print("=" * 100)
    print("FIXED PARAMS ON OOS: vol_mult=2.0, tp_mult=2.0 (no optimization)")
    print("=" * 100)
    trades_fixed = backtest(df_oos, vol_mult=2.0, tp_mult=2.0, timeout=TIMEOUT)
    m_fixed = compute_metrics(trades_fixed)
    print(f"Trades: {m_fixed['trades']}, PF: {m_fixed['pf']}, Win%: {m_fixed['win_rate']*100:.1f}%, "
          f"Total PnL: {m_fixed['total_pnl']:.4f}")
    print(f"Wins: {m_fixed['wins']}, Losses: {m_fixed['losses']}, Flat: {m_fixed['flat']}")
    if m_fixed['trades'] > 0:
        print(f"Avg Win: {m_fixed['avg_win']:.4f}, Avg Loss: {m_fixed['avg_loss']:.4f}")
    print()

    # ============================================================
    # 9. FIXED PARAMS ON FULL DATA
    # ============================================================
    print("=" * 100)
    print("FIXED PARAMS ON FULL DATA: vol_mult=2.0, tp_mult=2.0")
    print("=" * 100)
    trades_full_fixed = backtest(df, vol_mult=2.0, tp_mult=2.0, timeout=TIMEOUT)
    m_full_fixed = compute_metrics(trades_full_fixed)
    print(f"Trades: {m_full_fixed['trades']}, PF: {m_full_fixed['pf']}, Win%: {m_full_fixed['win_rate']*100:.1f}%, "
          f"Total PnL: {m_full_fixed['total_pnl']:.4f}")
    print(f"Wins: {m_full_fixed['wins']}, Losses: {m_full_fixed['losses']}, Flat: {m_full_fixed['flat']}")
    if m_full_fixed['trades'] > 0:
        print(f"Avg Win: {m_full_fixed['avg_win']:.4f}, Avg Loss: {m_full_fixed['avg_loss']:.4f}")
    print()

    # ============================================================
    # 10. ON/OFF FILTER (rolling 3-month PnL)
    # ============================================================
    print("=" * 100)
    print("ON/OFF FILTER ON FULL DATA")
    print("=" * 100)

    def backtest_with_filter(df, rsi_lower=20, rsi_upper=75, vol_mult=2.0, tp_mult=2.0, timeout=40):
        n = len(df)
        trades = []
        in_trade = False
        entry_idx = None
        entry_price = 0
        sl_price = 0
        tp_price = 0
        direction = 0
        bars_held = 0

        # For ON/OFF filter: track closed trade PnLs with dates
        closed_trades = []  # list of (exit_dt, pnl)

        def filter_on(current_dt):
            lookback = current_dt - pd.Timedelta(days=90)
            recent = sum(pnl for dt, pnl in closed_trades if dt >= lookback)
            return recent >= 0

        for i in range(timeout + 5, n):
            current_dt = df.index[i]

            if not in_trade:
                rsi_val = df["rsi"].iloc[i-1]
                vol_val = df["volume"].iloc[i-1]
                vol_sma_val = df["vol_sma"].iloc[i-1]

                if pd.isna(rsi_val) or pd.isna(vol_sma_val):
                    continue

                signal = False
                sig_dir = 0
                if rsi_val < rsi_lower and vol_val > vol_mult * vol_sma_val:
                    signal = True
                    sig_dir = 1
                elif rsi_val > rsi_upper and vol_val > vol_mult * vol_sma_val:
                    signal = True
                    sig_dir = -1

                if signal:
                    # Check ON/OFF filter
                    if not filter_on(current_dt):
                        continue  # filter OFF, skip signal

                    direction = sig_dir
                    entry_price = df["open"].iloc[i]
                    entry_idx = i
                    if direction == 1:
                        swing_low = df["low"].iloc[i-5:i].min()
                        sl_price = swing_low
                    else:
                        swing_high = df["high"].iloc[i-5:i].max()
                        sl_price = swing_high
                    atr_val = df["atr"].iloc[i-1]
                    tp_price = entry_price + tp_mult * atr_val if direction == 1 else entry_price - tp_mult * atr_val
                    in_trade = True
                    bars_held = 0
            else:
                bars_held += 1
                exit_price = None
                exit_reason = None

                if bars_held >= timeout:
                    exit_price = df["close"].iloc[i]
                    exit_reason = "timeout"

                if direction == 1:
                    if not np.isnan(df["low"].iloc[i]) and df["low"].iloc[i] <= sl_price:
                        exit_price = sl_price
                        exit_reason = "sl"
                    elif not np.isnan(df["high"].iloc[i]) and df["high"].iloc[i] >= tp_price:
                        exit_price = tp_price
                        exit_reason = "tp"
                    if exit_price is not None:
                        pnl = exit_price - entry_price
                        trade = {"entry_dt": df.index[entry_idx], "exit_dt": df.index[i],
                                 "direction": "LONG", "entry": entry_price, "exit": exit_price,
                                 "pnl": pnl, "pnl_pct": pnl / entry_price * 100,
                                 "bars": bars_held, "reason": exit_reason}
                        trades.append(trade)
                        closed_trades.append((df.index[i], pnl))
                        in_trade = False
                elif direction == -1:
                    if not np.isnan(df["high"].iloc[i]) and df["high"].iloc[i] >= sl_price:
                        exit_price = sl_price
                        exit_reason = "sl"
                    elif not np.isnan(df["low"].iloc[i]) and df["low"].iloc[i] <= tp_price:
                        exit_price = tp_price
                        exit_reason = "tp"
                    if exit_price is not None:
                        pnl = entry_price - exit_price
                        trade = {"entry_dt": df.index[entry_idx], "exit_dt": df.index[i],
                                 "direction": "SHORT", "entry": entry_price, "exit": exit_price,
                                 "pnl": pnl, "pnl_pct": pnl / entry_price * 100,
                                 "bars": bars_held, "reason": exit_reason}
                        trades.append(trade)
                        closed_trades.append((df.index[i], pnl))
                        in_trade = False

        return trades

    # Apply filter on best combo
    trades_filtered = backtest_with_filter(df, vol_mult=best_combo["vm"], tp_mult=best_combo["tp"])
    m_filtered = compute_metrics(trades_filtered)
    print(f"Best combo (vm={best_combo['vm']}, tp={best_combo['tp']}) with 3-month PnL filter:")
    print(f"Trades: {m_filtered['trades']}, PF: {m_filtered['pf']}, Win%: {m_filtered['win_rate']*100:.1f}%, "
          f"Total PnL: {m_filtered['total_pnl']:.4f}")
    print(f"Wins: {m_filtered['wins']}, Losses: {m_filtered['losses']}, Flat: {m_filtered['flat']}")
    print()

    # Apply filter on fixed params
    trades_filtered_fixed = backtest_with_filter(df, vol_mult=2.0, tp_mult=2.0)
    m_filtered_fixed = compute_metrics(trades_filtered_fixed)
    print(f"Fixed params (vm=2.0, tp=2.0) with 3-month PnL filter:")
    print(f"Trades: {m_filtered_fixed['trades']}, PF: {m_filtered_fixed['pf']}, Win%: {m_filtered_fixed['win_rate']*100:.1f}%, "
          f"Total PnL: {m_filtered_fixed['total_pnl']:.4f}")
    print(f"Wins: {m_filtered_fixed['wins']}, Losses: {m_filtered_fixed['losses']}, Flat: {m_filtered_fixed['flat']}")
    print()

    # ============================================================
    # 11. TEST ON NEW DATA FILE
    # ============================================================
    print("=" * 100)
    print(f"RESULTS ON NEW DATA FILE (27 febbraio.txt)")
    print("=" * 100)

    # Best combo on new data
    trades_new = backtest(btp_new, vol_mult=best_combo["vm"], tp_mult=best_combo["tp"], timeout=TIMEOUT)
    m_new = compute_metrics(trades_new)
    print(f"Best combo (vm={best_combo['vm']}, tp={best_combo['tp']}):")
    print(f"Trades: {m_new['trades']}, PF: {m_new['pf']}, Win%: {m_new['win_rate']*100:.1f}%, "
          f"Total PnL: {m_new['total_pnl']:.4f}")
    print(f"Wins: {m_new['wins']}, Losses: {m_new['losses']}, Flat: {m_new['flat']}")
    if m_new['trades'] > 0:
        print(f"Avg Win: {m_new['avg_win']:.4f}, Avg Loss: {m_new['avg_loss']:.4f}")
    print()

    # Fixed params on new data
    trades_new_fixed = backtest(btp_new, vol_mult=2.0, tp_mult=2.0, timeout=TIMEOUT)
    m_new_fixed = compute_metrics(trades_new_fixed)
    print(f"Fixed params (vm=2.0, tp=2.0):")
    print(f"Trades: {m_new_fixed['trades']}, PF: {m_new_fixed['pf']}, Win%: {m_new_fixed['win_rate']*100:.1f}%, "
          f"Total PnL: {m_new_fixed['total_pnl']:.4f}")
    print(f"Wins: {m_new_fixed['wins']}, Losses: {m_new_fixed['losses']}, Flat: {m_new_fixed['flat']}")
    print()

    # All combos on new data
    print("ALL COMBOS ON NEW DATA:")
    print(f"{'vol_mult':>8} {'tp_mult':>8} {'trades':>7} {'PF':>8} {'Win%':>6} {'TotalPnL':>10} {'Wins':>5} {'Loss':>5}")
    print("-" * 70)
    for vm in vol_mults:
        for tp in tp_mults:
            t = backtest(btp_new, vol_mult=vm, tp_mult=tp, timeout=TIMEOUT)
            m = compute_metrics(t)
            print(f"{vm:>8.1f} {tp:>8.1f} {m['trades']:>7} {m['pf']:>8.4f} {m['win_rate']*100:>5.1f}% {m['total_pnl']:>10.4f} {m['wins']:>5} {m['losses']:>5}")
    print()

    # Filtered on new data
    trades_new_filtered = backtest_with_filter(btp_new, vol_mult=best_combo["vm"], tp_mult=best_combo["tp"])
    m_new_filtered = compute_metrics(trades_new_filtered)
    print(f"Best combo on new data WITH filter:")
    print(f"Trades: {m_new_filtered['trades']}, PF: {m_new_filtered['pf']}, Win%: {m_new_filtered['win_rate']*100:.1f}%, "
          f"Total PnL: {m_new_filtered['total_pnl']:.4f}")
    print()

    # ============================================================
    # 12. DETAILED TRADE LIST (best combo on OOS and new data)
    # ============================================================
    if len(trades_oos) > 0:
        print("=" * 100)
        print("DETAILED TRADES - Best combo on OOS")
        print("=" * 100)
        print(f"{'#':>3} {'Dir':>5} {'Entry':>12} {'Exit':>12} {'EntryPx':>8} {'ExitPx':>8} {'PnL':>8} {'Bars':>5} {'Reason':>8}")
        print("-" * 100)
        for j, t in enumerate(trades_oos):
            print(f"{j+1:>3} {t['direction']:>5} {str(t['entry_dt'])[:16]:>12} {str(t['exit_dt'])[:16]:>12} {t['entry']:>8.4f} {t['exit']:>8.4f} {t['pnl']:>8.4f} {t['bars']:>5} {t['reason']:>8}")

    if len(trades_new) > 0:
        print()
        print("=" * 100)
        print("DETAILED TRADES - Best combo on NEW DATA")
        print("=" * 100)
        print(f"{'#':>3} {'Dir':>5} {'Entry':>12} {'Exit':>12} {'EntryPx':>8} {'ExitPx':>8} {'PnL':>8} {'Bars':>5} {'Reason':>8}")
        print("-" * 100)
        for j, t in enumerate(trades_new):
            print(f"{j+1:>3} {t['direction']:>5} {str(t['entry_dt'])[:16]:>12} {str(t['exit_dt'])[:16]:>12} {t['entry']:>8.4f} {t['exit']:>8.4f} {t['pnl']:>8.4f} {t['bars']:>5} {t['reason']:>8}")
else:
    print("No valid best combo found - cannot proceed to OOS testing.")
