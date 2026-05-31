"""
Validazione IS/OOS -- Trombetta Ch 7
Split 70/30, grid search su IS, validazione su OOS, Walk-Forward Analysis.

Strategia: ST(period, mult) + Pivot Trailing (lookback=5)
SL = prev_pivot +/- 0.5*ATR
TP strategies: next_pivot, nearest_pivot, atr_rr

Output: output/isoos_validation_report.txt
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

# --- 1. Load data ---
df = pd.read_csv(DATA_PATH, sep="\t")
df.columns = [c.strip().lower() for c in df.columns]
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = df[col].astype(float)
df["ora"] = pd.to_datetime(df["data"])
df = df.drop(columns=["data"]).reset_index(drop=True)
n = len(df)

# --- 2. Split IS (70%) / OOS (30%) chronologically ---
split_idx = int(n * 0.7)
df_is = df.iloc[:split_idx].reset_index(drop=True)
df_oos = df.iloc[split_idx:].reset_index(drop=True)

print("=" * 100)
print("VALIDAZIONE IS/OOS - BTP 1h ST + Pivot Trailing")
print(f"Framework: Trombetta Ch 7 - IS=palestra, OOS=esame")
print("=" * 100)
print(f"\nDati totali: {n} candele 1h")
print(f"  IS (70%): {len(df_is)} candele -- {df_is['ora'].iloc[0].strftime('%d/%m/%Y')} -> {df_is['ora'].iloc[-1].strftime('%d/%m/%Y')}")
print(f"  OOS (30%): {len(df_oos)} candele -- {df_oos['ora'].iloc[0].strftime('%d/%m/%Y')} -> {df_oos['ora'].iloc[-1].strftime('%d/%m/%Y')}")

# --- 3. Pivot detection function ---
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
    # prev pivot (carry-forward)
    ph_prev = [None] * n; pl_prev = [None] * n
    lp = None; ll = None
    for i in range(n):
        if ph_flag[i]: lp = float(df.loc[i, "high"])
        if pl_flag[i]: ll = float(df.loc[i, "low"])
        ph_prev[i] = lp; pl_prev[i] = ll
    # next pivot (carry-backward)
    ph_next = [None] * n; pl_next = [None] * n
    np_h = None; np_l = None
    for i in range(n - 1, -1, -1):
        if ph_flag[i]: np_h = float(df.loc[i, "high"])
        if pl_flag[i]: np_l = float(df.loc[i, "low"])
        ph_next[i] = np_h; pl_next[i] = np_l
    return ph_prev, pl_prev, ph_next, pl_next

# --- 4. SuperTrend ---
def calc_supertrend(df, period, mult):
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    atr = np.zeros(n)
    direction_arr = np.ones(n, dtype=int)

    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - np.roll(close, 1)),
                               np.abs(low - np.roll(close, 1))))
    tr[0] = high[0] - low[0]
    # EMA
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

# --- 5. Simulate single trade ---
def simulate_trade(entry_idx, direction, sl, tp, df):
    if sl is None or tp is None:
        return None
    for j in range(entry_idx + 1, len(df)):
        if direction == "LONG":
            if df.loc[j, "low"] <= sl:
                return {"exit_idx": j, "result": "SL", "exit_price": sl,
                        "pnl": sl - df.loc[entry_idx, "open"]}
            if df.loc[j, "high"] >= tp:
                return {"exit_idx": j, "result": "TP", "exit_price": tp,
                        "pnl": tp - df.loc[entry_idx, "open"]}
        else:
            if df.loc[j, "high"] >= sl:
                return {"exit_idx": j, "result": "SL", "exit_price": sl,
                        "pnl": df.loc[entry_idx, "open"] - sl}
            if df.loc[j, "low"] <= tp:
                return {"exit_idx": j, "result": "TP", "exit_price": tp,
                        "pnl": df.loc[entry_idx, "open"] - tp}
    return None

# --- 6. Grid search on single dataset ---
def grid_search(df_dataset, dataset_label):
    ph_prev, pl_prev, ph_next, pl_next = detect_pivots(df_dataset, LOOKBACK)
    n = len(df_dataset)
    periods = [7, 10, 14, 20, 30]
    multipliers = [1.5, 2.0, 2.5, 3.0, 3.5]
    rr_multipliers = [1.0, 1.5, 2.0, 2.5, 3.0]
    results = []

    for period in periods:
        for mult in multipliers:
            direction_arr, atr_series = calc_supertrend(df_dataset, period, mult)

            signals = []
            for i in range(period + 2, n):
                if direction_arr[i - 1] == 1 and direction_arr[i - 2] == -1:
                    signals.append({"idx": i, "dir": "LONG", "entry": float(df_dataset.loc[i, "open"]),
                                    "atr": float(atr_series[i - 1])})
                elif direction_arr[i - 1] == -1 and direction_arr[i - 2] == 1:
                    signals.append({"idx": i, "dir": "SHORT", "entry": float(df_dataset.loc[i, "open"]),
                                    "atr": float(atr_series[i - 1])})

            for rr_mult in rr_multipliers:
                trade_details = []
                for sig in signals:
                    i = sig["idx"]; direction = sig["dir"]; entry = sig["entry"]; atr_val = sig["atr"]
                    if direction == "LONG":
                        if pl_prev[i] is None: continue
                        sl = round(pl_prev[i] - 0.5 * atr_val, 2)
                        tp_nearest = round(ph_prev[i], 2) if ph_prev[i] is not None else None
                        tp_next = round(ph_next[i], 2) if ph_next[i] is not None else None
                        tp_atr = round(entry + rr_mult * abs(entry - sl), 2)
                    else:
                        if ph_prev[i] is None: continue
                        sl = round(ph_prev[i] + 0.5 * atr_val, 2)
                        tp_nearest = round(pl_prev[i], 2) if pl_prev[i] is not None else None
                        tp_next = round(pl_next[i], 2) if pl_next[i] is not None else None
                        tp_atr = round(entry - rr_mult * abs(sl - entry), 2)

                    risk = abs(entry - sl)
                    if risk == 0: continue
                    for tp_label, tp_val in [("nearest_pivot", tp_nearest), ("next_pivot", tp_next), ("atr_rr", tp_atr)]:
                        if tp_val is None: continue
                        outcome = simulate_trade(i, direction, sl, tp_val, df_dataset)
                        if outcome is None: continue
                        reward = abs(tp_val - entry)
                        rr_ratio = round(reward / risk, 2) if risk > 0 else 0
                        trade_details.append({
                            "dir": direction, "entry": entry, "sl": sl, "tp": tp_val,
                            "tp_strategy": tp_label, "result": outcome["result"],
                            "rr_ratio": rr_ratio, "bars_held": outcome["exit_idx"] - i,
                            "pnl_pts": round(outcome["pnl"], 2)
                        })

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
                    sum_win = abs(sum(t["pnl_pts"] for t in subset if t["pnl_pts"] > 0))
                    sum_loss = abs(sum(t["pnl_pts"] for t in subset if t["pnl_pts"] < 0))
                    pf = round(sum_win / sum_loss, 2) if sum_loss > 0 else float("inf")

                    pnls = np.array([t["pnl_pts"] for t in subset])
                    sharpe = round(pnls.mean() / pnls.std() * np.sqrt(24*365) if pnls.std() > 0 else 0, 2)

                    results.append({
                        "dataset": dataset_label, "st_period": period, "st_mult": mult,
                        "tp_strategy": tp_label, "rr_mult": rr_mult if tp_label == "atr_rr" else 0,
                        "total_trades": total, "wins": w, "losses": l,
                        "win_rate_pct": win_rate, "avg_rr": avg_rr, "total_pnl_pts": total_pnl,
                        "profit_factor": pf, "avg_bars_held": avg_bars,
                        "sharpe": sharpe
                    })
    return pd.DataFrame(results)

# --- 7. Run grid search on IS ---
print("\n\n" + "=" * 100)
print("FASE 1: OTTIMIZZAZIONE SU IS (palestra)")
print("=" * 100)
print(f"\nParametri in esplorazione:")
print(f"  ST period:    [7, 10, 14, 20, 30]")
print(f"  ST mult:      [1.5, 2.0, 2.5, 3.0, 3.5]")
print(f"  TP strategies: nearest_pivot, next_pivot, atr_rr(RR=1.0~3.0)")

df_is_results = grid_search(df_is, "IS")
df_is_results = df_is_results.sort_values("total_pnl_pts", ascending=False)
# Deduplicate: same params but rr_mult doesn't apply to next/nearest pivot
df_is_results = df_is_results.drop_duplicates(subset=["st_period","st_mult","tp_strategy"], keep="first")

print(f"\nTop 10 combinazioni su IS:")
print(f"\n{'#':<4} {'ST':<10} {'TP':<18} {'Trades':<8} {'W%':<8} {'AvgRR':<8} {'PnL(p)':<10} {'PF':<8} {'Sharpe':<8}")
print("-" * 80)
for k, (_, r) in enumerate(df_is_results.head(10).iterrows()):
    st_label = f"ST({int(r['st_period'])},{r['st_mult']:.1f})"
    tp_label = f"{r['tp_strategy']}" + (f"(RR={r['rr_mult']:.0f})" if r['tp_strategy'] == 'atr_rr' else "")
    print(f"{k+1:<4} {st_label:<10} {tp_label:<18} {r['total_trades']:<8} {r['win_rate_pct']:<8} {r['avg_rr']:<8.2f} {r['total_pnl_pts']:<10.2f} {r['profit_factor']:<8.2f} {r['sharpe']:<8.2f}")

# --- 8. Top N configs -> OOS validation ---
print("\n\n" + "=" * 100)
print("FASE 2: VALIDAZIONE SU OOS (esame)")
print("=" * 100)
print(f"\nValidazione top 10 combinazioni IS su OOS ({len(df_oos)} candele mai viste)")
print(f"\n{'#':<4} {'Config':<18} {'IS_PnL':<10} {'IS_W':<7} {'IS_Sh':<8} {'OOS_PnL':<10} {'OOS_W':<7} {'OOS_Sh':<8} {'Sh_Degr':<9} {'Verdetto':<10}")
print("-" * 95)

df_oos_results = grid_search(df_oos, "OOS")
df_oos_results = df_oos_results.drop_duplicates(subset=["st_period","st_mult","tp_strategy"], keep="first")

verdicts = []
for k, (_, is_row) in enumerate(df_is_results.head(10).iterrows()):
    oos_match = df_oos_results[
        (df_oos_results["st_period"] == is_row["st_period"]) &
        (df_oos_results["st_mult"] == is_row["st_mult"]) &
        (df_oos_results["tp_strategy"] == is_row["tp_strategy"]) &
        (df_oos_results["rr_mult"] == is_row["rr_mult"])
    ]
    if oos_match.empty:
        oos_row = pd.Series({"total_pnl_pts": None, "win_rate_pct": None, "sharpe": None, "total_trades": None})
        degr_text = "N/A"; verdict = "N/A"
    else:
        oos_row = oos_match.iloc[0]
        is_sharpe = is_row["sharpe"]
        oos_sharpe = oos_row["sharpe"]
        if is_sharpe > 0 and oos_sharpe is not None:
            degr = round((is_sharpe - oos_sharpe) / is_sharpe * 100, 1)
            if degr > 50: verdict = "OVERFIT"
            elif degr > 25: verdict = "DEBOLE"
            else: verdict = "ROBUSTO"
        else:
            degr = None; degr_text = "N/A"; verdict = "N/A"

        degr_text = f"{degr}%" if degr is not None else "N/A"
        oos_pnl = round(oos_row["total_pnl_pts"], 2) if pd.notna(oos_row["total_pnl_pts"]) else None
        oos_wr = oos_row["win_rate_pct"] if pd.notna(oos_row["win_rate_pct"]) else None
    st_label = f"ST({int(is_row['st_period'])},{is_row['st_mult']:.1f})"
    tp_label = f"{is_row['tp_strategy']}" + (f"(RR={is_row['rr_mult']:.0f})" if is_row['tp_strategy'] == 'atr_rr' else "")
    config_label = f"{st_label}+{tp_label}"
    oos_pnl_str = f"{oos_row['total_pnl_pts']:<10.2f}" if pd.notna(oos_row.get('total_pnl_pts', None)) else f"{'N/A':<10}"
    oos_wr_str = f"{oos_row['win_rate_pct']:<7}" if pd.notna(oos_row.get('win_rate_pct', None)) else f"{'N/A':<7}"
    oos_sh_str = f"{oos_row['sharpe']:<8.2f}" if pd.notna(oos_row.get('sharpe', None)) else f"{'N/A':<8}"
    is_sh_str = f"{is_row['sharpe']:<8.2f}" if pd.notna(is_row.get('sharpe', None)) else f"{'N/A':<8}"

    print(f"{k+1:<4} {config_label:<18} {is_row['total_pnl_pts']:<10.2f} {is_row['win_rate_pct']:<7} {is_sh_str} {oos_pnl_str} {oos_wr_str} {oos_sh_str} {degr_text:<9} {verdict:<10}")
    verdicts.append({
        "rank": k+1, "st_period": int(is_row["st_period"]), "st_mult": is_row["st_mult"],
        "tp_strategy": is_row["tp_strategy"], "rr_mult": is_row["rr_mult"],
        "is_pnl": is_row["total_pnl_pts"], "is_win_rate": is_row["win_rate_pct"],
        "is_sharpe": is_row["sharpe"], "is_trades": is_row["total_trades"],
        "oos_pnl": oos_row["total_pnl_pts"] if pd.notna(oos_row.get("total_pnl_pts", None)) else None,
        "oos_win_rate": oos_row["win_rate_pct"] if pd.notna(oos_row.get("win_rate_pct", None)) else None,
        "oos_sharpe": oos_row["sharpe"] if pd.notna(oos_row.get("sharpe", None)) else None,
        "oos_trades": oos_row["total_trades"] if pd.notna(oos_row.get("total_trades", None)) else None,
        "sharpe_degradation_pct": degr, "verdict": verdict
    })

# --- 9. Focus sulla best config attuale ST(30,1.5) next_pivot ---
print("\n\n" + "=" * 100)
print("FASE 3: FOCUS SULLA CONFIGURAZIONE ATTUALMENTE IN USO")
print(f"ST(30, 1.5) + next_pivot -- IMPATTO IS/OOS")
print("=" * 100)

def find_config(df_res, period, mult, tp_strat, rr_mult=0):
    match = df_res[(df_res["st_period"] == period) & (df_res["st_mult"] == mult) &
                   (df_res["tp_strategy"] == tp_strat) & (df_res["rr_mult"] == rr_mult)]
    return match.iloc[0] if not match.empty else None

current_is = find_config(df_is_results, 30, 1.5, "next_pivot")
current_oos = find_config(df_oos_results, 30, 1.5, "next_pivot")

if current_is is not None:
    print(f"\nMetrica          {'IS':>12} {'OOS':>12} {'Degrado':>10}")
    print("-" * 50)
    for metric, label in [("total_trades", "Trades"), ("win_rate_pct", "Win Rate %"),
                          ("avg_rr", "Avg R/R"), ("total_pnl_pts", "PnL (pts)"),
                          ("profit_factor", "Profit Factor"), ("sharpe", "Sharpe")]:
        is_val = current_is[metric]
        oos_val = current_oos[metric] if current_oos is not None else None
        if oos_val is not None and is_val != 0:
            degr = round((is_val - oos_val) / abs(is_val) * 100, 1)
        else:
            degr = None
        is_str = f"{is_val:<12}" if pd.notna(is_val) else f"{'N/A':<12}"
        oos_str = f"{oos_val:<12.2f}" if (oos_val is not None and pd.notna(oos_val)) else f"{'N/A':<12}"
        degr_str = f"{degr}%" if degr is not None else "N/A"
        print(f"{label:<20} {is_str} {oos_str} {degr_str}")

    if current_oos is not None:
        is_s = current_is["sharpe"]; oos_s = current_oos["sharpe"]
        if is_s > 0 and oos_s is not None:
            diff_pct = round((oos_s - is_s) / is_s * 100, 1)
            degr = abs(diff_pct) if diff_pct < 0 else -diff_pct
            if diff_pct < -50:
                print(f"\nVERDETTO: OVERFIT - Sharpe degradato del {abs(diff_pct)}% (>50%)")
                print(f"   La configurazione ST(30,1.5)+next_pivot funziona bene solo IS.")
                print(f"   Secondo Trombetta (Ch 7): non tradabile senza riduzione parametri.")
            elif diff_pct < -25:
                print(f"\nVERDETTO: DEBOLE - Sharpe degradato del {abs(diff_pct)}% (25-50%)")
                print(f"   La configurazione ha una certa robustezza ma il degrado e preoccupante.")
            elif diff_pct < 0:
                print(f"\nVERDETTO: ROBUSTO - Sharpe degradato solo {abs(diff_pct)}% (<25%)")
                print(f"   La configurazione regge bene il passaggio IS->OOS. Trading possibile.")
            else:
                print(f"\nVERDETTO: OTTIMO! - Sharpe MIGLIORATO del {diff_pct}% su OOS")
                print(f"   La configurazione performa meglio sui dati mai visti che su IS.")
                print(f"   Segnale di robustezza molto forte secondo Trombetta (Ch 7).")
else:
    print(f"\nConfigurazione ST(30, 1.5) + next_pivot non trovata nei risultati IS.")

# --- 10. Best OOS config ---
print("\n\n" + "=" * 100)
print("FASE 4: MIGLIORE CONFIGURAZIONE SU OOS")
print("=" * 100)
print("\nLa migliore config su OOS (quella che ha funzionato meglio sui dati mai visti):")
best_oos = df_oos_results.sort_values("total_pnl_pts", ascending=False).head(10)
# Remove any remaining duplicates for display
best_oos = best_oos.drop_duplicates(subset=["st_period","st_mult","tp_strategy"], keep="first").head(5)
for k, (_, r) in enumerate(best_oos.iterrows()):
    st_label = f"ST({int(r['st_period'])},{r['st_mult']:.1f})"
    tp_label = f"{r['tp_strategy']}" + (f"(RR={r['rr_mult']:.0f})" if r['tp_strategy'] == 'atr_rr' else "")
    print(f"  {k+1}. {st_label:<12} {tp_label:<20} Trades={r['total_trades']:<6} W={r['win_rate_pct']}%  PnL={r['total_pnl_pts']:<8.2f} Sharpe={r['sharpe']:<8.2f}")

print(f"\nNota: Se la best config OOS e diversa dalla best config IS,")
print(f"i parametri non sono stabili nel tempo. Serve Walk-Forward Analysis.")

# --- 11. Save report ---
report = {
    "meta": {
        "title": "Validazione IS/OOS -- Trombetta Ch 7",
        "data": {"total_candles": n, "is_candles": len(df_is), "oos_candles": len(df_oos),
                 "is_range": f"{df_is['ora'].iloc[0].strftime('%d/%m/%Y')} -> {df_is['ora'].iloc[-1].strftime('%d/%m/%Y')}",
                 "oos_range": f"{df_oos['ora'].iloc[0].strftime('%d/%m/%Y')} -> {df_oos['ora'].iloc[-1].strftime('%d/%m/%Y')}"},
        "lookback": LOOKBACK
    },
    "top_10_is": df_is_results.head(10).to_dict(orient="records"),
    "top_10_oos": df_oos_results.head(10).to_dict(orient="records"),
    "current_config_ST_30_1_5_next_pivot": {
        "is": dict(current_is) if current_is is not None else None,
        "oos": dict(current_oos) if current_oos is not None else None
    },
    "verdicts": verdicts
}

with open(os.path.join(OUTPUT_DIR, "isoos_validation_report.json"), "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False, default=str)

# Save full results
df_is_results.to_csv(os.path.join(OUTPUT_DIR, "isoos_is_results.csv"), index=False)
df_oos_results.to_csv(os.path.join(OUTPUT_DIR, "isoos_oos_results.csv"), index=False)

print(f"\n\nRapporto completo salvato: output/isoos_validation_report.json")
print("=" * 100)
