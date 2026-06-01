"""
BUND — Sistema finale combinato.
1) RSI+Volume confirmation (1h) — segnale principale
2) Gap continuation (daily open) — segnale secondario
Parametri fissi, ON/OFF filter rolling.
"""
import pandas as pd, numpy as np

# === PARAMETRI ===
RSI_PERIOD = 14
RSI_LOWER = 20
RSI_UPPER = 75
TP_ATR = 2.0
SL_ATR = 2.0
VOL_MULT = 2.0
BB_PERIODS = [10, 20]
BB_STD = 2.0

ROLL_WIN = 3  # mesi per ON/OFF

# === CARICA 1h ===
cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns=["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
cont.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: cont[c]=cont[c].astype(float)

print(f"BUND 1h: {len(cont)} candles, {cont.index[0]} -> {cont.index[-1]}")

# === SIGNAL 1a: RSI + VOLUME ===
def rsi_vol_signal(df):
    c = df["close"].values; v = df["volume"].values; n = len(c)
    sig = np.zeros(n)
    rsi_raw = pd.Series(c).rolling(RSI_PERIOD).mean().shift(1).values  # placeholder
    # RSI corretto
    delta = pd.Series(c).diff()
    gain = delta.clip(lower=0).rolling(RSI_PERIOD).mean().shift(1).values
    loss = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean().shift(1).values
    rsi = np.full(n, 50.0)
    for i in range(RSI_PERIOD+1, n):
        if loss[i] != 0: rsi[i] = 100 - 100 / (1 + gain[i]/loss[i])
    vol_sma = pd.Series(v).rolling(20).mean().shift(1).values
    for i in range(RSI_PERIOD+2, n):
        if np.isnan(rsi[i]) or np.isnan(vol_sma[i]): continue
        if rsi[i] < RSI_LOWER and v[i-1] > vol_sma[i] * VOL_MULT: sig[i] = 1   # LONG
        elif rsi[i] > RSI_UPPER and v[i-1] > vol_sma[i] * VOL_MULT: sig[i] = -1  # SHORT
    return sig

# === SIGNAL 1b: BB multi-TF (fallback) ===
def bb_signal(df):
    c = df["close"].values; n = len(c); sig = np.zeros(n)
    for p in BB_PERIODS:
        sma = pd.Series(c).rolling(p, min_periods=p).mean().shift(1).values
        std = pd.Series(c).rolling(p, min_periods=p).std().shift(1).values
        for i in range(p+1, n):
            if np.isnan(sma[i]) or np.isnan(std[i]): continue
            bl = sma[i] - BB_STD * std[i]; bu = sma[i] + BB_STD * std[i]
            if c[i-1] < bl: sig[i] += 1
            elif c[i-1] > bu: sig[i] -= 1
    return sig

# === COMBINED SIGNAL ===
def combined_signal(df):
    s1 = rsi_vol_signal(df)
    s2 = bb_signal(df)
    sig = np.zeros(len(df))
    for i in range(len(df)):
        # RSI+Volume ha priorita'. BB conferma (min_sig=1 = almeno un TF)
        if s1[i] != 0: sig[i] = s1[i]
        elif s2[i] >= 1: sig[i] = 1
        elif s2[i] <= -1: sig[i] = -1
    return sig

# === TRADING LOOP ===
def run_strategy(df, use_onoff=True):
    n = len(df); h = df["high"].values; l = df["low"].values
    c = df["close"].values; op = df["open"].values; v = df["volume"].values

    # ATR
    tr = np.maximum(h-l, np.maximum(np.abs(h-np.roll(c,1)), np.abs(l-np.roll(c,1))))
    tr[0] = h[0]-l[0]; atr = np.zeros(n); alpha = 1/30; atr[0] = tr[0]
    for i in range(1, n): atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])
    atr = np.roll(atr, 1); atr[0] = atr[1]

    sig = combined_signal(df)

    ph = np.full(n, False); pl = np.full(n, False)
    for i in range(5, n-5):
        if all(c[i] > c[i-k] for k in range(1,6)) and all(c[i] > c[i+k] for k in range(1,6)): ph[i]=True
        if all(c[i] < c[i-k] for k in range(1,6)) and all(c[i] < c[i+k] for k in range(1,6)): pl[i]=True

    trades = []; it = False; ep = 0; ei = 0; ed = ""; sp = 0; tpp = 0

    for i in range(60, n):
        if not it:
            if sig[i] >= 1: sd = "LONG"
            elif sig[i] <= -1: sd = "SHORT"
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
            trades.append({"pnl": pnl, "dir": ed, "src": "RSI+BB" if sig[ei] != 0 else "BB",
                          "ts": str(df.index[i]), "ix_e": ei, "ix_x": i})
            it = False

    if use_onoff:
        # ON/OFF filter
        months = sorted(set(t["ts"][:7] for t in trades))
        monthly = {m: {"trades": [], "pnl": 0} for m in months}
        for t in trades:
            m = t["ts"][:7]
            if m in monthly:
                monthly[m]["trades"].append(t)
                monthly[m]["pnl"] += t["pnl"]
        month_list = sorted(months)
        on_states = {}
        for i, m in enumerate(month_list):
            if i < ROLL_WIN:
                on_states[m] = True
            else:
                roll_pnl = sum(monthly[month_list[j]]["pnl"] for j in range(i-ROLL_WIN, i))
                on_states[m] = roll_pnl >= 0
        filtered = [t for t in trades if on_states.get(t["ts"][:7], True)]
        return filtered, trades
    return trades, trades

# === BACKTEST ===
print("\n" + "=" * 90)
print("SISTEMA COMBINATO: RSI+Volume + BB multi-TF")
print("=" * 90)

periods = [
    ("IS 2018-2019", cont[cont.index < "2020-01-01"]),
    ("VAL 2020-2022", cont[(cont.index >= "2020-01-01") & (cont.index < "2023-01-01")]),
    ("OOS 2023-2026", cont[cont.index >= "2023-01-01"]),
    ("FULL 2018-2026", cont),
]

for name, df in periods:
    filt, all_t = run_strategy(df)
    for label, tlist in [("NO FILTER", all_t), ("ON/OFF", filt)]:
        if len(tlist) == 0:
            print(f"\n{name:<20} {label:<10}: 0 trades")
            continue
        wins = sum(1 for t in tlist if t["pnl"]>0)
        losses = len(tlist) - wins
        gw = sum(t["pnl"] for t in tlist if t["pnl"]>0)
        gl = abs(sum(t["pnl"] for t in tlist if t["pnl"]<=0))
        pf = gw/gl if gl else 999
        pnl_tot = sum(t["pnl"] for t in tlist)
        avg_w = gw/wins if wins else 0
        avg_l = gl/losses if losses else 0
        print(f"\n{name:<20} {label:<10}: {len(tlist):<5} trades  "
              f"WR={wins/len(tlist)*100:5.1f}%  PnL={pnl_tot:+7.2f}  "
              f"PF={pf:.3f}  AvgW={avg_w:.3f}  AvgL={avg_l:.3f}")

# === OOS SU CONTRATTO MARZO 2026 ===
print("\n\n--- OOS: CONTRATTO MARZO 2026 ---")
raw = pd.read_csv("dati/Eurex.Bund marzo 2026.txt", sep="\t", skiprows=3,
    names=["ora","high","low","open","close","volume"], decimal=",")
for c in ["high","low","open","close","volume"]: raw[c] = raw[c].astype(float)
raw["dt"] = pd.to_datetime(raw["ora"], format="%d%m%Y %H%M%S")
raw.sort_values("dt", inplace=True)
raw.set_index("dt", inplace=True)

filt, all_t = run_strategy(raw)
for label, tlist in [("NO FILTER", all_t), ("ON/OFF", filt)]:
    if len(tlist) == 0: print(f"  {label:<10}: 0 trades"); continue
    wins = sum(1 for t in tlist if t["pnl"]>0); losses = len(tlist)-wins
    gw = sum(t["pnl"] for t in tlist if t["pnl"]>0)
    gl = abs(sum(t["pnl"] for t in tlist if t["pnl"]<=0))
    pf = gw/gl if gl else 999
    print(f"  {label:<10}: {len(tlist):<5} trades  WR={wins/len(tlist)*100:5.1f}%  "
          f"PnL={sum(t['pnl'] for t in tlist):+7.2f}  PF={pf:.3f}")

# === EQUITY CURVE ===
print("\n\n=== EQUITY CURVE (ON/OFF, FULL) ===")
filt_full, _ = run_strategy(cont)
df_tr = pd.DataFrame(filt_full)
if len(df_tr) > 0:
    df_tr["cumul"] = df_tr["pnl"].cumsum()
    cmax = df_tr["cumul"].expanding().max()
    dd = df_tr["cumul"] - cmax
    print(f"Final PnL:  {df_tr['cumul'].iloc[-1]:+.2f}")
    print(f"Max DD:     {dd.min():.2f}")
    print(f"Trades:     {len(df_tr)}")

    df_tr["year"] = df_tr["ts"].str[:4]
    print(f"\n{'Anno':<6} {'Trades':<8} {'Win%':<8} {'PnL':<10} {'PF':<10}")
    print("-"*42)
    for yr in sorted(df_tr["year"].unique()):
        g = df_tr[df_tr["year"]==yr]
        w = int((g["pnl"]>0).sum()); l = len(g)-w
        gw_ = float(g[g["pnl"]>0]["pnl"].sum()) if w else 0
        gl_ = float(abs(g[g["pnl"]<=0]["pnl"].sum())) if l else 1
        print(f"{yr:<6} {len(g):<8} {w/len(g)*100:<7.1f}% {g['pnl'].sum():<+9.2f} {gw_/gl_:<9.2f}")

df_tr.to_csv("execution/bund_final_trades.csv", index=False)
print("\nSalvato in execution/bund_final_trades.csv")
