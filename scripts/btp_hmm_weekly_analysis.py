import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings
warnings.filterwarnings('ignore')

def calculate_transition_matrix(states):
    states_shifted = states.shift(-1)
    df_trans = pd.DataFrame({'From': states, 'To': states_shifted}).dropna()
    mat = pd.crosstab(df_trans['From'], df_trans['To'], normalize='index')
    order = ['Bear', 'Sideways', 'Bull']
    mat = mat.reindex(index=order, columns=order).fillna(0)
    return mat

def main():
    file_path = "dati/giornaliero btp.txt"
    with open(file_path, 'r') as f:
        first_line = f.readline().strip()
    has_header = any(c.isalpha() for c in first_line.replace(',', '').replace('.', ''))

    if has_header:
        df = pd.read_csv(file_path, sep=r'\s+', decimal=',', parse_dates=['data'], dayfirst=True)
        df.rename(columns={'data': 'Datetime', 'close': 'Close', 'open': 'Open', 'high': 'High', 'low': 'Low', 'volume': 'Volume'}, inplace=True)
    else:
        df = pd.read_csv(file_path, sep=r'\s+', decimal=',', header=None, names=['Datetime', 'High', 'Low', 'Open', 'Close', 'Volume'], parse_dates=['Datetime'], dayfirst=True)

    df.set_index('Datetime', inplace=True)
    df.sort_index(inplace=True)

    # Resample to weekly: agg high=max, low=min, open=first, close=last, volume=sum
    weekly = df.resample('W-FRI').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Volume': 'sum'
    }).dropna()

    # Exclude current incomplete week
    today = pd.Timestamp.now().normalize()
    weekly = weekly[weekly.index < today]

    print(f"Total weekly bars: {len(weekly)} (from {weekly.index[0].date()} to {weekly.index[-1].date()})")

    # Weekly returns
    weekly['Return'] = weekly['Close'].pct_change()
    weekly.dropna(inplace=True)
    print(f"Weekly bars after return calc: {len(weekly)}")

    # Adaptive Regime with 20-week volatility window (approx 1 trading year)
    window = 20
    weekly['Vol_rolling'] = weekly['Return'].rolling(window=window).std()
    weekly['Vol_rolling_prev'] = weekly['Vol_rolling'].shift(1)
    weekly.dropna(inplace=True)

    # Labeling
    conditions = [
        (weekly['Return'] > weekly['Vol_rolling_prev']),
        (weekly['Return'] < -weekly['Vol_rolling_prev'])
    ]
    choices = ['Bull', 'Bear']
    weekly['State'] = np.select(conditions, choices, default='Sideways')

    print(f"\nState counts:")
    print(weekly['State'].value_counts())

    # Transition Matrix
    current_matrix = calculate_transition_matrix(weekly['State'])
    print(f"\n--- Transition Matrix (Weekly) ---")
    print(current_matrix.round(4))

    # Stickiness
    stickiness = np.diag(current_matrix)
    print(f"\n--- Stickiness ---")
    for state, stick in zip(['Bear', 'Sideways', 'Bull'], stickiness):
        print(f"  {state}: {stick:.2%}")

    # Matrix Squaring
    M = current_matrix.values
    M2 = np.linalg.matrix_power(M, 2)
    M3 = np.linalg.matrix_power(M, 3)
    M4 = np.linalg.matrix_power(M, 4)

    M2_df = pd.DataFrame(M2, index=current_matrix.index, columns=current_matrix.columns)
    M3_df = pd.DataFrame(M3, index=current_matrix.index, columns=current_matrix.columns)
    M4_df = pd.DataFrame(M4, index=current_matrix.index, columns=current_matrix.columns)

    print(f"\n--- M^2 (2 weeks) ---")
    print(M2_df.round(4))
    print(f"\n--- M^3 (3 weeks) ---")
    print(M3_df.round(4))
    print(f"\n--- M^4 (4 weeks) ---")
    print(M4_df.round(4))

    # Stationary Distribution
    eigenvals, eigenvecs = np.linalg.eig(M.T)
    idx = np.isclose(eigenvals, 1)
    if any(idx):
        stationary = eigenvecs[:, idx][:, 0].real
        stationary = stationary / np.sum(stationary)
        stat_df = pd.Series(stationary, index=current_matrix.index)
        print(f"\n--- Stationary Distribution ---")
        print(stat_df.round(4))
    else:
        print("\nNo eigenvalue = 1 found")

    # Walk Forward Backtest (weekly)
    print(f"\n--- Walk Forward Backtest ---")
    warmup = 52  # 1 year of weekly data
    wf_results = []

    states_series = weekly['State']
    returns_series = weekly['Return']

    for t in range(warmup, len(weekly) - 1):
        past_states = states_series.iloc[:t+1]
        current_state = past_states.iloc[-1]

        states_shifted = past_states.shift(-1)
        df_trans = pd.DataFrame({'From': past_states, 'To': states_shifted}).dropna()

        if len(df_trans) < 30:
            continue

        mat = pd.crosstab(df_trans['From'], df_trans['To'], normalize='index')
        order = ['Bear', 'Sideways', 'Bull']
        mat = mat.reindex(index=order, columns=order).fillna(0)

        if current_state in mat.index:
            probs = mat.loc[current_state]
            sig = probs['Bull'] - probs['Bear']
        else:
            sig = 0.0

        next_ret = returns_series.iloc[t+1]
        is_correct = (sig > 0 and next_ret > 0) or (sig < 0 and next_ret < 0)

        wf_results.append({
            'Signal': sig,
            'Next_Return': next_ret,
            'Correct': is_correct
        })

    wf_df = pd.DataFrame(wf_results)
    active_trades = wf_df[wf_df['Signal'] != 0]
    hit_rate = active_trades['Correct'].mean() if len(active_trades) > 0 else 0
    print(f"  Weeks simulated: {len(wf_df)}")
    print(f"  Active trades: {len(active_trades)}")
    print(f"  Hit Rate: {hit_rate:.2%}")

    # HMM
    print(f"\n--- HMM Confirmation ---")
    returns = weekly['Return'].values.reshape(-1, 1)
    hmm_model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000, random_state=42)
    hmm_model.fit(returns)
    hmm_states = hmm_model.predict(returns)

    means = hmm_model.means_.flatten()
    state_order = np.argsort(means)
    bear_idx = state_order[0]
    sideways_idx = state_order[1]
    bull_idx = state_order[2]

    hmm_mapping = {
        bear_idx: 'Bear',
        sideways_idx: 'Sideways',
        bull_idx: 'Bull'
    }

    hmm_current_label = hmm_mapping[hmm_states[-1]]
    current_state = weekly['State'].iloc[-1]
    global_alignment = (weekly['State'] == [hmm_mapping[s] for s in hmm_states]).mean()
    hmm_traffic_light = "VERDE" if hmm_current_label == current_state else "ROSSO"

    # Current week prediction
    last_time = weekly.index[-1]
    probs_next = current_matrix.loc[current_state]
    p_bull = probs_next['Bull']
    p_bear = probs_next['Bear']
    signal_value = p_bull - p_bear
    direction = "Long" if signal_value > 0 else "Short" if signal_value < 0 else "Neutral"

    print(f"\n{'='*50}")
    print(f"        WEEKLY BTP HMM ANALYSIS")
    print(f"{'='*50}")
    print(f"Last complete week ending: {last_time.date()}")
    print(f"Close price: {weekly['Close'].iloc[-1]:.2f}\n")
    print(f"1. TRANSITION MATRIX:")
    print(current_matrix.round(4))
    print(f"\n2. SIGNAL FOR NEXT WEEK:")
    print(f"   -> Direction: {direction}")
    print(f"   -> Signal Strength: {abs(signal_value):.2%}")
    print(f"   -> Bear: {p_bear:.2%} | Sideways: {probs_next['Sideways']:.2%} | Bull: {p_bull:.2%}")
    print(f"\n3. HMM CONFIRMATION:")
    print(f"   -> HMM Traffic Light: {hmm_traffic_light}")
    print(f"   -> Deterministic State: {current_state} | HMM State: {hmm_current_label}")
    print(f"   -> Global Alignment: {global_alignment:.2%}")
    print(f"\n4. WALK FORWARD HIT RATE: {hit_rate:.2%}")
    print(f"\n5. STICKINESS:")
    for state, stick in zip(['Bear', 'Sideways', 'Bull'], stickiness):
        print(f"   {state}: {stick:.2%}")
    print(f"\n6. STATIONARY DISTRIBUTION:")
    print(stat_df.round(4).to_string())
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
