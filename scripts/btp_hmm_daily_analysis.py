import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings
warnings.filterwarnings('ignore')

def main():
    # 1. Data Ingestion & Cleaning
    print("Loading daily data from dati/giornaliero btp.txt...")
    file_path = "dati/giornaliero btp.txt"
    # Leggiamo la prima riga per capire se c'è l'header
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
    
    # Escludiamo il giorno corrente se la barra giornaliera è ancora in formazione
    today_date = pd.Timestamp.now().normalize()
    df = df[df.index.normalize() < today_date]
    print(f"Esclusa la barra incompleta di oggi ({today_date.date()}) se presente.")
    
    # Calcolo dei rendimenti giornalieri
    df['Return'] = df['Close'].pct_change()
    df.dropna(inplace=True)
    print(f"Data loading completed. Total daily bars: {len(df)}")

    # 2. Adaptive Regime Definition (Soglia dinamica basata su 1 Deviazione Standard mobile a 20 giorni)
    print("\n--- Step 1 & 2: Definizione Adattiva ed Etichettatura ---")
    window = 20 # Finestra mobile classica a 20 giorni per la volatilità storica
    df['Vol_rolling'] = df['Return'].rolling(window=window).std()
    df['Vol_rolling_prev'] = df['Vol_rolling'].shift(1)
    df.dropna(inplace=True)

    # 3. Historical Labeling
    conditions = [
        (df['Return'] > df['Vol_rolling_prev']),
        (df['Return'] < -df['Vol_rolling_prev'])
    ]
    choices = ['Bull', 'Bear']
    df['State'] = np.select(conditions, choices, default='Sideways')
    
    print(f"Conteggio Stati Storici:")
    print(df['State'].value_counts())

    # 4. Markov Transition Matrix
    def calculate_transition_matrix(states):
        states_shifted = states.shift(-1)
        df_trans = pd.DataFrame({'From': states, 'To': states_shifted}).dropna()
        mat = pd.crosstab(df_trans['From'], df_trans['To'], normalize='index')
        order = ['Bear', 'Sideways', 'Bull']
        mat = mat.reindex(index=order, columns=order).fillna(0)
        return mat

    current_matrix = calculate_transition_matrix(df['State'])
    print("\n--- Step 4: Matrice di Transizione Attuale (Daily) ---")
    print(current_matrix.round(4))

    # 5. Stickiness Score (Diagonale della matrice)
    print("\n--- Step 5: Analisi della Persistenza (Stickiness) ---")
    stickiness = np.diag(current_matrix)
    for state, stick in zip(['Bear', 'Sideways', 'Bull'], stickiness):
        print(f"  {state}: {stick:.2%}")

    # 6. Matrix Squaring & Cubing (Previsioni a 2 e 3 giorni)
    M = current_matrix.values
    M2 = np.linalg.matrix_power(M, 2)
    M3 = np.linalg.matrix_power(M, 3)

    M2_df = pd.DataFrame(M2, index=current_matrix.index, columns=current_matrix.columns)
    M3_df = pd.DataFrame(M3, index=current_matrix.index, columns=current_matrix.columns)

    print("\n--- Step 6: Previsioni a 2 Giorni (M^2) ---")
    print(M2_df.round(4))
    print("\n--- Step 6: Previsioni a 3 Giorni (M^3) ---")
    print(M3_df.round(4))

    # 7. Stationary Distribution (Distribuzione Stazionaria)
    print("\n--- Step 7: Distribuzione Stazionaria (Lungo Termine) ---")
    eigenvals, eigenvecs = np.linalg.eig(M.T)
    idx = np.isclose(eigenvals, 1)
    if any(idx):
        stationary = eigenvecs[:, idx][:, 0].real
        stationary = stationary / np.sum(stationary)
        stat_df = pd.Series(stationary, index=current_matrix.index)
        print(stat_df.round(4))
    else:
        print("  Non è stata trovata una convergenza esatta a 1")

    # 8. Signal Generation & Walk Forward Backtest
    print("\n--- Step 9: Walk Forward Back-testing (Simulazione Dinamica) ---")
    warmup = 250  # Finestra di riscaldamento giornaliera (circa 1 anno di dati)
    wf_results = []
    
    states_series = df['State']
    returns_series = df['Return']
    
    for t in range(warmup, len(df) - 1):
        past_states = states_series.iloc[:t+1]
        current_state = past_states.iloc[-1]
        
        states_shifted = past_states.shift(-1)
        df_trans = pd.DataFrame({'From': past_states, 'To': states_shifted}).dropna()
        
        if len(df_trans) < 100:
            continue
            
        mat = pd.crosstab(df_trans['From'], df_trans['To'], normalize='index')
        order = ['Bear', 'Sideways', 'Bull']
        mat = mat.reindex(index=order, columns=order).fillna(0)
        
        if current_state in mat.index:
            probs = mat.loc[current_state]
            p_bull = probs['Bull']
            p_bear = probs['Bear']
            sig = p_bull - p_bear
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
    hit_rate = active_trades['Correct'].mean()
    print(f"  Giorni simulati nel Walk-Forward: {len(wf_df)}")
    print(f"  Direzioni previste corrette (Hit Rate): {hit_rate:.2%}")

    # 9. HMM Confirmation & Final Outputs
    print("\n--- Step 8 & 10: Generazione Segnale Odierno e Conferma HMM ---")
    
    current_state = df['State'].iloc[-1]
    last_time = df.index[-1]
    print(f"  Stato deterministico attuale ({last_time.date()}): {current_state}")
    
    probs_tomorrow = current_matrix.loc[current_state]
    p_bull = probs_tomorrow['Bull']
    p_bear = probs_tomorrow['Bear']
    signal_value = p_bull - p_bear
    direction = "Long" if signal_value > 0 else "Short" if signal_value < 0 else "Neutral"
    
    # HMM
    returns = df['Return'].values.reshape(-1, 1)
    hmm_model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000, random_state=42)
    hmm_model.fit(returns)
    hmm_states = hmm_model.predict(returns)
    
    # Mappatura HMM
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
    global_alignment = (df['State'] == [hmm_mapping[s] for s in hmm_states]).mean()
    
    hmm_traffic_light = "VERDE" if hmm_current_label == current_state else "ROSSO"
    
    print("\n==================================================")
    print("                 OUTPUT RICHIESTO")
    print("==================================================")
    print(f"Data Ultima Barra: {last_time.date()}")
    print(f"Prezzo di Chiusura:    {df['Close'].iloc[-1]:.2f}\n")
    print("1. MATRICE DI TRANSIZIONE ATTUALE:")
    print(current_matrix.round(4))
    print(f"\n2. SEGNALE OPERATIVO PER DOMANI:")
    print(f"   -> Direzione: {direction}")
    print(f"   -> Forza del Segnale (Size): {abs(signal_value):.2%}")
    print(f"\n3. CONFERMA HMM:")
    print(f"   -> Semaforo HMM: {hmm_traffic_light}")
    print(f"   -> Stato Deterministico: {current_state} | Stato HMM: {hmm_current_label}")
    print(f"   -> Allineamento Globale: {global_alignment:.2%}")
    print("==================================================")

if __name__ == "__main__":
    main()
