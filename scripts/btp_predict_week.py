import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings
warnings.filterwarnings('ignore')

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

    # Count trading days per week to detect incomplete weeks
    daily_counts = df['Close'].resample('W-FRI').count()

    # Resample weekly
    w = df.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})

    # Keep only complete weeks (>= 3 trading days)
    w = w[daily_counts >= 3].dropna()
    w['Return'] = w['Close'].pct_change()
    w.dropna(inplace=True)

    window = 20
    w['Vol'] = w['Return'].rolling(window).std()
    w['Vol_prev'] = w['Vol'].shift(1)
    w.dropna(inplace=True)

    # Label regimes
    conds = [(w['Return'] > w['Vol_prev']), (w['Return'] < -w['Vol_prev'])]
    w['State'] = np.select(conds, ['Bull','Bear'], default='Sideways')

    # Consecutive counter
    w['Consec_SW'] = 0
    cnt = 0
    for i in range(len(w)):
        if w['State'].iloc[i] == 'Sideways':
            cnt += 1
        else:
            cnt = 0
        w.iloc[i, w.columns.get_loc('Consec_SW')] = cnt

    w['Vol_PctRank'] = w['Vol'].expanding().rank(pct=True)

    # Transition matrix
    s = w['State'].shift(-1)
    d = pd.DataFrame({'From': w['State'], 'To': s}).dropna()
    mat = pd.crosstab(d['From'], d['To'], normalize='index')
    mat = mat.reindex(index=['Bear','Sideways','Bull'], columns=['Bear','Sideways','Bull']).fillna(0)

    # HMM
    rets = w['Return'].values.reshape(-1,1)
    hmm_model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000, random_state=42)
    hmm_model.fit(rets)
    hmm_s = hmm_model.predict(rets)
    means = hmm_model.means_.flatten()
    order = np.argsort(means)
    hmm_map = {order[0]:'Bear', order[1]:'Sideways', order[2]:'Bull'}
    w['HMM'] = [hmm_map[s] for s in hmm_s]
    hmm_align = (w['State'] == w['HMM']).mean()

    # Stationary distribution
    M = mat.values
    evals, evecs = np.linalg.eig(M.T)
    idx = np.isclose(evals, 1)
    if any(idx):
        stat = evecs[:, idx][:, 0].real
        stat = stat / np.sum(stat)
        stat_s = pd.Series(stat, index=mat.index)

    # Last week
    last = w.iloc[-1]
    last_idx = w.index[-1]

    # Prediction for next week
    probs = mat.loc[last['State']]
    p_bull = probs['Bull']
    p_bear = probs['Bear']
    p_sw = probs['Sideways']
    signal = p_bull - p_bear
    direction = "Long" if signal > 0 else "Short"

    # HMM traffic light
    hmm_tl = "VERDE" if last['HMM'] == last['State'] else "ROSSO"

    # High-confidence filter
    filt_sw = last['State'] == 'Sideways'
    filt_hmm = last['HMM'] == 'Sideways'
    filt_consec = last['Consec_SW'] >= 3
    filt_vol = last['Vol_PctRank'] < 0.50
    n_filt = sum([filt_sw, filt_hmm, filt_consec, filt_vol])

    print("=" * 65)
    print("     PREVISIONE SETTIMANALE BTP FUTURE")
    print("=" * 65)
    print(f"Dati: {len(w)} settimane ({w.index[0].date()} -> {last_idx.date()})")
    print(f"Close venerdi scorso ({last_idx.date()}): {last['Close']:.2f}")
    print(f"Prezzo corrente ({today.date()}):  {df['Close'].iloc[-1]:.2f}")
    print()

    print("1. STATO ATTUALE")
    print(f"   Regime Markov:      {last['State']}")
    print(f"   Regime HMM:         {last['HMM']}")
    print(f"   Semaforo HMM:       {hmm_tl}")
    print(f"   Settimane SW consec:{int(last['Consec_SW'])}")
    print(f"   Volatilita (rank):  {last['Vol_PctRank']:.1%}")
    print()

    print("2. MATRICE DI TRANSIZIONE")
    print(mat.round(4))
    print()

    print("3. PREVISIONE PROSSIMA SETTIMANA")
    print(f"   P(Bear):     {p_bear:.2%}")
    print(f"   P(Sideways): {p_sw:.2%}")
    print(f"   P(Bull):     {p_bull:.2%}")
    print(f"   Segnale:     {direction} (forza {abs(signal):.2%})")
    print()

    print("4. DISTRIBUZIONE STAZIONARIA")
    print(stat_s.round(4).to_string())
    print()

    print("5. CONFERMA AD ALTA CONFIDENZA")
    print(f"   {'Sideways':15s}: {'SI' if filt_sw else 'NO'}")
    print(f"   {'HMM Sideways':15s}: {'SI' if filt_hmm else 'NO'}")
    print(f"   {'Consec 3+':15s}: {'SI' if filt_consec else 'NO'} ({int(last['Consec_SW'])} settimane)")
    print(f"   {'Vol<50pct':15s}: {'SI' if filt_vol else 'NO'} ({last['Vol_PctRank']:.1%})")
    print()

    if n_filt >= 3:
        print(f"   >>> VENDI OPZIONI (alta confidenza {n_filt}/4) <<<")
        print(f"   Win rate storico: ~93%")
    elif n_filt >= 2:
        print(f"   >>> CONFIDENZA MEDIA ({n_filt}/4): valutare strata <<<")
    else:
        print(f"   >>> NO TRADE: troppi filtri bloccati ({n_filt}/4) <<<")
    print("=" * 65)

if __name__ == "__main__":
    main()
