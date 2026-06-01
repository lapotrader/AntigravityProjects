"""
Analisi: cosa predice l'OOS performance nel walk-forward?
Cerchiamo un segnale che distingua mesi buoni da mesi cattivi.
"""
import pandas as pd, numpy as np

# Ricarica e ricalcola il walk-forward per estrarre metriche
cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns=["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
cont.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: cont[c]=cont[c].astype(float)

# Stessa identica logica del walk-forward
def build_signal(df, bb_periods, bb_std):
    c = df["close"].values; n = len(c); sig = np.zeros(n)
    for p in bb_periods:
        sma = pd.Series(c).rolling(p, min_periods=p).mean().shift(1).values
        std = pd.Series(c).rolling(p, min_periods=p).std().shift(1).values
        for i in range(p+1, n):
            if np.isnan(sma[i]) or np.isnan(std[i]): continue
            bl = sma[i] - bb_std * std[i]; bu = sma[i] + bb_std * std[i]
            if c[i-1] < bl: sig[i] += 1
            elif c[i-1] > bu: sig[i] -= 1
    return sig

def run_mr(df_in, bb_periods, bb_std, sl_atr, tp_atr, min_sig):
    df = df_in.copy(); n = len(df)
    h = df["high"].values; l = df["low"].values
    c = df["close"].values; op = df["open"].values
    tr = np.maximum(h-l, np.maximum(np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1))))
    tr[0] = h[0]-l[0]; atr = np.zeros(n); alpha = 1/30; atr[0] = tr[0]
    for i in range(1, n): atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
    atr = np.roll(atr, 1); atr[0] = atr[1]
    sig = build_signal(df, bb_periods, bb_std)
    ph = np.full(n, False); pl = np.full(n, False)
    for i in range(5, n-5):
        if all(c[i] > c[i-k] for k in range(1,6)) and all(c[i] > c[i+k] for k in range(1,6)): ph[i]=True
        if all(c[i] < c[i-k] for k in range(1,6)) and all(c[i] < c[i+k] for k in range(1,6)): pl[i]=True
    trades = []; it = False; ep = 0; ei = 0; ed = ""; sp = 0; tpp = 0
    for i in range(max(bb_periods)+3, n):
        if not it:
            if sig[i] >= min_sig: sd = "LONG"
            elif sig[i] <= -min_sig: sd = "SHORT"
            else: continue
            ch = None; cl = None
            for j in range(i-5, -1, -1):
                if ph[j]: ch = float(c[j]); break
            for j in range(i-5, -1, -1):
                if pl[j]: cl = float(c[j]); break
            ep = float(op[i]); ei = i; av = float(atr[i])
            if av <= 0: continue
            if sd == "LONG":
                ed = "LONG"; sp = (cl - 0.5*av) if cl is not None else (ep - sl_atr*av)
                tpp = ep + tp_atr * av
                if sp >= ep: sp = ep - sl_atr*av
                if tpp <= ep: tpp = ep + av
            else:
                ed = "SHORT"; sp = (ch + 0.5*av) if ch is not None else (ep + sl_atr*av)
                tpp = ep - tp_atr * av
                if sp <= ep: sp = ep + sl_atr*av
                if tpp >= ep: tpp = ep - av
            it = True; continue
        lo = float(l[i]); hi = float(h[i]); ex = False; exp = 0
        if ed == "LONG":
            if lo <= sp: exp = sp; ex = True
            elif hi >= tpp: exp = tpp; ex = True
            elif (i - ei) >= 40: exp = float(c[i]); ex = True
        else:
            if hi >= sp: exp = sp; ex = True
            elif lo <= tpp: exp = tpp; ex = True
            elif (i - ei) >= 40: exp = float(c[i]); ex = True
        if ex:
            pnl = round(exp - ep, 2) if ed == "LONG" else round(ep - exp, 2)
            trades.append({"pnl": pnl}); it = False
    return trades

# Stessa griglia parametri e finestre
PARAM_GRID = []
for bp in [[10,20], [20,50], [10,20,50]]:
    for bs in [2.0, 2.5]:
        for sl in [1.5, 2.0, 3.0]:
            for tp in [2.0, 3.0]:
                for ms in [1, 2]:
                    PARAM_GRID.append({"bb_periods":bp,"bb_std":bs,"sl_atr":sl,"tp_atr":tp,"min_sig":ms})

dates = pd.date_range("2019-01-01", "2026-03-01", freq="MS")
IS_MONTHS = 6; OOS_MONTHS = 1

records = []

for di in range(len(dates) - IS_MONTHS - OOS_MONTHS):
    is_s = dates[di]; is_e = dates[di + IS_MONTHS]
    oos_s = dates[di + IS_MONTHS]; oos_e = dates[di + IS_MONTHS + OOS_MONTHS]
    is_df = cont[(cont.index >= is_s) & (cont.index < is_e)].copy()
    oos_df = cont[(cont.index >= oos_s) & (cont.index < oos_e)].copy()
    if len(is_df) < 300 or len(oos_df) < 50: continue

    # Trova best params su IS
    best = {"pf": -1, "params": None}
    for p in PARAM_GRID:
        try:
            trades = run_mr(is_df, **p)
            if len(trades) < 5: continue
            w = sum(1 for t in trades if t["pnl"] > 0)
            l = len(trades) - w
            if l == 0: continue
            gw = sum(t["pnl"] for t in trades if t["pnl"] > 0)
            gl = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
            pf = gw / gl if gl > 0 else 0
            if pf > best["pf"]:
                best = {"pf": pf, "params": p, "trades": len(trades), "wins": w, "losses": l,
                        "pnl": sum(t["pnl"] for t in trades), "gw": gw, "gl": gl}
        except: continue
    if best["pf"] <= 0: continue

    # OOS
    oos_trades = run_mr(oos_df, **best["params"])
    oos_w = sum(1 for t in oos_trades if t["pnl"] > 0)
    oos_l = len(oos_trades) - oos_w
    oos_gw = sum(t["pnl"] for t in oos_trades if t["pnl"] > 0) if oos_w else 0
    oos_gl = abs(sum(t["pnl"] for t in oos_trades if t["pnl"] <= 0)) if oos_l else 1
    oos_pf = oos_gw / oos_gl if oos_gl > 0 else 999
    oos_pnl = sum(t["pnl"] for t in oos_trades)

    p = best["params"]
    sig_count = int((np.abs(build_signal(is_df, p["bb_periods"], p["bb_std"])) >= p["min_sig"]).sum())

    records.append({
        "month": str(oos_s.date()),
        "oos_pf": oos_pf, "oos_pnl": oos_pnl, "oos_tr": len(oos_trades),
        "is_pf": best["pf"], "is_tr": best["trades"], "is_pnl": best["pnl"],
        "is_wr": best["wins"]/best["trades"]*100,
        "is_sig_count": sig_count,
        "bb_periods": str(p["bb_periods"]), "bb_std": p["bb_std"],
        "sl_atr": p["sl_atr"], "tp_atr": p["tp_atr"], "min_sig": p["min_sig"],
        "n_candles_is": len(is_df), "n_candles_oos": len(oos_df),
    })

df = pd.DataFrame(records)
print(f"Finestre analizzate: {len(df)}")

# 1) Correlazione IS PF vs OOS PF
corr = df["is_pf"].corr(df["oos_pf"])
print(f"\n1. Correlazione IS_PF -> OOS_PF: {corr:.3f}")
print("   -> L'ottimizzazione IS NON predice l'OOS. Normale.")

# 2) Parametri stabili vs OOS
# Quanto cambiano i parametri da una finestra all'altra
df["par_id"] = df["bb_periods"] + df["bb_std"].astype(str) + df["sl_atr"].astype(str) + df["tp_atr"].astype(str) + df["min_sig"].astype(str)
df["par_stable"] = df["par_id"] == df["par_id"].shift(1)
stable_pf = df[df["par_stable"]]["oos_pf"].mean()
unstable_pf = df[~df["par_stable"]]["oos_pf"].mean()
print(f"\n2. Parametri stabili da mese prec. -> OOS PF medio: {stable_pf:.3f}")
print(f"   Parametri cambiati             -> OOS PF medio: {unstable_pf:.3f}")

# 3) Numero segnali IS vs OOS
corr_sig = df["is_sig_count"].corr(df["oos_pf"])
print(f"\n3. Correlazione n deg segnali IS -> OOS_PF: {corr_sig:.3f}")

# 4) Quali parametri funzionano meglio OOS?
print("\n4. OOS PF medio per combinazione parametri:")
for grp, grpdf in df.groupby("bb_periods"):
    print(f"   BB{grp:<12} PF_med={grpdf['oos_pf'].mean():.3f}  finestre={len(grpdf)}")
for grp, grpdf in df.groupby("min_sig"):
    print(f"   min_sig={grp}   PF_med={grpdf['oos_pf'].mean():.3f}  finestre={len(grpdf)}")

# 5) Min_sig=1 (tanti segnali) vs min_sig=2 (pochi segnali)
for ms in [1, 2]:
    sub = df[df["min_sig"] == ms]
    print(f"\n   min_sig={ms}: {len(sub)} finestre, OOS PF medio={sub['oos_pf'].mean():.3f}, "
          f"OOS PnL tot={sub['oos_pnl'].sum():+.2f}, trades={sub['oos_tr'].sum()}")

# 6) TEST: se avessimo usato un filtro rolling per spegnere/accendere
# Simula: calcola PF rolling degli ultimi 3 mesi OOS. Se < 1.0, stop. Se > 1.2, riparti.
df["oos_pf_roll3"] = df["oos_pf"].rolling(3, min_periods=1).mean()
df["oos_pnl_roll3"] = df["oos_pnl"].rolling(3, min_periods=1).sum()

# Strategia: trade solo quando PF_roll3 >= 1.0
active = df["oos_pf_roll3"] >= 1.0
pnl_on = df.loc[active, "oos_pnl"].sum()
pnl_off = df.loc[~active, "oos_pnl"].sum()
tr_on = df.loc[active, "oos_tr"].sum()
tr_off = df.loc[~active, "oos_tr"].sum()
w_on = df.loc[active & (df["oos_pnl"] > 0)].shape[0]
w_off = df.loc[~active & (df["oos_pnl"] > 0)].shape[0]

print(f"\n\n=== SIMULAZIONE ON/OFF CON ROLLING PF (3 mesi) ===")
print(f"{'Stato':<10} {'Mesi':<8} {'Trades':<8} {'PnL':<10} {'MesiWin':<10}")
print("-"*46)
print(f"{'ON (PF>=1)':<10} {active.sum():<8} {tr_on:<8} {pnl_on:<+9.2f} {w_on:<10}")
print(f"{'OFF (PF<1)':<10} {(~active).sum():<8} {tr_off:<8} {pnl_off:<+9.2f} {w_off:<10}")

# Con hysteresis: ON se PF>=1.2, OFF se PF<0.9
active_h = pd.Series(index=df.index, dtype=bool)
state = False
for i in range(len(df)):
    if i < 3:
        active_h.iloc[i] = True
        continue
    r3 = df["oos_pf"].iloc[i-3:i].mean() if i >= 3 else df["oos_pf"].iloc[:i].mean()
    if not state and r3 >= 1.2: state = True
    elif state and r3 < 0.9: state = False
    active_h.iloc[i] = state

pnl_h_on = df.loc[active_h, "oos_pnl"].sum()
pnl_h_off = df.loc[~active_h, "oos_pnl"].sum()
print(f"\nCon hysteresis (ON>=1.2, OFF<0.9):")
print(f"{'ON':<10} {active_h.sum():<8} {df.loc[active_h,'oos_tr'].sum():<8} {pnl_h_on:<+9.2f}")
print(f"{'OFF':<10} {(~active_h).sum():<8} {df.loc[~active_h,'oos_tr'].sum():<8} {pnl_h_off:<+9.2f}")

# 7) Cosa predice meglio? Prova diverse finestre
print(f"\n=== QUAL E' LA MIGLIORE FINESTRA ROLLING? ===")
for w in [1, 2, 3, 4, 6]:
    roll = df["oos_pnl"].rolling(w, min_periods=1).sum()
    active = roll >= 0
    p = df.loc[active, "oos_pnl"].sum()
    print(f"  Rolling {w} mesi: ON={active.sum()}mesi PnL={p:+.2f}  (soglia=0)")
