import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings, logging
warnings.filterwarnings('ignore')
logging.captureWarnings(True)

fp = "dati/giornaliero btp.txt"
with open(fp) as f:
    fl = f.readline().strip()
has_h = any(c.isalpha() for c in fl.replace(',','').replace('.',''))
if has_h:
    df = pd.read_csv(fp, sep=r'\s+', decimal=',', parse_dates=['data'], dayfirst=True)
    df.rename(columns={'data':'Datetime','close':'Close','open':'Open','high':'High','low':'Low','volume':'Volume'}, inplace=True)
else:
    df = pd.read_csv(fp, sep=r'\s+', decimal=',', header=None,
                     names=['Datetime','High','Low','Open','Close','Volume'], parse_dates=['Datetime'], dayfirst=True)
df.set_index('Datetime', inplace=True)
df.sort_index(inplace=True)

dc = df['Close'].resample('W-FRI').count()
w = df.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
w = w[dc >= 3].dropna().copy()
w['Return'] = w['Close'].pct_change()

# Forward 1-week max excursion
w['Fwd_High'] = w['High'].shift(-1)
w['Fwd_Low'] = w['Low'].shift(-1)
w['Fwd_Move_Up'] = w['Fwd_High'] / w['Close'] - 1
w['Fwd_Move_Down'] = w['Fwd_Low'] / w['Close'] - 1
w['Fwd_Max_Abs'] = np.maximum(w['Fwd_Move_Up'], -w['Fwd_Move_Down'])

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
    if w['State'].iloc[i] == 'Sideways':
        cnt += 1
    else:
        cnt = 0
    w.iloc[i, w.columns.get_loc('Consec_SW')] = cnt

w['Vol_PctRank'] = w['Vol'].expanding().rank(pct=True)

print("=" * 80)
print("  ESCURSIONE 1-SETTIMANA CONDIZIONATA AI FILTRI")
print("=" * 80)
print(f"Totale settimane: {len(w)} ({w.index[0].date()} -> {w.index[-1].date()})")
print()

# Unconditional distribution
uncond_up_95 = w['Fwd_Move_Up'].quantile(0.95)
uncond_up_99 = w['Fwd_Move_Up'].quantile(0.99)
uncond_dn_05 = w['Fwd_Move_Down'].quantile(0.05)
uncond_dn_01 = w['Fwd_Move_Down'].quantile(0.01)
uncond_max_95 = w['Fwd_Max_Abs'].quantile(0.95)

print(f"INCONDIZIONATO (tutte le settimane):")
print(f"  Max rialzo 95° percentile:   {uncond_up_95:+.4%}")
print(f"  Max ribasso 5° percentile:   {uncond_dn_05:+.4%}")
print(f"  Escursione max 95° perc:     {uncond_max_95:.4%}")
print(f"  Range 90% (5°-95°):          {uncond_dn_05:+.4%} a {uncond_up_95:+.4%}")
print()

# Define filters to test
filters_list = [
    ('Tutte (base)', pd.Series(True, index=w.index)),
    ('Sideways', w['State'] == 'Sideways'),
    ('SW+Consec2', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 2)),
    ('SW+Consec3', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3)),
    ('SW+Consec4', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 4)),
    ('SW+Consec5', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 5)),
    ('SW+Consec6', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 6)),
    ('SW+HMM', (w['State'] == 'Sideways') & (w['HMM'] == 'Sideways')),
    ('SW+HMM+Consec3', (w['State'] == 'Sideways') & (w['HMM'] == 'Sideways') & (w['Consec_SW'] >= 3)),
    ('SW+HMM+Consec4', (w['State'] == 'Sideways') & (w['HMM'] == 'Sideways') & (w['Consec_SW'] >= 4)),
    ('SW+Vol<25%', (w['State'] == 'Sideways') & (w['Vol_PctRank'] < 0.25)),
    ('SW+Vol<15%', (w['State'] == 'Sideways') & (w['Vol_PctRank'] < 0.15)),
    ('SW+Vol<10%', (w['State'] == 'Sideways') & (w['Vol_PctRank'] < 0.10)),
    ('SW+Consec3+Vol<25%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3) & (w['Vol_PctRank'] < 0.25)),
    ('SW+Consec3+Vol<15%', (w['State'] == 'Sideways') & (w['Consec_SW'] >= 3) & (w['Vol_PctRank'] < 0.15)),
]

print(f"{'Filtro':25s} {'N':>4} {'%':>5} {'P(SW)':>7} {'Up95':>8} {'Dn05':>8} {'Range90':>8} {'Max95':>8} {'Max99':>9}")
print("-" * 85)

for name, mask in filters_list:
    sub = w[mask]
    n = len(sub)
    if n < 5:
        continue
    p_sw_next = ((sub['State'].shift(-1) == 'Sideways').mean()) if n > 1 else float('nan')
    up95 = sub['Fwd_Move_Up'].quantile(0.95)
    dn05 = sub['Fwd_Move_Down'].quantile(0.05)
    max95 = sub['Fwd_Max_Abs'].quantile(0.95)
    max99 = sub['Fwd_Max_Abs'].quantile(0.99)
    print(f"{name:25s} {n:>4} {n/len(w)*100:>4.0f}% {p_sw_next:>6.1%} {up95:>7.2%} {dn05:>7.2%} {(up95-dn05):>7.2%} {max95:>7.2%} {max99:>8.2%}")

print()
print("NOTE:")
print("- Up95 = 95° percentile del max rialzo settimanale")
print("- Dn05 = 5° percentile del max ribasso settimanale (tipicamente negativo)")
print("- Range90 = ampiezza dal 5° al 95° percentile")
print("- Max95 = 95° percentile del movimento massimo assoluto (up o down)")
print("- Max99 = 99° percentile del movimento massimo assoluto")
