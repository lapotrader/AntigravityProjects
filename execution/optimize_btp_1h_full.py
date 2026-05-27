import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

LOOKBACK = 5
DATA_PATH = "dati/btp_1h_full.txt"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -- 1. Load data
df = pd.read_csv(DATA_PATH, sep="\t")
df.columns = [c.strip().lower() for c in df.columns]
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = df[col].astype(float)
df["ora"] = pd.to_datetime(df["data"])
df = df.drop(columns=["data"])
df = df.reset_index(drop=True)
n = len(df)

# ── 2. Pivot detection (static, independent of ST params) ─────
pivot_high_flag = np.full(n, False)
pivot_low_flag = np.full(n, False)
for i in range(LOOKBACK, n - LOOKBACK):
    if all(df.loc[i, "high"] > df.loc[i - k, "high"] for k in range(1, LOOKBACK + 1)) and \
       all(df.loc[i, "high"] > df.loc[i + k, "high"] for k in range(1, LOOKBACK + 1)):
        pivot_high_flag[i] = True
    if all(df.loc[i, "low"] < df.loc[i - k, "low"] for k in range(1, LOOKBACK + 1)) and \
       all(df.loc[i, "low"] < df.loc[i + k, "low"] for k in range(1, LOOKBACK + 1)):
        pivot_low_flag[i] = True

# Carry-forward: nearest PREVIOUS pivot (for SL)
nearest_ph_prev = [None] * n
nearest_pl_prev = [None] * n
last_ph = None; last_pl = None
for i in range(n):
    if pivot_high_flag[i]: last_ph = float(df.loc[i, "high"])
    if pivot_low_flag[i]: last_pl = float(df.loc[i, "low"])
    nearest_ph_prev[i] = last_ph
    nearest_pl_prev[i] = last_pl

# Forward-fill: nearest NEXT pivot after entry (for TP)
nearest_ph_next = [None] * n
nearest_pl_next = [None] * n
next_ph = None; next_pl = None
for i in range(n - 1, -1, -1):
    if pivot_high_flag[i]: next_ph = float(df.loc[i, "high"])
    if pivot_low_flag[i]: next_pl = float(df.loc[i, "low"])
    nearest_ph_next[i] = next_ph
    nearest_pl_next[i] = next_pl

# ── 3. Simulation function ────────────────────────────────────
def simulate_trade(entry_idx, direction, sl, tp, df):
    if sl is None or tp is None:
        return None
    if direction == "LONG":
        for j in range(entry_idx + 1, len(df)):
            if df.loc[j, "low"] <= sl:
                return {"exit_idx": j, "result": "SL", "exit_price": sl, "pnl": sl - df.loc[entry_idx, "open"]}
            if df.loc[j, "high"] >= tp:
                return {"exit_idx": j, "result": "TP", "exit_price": tp, "pnl": tp - df.loc[entry_idx, "open"]}
    else:
        for j in range(entry_idx + 1, len(df)):
            if df.loc[j, "high"] >= sl:
                return {"exit_idx": j, "result": "SL", "exit_price": sl, "pnl": df.loc[entry_idx, "open"] - sl}
            if df.loc[j, "low"] <= tp:
                return {"exit_idx": j, "result": "TP", "exit_price": tp, "pnl": df.loc[entry_idx, "open"] - tp}
    return None

# ── 4. SuperTrend calculation ─────────────────────────────────
def calc_supertrend(df, period, multiplier):
    high, low, close = df["high"], df["low"], df["close"]
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    hl2 = (high + low) / 2
    basic_ub = hl2 + multiplier * atr
    basic_lb = hl2 - multiplier * atr

    final_ub = [0.0] * n; final_lb = [0.0] * n
    supertrend = [0.0] * n; direction_arr = [1] * n
    for i in range(n):
        if i == 0:
            final_ub[i] = basic_ub.iloc[i]; final_lb[i] = basic_lb.iloc[i]
            supertrend[i] = final_ub[i]; direction_arr[i] = -1; continue
        pc = close.iloc[i - 1]
        if basic_ub.iloc[i] < final_ub[i - 1] or pc > final_ub[i - 1]:
            final_ub[i] = basic_ub.iloc[i]
        else:
            final_ub[i] = final_ub[i - 1]
        if basic_lb.iloc[i] > final_lb[i - 1] or pc < final_lb[i - 1]:
            final_lb[i] = basic_lb.iloc[i]
        else:
            final_lb[i] = final_lb[i - 1]
        if supertrend[i - 1] == final_ub[i - 1]:
            if close.iloc[i] > final_ub[i]:
                supertrend[i] = final_lb[i]; direction_arr[i] = 1
            else:
                supertrend[i] = final_ub[i]; direction_arr[i] = -1
        else:
            if close.iloc[i] < final_lb[i]:
                supertrend[i] = final_ub[i]; direction_arr[i] = -1
            else:
                supertrend[i] = final_lb[i]; direction_arr[i] = 1
    return direction_arr, atr

# ── 5. Grid search ────────────────────────────────────────────
periods = [7, 10, 14, 20, 30]
multipliers = [1.5, 2.0, 2.5, 3.0, 3.5]
rr_multipliers = [1.0, 1.5, 2.0, 2.5, 3.0]

# TP strategies to compare:
# "next_pivot" = use next pivot after entry
# "nearest_pivot" = use nearest previous pivot (current logic)
# "atr_rr" = TP = entry + RR_mult * (entry - SL)

results = []

for period in periods:
    for mult in multipliers:
        direction_arr, atr_series = calc_supertrend(df, period, mult)

        signals = []
        for i in range(2, n):
            if i <= period: continue  # warmup
            prev_dir = direction_arr[i - 1]
            prev_prev_dir = direction_arr[i - 2]
            if prev_dir == 1 and prev_prev_dir == -1:
                signals.append({"idx": i, "dir": "LONG", "entry": float(df.loc[i, "open"]), "atr": float(atr_series.iloc[i - 1])})
            elif prev_dir == -1 and prev_prev_dir == 1:
                signals.append({"idx": i, "dir": "SHORT", "entry": float(df.loc[i, "open"]), "atr": float(atr_series.iloc[i - 1])})

        # Evaluate each TP strategy
        for rr_mult in rr_multipliers:
            wins = 0; losses = 0; total_rr = 0.0
            trade_details = []

            for sig in signals:
                i = sig["idx"]
                direction = sig["dir"]
                entry = sig["entry"]
                atr_val = sig["atr"]

                # SL: previous pivot +- 0.5*ATR
                ph_prev = nearest_ph_prev[i]
                pl_prev = nearest_pl_prev[i]

                if direction == "LONG":
                    if pl_prev is None: continue
                    sl = round(pl_prev - 0.5 * atr_val, 2)
                    # TP: 3 strategies
                    # Strategy A: nearest pivot high (before entry)
                    tp_nearest = round(ph_prev, 2) if ph_prev is not None else None
                    # Strategy B: next pivot high (after entry)
                    tp_next = round(nearest_ph_next[i], 2) if nearest_ph_next[i] is not None else None
                    # Strategy C: ATR-based RR
                    tp_atr = round(entry + rr_mult * (entry - sl), 2)
                else:
                    if ph_prev is None: continue
                    sl = round(ph_prev + 0.5 * atr_val, 2)
                    tp_nearest = round(pl_prev, 2) if pl_prev is not None else None
                    tp_next = round(nearest_pl_next[i], 2) if nearest_pl_next[i] is not None else None
                    tp_atr = round(entry - rr_mult * (sl - entry), 2)

                risk = abs(entry - sl)
                if risk == 0: continue

                # Simulate each TP variant
                for tp_label, tp_val in [("nearest_pivot", tp_nearest), ("next_pivot", tp_next), ("atr_rr", tp_atr)]:
                    if tp_val is None: continue
                    outcome = simulate_trade(i, direction, sl, tp_val, df)
                    if outcome is None: continue
                    pnl = outcome["pnl"]
                    actual_rr = pnl / risk if direction == "LONG" else pnl / risk  # already signed
                    reward = abs(tp_val - entry)
                    rr_ratio = round(reward / risk, 2) if risk > 0 else 0

                    is_win = 1 if outcome["result"] == "TP" else 0
                    trade_details.append({
                        "dir": direction, "entry": entry, "sl": sl, "tp": tp_val,
                        "tp_strategy": tp_label, "result": outcome["result"],
                        "rr_ratio": rr_ratio, "bars_held": outcome["exit_idx"] - i,
                        "pnl_pts": round(pnl, 2)
                    })

            # Aggregate by TP strategy
            for tp_label in ["nearest_pivot", "next_pivot", "atr_rr"]:
                subset = [t for t in trade_details if t["tp_strategy"] == tp_label]
                if not subset: continue
                w = sum(1 for t in subset if t["result"] == "TP")
                l = sum(1 for t in subset if t["result"] == "SL")
                total = w + l
                if total == 0: continue
                win_rate = round(w / total * 100, 1)
                avg_rr = round(np.mean([t["rr_ratio"] for t in subset]), 2)
                total_pnl = round(sum(t["pnl_pts"] for t in subset), 2)
                avg_bars = round(np.mean([t["bars_held"] for t in subset]), 1)
                max_loss = round(min(t["pnl_pts"] for t in subset), 2)
                max_win = round(max(t["pnl_pts"] for t in subset), 2)

                results.append({
                    "st_period": period, "st_mult": mult,
                    "tp_strategy": tp_label,
                    "rr_mult": rr_mult if tp_label == "atr_rr" else 0,
                    "total_signals": len(signals),
                    "total_trades": total,
                    "wins": w, "losses": l,
                    "win_rate_pct": win_rate,
                    "avg_rr": avg_rr, "total_pnl_pts": total_pnl,
                    "avg_bars_held": avg_bars,
                    "max_loss_pts": max_loss, "max_win_pts": max_win,
                    "profit_factor": round(abs(sum(t["pnl_pts"] for t in subset if t["pnl_pts"] > 0)) / abs(sum(t["pnl_pts"] for t in subset if t["pnl_pts"] < 0)) if sum(t["pnl_pts"] for t in subset if t["pnl_pts"] < 0) != 0 else float("inf"), 2)
                })

res_df = pd.DataFrame(results)
res_df = res_df.sort_values("total_pnl_pts", ascending=False)

# ── 6. Report ─────────────────────────────────────────────────
print("=" * 120)
print(f"OTTIMIZZAZIONE COMPLETA BTP 1h - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
print("=" * 120)

print(f"\nDATI: {n} candele 1h BTP Future")
print(f"PIVOT: lookback={LOOKBACK} | SUPERTREND: periodi {periods}, multiplier {multipliers}")
print(f"STRATEGIE TP: nearest_pivot, next_pivot, atr_rr(RR={rr_multipliers})")
print(f"TOTALE COMBINAZIONI: {len(res_df)}")

# Top 20 overall
print("\n" + "-" * 120)
print("TOP 20 COMBINAZIONI PER PNL TOTALE (punti)")
print("-" * 120)
header = f"{'ST_per':<6} {'ST_mult':<8} {'TP_strategy':<16} {'RR_mult':<8} {'Trades':<8} {'W%':<8} {'AvgRR':<8} {'PnL_pts':<10} {'PF':<8} {'AvgBars':<8} {'MaxLoss':<10}"
print(header)
print("-" * 120)
for _, r in res_df.head(20).iterrows():
    print(f"{r['st_period']:<6} {r['st_mult']:<8.1f} {r['tp_strategy']:<16} {r['rr_mult']:<8.0f} {r['total_trades']:<8} {r['win_rate_pct']:<8} {r['avg_rr']:<8.2f} {r['total_pnl_pts']:<10.2f} {r['profit_factor']:<8.2f} {r['avg_bars_held']:<8} {r['max_loss_pts']:<10.2f}")

# Best per TP strategy
print("\n" + "-" * 120)
print("MIGLIORE PER OGNI STRATEGIA TP (per PnL)")
print("-" * 120)
for strategy in ["nearest_pivot", "next_pivot", "atr_rr"]:
    subset = res_df[res_df["tp_strategy"] == strategy].head(3)
    print(f"\n  [{strategy}]")
    for _, r in subset.iterrows():
        rr_label = f" (RR={r['rr_mult']:.0f})" if strategy == "atr_rr" else ""
        print(f"    ST({r['st_period']}, {r['st_mult']:.1f}){rr_label} >> WinRate={r['win_rate_pct']}%  AvgRR={r['avg_rr']}  PnL={r['total_pnl_pts']:.2f} pts  PF={r['profit_factor']}  Trades={r['total_trades']}")

# ── 7. Detailed trade list for best config ────────────────────
print("\n" + "=" * 120)
print("DETTAGLIO TRADE - MIGLIORE CONFIGURAZIONE ASSOLUTA")
print("=" * 120)

best = res_df.iloc[0]
print(f"\nConfig: ST({best['st_period']}, {best['st_mult']:.1f}) | TP={best['tp_strategy']} | RR_mult={best['rr_mult']:.0f}")
print(f"WinRate: {best['win_rate_pct']}% | AvgRR: {best['avg_rr']} | PnL: {best['total_pnl_pts']:.2f} pts | PF: {best['profit_factor']}")

best_period = int(best['st_period'])
best_mult = best['st_mult']
best_tp_strat = best['tp_strategy']
best_rr_mult = int(best['rr_mult'])

# Re-run best config for detailed trade list
direction_arr, atr_series = calc_supertrend(df, best_period, best_mult)
signals = []
for i in range(2, n):
    if i <= best_period: continue
    prev_dir = direction_arr[i - 1]
    prev_prev_dir = direction_arr[i - 2]
    if prev_dir == 1 and prev_prev_dir == -1:
        signals.append({"idx": i, "dir": "LONG", "entry": float(df.loc[i, "open"]), "atr": float(atr_series.iloc[i - 1])})
    elif prev_dir == -1 and prev_prev_dir == 1:
        signals.append({"idx": i, "dir": "SHORT", "entry": float(df.loc[i, "open"]), "atr": float(atr_series.iloc[i - 1])})

all_trades = []
for sig in signals:
    i = sig["idx"]
    direction = sig["dir"]
    entry = sig["entry"]
    atr_val = sig["atr"]
    ph_prev = nearest_ph_prev[i]; pl_prev = nearest_pl_prev[i]

    if direction == "LONG":
        if pl_prev is None: continue
        sl = round(pl_prev - 0.5 * atr_val, 2)
        if best_tp_strat == "nearest_pivot":
            tp = round(ph_prev, 2) if ph_prev is not None else None
        elif best_tp_strat == "next_pivot":
            tp = round(nearest_ph_next[i], 2) if nearest_ph_next[i] is not None else None
        else:
            tp = round(entry + best_rr_mult * (entry - sl), 2)
    else:
        if ph_prev is None: continue
        sl = round(ph_prev + 0.5 * atr_val, 2)
        if best_tp_strat == "nearest_pivot":
            tp = round(pl_prev, 2) if pl_prev is not None else None
        elif best_tp_strat == "next_pivot":
            tp = round(nearest_pl_next[i], 2) if nearest_pl_next[i] is not None else None
        else:
            tp = round(entry - best_rr_mult * (sl - entry), 2)

    if tp is None: continue
    outcome = simulate_trade(i, direction, sl, tp, df)
    if outcome is None: continue
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr_ratio = round(reward / risk, 2) if risk > 0 else 0

    all_trades.append({
        "data": df.loc[i, "ora"].strftime("%d/%m/%Y %H:%M"),
        "dir": direction, "entry": entry, "sl": sl, "tp": tp,
        "result": outcome["result"], "rr": rr_ratio,
        "bars": outcome["exit_idx"] - i,
        "pnl": round(outcome["pnl"], 2),
        "exit_data": df.loc[outcome["exit_idx"], "ora"].strftime("%d/%m/%Y %H:%M")
    })

print(f"\n{'Data Entry':<20} {'Dir':<6} {'Entry':<9} {'SL':<9} {'TP':<9} {'Risultato':<10} {'R/R':<7} {'Barre':<7} {'PnL':<9} {'Exit':<20}")
print("-" * 115)
for t in all_trades:
    print(f"{t['data']:<20} {t['dir']:<6} {t['entry']:<9.2f} {t['sl']:<9.2f} {t['tp']:<9.2f} {t['result']:<10} {t['rr']:<7.2f} {t['bars']:<7} {t['pnl']:<9.2f} {t['exit_data']:<20}")

wins = sum(1 for t in all_trades if t['result'] == 'TP')
losses = sum(1 for t in all_trades if t['result'] == 'SL')
total_pnl = sum(t['pnl'] for t in all_trades)
avg_rr_all = np.mean([t['rr'] for t in all_trades])
print("-" * 115)
print(f"TOT: {len(all_trades)} trade | W={wins} L={losses} | WinRate={wins/len(all_trades)*100:.1f}% | PnL={total_pnl:.2f} pts | AvgRR={avg_rr_all:.2f}")

# Save full results
res_df.to_csv(os.path.join(OUTPUT_DIR, "optimization_full_results.csv"), index=False)
print(f"\nRisultati completi salvati in: {os.path.join(OUTPUT_DIR, 'optimization_full_results.csv')}")

# Save best config trade details
with open(os.path.join(OUTPUT_DIR, "best_config_trades.json"), "w") as f:
    json.dump({
        "config": {"st_period": best_period, "st_mult": best_mult, "tp_strategy": best_tp_strat, "rr_mult": best_rr_mult},
        "stats": {"total": len(all_trades), "wins": wins, "losses": losses, "win_rate": round(wins/len(all_trades)*100, 1), "total_pnl": total_pnl, "avg_rr": avg_rr_all},
        "trades": all_trades
    }, f, indent=2, ensure_ascii=False)

print(f"Dettaglio trade salvato in: {os.path.join(OUTPUT_DIR, 'best_config_trades.json')}")
