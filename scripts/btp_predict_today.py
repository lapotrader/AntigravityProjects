import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings
warnings.filterwarnings('ignore')

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
    
    # Escludiamo l'ultimo giorno (2026-05-26) per metterci nei panni di ieri (2026-05-25)
    df = df[df.index < '2026-05-26']
    
    df['Return'] = df['Close'].pct_change()
    df.dropna(inplace=True)
    
    window = 20
    df['Vol_rolling'] = df['Return'].rolling(window=window).std()
    df['Vol_rolling_prev'] = df['Vol_rolling'].shift(1)
    df.dropna(inplace=True)

    conditions = [
        (df['Return'] > df['Vol_rolling_prev']),
        (df['Return'] < -df['Vol_rolling_prev'])
    ]
    choices = ['Bull', 'Bear']
    df['State'] = np.select(conditions, choices, default='Sideways')
    
    current_matrix = calculate_transition_matrix(df['State'])
    
    # HMM
    returns = df['Return'].values.reshape(-1, 1)
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
    current_state = df['State'].iloc[-1]
    last_time = df.index[-1]
    
    probs_tomorrow = current_matrix.loc[current_state]
    p_bull = probs_tomorrow['Bull']
    p_bear = probs_tomorrow['Bear']
    signal_value = p_bull - p_bear
    direction = "Long" if signal_value > 0 else "Short" if signal_value < 0 else "Neutral"
    
    hmm_traffic_light = "VERDE" if hmm_current_label == current_state else "ROSSO"
    
    print("==================================================")
    print("      SIMULAZIONE CON DATI FINO A IERI (25/05/2026)")
    print("==================================================")
    print(f"Data di Chiusura Considerata: {last_time.date()}")
    print(f"Prezzo di Chiusura:           {df['Close'].iloc[-1]:.2f}")
    print(f"Stato Deterministico:         {current_state}")
    print(f"Stato HMM:                    {hmm_current_label}")
    print(f"Conferma HMM:                 {hmm_traffic_light}")
    print(f"\n1. MATRICE DI TRANSIZIONE A IERI:")
    print(current_matrix.round(4))
    print(f"\n2. PREVISIONE PER OGGI ({last_time.date()} -> 26/05/2026):")
    print(f"   -> Direzione Prevista: {direction}")
    print(f"   -> Forza del Segnale (Size): {abs(signal_value):.2%}")
    print(f"   -> Probabilità - Bear: {p_bear:.2%} | Sideways: {probs_tomorrow['Sideways']:.2%} | Bull: {p_bull:.2%}")
    print("==================================================")

def calculate_transition_matrix(states):
    states_shifted = states.shift(-1)
    df_trans = pd.DataFrame({'From': states, 'To': states_shifted}).dropna()
    mat = pd.crosstab(df_trans['From'], df_trans['To'], normalize='index')
    order = ['Bear', 'Sideways', 'Bull']
    mat = mat.reindex(index=order, columns=order).fillna(0)
    return mat

if __name__ == "__main__":
    main()
