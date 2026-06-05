import pandas as pd
import numpy as np
from numba import jit
import sys
sys.stdout.reconfigure(encoding='utf-8')

base = r"C:\Users\Trader\.gemini\antigravity\scratch\AntigravityProjects"

df1 = pd.read_csv(base + "/dati/dax_m1.txt", header=None,
    names=["date","time","open","high","low","close","volume"])
df1["dt"] = pd.to_datetime(df1["date"].astype(str) + " " + df1["time"])
df1 = df1.set_index("dt").drop(columns=["date","time"])
df3 = df1.resample("3min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()

h_arr = df3["high"].values.astype(np.float64)
l_arr = df3["low"].values.astype(np.float64)
c_arr = df3["close"].values.astype(np.float64)
o_arr = df3["open"].values.astype(np.float64)
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

PT_VAL = 5.0
COMM_EUR = 3.0
SLIP_PT = 1.0
comm_pt = COMM_EUR / PT_VAL

def in_fascia(hr, mn):
    return (hr>=9 and hr<11) or (hr==15 and mn>=30) or (hr>=16 and hr<17) or (hr==17 and mn<=30)

def is_after_22(hr):
    return hr >= 22

d, s2 = st(h_arr, l_arr, c_arr, 10, 3.0)

pnls_list, dts_list, yrs_list = [], [], []
pos, ep = 0, 0.0
for i in range(20, n_bars):
    if i+1 >= n_bars: continue
    dt_next = df3.index[i+1]
    hr_n, mn_n = dt_next.hour, dt_next.minute

    if pos != 0 and is_after_22(hr_n):
        ex = o_arr[i+1]
        if pos == 1: pnl = ex - ep - comm_pt - SLIP_PT
        else: pnl = ep - ex - comm_pt - SLIP_PT
        pnls_list.append(pnl); dts_list.append(dt_next); yrs_list.append(dt_next.year)
        pos = 0

    if pos != 0:
        if pos == 1 and d[i-1]==1 and d[i]==-1:
            ex = o_arr[i+1] - SLIP_PT
            pnl = ex - ep - comm_pt
            pnls_list.append(pnl); dts_list.append(dt_next); yrs_list.append(dt_next.year)
            pos = 0
        elif pos == -1 and d[i-1]==-1 and d[i]==1:
            ex = o_arr[i+1] + SLIP_PT
            pnl = ep - ex - comm_pt
            pnls_list.append(pnl); dts_list.append(dt_next); yrs_list.append(dt_next.year)
            pos = 0

    if pos == 0 and in_fascia(hr_n, mn_n):
        if d[i]==1 and d[i-1]==-1:
            pos = 1; ep = o_arr[i+1] + SLIP_PT
        elif d[i]==-1 and d[i-1]==1:
            pos = -1; ep = o_arr[i+1] - SLIP_PT

pnls = np.array(pnls_list)

def apply_cb(p, ml, cd):
    kept=[];c=0;r=0
    for j,val in enumerate(p):
        if r>0: r-=1; continue
        if val<0: c+=1
        else: c=0
        if c>=ml: r=cd;c=0; continue
        kept.append(j)
    return np.array([p[i] for i in kept]), np.array(kept)

kept, idx = apply_cb(pnls, 2, 3)
yrs_all = np.array(yrs_list)

train_mask = yrs_all < 2022
test_mask = yrs_all >= 2022
train_idx = idx[yrs_all[idx] < 2022]
test_idx = idx[yrs_all[idx] >= 2022]
kept_train = pnls[train_idx]
kept_test = pnls[test_idx]

def metrics(p, yrs_data, label=""):
    if len(p)==0: return
    cum=np.cumsum(p); peak=np.maximum.accumulate(cum); dd=cum-peak
    wins=p[p>0]; losses=p[p<0]
    pf=wins.sum()/abs(losses.sum()) if len(losses) else 0
    years_span = (yrs_data[-1] - yrs_data[0]).days / 365.25 if len(yrs_data) > 1 else 1
    calmar = (p.sum()/abs(dd.min()))/years_span if dd.min()!=0 else 0
    print(f"{label}:")
    print(f"  Trade:   {len(p):>5}")
    print(f"  PnL pt:  {p.sum():>+8.2f}")
    print(f"  PnL eur: {p.sum()*PT_VAL:>+10,.0f}")
    print(f"  PF:      {pf:.3f}")
    print(f"  WR:      {len(wins)/len(p)*100:.1f}%")
    print(f"  Max DD:  {dd.min()*PT_VAL:>+10,.0f}")
    print(f"  Calmar:  {calmar:.2f}")
    print(f"  PnL/yr:  {p.sum()*PT_VAL/years_span:>+10,.0f}")
    return p.sum()*PT_VAL

print("=" * 55)
print("MINI-DAX (5 EUR/pt) — SuperTrend(10,3.0) DAX 3min")
print(f"Commissioni: {COMM_EUR} EUR/giro  |  Slippage: {SLIP_PT} pt")
print("=" * 55)

dts_train = [dts_list[i] for i in train_idx]
dts_test = [dts_list[i] for i in test_idx]
metrics(kept_train, dts_train, "\n--- TRAIN 2016-2021 (CB 2loss cd3) ---")
metrics(kept_test, dts_test, "\n--- TEST 2022-2026 (CB 2loss cd3) ---")
metrics(np.concatenate([kept_train, kept_test]),
        dts_train + dts_test, "\n--- TOTALE 10 ANNI (CB 2loss cd3) ---")

pnl_full = 656281
pnl_mini = kept_train.sum()*PT_VAL + kept_test.sum()*PT_VAL
print(f"\n{'='*55}")
print(f"CONFRONTO:")
print(f"  Full DAX (25 EUR/pt): +{pnl_full:>+9,} EUR")
print(f"  Mini-DAX (5 EUR/pt):  +{pnl_mini:>+9,.0f} EUR")
print(f"  Rapporto:             {pnl_mini/pnl_full*100:.1f}%")
print(f"  Costi/giro:           3 EUR (stesso full e mini)")
print(f"  Costi in pt full:     0.12 pt  |  Costi in pt mini: 0.60 pt")
