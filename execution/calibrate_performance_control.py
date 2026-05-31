"""
Calibrazione Performance Control — Trombetta Ch 8
Grid search su parametri controllo dinamico per minimizzare DD
mantenendo beneficio sull'equity.
"""
import json, numpy as np, os, itertools, sys, io
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

OUTPUT_DIR = "output"
SUMMARY_PATH = os.path.join(OUTPUT_DIR, "btp_1h_equity_summary.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(SUMMARY_PATH, "r") as f:
    data = json.load(f)

pnls = np.array([t["pnl_eur"] for t in data["trades"]])
n_trades = len(pnls)

np.random.seed(42)
N_SIM = 5000
CAPITALE = 50000
RUIN = 0.5

def run_mc(pnls, n_trades, cfg):
    eqs, dds = [], []
    for _ in range(N_SIM):
        equity = CAPITALE
        peak = CAPITALE
        max_dd = 0
        sizing = 1.0
        cl, cw = 0, 0
        for pnl in np.random.choice(pnls, size=n_trades, replace=True):
            if pnl > 0:
                cl = 0; cw += 1
                if cw >= cfg["wt"]:
                    sizing = min(cfg["mx"], sizing + cfg["wi"])
            else:
                cw = 0; cl += 1
                if cl >= cfg["lt"]:
                    sizing = max(cfg["mn"], sizing - cfg["ld"])
            dd_cp = (peak - equity) / peak if peak > 0 else 0
            if dd_cp > cfg["dr"]:
                sizing = 0
            elif dd_cp > cfg["dc"]:
                sizing = min(sizing, 1.0)
                sizing = max(cfg["mn"], sizing - 0.25)
            equity += pnl * sizing
            if equity > peak: peak = equity
            dd = peak - equity
            if dd > max_dd: max_dd = dd
        eqs.append(equity)
        dds.append(max_dd / CAPITALE * 100)
    return np.array(eqs), np.array(dds)

# Baseline (no control)
baseline_eqs, baseline_dds = run_mc(pnls, n_trades, {"wt": 999, "lt": 999, "wi": 0, "ld": 0, "mx": 1, "mn": 1, "dc": 99, "dr": 99})
bl_med = np.median(baseline_eqs)
bl_p95dd = np.percentile(baseline_dds, 95)
bl_meddd = np.median(baseline_dds)

# Grid: reduce to essentials
params = {
    "wt": [7, 10],       # win streak threshold (higher = less aggressive)
    "lt": [2, 3],        # loss streak threshold
    "wi": [0.10, 0.15],  # win increment
    "ld": [0.25, 0.50],  # loss decrement
    "mx": [1.25],        # max sizing (fixed)
    "mn": [0.50],        # min sizing (fixed)
    "dc": [0.10],        # DD cap threshold (fixed)
    "dr": [0.20]         # DD stop threshold (fixed)
}

keys = list(params.keys())
results = []

for vals in itertools.product(*params.values()):
    cfg = dict(zip(keys, vals))
    eqs, dds = run_mc(pnls, n_trades, cfg)
    med_eq = np.median(eqs)
    p5_eq = np.percentile(eqs, 5)
    p95_dd = np.percentile(dds, 95)
    med_dd = np.median(dds)
    ruin = np.mean(eqs < CAPITALE * RUIN) * 100
    eq_delta = (med_eq - bl_med) / bl_med * 100
    dd_delta = p95_dd - bl_p95dd
    penalty = max(0, dd_delta) * 2.0
    score = eq_delta - penalty - (50 if ruin > 0 else 0)
    results.append({**cfg, "med_eq": med_eq, "p5_eq": p5_eq, "med_dd": med_dd, "p95_dd": p95_dd, "ruin": ruin, "eq_delta": eq_delta, "dd_delta": dd_delta, "score": score})

results.sort(key=lambda r: r["score"], reverse=True)
top5 = results[:5]

print("=" * 110)
print(f"Baseline: MedEq={bl_med:>8,.0f}  MedDD={bl_meddd:.1f}%  P95DD={bl_p95dd:.1f}%")
print("=" * 110)
hdr = f"{'Win>=':<5} {'Loss>=':<6} {'Wi':<5} {'Ld':<5} {'MedEq':<10} {'P5Eq':<10} {'MedDD':<6} {'P95DD':<6} {'Ruin':<6} {'EqChg':<7} {'DDChg':<6} {'Score':<7}"
print(hdr)
print("-" * 110)
for r in top5:
    print(f"{r['wt']:<5} {r['lt']:<6} {r['wi']:<5} {r['ld']:<5} {r['med_eq']:<10,.0f} {r['p5_eq']:<10,.0f} {r['med_dd']:<6.1f} {r['p95_dd']:<6.1f} {r['ruin']:<6.2f} {r['eq_delta']:<7.1f} {r['dd_delta']:<6.1f} {r['score']:<7.1f}")

# Current config
curr_cfg = {"wt": 5, "lt": 3, "wi": 0.25, "ld": 0.50, "mx": 1.5, "mn": 0.5, "dc": 0.10, "dr": 0.20}
curr_eqs, curr_dds = run_mc(pnls, n_trades, curr_cfg)
curr_med = np.median(curr_eqs)
curr_p5 = np.percentile(curr_eqs, 5)
curr_meddd = np.median(curr_dds)
curr_p95dd = np.percentile(curr_dds, 95)
curr_ruin = np.mean(curr_eqs < CAPITALE * RUIN) * 100

# Best config
best = top5[0]
best_eqs, best_dds = run_mc(pnls, n_trades, best)
best_p5 = np.percentile(best_eqs, 5)
best_p95dd = np.percentile(best_dds, 95)
best_ruin = np.mean(best_eqs < CAPITALE * RUIN) * 100

print("\n" + "=" * 110)
print("CONFRONTO: Baseline -> Current -> Best")
print("=" * 110)
print(f"{'Metrica':<30} {'Baseline':<15} {'Current':<15} {'Best':<15}")
print("-" * 75)
print(f"{'Mediana equity':<30} {bl_med:<15,.0f} {curr_med:<15,.0f} {best['med_eq']:<15,.0f} EUR")
print(f"{'P5 equity':<30} {np.percentile(baseline_eqs,5):<15,.0f} {curr_p5:<15,.0f} {best_p5:<15,.0f} EUR")
print(f"{'Mediana DD':<30} {bl_meddd:<15.1f} {curr_meddd:<15.1f} {np.median(best_dds):<15.1f} %")
print(f"{'P95 DD':<30} {bl_p95dd:<15.1f} {curr_p95dd:<15.1f} {best_p95dd:<15.1f} %")
print(f"{'Rischio rovina':<30} {0:<15.2f} {curr_ruin:<15.2f} {best_ruin:<15.2f} %")

print(f"\nBest config: win>={best['wt']} loss>={best['lt']} inc={best['wi']} dec={best['ld']}")
print(f"Current:     win>=5  loss>=3  inc=0.25  dec=0.50")

# Save
output = {
    "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
    "baseline": {"median_equity": round(bl_med,0), "median_dd": bl_meddd, "p95_dd": bl_p95dd},
    "current": {"config": curr_cfg, "median_equity": round(curr_med,0), "p5_equity": round(curr_p5,0), "median_dd": curr_meddd, "p95_dd": curr_p95dd, "ruin": curr_ruin},
    "best": {"config": {k: best[k] for k in keys}, "median_equity": round(best['med_eq'],0), "p5_equity": round(best_p5,0), "median_dd": round(np.median(best_dds),1), "p95_dd": best_p95dd, "ruin": best_ruin},
    "top5": results[:5]
}

with open(os.path.join(OUTPUT_DIR, "pc_calibration.json"), "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"\nSalvato: output/pc_calibration.json")
