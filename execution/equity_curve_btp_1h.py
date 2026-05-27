"""
Equity curve BTP 1h — ST(30, 1.5) + next_pivot
Costi: 3 EUR entry + 3 EUR exit = 6 EUR per trade
1 punto BTP = 1000 EUR
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

LOOKBACK = 5
ST_PERIOD = 30
ST_MULT = 1.5
COST_ENTRY = 3
COST_EXIT = 3
COST_TOTAL = COST_ENTRY + COST_EXIT
PUNTO_EUR = 1000
DATA_PATH = "dati/btp_1h_full.txt"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 1. Load data ---
df = pd.read_csv(DATA_PATH, sep="\t")
df.columns = [c.strip().lower() for c in df.columns]
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = df[col].astype(float)
df["ora"] = pd.to_datetime(df["data"])
df = df.drop(columns=["data"])
df = df.reset_index(drop=True)
n = len(df)

# --- 2. SuperTrend(30, 1.5) ---
high, low, close = df["high"], df["low"], df["close"]
tr1 = high - low
tr2 = (high - close.shift(1)).abs()
tr3 = (low - close.shift(1)).abs()
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr = tr.ewm(alpha=1 / ST_PERIOD, adjust=False).mean()
hl2 = (high + low) / 2
basic_ub = hl2 + ST_MULT * atr
basic_lb = hl2 - ST_MULT * atr

final_ub = [0.0] * n; final_lb = [0.0] * n
st = [0.0] * n; direction = [1] * n
for i in range(n):
    if i == 0:
        final_ub[i] = basic_ub.iloc[i]; final_lb[i] = basic_lb.iloc[i]
        st[i] = final_ub[i]; direction[i] = -1; continue
    pc = close.iloc[i - 1]
    if basic_ub.iloc[i] < final_ub[i - 1] or pc > final_ub[i - 1]:
        final_ub[i] = basic_ub.iloc[i]
    else:
        final_ub[i] = final_ub[i - 1]
    if basic_lb.iloc[i] > final_lb[i - 1] or pc < final_lb[i - 1]:
        final_lb[i] = basic_lb.iloc[i]
    else:
        final_lb[i] = final_lb[i - 1]
    if st[i - 1] == final_ub[i - 1]:
        if close.iloc[i] > final_ub[i]:
            st[i] = final_lb[i]; direction[i] = 1
        else:
            st[i] = final_ub[i]; direction[i] = -1
    else:
        if close.iloc[i] < final_lb[i]:
            st[i] = final_ub[i]; direction[i] = -1
        else:
            st[i] = final_lb[i]; direction[i] = 1

# --- 3. Pivots ---
pivot_high_flag = np.full(n, False)
pivot_low_flag = np.full(n, False)
for i in range(LOOKBACK, n - LOOKBACK):
    if all(df.loc[i, "high"] > df.loc[i - k, "high"] for k in range(1, LOOKBACK + 1)) and \
       all(df.loc[i, "high"] > df.loc[i + k, "high"] for k in range(1, LOOKBACK + 1)):
        pivot_high_flag[i] = True
    if all(df.loc[i, "low"] < df.loc[i - k, "low"] for k in range(1, LOOKBACK + 1)) and \
       all(df.loc[i, "low"] < df.loc[i + k, "low"] for k in range(1, LOOKBACK + 1)):
        pivot_low_flag[i] = True

prev_ph = [None] * n; prev_pl = [None] * n
lp = None; ll = None
for i in range(n):
    if pivot_high_flag[i]: lp = float(df.loc[i, "high"])
    if pivot_low_flag[i]: ll = float(df.loc[i, "low"])
    prev_ph[i] = lp; prev_pl[i] = ll

next_ph = [None] * n; next_pl = [None] * n
np_h = None; np_l = None
for i in range(n - 1, -1, -1):
    if pivot_high_flag[i]: np_h = float(df.loc[i, "high"])
    if pivot_low_flag[i]: np_l = float(df.loc[i, "low"])
    next_ph[i] = np_h; next_pl[i] = np_l

# --- 4. Signal detection with SL/TP ---
signals = []
for i in range(ST_PERIOD + 2, n):
    prev_dir = direction[i - 1]
    prev_prev_dir = direction[i - 2]
    if prev_dir == 1 and prev_prev_dir == -1:
        dir_label = "LONG"
    elif prev_dir == -1 and prev_prev_dir == 1:
        dir_label = "SHORT"
    else: continue
    entry = round(float(df.loc[i, "open"]), 2)
    atr_val = float(atr.iloc[i - 1])
    if dir_label == "LONG":
        pl = prev_pl[i]
        if pl is None: continue
        sl = round(pl - 0.5 * atr_val, 2)
        ph_next = next_ph[i]
        tp = round(ph_next, 2) if ph_next is not None else round(entry + (entry - sl), 2)
    else:
        ph = prev_ph[i]
        if ph is None: continue
        sl = round(ph + 0.5 * atr_val, 2)
        pl_next = next_pl[i]
        tp = round(pl_next, 2) if pl_next is not None else round(entry - (sl - entry), 2)
    if sl is None or tp is None: continue
    if dir_label == "LONG":
        if sl >= entry: continue
        if tp <= entry: tp = round(entry + (entry - sl), 2)
    if dir_label == "SHORT":
        if sl <= entry: continue
        if tp >= entry: tp = round(entry - (sl - entry), 2)
    signals.append({"idx": i, "dir": dir_label, "entry": entry, "sl": sl, "tp": tp, "atr": atr_val})

# --- 5. Simulate each trade ---
trades = []
equity = 0.0
equity_curve = []
dates = []

for sig in signals:
    i = sig["idx"]
    entry = sig["entry"]
    sl = sig["sl"]
    tp = sig["tp"]
    direction = sig["dir"]
    entry_date = df.loc[i, "ora"]

    # Walk forward to see if TP or SL hits first
    result = None; exit_price = None; exit_idx = None
    if direction == "LONG":
        for j in range(i + 1, n):
            if df.loc[j, "low"] <= sl:
                result = "SL"; exit_price = sl; exit_idx = j; break
            if df.loc[j, "high"] >= tp:
                result = "TP"; exit_price = tp; exit_idx = j; break
    else:
        for j in range(i + 1, n):
            if df.loc[j, "high"] >= sl:
                result = "SL"; exit_price = sl; exit_idx = j; break
            if df.loc[j, "low"] <= tp:
                result = "TP"; exit_price = tp; exit_idx = j; break

    if result is None: continue  # trade still open

    pnl_pts = round(exit_price - entry, 2) if direction == "LONG" else round(entry - exit_price, 2)
    pnl_eur = round(pnl_pts * PUNTO_EUR - COST_TOTAL, 2)
    equity += pnl_eur
    exit_date = df.loc[exit_idx, "ora"]

    trades.append({
        "entry_date": entry_date.strftime("%d/%m/%Y %H:%M"),
        "exit_date": exit_date.strftime("%d/%m/%Y %H:%M"),
        "dir": direction, "entry": entry, "sl": sl, "tp": tp,
        "result": result, "pnl_pts": pnl_pts, "pnl_eur": pnl_eur,
        "equity_eur": round(equity, 2), "bars": exit_idx - i
    })

    # Fill equity curve at each bar
    for k in range(len(dates), exit_idx + 1):
        equity_curve.append(equity)
        dates.append(df.loc[k, "ora"])

# Extend equity curve to end of data
while len(equity_curve) < n:
    equity_curve.append(equity)
    dates.append(df.loc[len(equity_curve) - 1, "ora"])

# --- 6. Statistics ---
pnls = [t["pnl_eur"] for t in trades]
wins = sum(1 for p in pnls if p > 0)
losses = sum(1 for p in pnls if p <= 0)
total = len(pnls)
win_rate = round(wins / total * 100, 1) if total else 0
total_pnl = round(sum(pnls), 2)
avg_win = round(np.mean([p for p in pnls if p > 0]), 2) if wins else 0
avg_loss = round(np.mean([p for p in pnls if p <= 0]), 2) if losses else 0
profit_factor = round(abs(sum(p for p in pnls if p > 0)) / abs(sum(p for p in pnls if p < 0)), 2) if sum(p for p in pnls if p < 0) != 0 else float("inf")
peak = np.maximum.accumulate(equity_curve)
dd = peak - equity_curve
max_dd_eur = round(np.max(dd), 2)
# DD% only when peak >= 1000 EUR (1 tick), otherwise 0
dd_pct = np.where(peak >= 1000, dd / peak * 100, 0)
max_dd_pct = round(np.max(dd_pct), 2)
avg_bars = round(np.mean([t["bars"] for t in trades]), 1)
longs = sum(1 for t in trades if t["dir"] == "LONG")
shorts = sum(1 for t in trades if t["dir"] == "SHORT")

# Sharpe-like: daily returns approximation
daily_returns = []
prev_equity = 0
for eq in equity_curve[::24]:  # sample every 24 bars (1 day)
    daily_returns.append(eq - prev_equity)
    prev_equity = eq
sharpe = round(np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252), 2) if np.std(daily_returns) > 0 else 0

# --- 7. Console report ---
print("=" * 100)
print(f"EQUITY CURVE BTP 1h — ST({ST_PERIOD}, {ST_MULT}) + next_pivot")
print(f"Costi: {COST_ENTRY} EUR entry + {COST_EXIT} EUR exit = {COST_TOTAL} EUR/trade")
print("=" * 100)

print(f"\n--- STATISTICHE ---")
print(f"  Periodo:           {df.loc[0, 'ora'].strftime('%d/%m/%Y')} - {df.loc[n-1, 'ora'].strftime('%d/%m/%Y')}")
print(f"  Trade totali:      {total}")
print(f"  LONG:              {longs}")
print(f"  SHORT:             {shorts}")
print(f"  Win rate:          {win_rate}% ({wins}W / {losses}L)")
print(f"  PnL totale:        {total_pnl:.2f} EUR")
print(f"  Avg win:           {avg_win:.2f} EUR")
print(f"  Avg loss:          {avg_loss:.2f} EUR")
print(f"  Profit factor:     {profit_factor}")
print(f"  Max drawdown:      {max_dd_eur:.2f} EUR ({max_dd_pct}%)")
print(f"  Avg bars held:     {avg_bars}")
print(f"  Sharpe ratio (dd): {sharpe}")

print(f"\n--- DETTAGLIO TRADE (costi inclusi) ---")
print(f"{'#':<4} {'Entry':<20} {'Exit':<20} {'Dir':<6} {'EntryP':<9} {'SL':<9} {'TP':<9} {'Ris':<6} {'PnL €':<10} {'Eq €':<10}")
print("-" * 120)
for k, t in enumerate(trades, 1):
    print(f"{k:<4} {t['entry_date']:<20} {t['exit_date']:<20} {t['dir']:<6} {t['entry']:<9.2f} {t['sl']:<9.2f} {t['tp']:<9.2f} {t['result']:<6} {t['pnl_eur']:<10.2f} {t['equity_eur']:<10.2f}")
print("-" * 120)
print(f"{'':<4} {'':<20} {'':<20} {'':<6} {'':<9} {'':<9} {'':<9} {'TOT':<6} {total_pnl:<10.2f} {round(equity, 2):<10.2f}")

# --- 8. Generate chart ---
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), gridspec_kw={'height_ratios': [3, 1]})
    fig.patch.set_facecolor('#0d1117')

    # Equity curve
    ax1.fill_between(dates, equity_curve, 0, color='#58a6ff', alpha=0.15)
    ax1.plot(dates, equity_curve, color='#58a6ff', linewidth=1.5, label=f'PnL: {total_pnl:.0f} EUR')
    ax1.axhline(y=0, color='#30363d', linewidth=0.8)
    ax1.set_facecolor('#161b22')
    ax1.set_title(f'Equity Curve — ST({ST_PERIOD}, {ST_MULT}) + next_pivot (costi {COST_TOTAL} EUR/trade)', color='white', fontsize=13)
    ax1.legend(loc='upper left', facecolor='#161b22', edgecolor='#30363d', labelcolor='white')
    ax1.tick_params(colors='#8b949e')
    ax1.spines['bottom'].set_color('#30363d')
    ax1.spines['left'].set_color('#30363d')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    # Drawdown
    ax2.fill_between(dates, dd, 0, color='#f85149', alpha=0.3)
    ax2.plot(dates, dd, color='#f85149', linewidth=1)
    ax2.set_facecolor('#161b22')
    ax2.set_title(f'Drawdown — Max: {max_dd_eur:.0f} EUR ({max_dd_pct}%)', color='white', fontsize=11)
    ax2.tick_params(colors='#8b949e')
    ax2.spines['bottom'].set_color('#30363d')
    ax2.spines['left'].set_color('#30363d')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    # Trade markers
    for t in trades:
        ed = pd.to_datetime(t['entry_date'], format='%d/%m/%Y %H:%M')
        color = '#3fb950' if t['pnl_eur'] > 0 else '#f85149'
        ax1.scatter(ed, t['equity_eur'], color=color, s=20, zorder=5)

    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.tight_layout()
    chart_path = os.path.join(OUTPUT_DIR, 'btp_1h_equity_curve.png')
    plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='#0d1117')
    print(f"\nGrafico salvato: {chart_path}")

    # Also save a version with candle backdrop
    fig2, ax = plt.subplots(figsize=(14, 6))
    fig2.patch.set_facecolor('#0d1117')
    ax.fill_between(dates, equity_curve, 0, color='#58a6ff', alpha=0.15)
    ax.plot(dates, equity_curve, color='#58a6ff', linewidth=1.5)
    ax.axhline(y=0, color='#30363d', linewidth=0.8)
    # Color segments green/red
    for t in trades:
        ed = pd.to_datetime(t['entry_date'], format='%d/%m/%Y %H:%M')
        xd = pd.to_datetime(t['exit_date'], format='%d/%m/%Y %H:%M')
        eq_at_entry = t['equity_eur'] - t['pnl_eur']
        eq_at_exit = t['equity_eur']
        color = '#3fb950' if t['pnl_eur'] > 0 else '#f85149'
        ax.plot([ed, xd], [eq_at_entry, eq_at_exit], color=color, linewidth=2.5, alpha=0.7)
    ax.set_facecolor('#161b22')
    ax.set_title(f'Equity Curve with Trade Segments — BTP 1h', color='white', fontsize=13)
    ax.tick_params(colors='#8b949e')
    ax.spines['bottom'].set_color('#30363d')
    ax.spines['left'].set_color('#30363d')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    chart2_path = os.path.join(OUTPUT_DIR, 'btp_1h_equity_segments.png')
    plt.savefig(chart2_path, dpi=150, bbox_inches='tight', facecolor='#0d1117')
    print(f"Grafico segmenti:  {chart2_path}")

except ImportError:
    print("\n[WARN] matplotlib non installato — salto generazione grafico")

# --- 9. Save equity curve data ---
np.savetxt(os.path.join(OUTPUT_DIR, "btp_1h_equity_curve.csv"),
           np.column_stack([dates, equity_curve]),
           delimiter=",", header="date,equity_eur", comments="", fmt="%s")

with open(os.path.join(OUTPUT_DIR, "btp_1h_equity_summary.json"), "w") as f:
    json.dump({
        "config": {"st_period": ST_PERIOD, "st_mult": ST_MULT, "cost_entry": COST_ENTRY, "cost_exit": COST_EXIT},
        "stats": {"total_trades": total, "wins": wins, "losses": losses, "win_rate": win_rate,
                  "total_pnl_eur": total_pnl, "avg_win_eur": avg_win, "avg_loss_eur": avg_loss,
                  "profit_factor": profit_factor, "max_dd_eur": max_dd_eur, "max_dd_pct": max_dd_pct,
                  "avg_bars_held": avg_bars, "sharpe": sharpe, "longs": longs, "shorts": shorts},
        "trades": trades, "equity_curve": [{"date": str(d), "equity": e} for d, e in zip(dates, equity_curve)]
    }, f, indent=2, ensure_ascii=False)

print(f"Salvato: output/btp_1h_equity_summary.json")
print("=" * 100)
