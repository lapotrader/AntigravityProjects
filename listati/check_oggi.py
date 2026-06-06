import pandas as pd
import numpy as np
from numba import jit
import sys
sys.stdout.reconfigure(encoding='utf-8')

base = r"C:\Users\Trader\.gemini\antigravity\scratch\AntigravityProjects"

cols = ["datetime","h","l","o","c","v"]
df = pd.read_csv(base + "/dati/ultimissimi5giugno.txt", sep="\t", header=None, names=cols)
df["dt"] = pd.to_datetime(df["datetime"], format="%d/%m/%Y %H:%M:%S")
df = df.set_index("dt").drop(columns=["datetime"])
df = df.astype(float)
df.columns = ["high","low","open","close","volume"]

h_arr = df["high"].values.astype(np.float64)
l_arr = df["low"].values.astype(np.float64)
c_arr = df["close"].values.astype(np.float64)
o_arr = df["open"].values.astype(np.float64)

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
    return d,s2,fu,fl

d, s2, fu, fl = st(h_arr, l_arr, c_arr, 10, 3.0)

today = pd.Timestamp("2026-06-05")

print("=== 05/06/2026 MATTINA (9:00-11:00) ===")
print("Ora      Open    High    Low   Close  ST dir   BandaSu  BandaGiu Reversal?")
print("-" * 75)
for i in range(20, len(df)):
    ts = df.index[i]
    if ts.date() == today.date() and 9 <= ts.hour < 11:
        rev = "<<< REVERSAL LONG" if d[i]==1 and d[i-1]==-1 else ""
        sd = "LONG" if d[i]==1 else "SHORT"
        print("{:5s} {:>8.1f} {:>7.1f} {:>7.1f} {:>7.1f}  {:>5s}  {:>8.1f} {:>8.1f}  {}".format(
            ts.strftime('%H:%M'), o_arr[i], h_arr[i], l_arr[i], c_arr[i], sd, fu[i], fl[i], rev))

print()
print("=== 05/06/2026 POMERIGGIO (15:30-17:30) ===")
print("Ora      Open    High    Low   Close  ST dir   BandaSu  BandaGiu Reversal?")
print("-" * 75)
for i in range(20, len(df)):
    ts = df.index[i]
    in_fascia = (ts.hour == 15 and ts.minute >= 30) or (16 <= ts.hour < 17) or (ts.hour == 17 and ts.minute <= 30)
    if ts.date() == today.date() and in_fascia:
        rev = "<<< REVERSAL LONG" if d[i]==1 and d[i-1]==-1 else ("<<< REVERSAL SHORT" if d[i]==-1 and d[i-1]==1 else "")
        sd = "LONG" if d[i]==1 else "SHORT"
        print("{:5s} {:>8.1f} {:>7.1f} {:>7.1f} {:>7.1f}  {:>5s}  {:>8.1f} {:>8.1f}  {}".format(
            ts.strftime('%H:%M'), o_arr[i], h_arr[i], l_arr[i], c_arr[i], sd, fu[i], fl[i], rev))

# Mostra anche se il prezzo ha incrociato le bande
print()
print("=== VERIFICA INCROCI BANDA ===")
for i in range(20, len(df)):
    ts = df.index[i]
    if ts.date() == today.date() and ts.hour >= 9:
        sd = "LONG" if d[i]==1 else "SHORT"
        # Controlla se c[i] ha toccato le bande
        touch_upper = c_arr[i] >= fu[i]
        touch_lower = c_arr[i] <= fl[i]
        if touch_upper or touch_lower:
            print("{:5s} Close={:.1f} Su={:.1f} Giù={:.1f} ST={} {}".format(
                ts.strftime('%H:%M'), c_arr[i], fu[i], fl[i], sd,
                "TOCCATO SU" if touch_upper else "TOCCATO GIÙ" if touch_lower else ""))
