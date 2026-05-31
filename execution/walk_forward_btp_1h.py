"""
Walk-Forward Analysis — Trombetta Ch 7 (Advanced)
Rolling IS/OOS windows per testare la stabilita dei parametri nel tempo.

Config: ST(period, mult) + Pivot Trailing (lookback=5)
IS window: 2000 bar  |  OOS forward: 500 bar  |  Step: 500 bar
-> ~11 finestre rolling su 7704 candele totali
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

LOOKBACK = 5
DATA_PATH = "dati/btp_1h_full.txt"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Walk-Forward params
IS_WINDOW = 2000
OOS_WINDOW = 500
STEP = 500

# Load data
df = pd.read_csv(DATA_PATH, sep="\t")
df.columns = [c.strip().lower() for c in df.columns]
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = df[col].astype(float)
df["ora"] = pd.to_datetime(df["data"])
df = df.drop(columns=["data"]).reset_index(drop=True)
n = len(df)

# --- Pivot detection ---
def detect_pivots(df, lookback):
    n = len(df)
    ph_flag = np.full(n, False); pl_flag = np.full(n, False)
    for i in range(lookback, n - lookback):
        if all(df.loc[i, "high"] > df.loc[i - k, "high"] for k in range(1, lookback + 1)) and \
           all(df.loc[i, "high"] > df.loc[i + k, "high"] for k in range(1, lookback + 1)):
            ph_flag[i] = True
        if all(df.loc[i, "low"] < df.loc[i - k, "low"] for k in range(1, lookback + 1)) and \
           all(df.loc[i, "low"] < df.loc[i + k, "low"] for k in range(1, lookback + 1)):
            pl_flag[i] = True
    ph_prev = [None] * n; pl_prev = [None] * n
    lp = None; ll = None
    for i in range(n):
        if ph_flag[i]: lp = float(df.loc[i, "high"])
        if pl_flag[i]: ll = float(df.loc[i, "low"])
        ph_prev[i] = lp; pl_prev[i] = ll
    ph_next = [None] * n; pl_next = [None] * n
    np_h = None; np_l = None
    for i in range(n - 1, -1, -1):
        if ph_flag[i]: np_h = float(df.loc[i, "high"])
        if pl_flag[i]: np_l = float(df.loc[i, "low"])
        ph_next[i] = np_h; pl_next[i] = np_l
    return ph_prev, pl_prev, ph_next, pl_next

# --- SuperTrend ---
def calc_supertrend(df, period, mult):
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    atr = np.zeros(n)
    direction_arr = np.ones(n, dtype=int)
    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - np.roll(close, 1)),
                               np.abs(low - np.roll(close, 1))))
    tr[0] = high[0] - low[0]
    alpha = 1 / period
    atr[0] = tr[0]
    for i in range(1, n):
        atr[i] = atr[i - 1] + alpha * (tr[i] - atr[i - 1])
    hl2 = (high + low) / 2
    basic_ub = hl2 + mult * atr
    basic_lb = hl2 - mult * atr
    final_ub = np.zeros(n); final_lb = np.zeros(n)
    st = np.zeros(n)
    for i in range(n):
        if i == 0:
            final_ub[i] = basic_ub[i]; final_lb[i] = basic_lb[i]
            st[i] = final_ub[i]; direction_arr[i] = -1; continue
        pc = close[i - 1]
        final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i - 1] or pc > final_ub[i - 1]) else final_ub[i - 1]
        final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i - 1] or pc < final_lb[i - 1]) else final_lb[i - 1]
        if st[i - 1] == final_ub[i - 1]:
            if close[i] > final_ub[i]:
                st[i] = final_lb[i]; direction_arr[i] = 1
            else:
                st[i] = final_ub[i]; direction_arr[i] = -1
        else:
            if close[i] < final_lb[i]:
                st[i] = final_ub[i]; direction_arr[i] = -1
            else:
                st[i] = final_lb[i]; direction_arr[i] = 1
    return direction_arr, atr

# --- Simulate trade ---
def simulate_trade(entry_idx, direction, sl, tp, df):
    if sl is None or tp is None: return None
    for j in range(entry_idx + 1, len(df)):
        if direction == "LONG":
            if df.loc[j, "low"] <= sl:
                return {"exit_idx": j, "result": "SL", "pnl": sl - df.loc[entry_idx, "open"]}
            if df.loc[j, "high"] >= tp:
                return {"exit_idx": j, "result": "TP", "pnl": tp - df.loc[entry_idx, "open"]}
        else:
            if df.loc[j, "high"] >= sl:
                return {"exit_idx": j, "result": "SL", "pnl": df.loc[entry_idx, "open"] - sl}
            if df.loc[j, "low"] <= tp:
                return {"exit_idx": j, "result": "TP", "pnl": df.loc[entry_idx, "open"] - tp}
    return None

# --- Grid search on a dataset slice ---
def grid_search(df, ph_prev, pl_prev, ph_next, pl_next, min_warmup=0):
    n = len(df)
    periods = [7, 10, 14, 20, 30]
    multipliers = [1.5, 2.0, 2.5, 3.0, 3.5]
    results = []

    for period in periods:
        for mult in multipliers:
            direction_arr, atr_series = calc_supertrend(df, period, mult)
            signals = []
            start_i = max(period + 2, min_warmup)
            for i in range(start_i, n):
                if direction_arr[i - 1] == 1 and direction_arr[i - 2] == -1:
                    signals.append({"idx": i, "dir": "LONG", "entry": float(df.loc[i, "open"]), "atr": float(atr_series[i - 1])})
                elif direction_arr[i - 1] == -1 and direction_arr[i - 2] == 1:
                    signals.append({"idx": i, "dir": "SHORT", "entry": float(df.loc[i, "open"]), "atr": float(atr_series[i - 1])})

            trade_details = []
            for sig in signals:
                i = sig["idx"]; direction = sig["dir"]; entry = sig["entry"]; atr_val = sig["atr"]
                if direction == "LONG":
                    if pl_prev[i] is None: continue
                    sl = round(pl_prev[i] - 0.5 * atr_val, 2)
                    tp = round(ph_next[i], 2) if ph_next[i] is not None else round(entry + abs(entry - sl), 2)
                else:
                    if ph_prev[i] is None: continue
                    sl = round(ph_prev[i] + 0.5 * atr_val, 2)
                    tp = round(pl_next[i], 2) if pl_next[i] is not None else round(entry - abs(sl - entry), 2)
                if sl is None or tp is None: continue
                if (direction == "LONG" and sl >= entry) or (direction == "SHORT" and sl <= entry): continue
                outcome = simulate_trade(i, direction, sl, tp, df)
                if outcome is None: continue
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                rr_ratio = round(reward / risk, 2) if risk > 0 else 0
                trade_details.append({
                    "dir": direction, "entry": entry, "sl": sl, "tp": tp,
                    "result": outcome["result"], "rr_ratio": rr_ratio,
                    "bars_held": outcome["exit_idx"] - i, "pnl_pts": round(outcome["pnl"], 2)
                })

            w = sum(1 for t in trade_details if t["result"] == "TP")
            l = sum(1 for t in trade_details if t["result"] == "SL")
            total = w + l
            if total == 0: continue
            total_pnl = round(sum(t["pnl_pts"] for t in trade_details), 2)
            avg_rr = round(np.mean([t["rr_ratio"] for t in trade_details]), 2)
            sum_win = abs(sum(t["pnl_pts"] for t in trade_details if t["pnl_pts"] > 0))
            sum_loss = abs(sum(t["pnl_pts"] for t in trade_details if t["pnl_pts"] < 0))
            pf = round(sum_win / sum_loss, 2) if sum_loss > 0 else float("inf")
            pnls = np.array([t["pnl_pts"] for t in trade_details])
            sharpe = round(pnls.mean() / pnls.std() * np.sqrt(24*365) if pnls.std() > 0 else 0, 2)

            results.append({
                "st_period": period, "st_mult": mult,
                "total_trades": total, "wins": w, "losses": l,
                "win_rate_pct": round(w / total * 100, 1), "avg_rr": avg_rr,
                "total_pnl_pts": total_pnl, "profit_factor": pf, "sharpe": sharpe
            })
    return pd.DataFrame(results).sort_values("total_pnl_pts", ascending=False)

# --- Walk-Forward Loop ---
print("=" * 100)
print("WALK-FORWARD ANALYSIS — BTP 1h ST + Pivot Trailing")
print("Framework: Trombetta Ch 7 — Rolling IS/OOS windows")
print("=" * 100)
print(f"\nConfigurazione:")
print(f"  IS window:    {IS_WINDOW} bar")
print(f"  OOS forward:  {OOS_WINDOW} bar")
print(f"  Step:         {STEP} bar")
print(f"  Dati totali:  {n} bar ({df['ora'].iloc[0].strftime('%d/%m/%Y')} -> {df['ora'].iloc[-1].strftime('%d/%m/%Y')})")

windows = []
start_pos = 0
while start_pos + IS_WINDOW + OOS_WINDOW <= n:
    is_end = start_pos + IS_WINDOW
    oos_end = is_end + OOS_WINDOW
    windows.append((start_pos, is_end, oos_end))
    start_pos += STEP
# Add last window if space remains
if start_pos + IS_WINDOW + OOS_WINDOW > n and start_pos + IS_WINDOW < n:
    oos_end = min(start_pos + IS_WINDOW + OOS_WINDOW, n)
    if oos_end - start_pos - IS_WINDOW >= 100:
        windows.append((start_pos, start_pos + IS_WINDOW, oos_end))

print(f"\nFinestre totali: {len(windows)}\n")

all_window_results = []
best_config_votes = {}

for w_idx, (s, is_e, oos_e) in enumerate(windows):
    df_is = df.iloc[s:is_e].reset_index(drop=True)
    df_oos = df.iloc[is_e:oos_e].reset_index(drop=True)

    # Pivots on IS
    ph_prev, pl_prev, ph_next, pl_next = detect_pivots(df_is, LOOKBACK)
    is_results = grid_search(df_is, ph_prev, pl_prev, ph_next, pl_next)

    if is_results.empty:
        continue

    best_is = is_results.iloc[0]
    best_period = int(best_is["st_period"])
    best_mult = best_is["st_mult"]

    # Count vote for best config
    config_key = f"ST({best_period},{best_mult})"
    best_config_votes[config_key] = best_config_votes.get(config_key, 0) + 1

    # Test same config on OOS
    ph_prev_o, pl_prev_o, ph_next_o, pl_next_o = detect_pivots(df_oos, LOOKBACK)
    dir_arr_o, atr_o = calc_supertrend(df_oos, best_period, best_mult)

    oos_trades = []
    for i in range(max(best_period + 2, 5), len(df_oos)):
        if dir_arr_o[i - 1] == 1 and dir_arr_o[i - 2] == -1:
            direction = "LONG"; entry = float(df_oos.loc[i, "open"])
        elif dir_arr_o[i - 1] == -1 and dir_arr_o[i - 2] == 1:
            direction = "SHORT"; entry = float(df_oos.loc[i, "open"])
        else: continue

        atr_val = float(atr_o[i - 1])
        if direction == "LONG":
            if pl_prev_o[i] is None: continue
            sl = round(pl_prev_o[i] - 0.5 * atr_val, 2)
            tp = round(ph_next_o[i], 2) if ph_next_o[i] is not None else round(entry + abs(entry - sl), 2)
        else:
            if ph_prev_o[i] is None: continue
            sl = round(ph_prev_o[i] + 0.5 * atr_val, 2)
            tp = round(pl_next_o[i], 2) if pl_next_o[i] is not None else round(entry - abs(sl - entry), 2)
        if sl is None or tp is None: continue
        if (direction == "LONG" and sl >= entry) or (direction == "SHORT" and sl <= entry): continue
        outcome = simulate_trade(i, direction, sl, tp, df_oos)
        if outcome is None: continue
        risk = abs(entry - sl); reward = abs(tp - entry)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0
        oos_trades.append({
            "dir": direction, "entry": entry, "result": outcome["result"],
            "pnl_pts": round(outcome["pnl"], 2), "rr_ratio": rr_ratio
        })

    oos_w = sum(1 for t in oos_trades if t["result"] == "TP")
    oos_l = sum(1 for t in oos_trades if t["result"] == "SL")
    oos_total = oos_w + oos_l
    oos_pnl = round(sum(t["pnl_pts"] for t in oos_trades), 2) if oos_trades else 0
    oos_wr = round(oos_w / oos_total * 100, 1) if oos_total > 0 else 0
    oos_pnls = np.array([t["pnl_pts"] for t in oos_trades])
    oos_sharpe = round(oos_pnls.mean() / oos_pnls.std() * np.sqrt(24*365), 2) if (oos_total > 1 and oos_pnls.std() > 0) else 0
    sum_win = abs(sum(t["pnl_pts"] for t in oos_trades if t["pnl_pts"] > 0))
    sum_loss = abs(sum(t["pnl_pts"] for t in oos_trades if t["pnl_pts"] < 0))
    oos_pf = round(sum_win / sum_loss, 2) if sum_loss > 0 else float("inf")

    is_range = f"{df_is['ora'].iloc[0].strftime('%d/%m/%Y')} -> {df_is['ora'].iloc[-1].strftime('%d/%m/%Y')}"
    oos_range = f"{df_oos['ora'].iloc[0].strftime('%d/%m/%Y')} -> {df_oos['ora'].iloc[-1].strftime('%d/%m/%Y')}"

    wr = best_is["win_rate_pct"]
    pf = best_is["profit_factor"]
    sh = best_is["sharpe"]
    pnl = best_is["total_pnl_pts"]

    print(f"Finestra {w_idx+1:2d}/{len(windows)} | "
          f"Best IS: ST({best_period},{best_mult}) | "
          f"IS: W={wr}% PF={pf} Sh={sh} PnL={pnl} | "
          f"OOS: W={oos_wr}% PF={oos_pf} Sh={oos_sharpe} PnL={oos_pnl}")

    all_window_results.append({
        "window": w_idx + 1,
        "is_range": is_range, "oos_range": oos_range,
        "best_period": best_period, "best_mult": best_mult,
        "is_trades": int(best_is["total_trades"]), "is_win_rate": wr,
        "is_pnl": pnl, "is_pf": pf, "is_sharpe": sh,
        "oos_trades": oos_total, "oos_win_rate": oos_wr,
        "oos_pnl": oos_pnl, "oos_pf": oos_pf, "oos_sharpe": oos_sharpe
    })

# --- Summary ---
print("\n" + "=" * 100)
print("RIEPILOGO WALK-FORWARD ANALYSIS")
print("=" * 100)

print(f"\nDistribuzione best config sulle {len(all_window_results)} finestre:")
print(f"{'Config':<20} {'Voti':<8} {'%':<8}")
print("-" * 36)
best_config_total = sum(best_config_votes.values())
for config, votes in sorted(best_config_votes.items(), key=lambda x: -x[1]):
    pct = round(votes / best_config_total * 100, 1)
    bar = "#" * votes
    print(f"{config:<20} {votes:<8} {pct:<8.1f} {bar}")

# Stability metric: how many unique best configs
unique_configs = len(best_config_votes)
stability_pct = round(best_config_votes.get(max(best_config_votes, key=best_config_votes.get), 0) / best_config_total * 100, 1)
print(f"\nStabilita parametri:")
print(f"  Configurazioni uniche vincenti: {unique_configs}")
print(f"  Config dominante: {max(best_config_votes, key=best_config_votes.get)} ({stability_pct}% finestre)")

# OOS performance summary across windows
oos_pnls = [w["oos_pnl"] for w in all_window_results]
oos_wrs = [w["oos_win_rate"] for w in all_window_results]
oos_sharpes = [w["oos_sharpe"] for w in all_window_results]
is_sharpes = [w["is_sharpe"] for w in all_window_results]

positive_oos = sum(1 for p in oos_pnls if p > 0)
prop_positive = round(positive_oos / len(oos_pnls) * 100, 1)
avg_oos_pnl = round(np.mean(oos_pnls), 2)
avg_oos_wr = round(np.mean(oos_wrs), 1)
avg_oos_sh = round(np.mean(oos_sharpes), 2)
avg_is_sh = round(np.mean(is_sharpes), 2)

sharpe_changes = [w["oos_sharpe"] - w["is_sharpe"] for w in all_window_results]
avg_sharpe_change = round(np.mean(sharpe_changes), 2)
improved_windows = sum(1 for c in sharpe_changes if c > 0)
degraded_windows = sum(1 for c in sharpe_changes if c < 0)

print(f"\nPerformance OOS su tutte le finestre:")
print(f"  OOS positive:     {positive_oos}/{len(oos_pnls)} ({prop_positive}%)")
print(f"  OOS PnL medio:    {avg_oos_pnl} pts")
print(f"  OOS Win Rate avg: {avg_oos_wr}%")
print(f"  OOS Sharpe avg:   {avg_oos_sh}")
print(f"  IS Sharpe avg:    {avg_is_sh}")
print(f"  Sharpe migliorato: {improved_windows} finestre")
print(f"  Sharpe degradato:  {degraded_windows} finestre")
print(f"  Delta Sharpe medio: {avg_sharpe_change:+.2f}")

# Final verdict
print(f"\n" + "=" * 100)
print("VERDETTO FINALE WALK-FORWARD")
print("=" * 100)
if stability_pct >= 50 and avg_oos_sh > 0 and prop_positive >= 70:
    print(f"ROBUSTO — Config dominante nel {stability_pct}% finestre,")
    print(f"   OOS medio positivo ({avg_oos_pnl} pts), Sharpe medio {avg_oos_sh}.")
    print(f"   La strategia supera la Walk-Forward Analysis.")
elif stability_pct >= 30 and avg_oos_sh > 0:
    print(f"ACCETTABILE — Config dominante nel {stability_pct}% finestre,")
    print(f"   OOS positivo in media ({avg_oos_pnl} pts).")
    print(f"   Parametri non perfettamente stabili ma performance positiva.")
else:
    print(f"DEBOLE — Config dominante solo {stability_pct}% finestre,")
    print(f"   Sharpe medio OOS {avg_oos_sh}. Parametri instabili nel tempo.")

print(f"\nDettaglio completo salvato: output/walk_forward_results.json")

# Save
with open(os.path.join(OUTPUT_DIR, "walk_forward_results.json"), "w") as f:
    json.dump({
        "config": {"is_window": IS_WINDOW, "oos_window": OOS_WINDOW, "step": STEP,
                   "is_range": f"{df['ora'].iloc[0].strftime('%d/%m/%Y')} -> {df['ora'].iloc[-1].strftime('%d/%m/%Y')}"},
        "windows": all_window_results,
        "best_config_votes": best_config_votes,
        "summary": {
            "unique_configs": unique_configs,
            "dominant_config": max(best_config_votes, key=best_config_votes.get),
            "dominant_pct": stability_pct,
            "oos_positive_windows": prop_positive,
            "avg_oos_pnl_pts": avg_oos_pnl,
            "avg_oos_win_rate": avg_oos_wr,
            "avg_is_sharpe": avg_is_sh,
            "avg_oos_sharpe": avg_oos_sh,
            "avg_sharpe_delta": avg_sharpe_change,
            "improved_windows": improved_windows,
            "degraded_windows": degraded_windows
        }
    }, f, indent=2, ensure_ascii=False, default=str)

# CSV for easy analysis
pd.DataFrame(all_window_results).to_csv(os.path.join(OUTPUT_DIR, "walk_forward_results.csv"), index=False)
print(f"Dettaglio CSV salvato: output/walk_forward_results.csv")
print("=" * 100)
