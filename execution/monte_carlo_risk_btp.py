"""
Monte Carlo Evoluto + Risk Management — Trombetta Ch 8
Controllo statico (1% per trade) + dinamico (Performance Control) + rischio di rovina.

Data: trade PnL history dalla strategia ST(30,1.5)+next_pivot
Output: output/mc_risk_report.json, output/mc_equity_fan.png
"""
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

OUTPUT_DIR = "output"
SUMMARY_PATH = os.path.join(OUTPUT_DIR, "btp_1h_equity_summary.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 1. Load trade data ---
with open(SUMMARY_PATH, "r") as f:
    data = json.load(f)

trades = data["trades"]
pnls = np.array([t["pnl_eur"] for t in trades])
n_trades = len(pnls)
total_pnl = sum(pnls)
avg_win = np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0
avg_loss = np.mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0
win_rate = sum(1 for p in pnls if p > 0) / n_trades

print("=" * 100)
print("MONTE CARLO E RISK MANAGEMENT — BTP 1h ST(30,1.5)+next_pivot")
print("Framework: Trombetta Ch 8 — Controllo statico, dinamico, Monte Carlo evoluto")
print("=" * 100)

print(f"\nDati trade ({n_trades} operazioni):")
print(f"  PnL totale:      {total_pnl:+.2f} EUR")
print(f"  Avg win:         {avg_win:.2f} EUR")
print(f"  Avg loss:        {avg_loss:.2f} EUR")
print(f"  Win rate:        {win_rate*100:.1f}%")
print(f"  Max win:         {max(pnls):.2f} EUR")
print(f"  Max loss:        {min(pnls):.2f} EUR")
print(f"  Std dev PnL:     {np.std(pnls):.2f} EUR")

# --- 2. Monte Carlo simulation ---
N_SIMULATIONS = 10000
CAPITALE_INIZIALE = 50000
RUIN_THRESHOLD = 0.5  # rovina se equity < 50% capitale iniziale
RISCHIO_STATICO = 0.01  # 1% per trade

np.random.seed(42)

final_equities = []
max_dds_pct = []
max_dds_eur = []
ruin_count = 0
all_paths = np.zeros((min(N_SIMULATIONS, 500), n_trades))  # save max 500 paths for chart

for sim in range(N_SIMULATIONS):
    equity = CAPITALE_INIZIALE
    peak = CAPITALE_INIZIALE
    max_dd = 0
    ruined = False

    # Resample trades with replacement
    sim_pnls = np.random.choice(pnls, size=n_trades, replace=True)

    for step, pnl in enumerate(sim_pnls):
        equity += pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        dd_pct = dd / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
        if equity < CAPITALE_INIZIALE * RUIN_THRESHOLD:
            ruined = True

    final_equities.append(equity)
    max_dds_eur.append(max_dd)
    max_dds_pct.append(max_dd / CAPITALE_INIZIALE * 100)
    if ruined:
        ruin_count += 1

    if sim < 500:
        eq = CAPITALE_INIZIALE
        for step, pnl in enumerate(sim_pnls):
            eq += pnl
            all_paths[sim, step] = eq

final_equities = np.array(final_equities)
max_dds_eur = np.array(max_dds_eur)
max_dds_pct = np.array(max_dds_pct)
ruin_prob = ruin_count / N_SIMULATIONS * 100

# --- 3. Monte Carlo Statistics ---
print("\n" + "=" * 100)
print("MONTE CARLO: 10.000 SIMULAZIONI (ricampionamento con reinserimento)")
print("=" * 100)

print(f"\nDistribuzione equity finale (capitale iniziale: {CAPITALE_INIZIALE:,} EUR):")
for pct in [5, 10, 25, 50, 75, 90, 95]:
    val = np.percentile(final_equities, pct)
    print(f"  {pct:>2}° percentile:  {val:>10,.0f} EUR  ({val - CAPITALE_INIZIALE:>+8,.0f} EUR PnL)")

print(f"\nDistribuzione max drawdown (% capitale iniziale):")
for pct in [50, 75, 90, 95, 99]:
    val = np.percentile(max_dds_pct, pct)
    print(f"  Il {pct}% delle simulazioni ha DD massimo < {val:.1f}%")

print(f"\n  DD massimo assoluto:     {max(max_dds_pct):.1f}%")
print(f"  DD medio:                {np.mean(max_dds_pct):.1f}%")
print(f"  Mediana DD:              {np.median(max_dds_pct):.1f}%")

print(f"\nRischio di rovina:")
print(f"  Soglia rovina:           < {CAPITALE_INIZIALE * RUIN_THRESHOLD:,.0f} EUR ({RUIN_THRESHOLD*100:.0f}%)")
print(f"  Probabilita di rovina:   {ruin_prob:.2f}%")
if ruin_prob < 0.1:
    print(f"  Giudizio:                TRASCURABILE (<< 1%)")
elif ruin_prob < 1:
    print(f"  Giudizio:                BASSO (< 1%)")
elif ruin_prob < 5:
    print(f"  Giudizio:                MODERATO (1-5%)")
else:
    print(f"  Giudizio:                ALTO (> 5%) - RIVEDERE SISTEMA")

# --- 4. Static Risk Control (Controllo Statico) ---
print("\n" + "=" * 100)
print("CONTROLLO STATICO DEL RISCHIO — Position Sizing")
print("=" * 100)
print(f"\nRegola Trombetta Ch 8: rischiare max 1% del capitale per trade.")
print(f"  Capitale:                {CAPITALE_INIZIALE:,} EUR")
print(f"  Rischio per trade (1%):  {CAPITALE_INIZIALE * RISCHIO_STATICO:,.0f} EUR")

# Average risk per trade in points from our strategy
risk_pts = []
for t in trades:
    entry = t["entry"]
    sl = t["sl"]
    risk_pts.append(abs(entry - sl))
avg_risk_pts = np.mean(risk_pts)
max_risk_pts = max(risk_pts)
min_risk_pts = min(risk_pts)

print(f"\nDati SL della strategia:")
print(f"  Risk medio:              {avg_risk_pts:.2f} punti BTP")
print(f"  Risk min:                {min_risk_pts:.2f} punti")
print(f"  Risk max:                {max_risk_pts:.2f} punti")
print(f"  1 punto BTP =            1,000 EUR")

risk_per_contract_avg = avg_risk_pts * 1000
risk_per_contract_max = max_risk_pts * 1000
recommended_contracts_avg = int(CAPITALE_INIZIALE * RISCHIO_STATICO / risk_per_contract_avg)
recommended_contracts_max = int(CAPITALE_INIZIALE * RISCHIO_STATICO / risk_per_contract_max)
recommended_contracts_min = max(1, int(CAPITALE_INIZIALE * RISCHIO_STATICO / (min_risk_pts * 1000)))
recommended_contracts = 1  # default

print(f"\n  Rischio per 1 contratto (avg SL): {risk_per_contract_avg:,.0f} EUR")
print(f"  Rischio per 1 contratto (max SL): {risk_per_contract_max:,.0f} EUR")

print(f"\nRaccomandazione sizing ({RISCHIO_STATICO*100:.0f}% rischio per trade):")
if recommended_contracts_avg < 1 or recommended_contracts_max < 1:
    risk_pct_1contract = round(risk_per_contract_avg / CAPITALE_INIZIALE * 100, 2)
    min_capital_1contract = int(risk_per_contract_avg / RISCHIO_STATICO)
    print(f"  Con {CAPITALE_INIZIALE:,} EUR capitale: 1 contratto = {risk_pct_1contract}% rischio (limite 1%)")
    print(f"  Capitale minimo per 1 contratto al 1%: {min_capital_1contract:,} EUR")
    print(f"  Raccomandato: 1 contratto con rischio {risk_pct_1contract}% (accettabile)")
    recommended_contracts = 1
else:
    print(f"  Su risk medio ({avg_risk_pts:.1f} pt):  {recommended_contracts_avg} contratto/i -> {risk_per_contract_avg*recommended_contracts_avg:,.0f} EUR rischio")
    print(f"  Su risk max ({max_risk_pts:.1f} pt):   {recommended_contracts_max} contratto/i -> {risk_per_contract_max*recommended_contracts_max:,.0f} EUR rischio")
    print(f"  Raccomandato: {min(recommended_contracts_avg, recommended_contracts_max)} contratto/i per sicurezza")
    recommended_contracts = min(recommended_contracts_avg, recommended_contracts_max)

# Risk per trade in EUR for 1 contract
print(f"\nDettaglio per 1 contratto:")
for pct in [0.5, 1.0, 1.5, 2.0]:
    risco = pct / 100 * CAPITALE_INIZIALE
    pts = risco / 1000
    print(f"  {pct:.1f}% capitale ({risco:,.0f} EUR) = {pts:.2f} punti BTP")

# --- 5. Dynamic Risk Control (Performance Control) ---
print("\n" + "=" * 100)
print("CONTROLLO DINAMICO DEL RISCHIO — Performance Control")
print("Framework: Trombetta Ch 8 — Sistema anti-prociclico")
print("=" * 100)

print(f"\nRegole calibrate (basate su {n_trades} trade storici):")
print(f"  Base:                 1 contratto per default")
print(f"  Dopo 3 perdite consecutive:  -0.25 (min 0.5 contratto)")
print(f"  Dopo 7 vincite consecutive:  +0.15 (max 1.25 contratti)")
print(f"  Dopo DD > 10%:               cap a 1.0, riduci")
print(f"  Dopo DD > 20%:               stop trading fino a review")

# Win/loss streaks analysis
print(f"\nAnalisi streak dal backtest ({n_trades} trade):")
loss_streaks = []
win_streaks = []
current = 0
current_type = None

for pnl in pnls:
    typ = "W" if pnl > 0 else "L"
    if typ == current_type:
        current += 1
    else:
        if current_type == "W": win_streaks.append(current)
        elif current_type == "L": loss_streaks.append(current)
        current = 1
        current_type = typ
if current_type == "W": win_streaks.append(current)
elif current_type == "L": loss_streaks.append(current)

print(f"  Max vincite consecutive:  {max(win_streaks) if win_streaks else 0}")
print(f"  Max perdite consecutive:  {max(loss_streaks) if loss_streaks else 0}")
print(f"  Perdite >3 consecutive:   {sum(1 for s in loss_streaks if s >= 3)} volte")
print(f"  Perdite >5 consecutive:   {sum(1 for s in loss_streaks if s >= 5)} volte")

# --- 6. Monte Carlo with Dynamic Control ---
print("\n" + "=" * 100)
print("MONTE CARLO CON PERFORMANCE CONTROL (simulazione)")

N_SIM_DYNAMIC = 5000
np.random.seed(42)
final_eq_dynamic = []
max_dd_dynamic = []

for sim in range(N_SIM_DYNAMIC):
    equity = CAPITALE_INIZIALE
    peak = CAPITALE_INIZIALE
    max_dd = 0
    sizing = 1.0
    consec_losses = 0
    consec_wins = 0

    sim_pnls = np.random.choice(pnls, size=n_trades, replace=True)

    for pnl in sim_pnls:
        if pnl > 0:
            consec_losses = 0
            consec_wins += 1
            if consec_wins >= 7:
                sizing = min(1.25, sizing + 0.15)
        else:
            consec_wins = 0
            consec_losses += 1
            if consec_losses >= 3:
                sizing = max(0.5, sizing - 0.25)

        # DD protection
        dd_current_pct = (peak - equity) / peak if peak > 0 else 0
        if dd_current_pct > 0.20:
            sizing = 0
        elif dd_current_pct > 0.10:
            sizing = min(sizing, 1.0)
            sizing = max(0.5, sizing - 0.25)

        equity += pnl * sizing
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd

    final_eq_dynamic.append(equity)
    max_dd_dynamic.append(max_dd / CAPITALE_INIZIALE * 100)

final_eq_dynamic = np.array(final_eq_dynamic)
max_dd_dynamic = np.array(max_dd_dynamic)

print(f"\nConfronto: Senza vs Con Performance Control:")
print(f"{'Metrica':<35} {'Senza Control':<18} {'Con Control':<18}")
print("-" * 71)
print(f"{'Mediana equity finale':<35} {np.median(final_equities):<18,.0f} {np.median(final_eq_dynamic):<18,.0f} EUR")
print(f"{'P5 equity finale':<35} {np.percentile(final_equities, 5):<18,.0f} {np.percentile(final_eq_dynamic, 5):<18,.0f} EUR")
print(f"{'P95 equity finale':<35} {np.percentile(final_equities, 95):<18,.0f} {np.percentile(final_eq_dynamic, 95):<18,.0f} EUR")
print(f"{'Mediana DD %':<35} {np.median(max_dds_pct):<18.1f} {np.median(max_dd_dynamic):<18.1f} %")
print(f"{'P95 DD %':<35} {np.percentile(max_dds_pct, 95):<18.1f} {np.percentile(max_dd_dynamic, 95):<18.1f} %")
print(f"{'Rischio rovina %':<35} {ruin_prob:<18.2f} {sum(1 for e in final_eq_dynamic if e < CAPITALE_INIZIALE*RUIN_THRESHOLD)/N_SIM_DYNAMIC*100:<18.2f} %")

# --- 7. Save report ---
report = {
    "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "capitale_iniziale": CAPITALE_INIZIALE,
    "trade_data": {"n_trades": n_trades, "total_pnl_eur": total_pnl,
                   "avg_win_eur": round(avg_win, 2), "avg_loss_eur": round(avg_loss, 2),
                   "win_rate": round(win_rate*100, 1),
                   "max_win_eur": round(max(pnls), 2), "max_loss_eur": round(min(pnls), 2)},
    "monte_carlo": {
        "n_simulations": N_SIMULATIONS,
        "final_equity_percentiles": {str(p): round(np.percentile(final_equities, p), 2) for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]},
        "max_dd_percentiles": {str(p): round(np.percentile(max_dds_pct, p), 2) for p in [50, 75, 90, 95, 99]},
        "max_dd_assoluto": round(max(max_dds_pct), 2),
        "dd_medio": round(np.mean(max_dds_pct), 2),
        "ruin_probability_pct": round(ruin_prob, 2),
        "ruin_threshold": RUIN_THRESHOLD
    },
    "static_risk": {
        "risk_per_trade_pct": RISCHIO_STATICO,
        "risk_per_trade_eur": round(CAPITALE_INIZIALE * RISCHIO_STATICO, 2),
        "avg_risk_per_contract_eur": round(risk_per_contract_avg, 2),
        "recommended_contracts": recommended_contracts,
        "risk_per_contract_pts_avg": round(avg_risk_pts, 2),
        "risk_per_contract_pts_max": round(max_risk_pts, 2)
    },
    "dynamic_control": {
        "max_win_streak": max(win_streaks) if win_streaks else 0,
        "max_loss_streak": max(loss_streaks) if loss_streaks else 0,
        "times_loss_streak_ge_3": sum(1 for s in loss_streaks if s >= 3),
        "times_loss_streak_ge_5": sum(1 for s in loss_streaks if s >= 5),
        "mc_dynamic_median_equity": round(np.median(final_eq_dynamic), 2),
        "mc_dynamic_p95_dd": round(np.percentile(max_dd_dynamic, 95), 2),
        "mc_dynamic_ruin_pct": round(sum(1 for e in final_eq_dynamic if e < CAPITALE_INIZIALE*RUIN_THRESHOLD) / N_SIM_DYNAMIC * 100, 2)
    }
}

with open(os.path.join(OUTPUT_DIR, "mc_risk_report.json"), "w") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

# --- 8. Chart: Equity fan chart ---
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.patch.set_facecolor('#0d1117')

    # Subplot 1: Fan chart of first 500 paths
    ax = axes[0, 0]
    ax.set_facecolor('#161b22')
    for sim_idx in range(0, 500, 5):
        path = all_paths[sim_idx]
        ax.plot(range(n_trades), path, color='#58a6ff', alpha=0.03, linewidth=0.5)
    # Median path
    median_path = np.median(all_paths[:500], axis=0)
    ax.plot(range(n_trades), median_path, color='#f0883e', linewidth=2, label='Mediana')
    ax.axhline(y=CAPITALE_INIZIALE, color='#30363d', linewidth=0.8, linestyle='--')
    ax.axhline(y=CAPITALE_INIZIALE * RUIN_THRESHOLD, color='#f85149', linewidth=0.8, linestyle=':',
               label=f'Soglia rovina ({RUIN_THRESHOLD*100:.0f}%)')
    ax.set_title('Monte Carlo: traiettorie equity (500 campioni)', color='white', fontsize=11)
    ax.set_xlabel('Trade #', color='#8b949e')
    ax.set_ylabel('Equity (EUR)', color='#8b949e')
    ax.tick_params(colors='#8b949e')
    ax.spines['bottom'].set_color('#30363d')
    ax.spines['left'].set_color('#30363d')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(facecolor='#161b22', edgecolor='#30363d', labelcolor='white')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    # Subplot 2: Distribution of final equity
    ax = axes[0, 1]
    ax.set_facecolor('#161b22')
    ax.hist(final_equities, bins=80, color='#58a6ff', alpha=0.6, edgecolor='none')
    ax.axvline(x=CAPITALE_INIZIALE, color='#30363d', linewidth=0.8, linestyle='--', label=f'Capitale iniziale')
    ax.axvline(x=CAPITALE_INIZIALE * RUIN_THRESHOLD, color='#f85149', linewidth=1.2, linestyle=':',
               label=f'Soglia rovina')
    ax.axvline(x=np.percentile(final_equities, 5), color='#d29922', linewidth=1.2, linestyle='-',
               label=f'P5: {np.percentile(final_equities, 5):,.0f}')
    ax.axvline(x=np.median(final_equities), color='#f0883e', linewidth=1.5, linestyle='-',
               label=f'P50: {np.median(final_equities):,.0f}')
    ax.axvline(x=np.percentile(final_equities, 95), color='#3fb950', linewidth=1.2, linestyle='-',
               label=f'P95: {np.percentile(final_equities, 95):,.0f}')
    ax.set_title('Distribuzione equity finale (10.000 sim)', color='white', fontsize=11)
    ax.tick_params(colors='#8b949e')
    ax.spines['bottom'].set_color('#30363d')
    ax.spines['left'].set_color('#30363d')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(facecolor='#161b22', edgecolor='#30363d', labelcolor='white', fontsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    # Subplot 3: Distribution of max drawdown
    ax = axes[1, 0]
    ax.set_facecolor('#161b22')
    ax.hist(max_dds_pct, bins=60, color='#f85149', alpha=0.6, edgecolor='none')
    ax.axvline(x=np.median(max_dds_pct), color='#f0883e', linewidth=1.5,
               label=f'Mediana: {np.median(max_dds_pct):.1f}%')
    ax.axvline(x=np.percentile(max_dds_pct, 95), color='#d29922', linewidth=1.2,
               label=f'P95: {np.percentile(max_dds_pct, 95):.1f}%')
    ax.set_title('Distribuzione max drawdown %', color='white', fontsize=11)
    ax.set_xlabel('Drawdown %', color='#8b949e')
    ax.tick_params(colors='#8b949e')
    ax.spines['bottom'].set_color('#30363d')
    ax.spines['left'].set_color('#30363d')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(facecolor='#161b22', edgecolor='#30363d', labelcolor='white')

    # Subplot 4: Static vs Dynamic control comparison
    ax = axes[1, 1]
    ax.set_facecolor('#161b22')
    ax.hist(final_equities, bins=60, color='#58a6ff', alpha=0.4, edgecolor='none', label='Senza control')
    ax.hist(final_eq_dynamic, bins=60, color='#3fb950', alpha=0.4, edgecolor='none', label='Con Performance Control')
    ax.axvline(x=CAPITALE_INIZIALE, color='#30363d', linewidth=0.8, linestyle='--')
    ax.set_title('Confronto: Con vs Senza Performance Control', color='white', fontsize=11)
    ax.tick_params(colors='#8b949e')
    ax.spines['bottom'].set_color('#30363d')
    ax.spines['left'].set_color('#30363d')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(facecolor='#161b22', edgecolor='#30363d', labelcolor='white')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'))

    plt.tight_layout()
    chart_path = os.path.join(OUTPUT_DIR, 'mc_equity_fan.png')
    plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='#0d1117')
    print(f"\nGrafico salvato: {chart_path}")

except ImportError:
    print("\n[WARN] matplotlib non installato - salto grafico")

print("\n" + "=" * 100)
print("Report salvato: output/mc_risk_report.json")
print("=" * 100)
