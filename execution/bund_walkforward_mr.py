"""
Rolling walk-forward mean reversion — BUND 1h.
Simula adattamento continuo: ogni mese ottimizza parametri su 6 mesi IS, testa sul mese successivo OOS.
Nessun look-ahead: segnali basati solo su dati disponibili all'open.
"""
import pandas as pd, numpy as np, warnings
warnings.filterwarnings("ignore")

# === CARICA DATI ===
cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns=["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
cont.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: cont[c]=cont[c].astype(float)
print(f"BUND 1h: {len(cont)} candles, {cont.index[0]} -> {cont.index[-1]}")

# === MULTI-TIMEFRAME SIGNAL (NO LOOK-AHEAD) ===
def build_signal(df, bb_periods, bb_std):
    """Pre-calcola segnali multi-TF. Valore a bar i = disponibile all'open di bar i."""
    c = df["close"].values
    n = len(c)
    sig = np.zeros(n)
    for p in bb_periods:
        sma = pd.Series(c).rolling(p, min_periods=p).mean().shift(1).values
        std = pd.Series(c).rolling(p, min_periods=p).std().shift(1).values
        for i in range(p+1, n):
            if np.isnan(sma[i]) or np.isnan(std[i]): continue
            bl = sma[i] - bb_std * std[i]
            bu = sma[i] + bb_std * std[i]
            if c[i-1] < bl: sig[i] += 1      # long segnale
            elif c[i-1] > bu: sig[i] -= 1     # short segnale
    return sig

def run_mr(df_in, bb_periods, bb_std, sl_atr, tp_atr, min_sig):
    """Mean reversion su df_in, multi-TF conferma, nessun look-ahead."""
    df = df_in.copy()
    n = len(df)
    h = df["high"].values; l = df["low"].values
    c = df["close"].values; op = df["open"].values

    # ATR (storico, shiftato per sicurezza)
    tr = np.maximum(h-l, np.maximum(np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1))))
    tr[0] = h[0]-l[0]
    atr = np.zeros(n); alpha = 1/30; atr[0] = tr[0]
    for i in range(1, n): atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
    atr = np.roll(atr, 1); atr[0] = atr[1]  # shift: valore a i basato su dati fino a i-1

    # Segnale
    sig = build_signal(df, bb_periods, bb_std)

    # Swing HL per SL
    ph = np.full(n, False); pl = np.full(n, False)
    for i in range(5, n-5):
        if all(c[i] > c[i-k] for k in range(1,6)) and all(c[i] > c[i+k] for k in range(1,6)): ph[i]=True
        if all(c[i] < c[i-k] for k in range(1,6)) and all(c[i] < c[i+k] for k in range(1,6)): pl[i]=True

    trades = []; it = False; ep = 0; ei = 0; ed = ""; sp = 0; tpp = 0
    start_i = max(bb_periods) + 3

    for i in range(start_i, n):
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
                ed = "LONG"
                sp = (cl - 0.5*av) if cl is not None else (ep - sl_atr*av)
                tpp = ep + tp_atr * av
                if sp >= ep: sp = ep - sl_atr*av
                if tpp <= ep: tpp = ep + av
            else:
                ed = "SHORT"
                sp = (ch + 0.5*av) if ch is not None else (ep + sl_atr*av)
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
            trades.append({"pnl": pnl, "dir": ed})
            it = False

    return trades

# === ROLLING WALK-FORWARD ===
START = "2019-01-01"
IS_MONTHS = 6
OOS_MONTHS = 1

# Parameter grid (mirata: combinazioni sensate)
PARAM_GRID = []
for bp in [[10,20], [20,50], [10,20,50]]:
    for bs in [2.0, 2.5]:
        for sl in [1.5, 2.0, 3.0]:
            for tp in [2.0, 3.0]:
                for ms in [1, 2]:
                    PARAM_GRID.append({"bb_periods":bp,"bb_std":bs,"sl_atr":sl,"tp_atr":tp,"min_sig":ms})
print(f"Parameter grid: {len(PARAM_GRID)} combinazioni")

# Finestre mensili rolling
dates = pd.date_range(START, "2026-03-01", freq="MS")
monthly_log = []
all_oos_trades = []

for di in range(len(dates) - IS_MONTHS - OOS_MONTHS):
    is_s = dates[di]
    is_e = dates[di + IS_MONTHS]
    oos_s = dates[di + IS_MONTHS]
    oos_e = dates[di + IS_MONTHS + OOS_MONTHS]

    is_df = cont[(cont.index >= is_s) & (cont.index < is_e)].copy()
    oos_df = cont[(cont.index >= oos_s) & (cont.index < oos_e)].copy()

    if len(is_df) < 300 or len(oos_df) < 50:
        continue

    # Ottimizzazione su IS
    best = {"pf": -1}
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
                best = {"pf": pf, "params": p, "trades": len(trades), "pnl": sum(t["pnl"] for t in trades)}
        except Exception:
            continue

    if best["pf"] <= 0: continue

    # Test OOS
    oos_trades = run_mr(oos_df, **best["params"])
    oos_w = sum(1 for t in oos_trades if t["pnl"] > 0)
    oos_l = len(oos_trades) - oos_w
    oos_gw = sum(t["pnl"] for t in oos_trades if t["pnl"] > 0) if oos_w else 0
    oos_gl = abs(sum(t["pnl"] for t in oos_trades if t["pnl"] <= 0)) if oos_l else 1
    oos_pf = oos_gw / oos_gl if oos_gl > 0 else 999
    oos_pnl = sum(t["pnl"] for t in oos_trades)

    p = best["params"]
    monthly_log.append({
        "is_s": str(is_s.date()), "is_e": str(is_e.date()),
        "oos_s": str(oos_s.date()), "oos_e": str(oos_e.date()),
        "is_tr": best["trades"], "is_pf": best["pf"],
        "oos_tr": len(oos_trades), "oos_wr": oos_w/len(oos_trades)*100 if oos_trades else 0,
        "oos_pf": oos_pf, "oos_pnl": oos_pnl,
        "par": f"BB{''.join(str(x) for x in p['bb_periods'])}_s{p['bb_std']}_sl{p['sl_atr']}_tp{p['tp_atr']}_sig{p['min_sig']}"
    })
    for t in oos_trades:
        all_oos_trades.append({**t, "month": str(oos_s.date())})

    if len(monthly_log) % 12 == 0:
        print(f"  [{len(monthly_log)}] IS {is_s.date()}->{is_e.date()} OOS {oos_s.date()}->{oos_e.date()}  "
              f"IS_pf={best['pf']:.2f} OOS_tr={len(oos_trades)} OOS_pf={oos_pf:.2f} PnL={oos_pnl:+.2f}")

# === REPORT FINALE ===
df_oot = pd.DataFrame(all_oos_trades)
total = len(df_oot)
wins = int((df_oot["pnl"] > 0).sum())
losses = total - wins
gw = float(df_oot[df_oot["pnl"] > 0]["pnl"].sum()) if wins else 0
gl = float(abs(df_oot[df_oot["pnl"] <= 0]["pnl"].sum())) if losses else 1
tot_pnl = float(df_oot["pnl"].sum())

print("\n" + "=" * 80)
print("WALK-FORWARD OOS CUMULATIVO")
print("=" * 80)
print(f"Finestre:        {len(monthly_log)} ({monthly_log[0]['is_s']} -> {monthly_log[-1]['oos_e']})")
print(f"Trades OOS:      {total}")
print(f"Win rate:        {wins/total*100:.1f}%" if total else "N/A")
print(f"PnL:             {tot_pnl:+.2f} pt")
print(f"PF:              {gw/gl:.4f}" if gl else "999")
print(f"Avg win:         {gw/wins:.3f}" if wins else "N/A")
print(f"Avg loss:        {gl/losses:.3f}" if losses else "N/A")
print(f"Avg trade:       {tot_pnl/total:.4f}" if total else "N/A")
print(f"Trades/mese:     {total/len(monthly_log):.1f}")

if total > 0:
    df_oot["cumul"] = df_oot["pnl"].cumsum()
    cumul_max = df_oot["cumul"].expanding().max()
    print(f"Max DD:          {df_oot['cumul'].min():+.2f}")
    print(f"Max DD da peak:  {(df_oot['cumul'] - cumul_max).min():.2f}")
    print(f"Final equity:    {df_oot['cumul'].iloc[-1]:+.2f}")

if total > 0:
    df_oot["year"] = df_oot["month"].str[:4]
    print("\n=== PER ANNO ===")
    print(f"{'Anno':<6} {'Trades':<8} {'Win%':<8} {'PnL':<10} {'PF':<10}")
    print("-" * 42)
    for yr in sorted(df_oot["year"].unique()):
        grp = df_oot[df_oot["year"] == yr]
        w = int((grp["pnl"] > 0).sum())
        l = len(grp) - w
        g = float(grp[grp["pnl"] > 0]["pnl"].sum()) if w else 0
        ls = float(abs(grp[grp["pnl"] <= 0]["pnl"].sum())) if l else 1
        print(f"{yr:<6} {len(grp):<8} {w/len(grp)*100:<7.1f}% {grp['pnl'].sum():<+9.2f} {g/ls:<9.2f}")

    # Equity per mese
    print("\n=== EQUITY MENSILE ===")
    print(f"{'Mese':<10} {'Trades':<8} {'PnL':<10} {'Cumul':<10}")
    print("-" * 38)
    cumul = 0
    for m in sorted(df_oot["month"].unique()):
        grp = df_oot[df_oot["month"] == m]
        cumul += grp["pnl"].sum()
        print(f"{m:<10} {len(grp):<8} {grp['pnl'].sum():<+9.2f} {cumul:<+9.2f}")

print("\n\n=== SELEZIONE PARAMETRI PER FINESTRA ===")
print(f"{'IS start':<12} {'IS end':<12} {'OOS start':<12} {'OOS end':<12} {'IS_tr':<6} {'IS_PF':<7} {'OOS_tr':<6} {'OOS_WR':<7} {'OOS_PF':<7} {'PnL':<8} {'Param':<30}")
print("-" * 118)
for r in monthly_log:
    print(f"{r['is_s']:<12} {r['is_e']:<12} {r['oos_s']:<12} {r['oos_e']:<12} "
          f"{r['is_tr']:<6} {r['is_pf']:<7.2f} {r['oos_tr']:<6} {r['oos_wr']:<6.1f}% {r['oos_pf']:<7.2f} {r['oos_pnl']:<+7.2f} {r['par']:<30}")
