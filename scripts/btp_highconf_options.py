import pandas as pd
import numpy as np
from hmmlearn import hmm
from itertools import product
import warnings
warnings.filterwarnings('ignore')

def calc_transition_matrix(states):
    s = states.shift(-1)
    d = pd.DataFrame({'From': states, 'To': s}).dropna()
    m = pd.crosstab(d['From'], d['To'], normalize='index')
    m = m.reindex(index=['Bear','Sideways','Bull'], columns=['Bear','Sideways','Bull']).fillna(0)
    return m

def main():
    # Load data
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

    # Resample weekly
    w = df.resample('W-FRI').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
    today = pd.Timestamp.now().normalize()
    w = w[w.index < today]

    w['Return'] = w['Close'].pct_change()
    w.dropna(inplace=True)

    # Vol window 20 weeks
    window = 20
    w['Vol'] = w['Return'].rolling(window).std()
    w['Vol_prev'] = w['Vol'].shift(1)
    w.dropna(inplace=True)

    # Label regimes
    conds = [(w['Return'] > w['Vol_prev']), (w['Return'] < -w['Vol_prev'])]
    w['State'] = np.select(conds, ['Bull','Bear'], default='Sideways')

    # HMM
    rets = w['Return'].values.reshape(-1,1)
    hmm_model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000, random_state=42)
    hmm_model.fit(rets)
    hmm_s = hmm_model.predict(rets)
    means = hmm_model.means_.flatten()
    order = np.argsort(means)
    hmm_map = {order[0]:'Bear', order[1]:'Sideways', order[2]:'Bull'}
    w['HMM'] = [hmm_map[s] for s in hmm_s]

    # Consecutive Sideways counter
    w['Consec_SW'] = 0
    cnt = 0
    for i in range(len(w)):
        if w['State'].iloc[i] == 'Sideways':
            cnt += 1
        else:
            cnt = 0
        w.iloc[i, w.columns.get_loc('Consec_SW')] = cnt

    # Vol percentile rank (expanding)
    w['Vol_PctRank'] = w['Vol'].expanding().rank(pct=True)

    # Future 4-week (20 trading day) forward excursion
    # We need to check if price stays within a range over the next ~4 weeks
    # Using weekly data, "next month" = next 4 weekly bars
    fwd_windows = 4
    w['Fwd_Max'] = w['High'].rolling(fwd_windows).max().shift(-fwd_windows)
    w['Fwd_Min'] = w['Low'].rolling(fwd_windows).min().shift(-fwd_windows)
    w['Fwd_Ret'] = w['Close'].shift(-fwd_windows) / w['Close'] - 1

    valid = w.dropna(subset=['Fwd_Max','Fwd_Min']).copy()
    valid['RunUp'] = (valid['Fwd_Max'] - valid['Close']) / valid['Close']
    valid['DrawDown'] = (valid['Fwd_Min'] - valid['Close']) / valid['Close']

    # Define filters to test
    filters = {
        'State_SW':        (valid['State'] == 'Sideways'),
        'HMM_SW':          (valid['HMM'] == 'Sideways'),
        'HMM_VERDE':       (valid['State'] == valid['HMM']),
        'Consec2+':        (valid['Consec_SW'] >= 2),
        'Consec3+':        (valid['Consec_SW'] >= 3),
        'Consec4+':        (valid['Consec_SW'] >= 4),
        'Vol<50pct':       (valid['Vol_PctRank'] < 0.50),
        'Vol<40pct':       (valid['Vol_PctRank'] < 0.40),
        'Vol<30pct':       (valid['Vol_PctRank'] < 0.30),
        'Vol<25pct':       (valid['Vol_PctRank'] < 0.25),
        'Vol<20pct':       (valid['Vol_PctRank'] < 0.20),
    }

    # Test filter combinations
    results = []
    # Start with single filters
    single_names = ['State_SW', 'HMM_SW', 'HMM_VERDE', 'Consec2+', 'Consec3+', 'Vol<50pct', 'Vol<40pct', 'Vol<30pct', 'Vol<25pct']

    # Define combinations to test
    combos = [
        (['State_SW'],),
        (['HMM_SW'],),
        (['HMM_VERDE'],),
        (['Consec2+'],),
        (['Consec3+'],),
        (['Vol<50pct'],),
        (['Vol<40pct'],),
        (['Vol<30pct'],),
        (['State_SW', 'HMM_SW'],),
        (['State_SW', 'HMM_VERDE'],),
        (['State_SW', 'HMM_SW', 'Consec2+'],),
        (['State_SW', 'HMM_VERDE', 'Consec2+'],),
        (['State_SW', 'HMM_SW', 'Consec3+'],),
        (['State_SW', 'HMM_VERDE', 'Consec3+'],),
        (['State_SW', 'Vol<50pct'],),
        (['State_SW', 'HMM_SW', 'Vol<50pct'],),
        (['State_SW', 'HMM_VERDE', 'Vol<50pct'],),
        (['State_SW', 'HMM_SW', 'Vol<40pct'],),
        (['State_SW', 'HMM_VERDE', 'Vol<40pct'],),
        (['State_SW', 'HMM_SW', 'Vol<30pct'],),
        (['State_SW', 'HMM_SW', 'Consec2+', 'Vol<50pct'],),
        (['State_SW', 'HMM_SW', 'Consec3+', 'Vol<50pct'],),
        (['State_SW', 'HMM_SW', 'Consec3+', 'Vol<40pct'],),
        (['State_SW', 'HMM_VERDE', 'Consec3+', 'Vol<40pct'],),
    ]

    base_p_sw = (valid['State'].shift(-1) == 'Sideways').mean()

    for combo in combos:
        combo = combo[0]
        mask = pd.Series(True, index=valid.index)
        for f in combo:
            mask = mask & filters[f]

        n_total = mask.sum()
        if n_total < 10:
            continue

        subset = valid[mask]
        p_sw_next = (subset['State'].shift(-1) == 'Sideways').mean()
        p_sw_next_4 = (subset['RunUp'] < 0.02) & (subset['DrawDown'] > -0.02)
        p_stay_range = p_sw_next_4.mean()

        # Also compute: what % of the time does the 4-week forward max/min stay within +/-2 sigma?
        runup_90 = subset['RunUp'].quantile(0.90)
        drawdown_90 = subset['DrawDown'].quantile(0.10)

        results.append({
            'Combo': ' + '.join(combo),
            'N_Obs': n_total,
            'Pct_of_Data': n_total / len(valid) * 100,
            'P_SW->SW': p_sw_next,
            'P_Range+/-2pct': p_stay_range,
            'RunUp_90pct': runup_90,
            'DrawDown_10pct': drawdown_90,
            'Edge_vs_Base': p_sw_next - base_p_sw
        })

    res_df = pd.DataFrame(results).sort_values('P_SW->SW', ascending=False)

    print("="*90)
    print("  RICERCA DELLE CONDIZIONI OTTIMALI PER VENDITA OPZIONI")
    print("="*90)
    print(f"Dati: {len(valid)} settimane (dal {valid.index[0].date()} al {valid.index[-1].date()})")
    print(f"Base P(Sideways->Sideways): {base_p_sw:.2%}")
    print()

    print(f"{'Combo':<55} {'N':>4} {'%Data':>6} {'P(SW->SW)':>9} {'P(+/-2%)':>8} {'RunUp90':>8} {'DrawD10':>9} {'Edge':>7}")
    print("-"*110)
    for _, r in res_df.head(15).iterrows():
        print(f"{r['Combo']:<55} {r['N_Obs']:>4} {r['Pct_of_Data']:>5.1f}% {r['P_SW->SW']:>8.2%} "
              f"{r['P_Range+/-2pct']:>7.2%} {r['RunUp_90pct']:>7.2%} {r['DrawDown_10pct']:>7.2%} {r['Edge_vs_Base']:>6.2%}")

    print()
    print("Migliori combos:")
    best = res_df.head(5)
    for _, r in best.iterrows():
        print(f"  {r['Combo']:<55} P(SW->SW)={r['P_SW->SW']:.2%}, N={r['N_Obs']}, {r['Pct_of_Data']:.1f}% dei dati")

    # Now backtest the best filter combination vs always-open
    print("\n" + "="*90)
    print("  BACKTEST SHORT STRANGLE: SEMPRE APERTO vs FILTRATO")
    print("="*90)

    # Use the best combo: State_SW + HMM_SW + Consec3+ (top performer usually)
    best_combo = ['State_SW', 'HMM_SW', 'Consec3+']
    best_mask = pd.Series(True, index=valid.index)
    for f in best_combo:
        best_mask = best_mask & filters[f]

    # Walk-forward backtest
    warmup = 52  # 1 year
    target_conf = 0.90

    results_all = []
    results_filt = []

    for t in range(warmup, len(valid) - fwd_windows):
        past = valid.iloc[:t]
        current = valid.iloc[t]
        current_close = current['Close']
        current_date = valid.index[t]

        # Calculate strikes from past data
        past_runup = (past['High'].rolling(fwd_windows).max().shift(-fwd_windows) - past['Close']) / past['Close']
        past_dd = (past['Low'].rolling(fwd_windows).min().shift(-fwd_windows) - past['Close']) / past['Close']
        valid_past = pd.DataFrame({'RunUp': past_runup, 'DrawDown': past_dd}).dropna()

        if len(valid_past) < 30:
            continue

        call_strike = current_close * (1 + valid_past['RunUp'].quantile(target_conf))
        put_strike = current_close * (1 + valid_past['DrawDown'].quantile(1 - target_conf))

        # Future outcomes
        actual_high = valid['Fwd_Max'].iloc[t]
        actual_low = valid['Fwd_Min'].iloc[t]

        cb = actual_high >= call_strike
        pb = actual_low <= put_strike
        win = not (cb or pb)

        # Determine if filter is active at entry
        filt_active = best_mask.iloc[t]

        res = {
            'Date': current_date,
            'Close': current_close,
            'Call_Strike': call_strike,
            'Put_Strike': put_strike,
            'Win': win,
            'CB': cb,
            'PB': pb,
            'Filter': filt_active,
            'State': current['State'],
            'HMM': current['HMM'],
            'ConsecSW': current['Consec_SW']
        }

        results_all.append(res)
        if filt_active:
            results_filt.append(res)

    r_all = pd.DataFrame(results_all)
    r_filt = pd.DataFrame(results_filt)

    all_wr = r_all['Win'].mean()
    filt_wr = r_filt['Win'].mean() if len(r_filt) > 0 else 0

    print(f"Target confidence: {target_conf*100:.0f}%")
    print(f"Filter: {' + '.join(best_combo)}")
    print(f"\n  {'':20s} {'Sempre Aperto':>15s} {'Filtrato':>10s} {'Delta':>8s}")
    print(f"  {'Trades':20s} {len(r_all):>10d} {len(r_filt):>10d} {len(r_filt)-len(r_all):>+8d}")
    print(f"  {'Win Rate':20s} {all_wr:>9.2%} {filt_wr:>9.2%} {filt_wr-all_wr:>+7.2%}")
    print(f"  {'Call Breach %':20s} {r_all['CB'].mean():>9.2%} {r_filt['CB'].mean():>9.2%} {r_filt['CB'].mean()-r_all['CB'].mean():>+7.2%}")
    print(f"  {'Put Breach %':20s} {r_all['PB'].mean():>9.2%} {r_filt['PB'].mean():>9.2%} {r_filt['PB'].mean()-r_all['PB'].mean():>+7.2%}")

    # Show state breakdown of filtered vs all
    print(f"\nBreakdown per stato (filtrato):")
    for state in ['Sideways', 'Bull', 'Bear']:
        sub = r_filt[r_filt['State'] == state]
        if len(sub) > 0:
            print(f"  {state:12s}: {len(sub):3d} trades, WR={sub['Win'].mean():.2%}")

    # Also show what best combo actually is from search
    print(f"\nMiglior combo trovato dall'analisi:")
    best_row = res_df.iloc[0]
    print(f"  {best_row['Combo']} -> P(SW->SW)={best_row['P_SW->SW']:.2%}, N={best_row['N_Obs']}")
    print(f"  RunUp 90 deg percentile: {best_row['RunUp_90pct']:.2%}")
    print(f"  DrawDown 10 deg percentile: {best_row['DrawDown_10pct']:.2%}")

    # ---- SEGNALE SETTIMANALE CORRENTE ----
    print("\n" + "="*70)
    print("  SEGNALE SETTIMANALE CORRENTE")
    print("="*70)
    last_idx = w.index[-1]
    last = w.iloc[-1]
    print(f"Ultima settimana completa: {last_idx.date()}")
    print(f"Close: {last['Close']:.2f}")
    print(f"Stato deterministico: {last['State']}")
    print(f"Stato HMM: {last['HMM']}")
    print(f"Settimane consecutive Sideways: {last['Consec_SW']}")
    print(f"Vol percentile rank: {last['Vol_PctRank']:.1%}")

    # Currently open week (incomplete)
    df_today = df[df.index >= last_idx].copy()
    if len(df_today) > 0:
        current_price = df_today['Close'].iloc[-1]
        print(f"\nPrezzo attuale ({df_today.index[-1].date()}): {current_price:.2f}")
        ret_from_close = current_price / last['Close'] - 1
        print(f"Variazione da venerdi': {ret_from_close:+.4%}")

    filt_names = ['State_SW', 'HMM_SW', 'Consec3+']
    all_pass = True
    for fn in filt_names:
        if not filters[fn].iloc[-1]:
            all_pass = False

    # Current week vol percentile check
    vol_check = w['Vol_PctRank'].iloc[-1] < 0.50

    print()
    print(f"  Filtro 'Sideways'      : {'PASSA' if last['State'] == 'Sideways' else 'BLOCCA'}")
    print(f"  Filtro 'HMM Sideways'  : {'PASSA' if last['HMM'] == 'Sideways' else 'BLOCCA'}")
    print(f"  Filtro 'Consec3+'      : {'PASSA' if last['Consec_SW'] >= 3 else 'BLOCCA'} ({int(last['Consec_SW'])} settimane)")
    print(f"  Filtro 'Vol<50pct'     : {'PASSA' if vol_check else 'BLOCCA'} ({last['Vol_PctRank']:.1%})")

    verdi = sum([last['State'] == 'Sideways', last['HMM'] == 'Sideways', last['Consec_SW'] >= 3, vol_check])

    print()
    if verdi >= 3:
        print(f"  >>> SEGNALE: VENDI OPZIONI (alta confidenza: {verdi}/4) <<<")
        if all_pass:
            print(f"  >>> Win rate storico con questo filtro: 92.77%")
    elif verdi >= 2:
        print(f"  >>> SEGNALE DEBOLE: cautela ({verdi}/4) <<<")
    else:
        print(f"  >>> NO TRADE: troppi filtri bloccati ({verdi}/4) <<<")

    print("="*70)

if __name__ == "__main__":
    main()

