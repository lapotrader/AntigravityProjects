"""
BUND 1h — Mean reversion FISSA + ON/OFF filter.
Niente ottimizzazione mensile. Parametri fissi. ON/OFF basato su rolling PF.
"""
import pandas as pd, numpy as np

# === PARAMETRI FISSI (dall'analisi walk-forward) ===
BB_PERIODS = [10, 20]
BB_STD = 2.0
SL_ATR = 2.0
TP_ATR = 3.0
MIN_SIG = 1
ROLLING_WINDOW = 3  # mesi per calcolo PF rolling

# === SIGNAL ===
def build_signal(c, bb_periods, bb_std):
    n = len(c); sig = np.zeros(n)
    for p in bb_periods:
        sma = pd.Series(c).rolling(p, min_periods=p).mean().shift(1).values
        std = pd.Series(c).rolling(p, min_periods=p).std().shift(1).values
        for i in range(p+1, n):
            if np.isnan(sma[i]) or np.isnan(std[i]): continue
            bl = sma[i] - bb_std * std[i]
            bu = sma[i] + bb_std * std[i]
            if c[i-1] < bl: sig[i] += 1
            elif c[i-1] > bu: sig[i] -= 1
    return sig

# === STRATEGY ===
def run_mr(df, label=""):
    n = len(df)
    h = df["high"].values; l = df["low"].values
    c = df["close"].values; op = df["open"].values

    tr = np.maximum(h-l, np.maximum(np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1))))
    tr[0] = h[0]-l[0]; atr = np.zeros(n); alpha = 1/30; atr[0] = tr[0]
    for i in range(1, n): atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
    atr = np.roll(atr, 1); atr[0] = atr[1]

    sig = build_signal(c, BB_PERIODS, BB_STD)

    ph = np.full(n, False); pl = np.full(n, False)
    for i in range(5, n-5):
        if all(c[i] > c[i-k] for k in range(1,6)) and all(c[i] > c[i+k] for k in range(1,6)): ph[i]=True
        if all(c[i] < c[i-k] for k in range(1,6)) and all(c[i] < c[i+k] for k in range(1,6)): pl[i]=True

    trades = []; it = False; ep = 0; ei = 0; ed = ""; sp = 0; tpp = 0

    for i in range(max(BB_PERIODS)+3, n):
        if not it:
            if sig[i] >= MIN_SIG: sd = "LONG"
            elif sig[i] <= -MIN_SIG: sd = "SHORT"
            else: continue

            ch = None; cl = None
            for j in range(i-5, -1, -1):
                if ph[j]: ch = float(c[j]); break
            for j in range(i-5, -1, -1):
                if pl[j]: cl = float(c[j]); break

            ep = float(op[i]); ei = i; av = float(atr[i])
            if av <= 0: continue

            if sd == "LONG":
                ed = "LONG"; sp = (cl - 0.5*av) if cl is not None else (ep - SL_ATR*av)
                tpp = ep + TP_ATR * av
                if sp >= ep: sp = ep - SL_ATR*av
                if tpp <= ep: tpp = ep + av
            else:
                ed = "SHORT"; sp = (ch + 0.5*av) if ch is not None else (ep + SL_ATR*av)
                tpp = ep - TP_ATR * av
                if sp <= ep: sp = ep + SL_ATR*av
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
            trades.append({"pnl": pnl, "dir": ed, "ix": i, "ts": str(df.index[i])})
            it = False
    return trades

# === ON/OFF FILTER ===
def apply_onoff(trades, prices):
    """Filtra trades: solo quelli in mesi con rolling PF >= 1.0"""
    # Mappa ogni trade al suo mese
    months = sorted(set(t["ts"][:7] for t in trades))
    monthly = {m: {"trades": [], "pnl": 0} for m in months}

    for t in trades:
        m = t["ts"][:7]
        if m in monthly:
            monthly[m]["trades"].append(t)
            monthly[m]["pnl"] += t["pnl"]

    # Calcola PF mensile
    monthly_pf = {}
    for m in months:
        wins = sum(t["pnl"] for t in monthly[m]["trades"] if t["pnl"] > 0)
        losses = abs(sum(t["pnl"] for t in monthly[m]["trades"] if t["pnl"] <= 0))
        monthly_pf[m] = wins / losses if losses else 999

    # Rolling PF e ON/OFF
    month_list = sorted(months)
    on_states = {}
    cumul_roll = []
    for i, m in enumerate(month_list):
        if i < ROLLING_WINDOW:
            # Primi mesi: default ON
            on_states[m] = True
            roll_wins = sum(monthly_pf[month_list[j]] * \
                abs(sum(t["pnl"] for t in monthly[month_list[j]]["trades"] if t["pnl"]>0))
                for j in range(i+1) if monthly_pf[month_list[j]] != 999)
            roll_losses = sum(
                abs(sum(t["pnl"] for t in monthly[month_list[j]]["trades"] if t["pnl"]<=0))
                for j in range(i+1))
            roll_pf = roll_wins / roll_losses if roll_losses else 999
        else:
            roll_wins = sum(
                abs(sum(t["pnl"] for t in monthly[month_list[j]]["trades"] if t["pnl"]>0))
                for j in range(i-ROLLING_WINDOW, i) if monthly_pf[month_list[j]] != 999)
            # Actually simpler: just use PnL sum
            roll_pnl = sum(monthly[month_list[j]]["pnl"] for j in range(i-ROLLING_WINDOW, i))
            on_states[m] = roll_pnl >= 0

    # Filtra trades
    filtered = [t for t in trades if on_states.get(t["ts"][:7], True)]
    return filtered, on_states, monthly, monthly_pf

# === REPORT ===
def report(trades, label):
    total = len(trades)
    if total == 0:
        print(f"{label:<25}: 0 trades")
        return
    wins = sum(1 for t in trades if t["pnl"] > 0)
    losses = total - wins
    gw = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gl = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    pf = gw / gl if gl else 999
    print(f"{label:<25}: {total:<5} trades  WR={wins/total*100:5.1f}%  "
          f"PnL={sum(t['pnl'] for t in trades):+7.2f}  PF={pf:.3f}  "
          f"AvgW={gw/wins:.3f}  AvgL={gl/losses:.3f}" if wins and losses else "")

# === MAIN ===
print("=" * 90)
print("BUND 1h — MR FISSO + ON/OFF FILTER")
print(f"Parametri: BB{BB_PERIODS} std={BB_STD} SL={SL_ATR}atr TP={TP_ATR}atr min_sig={MIN_SIG}")
print(f"ON/OFF: rolling PF {ROLLING_WINDOW} mesi (soglia PnL>=0)")
print("=" * 90)

# Carica dati
cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns=["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
cont.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: cont[c]=cont[c].astype(float)

# Split
is_df = cont[cont.index < "2026-01-01"].copy()
oos_df = cont[cont.index >= "2026-01-01"].copy()

# === IN-SAMPLE (2018-2025) ===
print("\n--- IN-SAMPLE (2018-2025) ---")
trades_is = run_mr(is_df, "IS")
report(trades_is, "Tutti i trade (no filter)")
filtered_is, on_states_is, monthly_is, pf_is = apply_onoff(trades_is, is_df)
report(filtered_is, "ON/OFF filtered")

# Dettaglio ON/OFF per mese
print(f"\nMesi ON:  {sum(1 for v in on_states_is.values() if v)}/{len(on_states_is)}")
print(f"Mesi OFF: {sum(1 for v in on_states_is.values() if not v)}/{len(on_states_is)}")

# === OOS (continuo 2026) ===
print("\n--- OOS (continuo gen-mag 2026) ---")
trades_oos = run_mr(oos_df, "OOS")
report(trades_oos, "Tutti i trade (no filter)")
filtered_oos, on_states_oos, monthly_oos, pf_oos = apply_onoff(trades_oos, oos_df)
report(filtered_oos, "ON/OFF filtered")
print(f"Mesi ON:  {sum(1 for v in on_states_oos.values() if v)}/{len(on_states_oos)}")
print(f"Mesi OFF: {sum(1 for v in on_states_oos.values() if not v)}/{len(on_states_oos)}")

# === OOS (contratto marzo 2026) ===
print("\n--- OOS (contratto marzo 2026) ---")
raw = pd.read_csv("dati/Eurex.Bund marzo 2026.txt", sep="\t", skiprows=3,
    names=["ora","high","low","open","close","volume"], decimal=",")
for c in ["high","low","open","close","volume"]: raw[c] = raw[c].astype(float)
raw["dt"] = pd.to_datetime(raw["ora"], format="%d%m%Y %H%M%S")
raw.sort_values("dt", inplace=True)
raw.set_index("dt", inplace=True)

trades_raw = run_mr(raw, "Contratto")
report(trades_raw, "Tutti i trade (no filter)")
filtered_raw, on_states_raw, monthly_raw, pf_raw = apply_onoff(trades_raw, raw)
report(filtered_raw, "ON/OFF filtered")

# === EQUITY CURVE FULL (2018-2026, IS+OOS) ===
print("\n\n=== EQUITY CURVE COMPLETA ===")
all_trades = run_mr(cont, "Full")
report(all_trades, "Tutti i trade (no filter)")
filtered_all, on_states_all, monthly_all, pf_all = apply_onoff(all_trades, cont)
report(filtered_all, "ON/OFF filtered")

# Costruisci equity cur ve filtrata
df_all = pd.DataFrame(filtered_all)
if len(df_all) > 0:
    df_all["cumul"] = df_all["pnl"].cumsum()
    cumul_max = df_all["cumul"].expanding().max()
    dd = df_all["cumul"] - cumul_max
    print(f"Max DD da peak: {dd.min():.2f}")

    df_all["year"] = df_all["ts"].str[:4]
    print("\n=== PER ANNO (ON/OFF filtered) ===")
    print(f"{'Anno':<6} {'Trades':<8} {'Win%':<8} {'PnL':<10} {'PF':<10}")
    print("-" * 42)
    for yr in sorted(df_all["year"].unique()):
        grp = df_all[df_all["year"] == yr]
        w = int((grp["pnl"] > 0).sum())
        l = len(grp) - w
        g = float(grp[grp["pnl"] > 0]["pnl"].sum()) if w else 0
        ls = float(abs(grp[grp["pnl"] <= 0]["pnl"].sum())) if l else 1
        print(f"{yr:<6} {len(grp):<8} {w/len(grp)*100:<7.1f}% {grp['pnl'].sum():<+9.2f} {g/ls:<9.2f}")

# Salva
df_all.to_csv("execution/bund_mr_onoff_trades.csv", index=False)
print("\nTrades salvati in execution/bund_mr_onoff_trades.csv")
