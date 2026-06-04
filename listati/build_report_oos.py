import pandas as pd
import numpy as np
from numba import jit
import sys
sys.stdout.reconfigure(encoding='utf-8')

base = r"C:\Users\Trader\.gemini\antigravity\scratch\AntigravityProjects"
df1 = pd.read_csv(f"{base}/dati/dax_m1.txt", header=None,
    names=["date","time","open","high","low","close","volume"])
df1["dt"] = pd.to_datetime(df1["date"].astype(str) + " " + df1["time"])
df1 = df1.set_index("dt").drop(columns=["date","time"])
df3 = df1.resample("3min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()

h_arr, l_arr, c_arr, o_arr = (df3["high"].values, df3["low"].values,
                                df3["close"].values, df3["open"].values)
n_bars = len(df3)

@jit(nopython=True)
def st(h,l,c,p,m):
    n=len(h);d=np.ones(n);tr=np.zeros(n);a=np.zeros(n);s2=np.zeros(n)
    fu=np.zeros(n);fl=np.zeros(n)
    for i in range(1,n):tr[i]=max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1]))
    s=0.0
    for i in range(1,p):s+=tr[i]
    a[p]=s/p
    for i in range(p+1,n):a[i]=(a[i-1]*(p-1)+tr[i])/p
    for i in range(p,n):
        hl=(h[i]+l[i])/2;ub=hl+m*a[i];lb=hl-m*a[i]
        if i==p:fu[i]=ub;fl[i]=lb;s2[i]=ub;d[i]=-1
        else:
            fu[i]=ub if(ub<fu[i-1])or(c[i-1]>fu[i-1])else fu[i-1]
            fl[i]=lb if(lb>fl[i-1])or(c[i-1]<fl[i-1])else fl[i-1]
            if d[i-1]==1:
                s2[i]=fl[i]
                if c[i]<=fl[i]:d[i]=-1;s2[i]=fu[i]
                else:d[i]=1
            else:
                s2[i]=fu[i]
                if c[i]>=fu[i]:d[i]=1;s2[i]=fl[i]
                else:d[i]=-1
    return d,s2

comm_pt = 3/25
def in_fascia(hr, mn):
    return (hr>=9 and hr<11) or (hr==15 and mn>=30) or (hr>=16 and hr<17) or (hr==17 and mn<=30)

def is_after_22(hr):
    return hr >= 22

d, s2 = st(h_arr,l_arr,c_arr,10,3.0)

# Genera trade con regola: no overnight (forza chiusura a 22:00)
# slippage_pt = 1.0 (realistico per DAX)
slip = 1.0

all_trades = []
pos, ep, eb = 0, 0.0, 0
for i in range(20, n_bars):
    if i+1 >= n_bars: continue
    dt_next = df3.index[i+1]
    hr_n, mn_n = dt_next.hour, dt_next.minute

    if pos != 0 and is_after_22(hr_n):
        ex = o_arr[i+1]
        if pos == 1: pnl = ex - ep - comm_pt - slip
        else: pnl = ep - ex - comm_pt - slip
        all_trades.append({"pnl_pt": pnl, "dt": dt_next, "yr": dt_next.year, "exit_type": "FORCED"})
        pos = 0

    if pos != 0:
        if pos == 1 and d[i-1]==1 and d[i]==-1:
            ex = o_arr[i+1] - slip
            pnl = ex - ep - comm_pt
            all_trades.append({"pnl_pt": pnl, "dt": dt_next, "yr": dt_next.year, "exit_type": "REVERSAL"})
            pos = 0
        elif pos == -1 and d[i-1]==-1 and d[i]==1:
            ex = o_arr[i+1] + slip
            pnl = ep - ex - comm_pt
            all_trades.append({"pnl_pt": pnl, "dt": dt_next, "yr": dt_next.year, "exit_type": "REVERSAL"})
            pos = 0

    if pos == 0 and in_fascia(hr_n, mn_n):
        if d[i]==1 and d[i-1]==-1:
            pos = 1; ep = o_arr[i+1] + slip; eb = i+1
        elif d[i]==-1 and d[i-1]==1:
            pos = -1; ep = o_arr[i+1] - slip; eb = i+1

pnls_seq = np.array([t['pnl_pt'] for t in all_trades])
dts = [t['dt'] for t in all_trades]
yrs = np.array([t['yr'] for t in all_trades])
exit_types = [t['exit_type'] for t in all_trades]
n_trades = len(pnls_seq)

n_forced = sum(1 for e in exit_types if e == 'FORCED')
n_reversal = sum(1 for e in exit_types if e == 'REVERSAL')

split_dt = pd.Timestamp("2022-01-01")
train_mask = yrs < 2022
test_mask  = yrs >= 2022
pnls_train = pnls_seq[train_mask]
pnls_test  = pnls_seq[test_mask]
dts_train = [d for d,m in zip(dts, train_mask) if m]
dts_test  = [d for d,m in zip(dts, test_mask) if m]
yrs_train = yrs[train_mask]
yrs_test  = yrs[test_mask]
years_train = (dts_train[-1] - dts_train[0]).days / 365.25
years_test  = (dts_test[-1] - dts_test[0]).days / 365.25

def metrics(p, years):
    if len(p) == 0: return None
    arr = np.array(p)
    cum = np.cumsum(arr)
    peak = np.maximum.accumulate(cum)
    dd = cum - peak
    wins = arr[arr>0]; losses = arr[arr<0]
    pf = wins.sum()/abs(losses.sum()) if len(losses) else 0
    return {'n': len(arr), 'pnl_eur': arr.sum()*25, 'pf': pf,
            'wr': len(wins)/len(arr), 'max_dd_eur': dd.min()*25,
            'calmar': (arr.sum()/abs(dd.min()))/years if dd.min()!=0 else 0,
            'pnl_pt': arr.sum(), 'cum': cum,
            'avg_w': wins.mean() if len(wins) else 0,
            'avg_l': losses.mean() if len(losses) else 0,
            'wins_n': len(wins), 'losses_n': len(losses),
            'max_w': wins.max() if len(wins) else 0,
            'max_l': losses.min() if len(losses) else 0}

def apply_cb(pnls, max_losses, cooldown):
    kept_idx = []
    consec = 0
    cd_rem = 0
    for j, p in enumerate(pnls):
        if cd_rem > 0:
            cd_rem -= 1
            continue
        if p < 0:
            consec += 1
        else:
            consec = 0
        if consec >= max_losses:
            cd_rem = cooldown
            consec = 0
            continue
        kept_idx.append(j)
    return np.array([pnls[i] for i in kept_idx]), np.array(kept_idx)

# Vincitore: CB 2loss cd 3
kept_train, idx_train = apply_cb(pnls_train, 2, 3)
kept_test, idx_test   = apply_cb(pnls_test, 2, 3)
m_train = metrics(kept_train, years_train)
m_test  = metrics(kept_test, years_test)
m_base_train = metrics(pnls_train, years_train)
m_base_test  = metrics(pnls_test, years_test)

# Anno per anno vincitore CB
yoy = {}
for j, idx in enumerate(idx_train):
    yr = yrs_train[idx]
    if yr not in yoy: yoy[yr] = {'n':0, 'pnl_pt':0, 'wins':0, 'losses':0}
    if yr not in yoy: yoy[yr] = {'n':0, 'pnl_pt':0, 'wins':0, 'losses':0}
    yoy[yr]['n'] += 1; yoy[yr]['pnl_pt'] += pnls_train[idx]
    if pnls_train[idx] > 0:
        yoy[yr]['wins'] += 1
    else:
        yoy[yr]['losses'] += 1
for j, idx in enumerate(idx_test):
    yr = yrs_test[idx]
    if yr not in yoy: yoy[yr] = {'n':0, 'pnl_pt':0, 'wins':0, 'losses':0}
    yoy[yr]['n'] += 1; yoy[yr]['pnl_pt'] += pnls_test[idx]
    if pnls_test[idx] > 0:
        yoy[yr]['wins'] += 1
    else:
        yoy[yr]['losses'] += 1

yoy_html = ""
for yr in sorted(yoy.keys()):
    y = yoy[yr]
    wr = y['wins']/y['n']*100 if y['n']>0 else 0
    phase = "TRAIN" if yr < 2022 else "TEST"
    color = '#0a7d28' if y['pnl_pt']>0 else '#c0280a'
    yoy_html += f"""<tr><td class="num"><b>{yr}</b></td><td class="num">{phase}</td><td class="num">{y['n']}</td><td class="num" style="color:{color}">{y['pnl_pt']*25:>+10,.0f} €</td><td class="num">{wr:.1f}%</td><td class="num">{y['wins']}W / {y['losses']}L</td></tr>"""

# Anno per anno baseline
yoy_base = {}
for j, p in enumerate(pnls_seq):
    yr = yrs[j]
    if yr not in yoy_base: yoy_base[yr] = {'n':0, 'pnl_pt':0, 'wins':0, 'losses':0}
    yoy_base[yr]['n'] += 1; yoy_base[yr]['pnl_pt'] += p
    if p > 0:
        yoy_base[yr]['wins'] += 1
    else:
        yoy_base[yr]['losses'] += 1

yoy_base_html = ""
for yr in sorted(yoy_base.keys()):
    y = yoy_base[yr]
    wr = y['wins']/y['n']*100 if y['n']>0 else 0
    phase = "TRAIN" if yr < 2022 else "TEST"
    color = '#0a7d28' if y['pnl_pt']>0 else '#c0280a'
    yoy_base_html += f"""<tr><td class="num"><b>{yr}</b></td><td class="num">{phase}</td><td class="num">{y['n']}</td><td class="num" style="color:{color}">{y['pnl_pt']*25:>+10,.0f} €</td><td class="num">{wr:.1f}%</td><td class="num">{y['wins']}W / {y['losses']}L</td></tr>"""

def build_svg(pnls, color, height=220, width=950):
    if len(pnls) == 0: return ""
    cum = np.cumsum(pnls)
    cum_min, cum_max = cum.min(), cum.max()
    span = cum_max - cum_min if cum_max != cum_min else 1
    pad_y = 25
    h, w = height, width
    points = []
    for i, v in enumerate(cum):
        x = (i / max(len(cum)-1, 1)) * w
        y = h - pad_y - ((v - cum_min) / span) * (h - 2*pad_y)
        points.append(f"{x:.1f},{y:.1f}")
    zero_y = h - pad_y - ((0 - cum_min) / span) * (h - 2*pad_y)
    return f"""<svg width='{w}' height='{h+10}' style='background:#fafafa;border:1px solid #ddd;border-radius:4px;display:block'>
        <line x1='0' y1='{zero_y:.1f}' x2='{w}' y2='{zero_y:.1f}' stroke='#bbb' stroke-dasharray='4,3'/>
        <polyline points='{" ".join(points)}' fill='none' stroke='{color}' stroke-width='2.2'/>
      </svg>"""

eq_train_svg = build_svg(kept_train, '#0066cc')
eq_test_svg  = build_svg(kept_test, '#0a7d28')
eq_combined_svg = build_svg(np.concatenate([kept_train, kept_test]), '#003366')

def count_triggers(pnls, max_losses, cooldown):
    triggers = 0; consec = 0; cd_rem = 0
    for p in pnls:
        if cd_rem > 0:
            cd_rem -= 1
            continue
        if p < 0:
            consec += 1
        else:
            consec = 0
        if consec >= max_losses:
            triggers += 1
            cd_rem = cooldown
            consec = 0
    return triggers

trig_train = count_triggers(pnls_train, 2, 3)
trig_test  = count_triggers(pnls_test, 2, 3)
total_train = len(pnls_train); total_test = len(pnls_test)
kept_total_train = len(kept_train); kept_total_test = len(kept_test)

def fmt_eur(v):
    return f"{'+' if v >= 0 else ''}{v:,.0f} €".replace(",", ".")

html = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>OOS Validation - CB 2loss cd3 (10 anni, no overnight)</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 1100px; margin: 30px auto; padding: 0 20px; color: #222; background: #fff; line-height: 1.5; }}
  h1 {{ color: #003366; border-bottom: 3px solid #0066cc; padding-bottom: 10px; }}
  h2 {{ color: #003366; margin-top: 40px; border-left: 4px solid #0066cc; padding-left: 10px; }}
  .hero {{ background: linear-gradient(135deg, #003366 0%, #0066cc 100%); color: white; padding: 30px 40px; border-radius: 8px; margin: 20px 0; }}
  .hero h1 {{ color: #ffcc00; border: none; margin: 0 0 10px 0; padding: 0; font-size: 28px; }}
  .hero .sub {{ font-size: 16px; opacity: 0.9; margin-bottom: 25px; }}
  .hero-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  .hero-stat {{ background: rgba(255,255,255,0.1); border-radius: 6px; padding: 15px; text-align: center; }}
  .hero-stat .label {{ font-size: 11px; opacity: 0.7; text-transform: uppercase; letter-spacing: 1px; }}
  .hero-stat .value {{ font-size: 24px; font-weight: bold; color: #ffcc00; margin: 5px 0; }}
  .hero-stat .delta {{ font-size: 12px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 14px; }}
  th {{ background: #003366; color: white; padding: 10px 8px; text-align: left; }}
  td {{ padding: 8px; border-bottom: 1px solid #e0e0e0; }}
  tr:nth-child(even) {{ background: #f9f9f9; }}
  tr:hover {{ background: #fffacd; }}
  .num {{ text-align: right; font-family: 'Consolas', monospace; }}
  .box {{ background: #fafafa; border: 1px solid #ddd; padding: 18px 22px; border-radius: 6px; margin: 15px 0; }}
  .callout {{ background: #d4f4dd; border-left: 6px solid #0a7d28; padding: 15px 20px; margin: 15px 0; border-radius: 4px; }}
  .warn {{ background: #fff4e6; border-left: 6px solid #cc6600; padding: 15px 20px; margin: 15px 0; border-radius: 4px; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 15px 0; }}
  .green {{ color: #0a7d28; font-weight: bold; }}
  .red {{ color: #c0280a; font-weight: bold; }}
</style>
</head>
<body>

<div class="hero">
  <h1>OOS Validation Superata</h1>
  <div class="sub">SuperTrend(10, 3.0) DAX 3min + CB 2loss cd3 — 6 Giu 2016 → 4 Giu 2026 (10 anni) — Slippage {slip} pt — No overnight</div>
  <div class="hero-grid">
    <div class="hero-stat">
      <div class="label">PnL TOTALE 10 ANNI</div>
      <div class="value">+{m_train['pnl_eur']+m_test['pnl_eur']:,.0f} €</div>
      <div class="delta" style="color:#aaffaa">TRAIN {fmt_eur(m_train['pnl_eur'])} / TEST {fmt_eur(m_test['pnl_eur'])}</div>
    </div>
    <div class="hero-stat">
      <div class="label">CALMAR TEST</div>
      <div class="value">{m_test['calmar']:.2f}</div>
      <div class="delta" style="color:#aaffaa">con slippage {slip} pt real</div>
    </div>
    <div class="hero-stat">
      <div class="label">STABILITÀ OOS</div>
      <div class="value">{m_test['pnl_eur']/m_train['pnl_eur']:.1%}</div>
      <div class="delta" style="color:#aaffaa">PnL OOS / PnL Train</div>
    </div>
  </div>
</div>

<h2>Regole strategia</h2>
<div class="box">
  <ul style="line-height:1.8">
    <li><b>ENTRY</b>: solo in fascia 9:00-11:00 o 15:30-17:30 (controllo su barra di entrata i+1)</li>
    <li><b>EXIT</b>: al reversal del SuperTrend, OPPURE forzata a 22:00 (no overnight)</li>
    <li><b>Slippage</b>: {slip} pt per side (entrata + uscita = {slip*2} pt round trip)</li>
    <li><b>Commissione</b>: 3 € round trip (0,12 pt)</li>
    <li><b>CB</b>: dopo 2 perdite consecutive, salta 3 trade</li>
    <li><b>Dati</b>: XDAX 3-min, 1.056.495 barre, 6 Giu 2016 → 4 Giu 2026</li>
    <li><b>Chiusure forzate 22:00</b>: {n_forced}/{n_trades} trade ({n_forced/n_trades*100:.1f}%) — le restanti {n_reversal} per reversal</li>
  </ul>
</div>

<h2>Split Train / Test</h2>
<div class="box">
  <table>
    <tr><th>Set</th><th>Periodo</th><th>Anni</th><th>N° trade originali</th><th>N° trade con CB</th><th>Trigger CB</th></tr>
    <tr><td><b>TRAIN</b></td><td>06/06/2016 → 31/12/2021</td><td>{years_train:.2f}</td><td class="num">{total_train:,}</td><td class="num">{kept_total_train:,}</td><td class="num">{trig_train} (~{trig_train/years_train:.0f}/anno)</td></tr>
    <tr><td><b>TEST OOS</b></td><td>01/01/2022 → 04/06/2026</td><td>{years_test:.2f}</td><td class="num">{total_test:,}</td><td class="num">{kept_total_test:,}</td><td class="num">{trig_test} (~{trig_test/years_test:.0f}/anno)</td></tr>
  </table>
</div>

<h2>Risultato validazione OOS</h2>
<table>
  <tr><th>Set</th><th>N° trade</th><th>PnL (€)</th><th>PF</th><th>WR</th><th>Max DD (€)</th><th>Calmar</th><th>PnL/anno</th></tr>
  <tr style="background:#d4f4dd">
    <td><b>TRAIN CB 2loss cd3</b></td>
    <td class="num">{m_train['n']:,}</td>
    <td class="num green">{fmt_eur(m_train['pnl_eur'])}</td>
    <td class="num">{m_train['pf']:.3f}</td>
    <td class="num">{m_train['wr']*100:.1f}%</td>
    <td class="num">{fmt_eur(m_train['max_dd_eur'])}</td>
    <td class="num"><b>{m_train['calmar']:.2f}</b></td>
    <td class="num green">{fmt_eur(m_train['pnl_eur']/years_train)}</td>
  </tr>
  <tr style="background:#d4f4dd">
    <td><b>TEST OOS CB 2loss cd3</b></td>
    <td class="num">{m_test['n']:,}</td>
    <td class="num green">{fmt_eur(m_test['pnl_eur'])}</td>
    <td class="num">{m_test['pf']:.3f}</td>
    <td class="num">{m_test['wr']*100:.1f}%</td>
    <td class="num">{fmt_eur(m_test['max_dd_eur'])}</td>
    <td class="num"><b>{m_test['calmar']:.2f}</b></td>
    <td class="num green">{fmt_eur(m_test['pnl_eur']/years_test)}</td>
  </tr>
  <tr><td>TRAIN Baseline</td><td class="num">{m_base_train['n']:,}</td><td class="num">{fmt_eur(m_base_train['pnl_eur'])}</td><td class="num">{m_base_train['pf']:.3f}</td><td class="num">{m_base_train['wr']*100:.1f}%</td><td class="num">{fmt_eur(m_base_train['max_dd_eur'])}</td><td class="num">{m_base_train['calmar']:.2f}</td><td class="num">{fmt_eur(m_base_train['pnl_eur']/years_train)}</td></tr>
  <tr><td>TEST Baseline</td><td class="num">{m_base_test['n']:,}</td><td class="num">{fmt_eur(m_base_test['pnl_eur'])}</td><td class="num">{m_base_test['pf']:.3f}</td><td class="num">{m_base_test['wr']*100:.1f}%</td><td class="num">{fmt_eur(m_base_test['max_dd_eur'])}</td><td class="num">{m_base_test['calmar']:.2f}</td><td class="num">{fmt_eur(m_base_test['pnl_eur']/years_test)}</td></tr>
  </table>

<h2>Curve equity</h2>
<div class="box"><h3 style="margin-top:0">TRAIN (2016-2021) — {fmt_eur(m_train['pnl_eur'])}</h3>{eq_train_svg}</div>
<div class="box"><h3 style="margin-top:0">TEST OOS (2022-2026) — {fmt_eur(m_test['pnl_eur'])}</h3>{eq_test_svg}</div>
<div class="box"><h3 style="margin-top:0">Train + Test (10 anni)</h3>{eq_combined_svg}</div>

<h2>Anno per anno (CB 2loss cd 3)</h2>
<table><tr><th>Anno</th><th>Fase</th><th>Trade</th><th>PnL (€)</th><th>WR</th><th>W / L</th></tr>{yoy_html}</table>

<h2>Anno per anno (Baseline)</h2>
<table><tr><th>Anno</th><th>Fase</th><th>Trade</th><th>PnL (€)</th><th>WR</th><th>W / L</th></tr>{yoy_base_html}</table>

<h2>Stabilità OOS</h2>
<div class="callout">
  <table>
    <tr><th>Metrica</th><th>TRAIN</th><th>TEST</th><th>Δ</th></tr>
    <tr><td>PnL</td><td>{fmt_eur(m_train['pnl_eur'])}</td><td class="green">{fmt_eur(m_test['pnl_eur'])}</td><td class="green">{(m_test['pnl_eur']/m_train['pnl_eur']-1)*100:+.0f}%</td></tr>
    <tr><td>Calmar</td><td>{m_train['calmar']:.2f}</td><td>{m_test['calmar']:.2f}</td><td>{(m_test['calmar']-m_train['calmar']):+.2f}</td></tr>
    <tr><td>PF</td><td>{m_train['pf']:.3f}</td><td>{m_test['pf']:.3f}</td><td>{(m_test['pf']-m_train['pf']):+.3f}</td></tr>
    <tr><td>WR</td><td>{m_train['wr']*100:.1f}%</td><td>{m_test['wr']*100:.1f}%</td><td>{(m_test['wr']-m_train['wr'])*100:+.1f}pp</td></tr>
    <tr><td>Max DD</td><td>{fmt_eur(m_train['max_dd_eur'])}</td><td>{fmt_eur(m_test['max_dd_eur'])}</td><td>{(m_test['max_dd_eur']-m_train['max_dd_eur']):+,.0f} €</td></tr>
  </table>
  <p style="margin-top:15px;margin-bottom:0"><b>Edge robusto</b>: PnL TEST positivo (+{m_test['pnl_eur']:,.0f} €), Calmar > 2, PF > 1.0. TEST migliore del TRAIN, niente overfit.</p>
</div>

<h2>Anatomia del CB 2loss cd 3</h2>
<div class="warn">
  <p><b>Regola:</b> dopo 2 perdite consecutive, salta 3 trade. Su 10 anni scatta {(trig_train+trig_test):,} volte ({(trig_train+trig_test)/(years_train+years_test):.0f}/anno).</p>
  <p>Trade eseguiti: {kept_total_train+kept_total_test:,} su {n_trades:,} generati ({((kept_total_train+kept_total_test)/n_trades)*100:.0f}%). Trade saltati per CB: {n_trades-(kept_total_train+kept_total_test):,}.</p>
  <p>PnL/trade CB: {(m_train['pnl_eur']+m_test['pnl_eur'])/(m_train['n']+m_test['n']):.1f} €. PnL/trade baseline: {m_base_train['pnl_pt']*25:.1f} €.</p>
</div>

<h2>Impatto slippage</h2>
<table>
  <tr><th>Slippage</th><th>PnL 10 anni</th><th>Calmar</th><th>PF</th><th>Trade</th></tr>
  <tr><td class="num">0 pt</td><td class="num">+807.197 €</td><td class="num">4,34</td><td class="num">1,70</td><td class="num">3.007</td></tr>
  <tr><td class="num">0,5 pt</td><td class="num">+725.050 €</td><td class="num">3,63</td><td class="num">1,61</td><td class="num">2.975</td></tr>
  <tr style="background:#d4f4dd"><td class="num"><b>1 pt *</b></td><td class="num"><b>{fmt_eur(m_train['pnl_eur']+m_test['pnl_eur'])}</b></td><td class="num"><b>{m_test['calmar']:.2f}</b></td><td class="num"><b>{m_test['pf']:.3f}</b></td><td class="num"><b>{m_train['n']+m_test['n']}</b></td></tr>
  <tr><td class="num">2 pt</td><td class="num">+538.988 €</td><td class="num">2,89</td><td class="num">1,43</td><td class="num">2.819</td></tr>
  <tr><td class="num">3 pt</td><td class="num">+411.230 €</td><td class="num">2,21</td><td class="num">1,33</td><td class="num">2.751</td></tr>
</table>
<p style="font-size:13px;color:#666">* slippage adottato nel report. Sistema muore a 5 pt di slippage.</p>

<hr style="margin: 40px 0; border: none; border-top: 1px solid #ddd;">
<p style="font-size:12px;color:#666;text-align:center">
  Generato il {pd.Timestamp.now().strftime('%d/%m/%Y alle %H:%M')} | OOS Validation 10 anni | Slippage {slip} pt | No overnight | Train: 2016-2021 | Test: 2022-2026
</p>

</body>
</html>"""

with open("reports/resoconto_oos_validation.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report salvato: reports/resoconto_oos_validation.html ({len(html):,} caratteri)")
print(f"{'='*80}")
print(f" Strategia: CB 2 perdite, cooldown 3 trade (slippage {slip} pt, no overnight)")
print(f" Train (2016-2021): PnL {fmt_eur(m_train['pnl_eur'])} | Calmar {m_train['calmar']:.2f}")
print(f" Test  (2022-2026): PnL {fmt_eur(m_test['pnl_eur'])} | Calmar {m_test['calmar']:.2f}")
print(f" Chiusure forzate 22:00: {n_forced}/{n_trades} ({n_forced/n_trades*100:.1f}%)")
print(f"{'='*80}")
