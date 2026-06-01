"""
Analisi: posso stimare il next_pivot al momento dell'entry?
Cerco correlazioni tra condizioni di mercato e distanza dal prossimo pivot.
"""
import pandas as pd, numpy as np

SRC = "dati/btp_1h_full.txt"
ST_PERIOD=30; ST_MULT=1.5; LOOKBACK=5

df = pd.read_csv(SRC, sep="\t", decimal=".")
df.columns=["data","open","high","low","close","volume"]
df["ora"]=pd.to_datetime(df["data"])
n=len(df)
high,low,close=df["high"].values,df["low"].values,df["close"].values
print(f"Dataset: {n} candles\n")

# --- ATR ---
tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])

# --- ST ---
hl2=(high+low)/2; final_ub=np.zeros(n); final_lb=np.zeros(n); st=np.zeros(n)
direction=np.ones(n,dtype=int)
for i in range(n):
    if i==0: final_ub[i]=hl2[i]+ST_MULT*atr[i]; final_lb[i]=hl2[i]-ST_MULT*atr[i]; st[i]=final_ub[i]; direction[i]=-1; continue
    pc=close[i-1]; ub=hl2[i]+ST_MULT*atr[i]; lb=hl2[i]-ST_MULT*atr[i]
    final_ub[i]=ub if (ub<final_ub[i-1] or pc>final_ub[i-1]) else final_ub[i-1]
    final_lb[i]=lb if (lb>final_lb[i-1] or pc<final_lb[i-1]) else final_lb[i-1]
    if st[i-1]==final_ub[i-1]:
        if close[i]>final_ub[i]: st[i]=final_lb[i]; direction[i]=1
        else: st[i]=final_ub[i]; direction[i]=-1
    else:
        if close[i]<final_lb[i]: st[i]=final_ub[i]; direction[i]=-1
        else: st[i]=final_lb[i]; direction[i]=1

# --- Next pivot from each candle (forward looking - for analysis only) ---
ph_flag=np.full(n,False); pl_flag=np.full(n,False)
for i in range(LOOKBACK, n-LOOKBACK):
    if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
       all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph_flag[i]=True
    if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
       all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl_flag[i]=True

# Next pivot distance from each candle
next_ph_dist = [None]*n; next_pl_dist = [None]*n
np_h = None; np_l = None
for i in range(n-1, -1, -1):
    if ph_flag[i]: np_h = float(df.loc[i,"high"])
    if pl_flag[i]: np_l = float(df.loc[i,"low"])
    if np_h is not None: next_ph_dist[i] = np_h - float(close[i])
    if np_l is not None: next_pl_dist[i] = float(close[i]) - np_l

# --- Collect data at each ST entry signal ---
entries = []
for i in range(ST_PERIOD+2, n):
    prev=direction[i-1]; pprev=direction[i-2]
    if prev==1 and pprev==-1: dir_label="LONG"
    elif prev==-1 and pprev==1: dir_label="SHORT"
    else: continue

    entry=float(df.loc[i,"open"])
    atr_v=float(atr[i-1])
    next_ph = next_ph_dist[i]; next_pl = next_pl_dist[i]

    # ATR ratio and recent volatility
    atr_ma20 = np.mean(atr[max(0,i-20):i])
    atr_ratio = atr_v / atr_ma20 if atr_ma20 > 0 else 1

    # Distance from last confirmed pivot
    cp_high=None; cp_low=None
    for j in range(i-5, -1, -1):
        if ph_flag[j]: cp_high=float(df.loc[j,"high"]); break
    for j in range(i-5, -1, -1):
        if pl_flag[j]: cp_low=float(df.loc[j,"low"]); break
    dist_from_prev_ph = (entry - cp_high) if cp_high is not None else None
    dist_from_prev_pl = (entry - cp_low) if cp_low is not None else None

    entries.append({
        "i":i,"dir":dir_label,"entry":entry,"atr":atr_v,
        "atr_ratio":atr_ratio,
        "next_ph_dist":next_ph,"next_pl_dist":next_pl,
        "next_ph_mult":next_ph/atr_v if next_ph is not None and atr_v>0 else None,
        "next_pl_mult":next_pl/atr_v if next_pl is not None and atr_v>0 else None,
        "dist_prev_ph":dist_from_prev_ph,"dist_prev_pl":dist_from_prev_pl,
    })

# --- STATISTICS ---
print("=== DISTANZA NEXT PIVOT IN MULTIPLI DI ATR ===")
longs = [e for e in entries if e["dir"]=="LONG" and e["next_ph_mult"] is not None]
shorts = [e for e in entries if e["dir"]=="SHORT" and e["next_pl_mult"] is not None]

for label, data in [("LONG -> next pivot HIGH", longs), ("SHORT -> next pivot LOW", shorts)]:
    mults = [d["next_ph_mult"] if d["dir"]=="LONG" else d["next_pl_mult"] for d in data]
    mults = [m for m in mults if m is not None and m > 0 and m < 20]
    print(f"\n{label} ({len(data)} entry):")
    print(f"  Media moltiplicatore ATR: {np.mean(mults):.2f}x")
    print(f"  Mediana:                  {np.median(mults):.2f}x")
    print(f"  Dev Std:                  {np.std(mults):.2f}x")
    print(f"  Min:                      {min(mults):.2f}x")
    print(f"  Max:                      {max(mults):.2f}x")
    print(f"  Pct 25-75:                {np.percentile(mults,25):.2f}-{np.percentile(mults,75):.2f}x")
    print(f"  Pct 10-90:                {np.percentile(mults,10):.2f}-{np.percentile(mults,90):.2f}x")
    # Breakdown by ATR regime
    low_atr = [m for d,m in zip(data,mults) if d["atr_ratio"] < 0.9]
    mid_atr = [m for d,m in zip(data,mults) if 0.9 <= d["atr_ratio"] <= 1.1]
    high_atr = [m for d,m in zip(data,mults) if d["atr_ratio"] > 1.1]
    print(f"  Bassa volatilita (atr<0.9): mean={np.mean(low_atr):.2f}x (n={len(low_atr)})" if low_atr else "")
    print(f"  Media volatilita:           mean={np.mean(mid_atr):.2f}x (n={len(mid_atr)})" if mid_atr else "")
    print(f"  Alta volatilita (atr>1.1):  mean={np.mean(high_atr):.2f}x (n={len(high_atr)})" if high_atr else "")

# --- Can I predict next pivot at entry? ---
print("\n\n=== REGRESSIONE: POSSO PREVEDERE LA DISTANZA? ===")
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

def test_prediction(data, target_key):
    X_data = []
    y_data = []
    for e in data:
        if e[target_key] is None: continue
        dist = e[target_key]
        if dist <= 0 or dist > 20*e["atr"]: continue
        # Features: ATR, ATR ratio, distance from prev pivot
        X_data.append([e["atr"], e["atr_ratio"],
            e["dist_prev_ph"] if e["dist_prev_ph"] is not None else 0,
            e["dist_prev_pl"] if e["dist_prev_pl"] is not None else 0])
        y_data.append(dist)
    if len(X_data) < 50: return None, None, None
    X = np.array(X_data); y = np.array(y_data)
    # Simple baseline: always predict mean * atr
    baseline = np.mean([y[i]/X[i,0] for i in range(len(y))]) * np.array([X[i,0] for i in range(len(X))])
    baseline_r2 = 1 - np.sum((y - baseline)**2) / np.sum((y - np.mean(y))**2)
    # Linear regression
    model = LinearRegression()
    model.fit(X, y)
    pred = model.predict(X)
    r2 = r2_score(y, pred)
    coefs = model.coef_
    return r2, baseline_r2, coefs

pred_long = test_prediction(longs, "next_ph_dist")
pred_short = test_prediction(shorts, "next_pl_dist")

print("LONG -> prevedere next pivot HIGH:")
if pred_long[0] is not None:
    print(f"  R2 (ATR medio):           {pred_long[1]:.3f} (baseline: usa ATR medio)")
    print(f"  R2 (regressione lineare): {pred_long[0]:.3f}")
    print(f"  Coefficienti: [ATR, atr_ratio, dist_prev_ph, dist_prev_pl]: {pred_long[2]}")

print("\nSHORT -> prevedere next pivot LOW:")
if pred_short[0] is not None:
    print(f"  R2 (ATR medio):           {pred_short[1]:.3f} (baseline: usa ATR medio)")
    print(f"  R2 (regressione lineare): {pred_short[0]:.3f}")

# --- CORRELATION: ATR vs next_pivot_distance ---
print("\n\n=== CORRELAZIONE ATR vs NEXT PIVOT DISTANCE ===")
for label, data in [("LONG -> HIGH", longs), ("SHORT -> LOW", shorts)]:
    if label == "LONG -> HIGH":
        atrs = [d["atr"] for d in data if d["next_ph_dist"] is not None and d["next_ph_dist"] > 0]
        dists = [d["next_ph_dist"] for d in data if d["next_ph_dist"] is not None and d["next_ph_dist"] > 0]
    else:
        atrs = [d["atr"] for d in data if d["next_pl_dist"] is not None and d["next_pl_dist"] > 0]
        dists = [d["next_pl_dist"] for d in data if d["next_pl_dist"] is not None and d["next_pl_dist"] > 0]
    if len(atrs) > 5:
        corr = np.corrcoef(atrs, dists)[0,1]
        print(f"  {label}: correlazione ATR-distanza = {corr:.3f}")

# --- BEST TP estimate ---
print("\n\n=== MIGLIOR STIMA TP ALL'ENTRY ===")
print("Basata su: entry + ATR * moltiplicatore_medio")
for label, data in [("LONG TP (next HIGH)", longs), ("SHORT TP (next LOW)", shorts)]:
    if label == "LONG TP (next HIGH)":
        mults = [d["next_ph_mult"] for d in data if d["next_ph_mult"] is not None and d["next_ph_mult"] > 0 and d["next_ph_mult"] < 20]
    else:
        mults = [d["next_pl_mult"] for d in data if d["next_pl_mult"] is not None and d["next_pl_mult"] > 0 and d["next_pl_mult"] < 20]
    print(f"  {label}:")
    print(f"    Media ATR mult: {np.mean(mults):.2f}x")
    print(f"    Mediana ATR mult: {np.median(mults):.2f}x")
    print(f"    Miglior stima: entry + ATR x {np.median(mults):.1f}")
    # Coverage: % of actual pivots within +/- 20% of estimate
    median_m = np.median(mults)
    within_pct = sum(1 for m in mults if 0.8*median_m <= m <= 1.2*median_m) / len(mults) * 100
    print(f"    % pivot entro +/-20% della stima: {within_pct:.0f}%")
