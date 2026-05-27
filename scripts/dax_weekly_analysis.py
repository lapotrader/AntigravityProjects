import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings, logging
warnings.filterwarnings('ignore')
logging.captureWarnings(True)

df = pd.read_csv('dati/dax_220m.txt', sep='\t', parse_dates=['data'])
df.rename(columns={'data':'Datetime','close':'Close','open':'Open','high':'High','low':'Low','volume':'Volume'}, inplace=True)
df.set_index('Datetime', inplace=True)

daily = df.resample('D').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
dc = daily['Close'].resample('W-FRI').count()
w = daily.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
w = w[dc >= 3].dropna().copy()

w['Fwd_High'] = w['High'].shift(-1)
w['Fwd_Low'] = w['Low'].shift(-1)
w['Fwd_Up'] = w['Fwd_High'] / w['Close'] - 1
w['Fwd_Down'] = w['Fwd_Low'] / w['Close'] - 1
w['Fwd_Max_Abs'] = np.maximum(w['Fwd_Up'], -w['Fwd_Down'])
w['Return'] = w['Close'].pct_change()
w.dropna(inplace=True)

window = 20
w['Vol'] = w['Return'].rolling(window).std()
w['Vol_prev'] = w['Vol'].shift(1)
w.dropna(inplace=True)

# Labels
conds = [(w['Return'] > w['Vol_prev']), (w['Return'] < -w['Vol_prev'])]
w['State'] = np.select(conds, ['Bull','Bear'], default='Sideways')

# HMM
rets = w['Return'].values.reshape(-1,1)
hm = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000, random_state=42)
hm.fit(rets)
hs = hm.predict(rets)
means = hm.means_.flatten()
order = np.argsort(means)
hmm_map = {order[0]:'Bear', order[1]:'Sideways', order[2]:'Bull'}
w['HMM'] = [hmm_map[s] for s in hs]

# Consecutive Sideways
w['Consec_SW'] = 0
cnt = 0
for i in range(len(w)):
    w.iloc[i, w.columns.get_loc('Consec_SW')] = cnt
    if w['State'].iloc[i] == 'Sideways':
        cnt += 1
    else:
        cnt = 0

w['Vol_PctRank'] = w['Vol'].expanding().rank(pct=True)

# Transition matrix
s = w['State'].shift(-1)
d = pd.DataFrame({'From': w['State'], 'To': s}).dropna()
mat = pd.crosstab(d['From'], d['To'], normalize='index')
mat = mat.reindex(index=['Bear','Sideways','Bull'], columns=['Bear','Sideways','Bull']).fillna(0)

# Stationary
M = mat.values
evals, evecs = np.linalg.eig(M.T)
idx = np.isclose(evals, 1)
if any(idx):
    stat = evecs[:, idx][:, 0].real
    stat = stat / np.sum(stat)
    stat_s = pd.Series(stat, index=mat.index)

hmm_align = (w['State'] == w['HMM']).mean()

# Current price level
last_close = w['Close'].iloc[-1]

print("=" * 75)
print("  ANALISI DAX FUTURE — SETTIMANALE")
print("=" * 75)
print(f"Dati: {len(w)} settimane ({w.index[0].date()} -> {w.index[-1].date()})")
print(f"Ultimo prezzo: {last_close:.2f} (al {w.index[-1].date()})")
print(f"Punti per 1%: {last_close * 0.01:.1f} punti")
print()

print("1. DISTRIBUZIONE STATI")
st_cnt = w['State'].value_counts()
for s in ['Sideways','Bull','Bear']:
    print(f"   {s:12s}: {st_cnt.get(s,0):>3} ({st_cnt.get(s,0)/len(w)*100:.1f}%)")
print()

print("2. MATRICE DI TRANSIZIONE")
print(mat.round(4))
print()

print("3. STICKINESS")
for s in ['Bear','Sideways','Bull']:
    print(f"   {s:12s}: {mat.loc[s,s]:.2%}")
print()

print("4. DISTRIBUZIONE STAZIONARIA")
print(stat_s.round(4).to_string())
print()

print("5. ACCURATEZZA PREDITTIVA 1-SETTIMANA")
next_state = w['State'].shift(-1)
for state in ['Sideways','Bull','Bear']:
    mask = w['State'] == state
    n = mask.sum()
    if n > 0:
        p_sw = (next_state[mask] == 'Sideways').mean()
        p_same = (next_state[mask] == state).mean()
        print(f"   Da {state:12s}: P(SW)={p_sw:.2%}, P(stesso)={p_same:.2%}, N={n}")
print()

print("6. HMM")
print(f"   Allineamento globale: {hmm_align:.2%}")
print(f"   Semaforo corrente: {'VERDE' if w['State'].iloc[-1] == w['HMM'].iloc[-1] else 'ROSSO'}")
print(f"   Stato Markov: {w['State'].iloc[-1]} | Stato HMM: {w['HMM'].iloc[-1]}")
print()

# ---- EXCURSION ANALYSIS ----
print("=" * 75)
print("  ESCURSIONE 1-SETTIMANA CONDIZIONATA AI FILTRI")
print("=" * 75)

filters_list = [
    ('Tutte (base)', pd.Series(True, index=w.index)),
    ('Sideways', w['State'] == 'Sideways'),
    ('SW+Consec2', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 2)),
    ('SW+Consec3', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3)),
    ('SW+Consec4', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 4)),
    ('SW+Consec5', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 5)),
    ('SW+HMM', (w['State'] == 'Sideways') & (w['HMM'] == 'Sideways')),
    ('SW+HMM+Consec3', (w['State'] == 'Sideways') & (w['HMM'] == 'Sideways') & (w['Consec_SW'] >= 3)),
    ('SW+Vol<25%', (w['State'] == 'Sideways') & (w['Vol_PctRank'] < 0.25)),
    ('SW+Vol<15%', (w['State'] == 'Sideways') & (w['Vol_PctRank'] < 0.15)),
    ('SW+Vol<10%', (w['State'] == 'Sideways') & (w['Vol_PctRank'] < 0.10)),
    ('SW+Consec3+Vol<50%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3) & (w['Vol_PctRank'] < 0.50)),
    ('SW+Consec3+Vol<40%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3) & (w['Vol_PctRank'] < 0.40)),
    ('SW+Consec3+Vol<30%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3) & (w['Vol_PctRank'] < 0.30)),
    ('SW+Consec3+Vol<25%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3) & (w['Vol_PctRank'] < 0.25)),
    ('SW+Consec3+Vol<20%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3) & (w['Vol_PctRank'] < 0.20)),
    ('SW+Consec3+Vol<15%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3) & (w['Vol_PctRank'] < 0.15)),
    ('SW+Consec2+Vol<25%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 2) & (w['Vol_PctRank'] < 0.25)),
    ('SW+Consec2+Vol<20%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 2) & (w['Vol_PctRank'] < 0.20)),
    ('SW+Consec2+Vol<15%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 2) & (w['Vol_PctRank'] < 0.15)),
    ('SW+Consec4+Vol<50%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 4) & (w['Vol_PctRank'] < 0.50)),
    ('SW+Consec4+Vol<30%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 4) & (w['Vol_PctRank'] < 0.30)),
    ('SW+Consec4+Vol<20%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 4) & (w['Vol_PctRank'] < 0.20)),
]

print(f"{'Filtro':25s} {'N':>4} {'%':>5} {'Up95':>8} {'Dn05':>8} {'Range90':>8} {'Max95':>8} {'Max99':>9} {'Strike99':>9}")
print("-" * 85)

results_list = []
for name, mask in filters_list:
    sub = w[mask]
    n = len(sub)
    if n < 5:
        continue
    up95 = sub['Fwd_Up'].quantile(0.95)
    dn05 = sub['Fwd_Down'].quantile(0.05)
    max95 = sub['Fwd_Max_Abs'].quantile(0.95)
    max99 = sub['Fwd_Max_Abs'].quantile(0.99)
    strike99 = max99 * 100  # in percent
    results_list.append((name, n, n/len(w)*100, up95, dn05, up95-dn05, max95, max99, strike99))
    print(f"{name:25s} {n:>4} {n/len(w)*100:>4.0f}% {up95:>7.2%} {dn05:>7.2%} {(up95-dn05):>7.2%} {max95:>7.2%} {max99:>8.2%} {strike99:>7.1f}%")

print()
print(f"Punti per 1% a {last_close:.0f}: {last_close*0.01:.0f} punti")
print()

# Current status
last = w.iloc[-1]
print(f"SEGNALE CORRENTE (al {w.index[-1].date()}):")
print(f"  Stato: {last['State']}")
print(f"  HMM: {last['HMM']}")
print(f"  Semaforo: {'VERDE' if last['State'] == last['HMM'] else 'ROSSO'}")
print(f"  Consec SW: {int(last['Consec_SW'])}")
print(f"  Vol rank: {last['Vol_PctRank']:.1%}")
sw_ok = last['State'] == 'Sideways'
hmm_ok = last['HMM'] == 'Sideways'
consec_ok = last['Consec_SW'] >= 3
vol_ok = last['Vol_PctRank'] < 0.25
n_pass = sum([sw_ok, hmm_ok, consec_ok, vol_ok])
print(f"  Filtri: SW={sw_ok}, HMM={hmm_ok}, Consec={consec_ok}, Vol25={vol_ok} -> {n_pass}/4")
if n_pass >= 3:
    print(f"  >>> VENDI OPZIONI (alta confidenza)")
elif n_pass >= 2:
    print(f"  >>> CONFIDENZA MEDIA")
else:
    print(f"  >>> NO TRADE")
print("=" * 75)
