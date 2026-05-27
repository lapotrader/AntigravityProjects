import pandas as pd, numpy as np
from hmmlearn import hmm
import warnings, logging
warnings.filterwarnings('ignore'); logging.captureWarnings(True)

df = pd.read_csv('dati/stoxx_220m.txt', sep='\t', parse_dates=['Data'])
df.rename(columns={'Data':'Datetime','Close':'Close','Open':'Open','High':'High','Low':'Low','Volume':'Volume'}, inplace=True)
df.set_index('Datetime', inplace=True)

daily = df.resample('D').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
dc = daily['Close'].resample('W-FRI').count()
w = daily.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
w = w[dc >= 3].dropna().copy()
w['Fwd_High'] = w['High'].shift(-1); w['Fwd_Low'] = w['Low'].shift(-1)
w['Fwd_Up'] = w['Fwd_High'] / w['Close'] - 1; w['Fwd_Down'] = w['Fwd_Low'] / w['Close'] - 1
w['Fwd_Max_Abs'] = np.maximum(w['Fwd_Up'], -w['Fwd_Down'])
w['Return'] = w['Close'].pct_change(); w.dropna(inplace=True)

window = 20
w['Vol'] = w['Return'].rolling(window).std(); w['Vol_prev'] = w['Vol'].shift(1); w.dropna(inplace=True)
conds = [(w['Return'] > w['Vol_prev']), (w['Return'] < -w['Vol_prev'])]
w['State'] = np.select(conds, ['Bull','Bear'], default='Sideways')

rets = w['Return'].values.reshape(-1,1)
hm = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000, random_state=42)
hm.fit(rets); hs = hm.predict(rets)
means = hm.means_.flatten(); order = np.argsort(means)
w['HMM'] = [{order[0]:'Bear',order[1]:'Sideways',order[2]:'Bull'}[s] for s in hs]

w['Consec_SW'] = 0; cnt = 0
for i in range(len(w)):
    w.iloc[i, w.columns.get_loc('Consec_SW')] = cnt
    cnt = cnt + 1 if w['State'].iloc[i] == 'Sideways' else 0
w['Vol_PctRank'] = w['Vol'].expanding().rank(pct=True)

s = w['State'].shift(-1)
d = pd.DataFrame({'From': w['State'], 'To': s}).dropna()
mat = pd.crosstab(d['From'], d['To'], normalize='index')
mat = mat.reindex(index=['Bear','Sideways','Bull'], columns=['Bear','Sideways','Bull']).fillna(0)
M = mat.values
evals, evecs = np.linalg.eig(M.T)
idx = np.isclose(evals, 1)
stat_s = pd.Series(evecs[:, idx][:, 0].real / np.sum(evecs[:, idx][:, 0].real), index=mat.index) if any(idx) else pd.Series()

print("="*75)
print("  ANALISI STOXX FUTURE — SETTIMANALE")
print("="*75)
print(f"Dati: {len(w)} settimane ({w.index[0].date()} -> {w.index[-1].date()})")
print(f"Ultimo prezzo: {w['Close'].iloc[-1]:.2f} (al {w.index[-1].date()})")
print(f"Punti per 1%: {w['Close'].iloc[-1]*0.01:.1f}")
print()
print("1. DISTRIBUZIONE STATI")
for s in ['Sideways','Bull','Bear']: print(f"   {s:12s}: {w['State'].value_counts().get(s,0)} ({w['State'].value_counts().get(s,0)/len(w)*100:.1f}%)")
print()
print("2. MATRICE DI TRANSIZIONE"); print(mat.round(4))
print("\n3. STICKINESS")
for s in ['Bear','Sideways','Bull']: print(f"   {s:12s}: {mat.loc[s,s]:.2%}")
print("\n4. DISTRIBUZIONE STAZIONARIA"); print(stat_s.round(4).to_string())
print("\n5. HMM")
print(f"   Allineamento: {(w['State']==w['HMM']).mean():.2%}")
tl = 'VERDE' if w['State'].iloc[-1]==w['HMM'].iloc[-1] else 'ROSSO'
print(f"   Semaforo: {tl} | Markov: {w['State'].iloc[-1]} | HMM: {w['HMM'].iloc[-1]}")

print("\n" + "="*75)
print("  ESCURSIONE 1-SETTIMANA CONDIZIONATA")
print("="*75)
flt = [
    ('Tutte', pd.Series(True, index=w.index)),
    ('Sideways', w['State']=='Sideways'),
    ('SW+Consec2', (w['State']=='Sideways')&(w['Consec_SW']>=2)),
    ('SW+Consec3', (w['State']=='Sideways')&(w['Consec_SW']>=3)),
    ('SW+Consec4', (w['State']=='Sideways')&(w['Consec_SW']>=4)),
    ('SW+Consec5', (w['State']=='Sideways')&(w['Consec_SW']>=5)),
    ('SW+HMM', (w['State']=='Sideways')&(w['HMM']=='Sideways')),
    ('SW+Vol<25%', (w['State']=='Sideways')&(w['Vol_PctRank']<0.25)),
    ('SW+Vol<15%', (w['State']=='Sideways')&(w['Vol_PctRank']<0.15)),
    ('SW+Consec3+Vol<50%', (w['State']=='Sideways')&(w['Consec_SW']>=3)&(w['Vol_PctRank']<0.50)),
    ('SW+Consec3+Vol<40%', (w['State']=='Sideways')&(w['Consec_SW']>=3)&(w['Vol_PctRank']<0.40)),
    ('SW+Consec3+Vol<30%', (w['State']=='Sideways')&(w['Consec_SW']>=3)&(w['Vol_PctRank']<0.30)),
    ('SW+Consec3+Vol<25%', (w['State']=='Sideways')&(w['Consec_SW']>=3)&(w['Vol_PctRank']<0.25)),
    ('SW+Consec2+Vol<25%', (w['State']=='Sideways')&(w['Consec_SW']>=2)&(w['Vol_PctRank']<0.25)),
    ('SW+Consec2+Vol<20%', (w['State']=='Sideways')&(w['Consec_SW']>=2)&(w['Vol_PctRank']<0.20)),
    ('SW+Consec2+Vol<15%', (w['State']=='Sideways')&(w['Consec_SW']>=2)&(w['Vol_PctRank']<0.15)),
]
print(f"{'Filtro':25s} {'N':>4} {'%':>5} {'Max95':>8} {'Max99':>9} {'Strike99':>9}")
print("-"*65)
for n, m in flt:
    sub = w[m]; ln = len(sub)
    if ln<5: continue
    mx95 = sub['Fwd_Max_Abs'].quantile(0.95)
    mx99 = sub['Fwd_Max_Abs'].quantile(0.99)
    print(f"{n:25s} {ln:>4} {ln/len(w)*100:>4.0f}% {mx95:>7.2%} {mx99:>8.2%} {mx99*100:>7.1f}%")

last = w.iloc[-1]
print(f"\nSEGNALE CORRENTE (al {w.index[-1].date()}):")
print(f"  Stato: {last['State']} | HMM: {last['HMM']}")
print(f"  Semaforo: {tl} | Consec SW: {int(last['Consec_SW'])} | Vol: {last['Vol_PctRank']:.1%}")
sw=last['State']=='Sideways'; h=last['HMM']=='Sideways'; c=last['Consec_SW']>=3; v=last['Vol_PctRank']<0.25
nf = sum([sw,h,c,v])
print(f"  Filtri: SW={sw}, HMM={h}, Consec={c}, Vol25={v} -> {nf}/4")
print(f"  >>> {'VENDI OPZIONI' if nf>=3 else 'CONFIDENZA MEDIA' if nf>=2 else 'NO TRADE'}")
print("="*75)
