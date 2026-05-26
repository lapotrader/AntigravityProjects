import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings
warnings.filterwarnings('ignore')
import logging
logging.captureWarnings(True)

def main():
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

    today = pd.Timestamp.now().normalize()
    dc = df['Close'].resample('W-FRI').count()
    w = df.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
    w = w[dc >= 3].dropna().copy()
    w['Return'] = w['Close'].pct_change()
    w.dropna(inplace=True)

    window = 20
    w['Vol'] = w['Return'].rolling(window).std()

    # Need at least 20+1 weeks of warmup before we can start
    warmup = window + 1

    results = []

    for t in range(warmup, len(w) - 1):
        past = w.iloc[:t+1].copy()
        cur = w.iloc[t]
        future = w.iloc[t+1]

        # Vol threshold
        vol_prev = past['Vol'].iloc[-1]
        ret = cur['Return']

        # Label current week
        state = 'Sideways'
        if ret > vol_prev:
            state = 'Bull'
        elif ret < -vol_prev:
            state = 'Bear'

        # HMM on past data
        past_rets = past['Return'].values.reshape(-1,1)
        hm = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=500, random_state=42)
        hm.fit(past_rets)
        hs = hm.predict(past_rets)
        means = hm.means_.flatten()
        order = np.argsort(means)
        hmm_map = {order[0]:'Bear', order[1]:'Sideways', order[2]:'Bull'}
        hmm_state = hmm_map[hs[-1]]

        # Consecutive SW
        consec = 0
        for i in range(t, -1, -1):
            ret_i = w['Return'].iloc[i]
            vol_i = past['Vol'].iloc[i]
            if abs(ret_i) <= vol_i:
                consec += 1
            else:
                break

        # Vol percentile
        vol_pct = (past['Vol'] < past['Vol'].iloc[-1]).mean()

        # Transition matrix
        states_series = past['State'] if 'State' in past else pd.Series(index=past.index)
        # Actually compute state for all past weeks
        past_states = []
        for i in range(len(past)):
            ri = past['Return'].iloc[i]
            vi = past['Vol'].iloc[i]
            if ri > vi:
                past_states.append('Bull')
            elif ri < -vi:
                past_states.append('Bear')
            else:
                past_states.append('Sideways')
        past['State'] = past_states

        s = past['State'].shift(-1)
        d = pd.DataFrame({'From': past['State'], 'To': s}).dropna()
        mat = pd.crosstab(d['From'], d['To'], normalize='index')
        mat = mat.reindex(index=['Bear','Sideways','Bull'], columns=['Bear','Sideways','Bull']).fillna(0)

        # Future state
        fwd_ret = future['Return']
        fwd_vol = past['Vol'].iloc[-1]
        future_state = 'Sideways'
        if fwd_ret > fwd_vol:
            future_state = 'Bull'
        elif fwd_ret < -fwd_vol:
            future_state = 'Bear'

        # Prediction from matrix
        probs = mat.loc[state] if state in mat.index else pd.Series({'Bear':0,'Sideways':1,'Bull':0})
        pred_state = probs.idxmax()
        pred_correct = (pred_state == future_state)

        # Directional signal
        sig = probs['Bull'] - probs['Bear']
        dir_correct = (sig > 0 and fwd_ret > 0) or (sig < 0 and fwd_ret < 0)

        # Filter checks
        f_sw = (state == 'Sideways')
        f_hmm = (hmm_state == 'Sideways')
        f_consec = (consec >= 3)
        f_vol50 = (vol_pct < 0.50)
        n_filt = sum([f_sw, f_hmm, f_consec, f_vol50])
        all_pass = (f_sw and f_hmm and f_consec and f_vol50)

        results.append({
            'Date': w.index[t],
            'Close': cur['Close'],
            'State': state,
            'HMM': hmm_state,
            'Future_State': future_state,
            'Pred_State': pred_state,
            'Pred_Correct': pred_correct,
            'Fwd_Ret': fwd_ret,
            'Signal': sig,
            'Dir_Correct': dir_correct,
            'Consec_SW': consec,
            'Vol_Pct': vol_pct,
            'F_SW': f_sw,
            'F_HMM': f_hmm,
            'F_Consec': f_consec,
            'F_Vol50': f_vol50,
            'N_Filt': n_filt,
            'All_Filt': all_pass
        })

    r = pd.DataFrame(results)

    print("=" * 70)
    print("  STATISTICA 1-SETTIMANA: WALK-FORWARD COMPLETO")
    print("=" * 70)
    print(f"Periodo: {w.index[warmup].date()} -> {w.index[-2].date()}")
    print(f"Settimane testate: {len(r)}")
    print()

    # 1. Overall prediction accuracy
    print("1. ACCURATEZZA PREDITTIVA (Markov) - TUTTE")
    base_acc = r['Pred_Correct'].mean()
    print(f"   Hit Rate predizione stato Markov: {base_acc:.2%}")

    # 2. By current state
    print(f"\n2. HIT RATE PER STATO CORRENTE")
    for state in ['Sideways', 'Bull', 'Bear']:
        sub = r[r['State'] == state]
        if len(sub) > 0:
            acc = sub['Pred_Correct'].mean()
            fwd_sw = (sub['Future_State'] == 'Sideways').mean()
            print(f"   {state:12s}: hit={acc:.2%}, P(SW next)={fwd_sw:.2%}, N={len(sub)}")

    # 3. By filter combination
    print(f"\n3. HIT RATE PER NUMERO FILTRI ATTIVI")
    for nf in range(5):
        sub = r[r['N_Filt'] == nf]
        if len(sub) > 0:
            acc = sub['Pred_Correct'].mean()
            dir_acc = sub['Dir_Correct'].mean()
            p_sw_next = (sub['Future_State'] == 'Sideways').mean()
            print(f"   {nf}/4 filtri: hit={acc:.2%}, dir={dir_acc:.2%}, P(SW)={p_sw_next:.2%}, N={len(sub)}")

    # 4. Specific combos
    print(f"\n4. HIT RATE COMBINAZIONI SPECIFICHE")
    combos = [
        ('Solo FW', r['F_SW']),
        ('SW + HMM', r['F_SW'] & r['F_HMM']),
        ('SW + HMM + Consec3', r['F_SW'] & r['F_HMM'] & r['F_Consec']),
        ('SW + HMM + Vol<50', r['F_SW'] & r['F_HMM'] & r['F_Vol50']),
        ('SW + HMM + Consec3 + Vol50', r['F_SW'] & r['F_HMM'] & r['F_Consec'] & r['F_Vol50']),
        ('SW + Vol<50', r['F_SW'] & r['F_Vol50']),
        ('SW + Consec2', r['F_SW'] & (r['Consec_SW'] >= 2)),
        ('SW + Consec3', r['F_SW'] & r['F_Consec']),
        ('Tutti 4 filtri', r['All_Filt']),
    ]
    print(f"   {'Combo':30s} {'Hit':>7} {'Dir':>7} {'P(SW)':>7} {'N':>5} {'%Data':>7}")
    print(f"   {'-'*60}")
    for name, mask in combos:
        sub = r[mask]
        if len(sub) > 0:
            hit = sub['Pred_Correct'].mean()
            dir_hit = sub['Dir_Correct'].mean()
            p_sw = (sub['Future_State'] == 'Sideways').mean()
            print(f"   {name:30s} {hit:>6.2%} {dir_hit:>6.2%} {p_sw:>6.2%} {len(sub):>4} {len(sub)/len(r):>6.2%}")

    # 5. HMM traffic light analysis
    print(f"\n5. HMM TRAFFIC LIGHT")
    verde = r[r['State'] == r['HMM']]
    rosso = r[r['State'] != r['HMM']]
    print(f"   VERDE: hit={verde['Pred_Correct'].mean():.2%}, P(SW)={(verde['Future_State']=='Sideways').mean():.2%}, N={len(verde)}")
    print(f"   ROSSO: hit={rosso['Pred_Correct'].mean():.2%}, P(SW)={(rosso['Future_State']=='Sideways').mean():.2%}, N={len(rosso)}")

    # 6. Directional accuracy
    print(f"\n6. ACCURATEZZA DIREZIONALE (Long/Short)")
    print(f"   Tutti i segnali:    {r['Dir_Correct'].mean():.2%}")
    for state in ['Sideways', 'Bull', 'Bear']:
        sub = r[r['State'] == state]
        if len(sub) > 0:
            print(f"   Da {state:12s}: {sub['Dir_Correct'].mean():.2%} (N={len(sub)})")

    print("=" * 70)

if __name__ == "__main__":
    main()
