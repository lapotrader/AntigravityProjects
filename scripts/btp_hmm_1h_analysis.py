import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings
warnings.filterwarnings('ignore')

def main():
    # 1. Data Ingestion & Resampling to 1 Hour
    print("Loading raw tick data from dati/btp 2023-25.txt...")
    file_path = "dati/btp 2023-25.txt"
    df = pd.read_csv(file_path, sep='\t', header=None, names=['Datetime', 'Price', 'Volume'])
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df.set_index('Datetime', inplace=True)

    print("Resampling to 1-hour OHLCV bars...")
    # Raggruppamento orario
    hourly_df = df['Price'].resample('h').agg(['first', 'max', 'min', 'last'])
    hourly_df.columns = ['Open', 'High', 'Low', 'Close']
    hourly_df['Volume'] = df['Volume'].resample('h').sum()
    
    # Filtriamo solo le ore di contrattazione attiva (dalle 08:00 alle 19:00, quindi index.hour tra 8 e 18 incluse)
    hourly_df = hourly_df[(hourly_df.index.hour >= 8) & (hourly_df.index.hour < 19)]
    hourly_df.dropna(inplace=True)
    
    # Calcolo dei rendimenti orari
    hourly_df['Return'] = hourly_df['Close'].pct_change()
    hourly_df.dropna(inplace=True)
    print(f"Resampling completed. Total 1h bars: {len(hourly_df)}")

    # 2. Adaptive Regime Definition (Soglia dinamica basata su 1 Deviazione Standard mobile)
    print("\n--- Step 1 & 2: Definizione Adattiva ed Etichettatura ---")
    window = 50 # Finestra mobile oraria per catturare la volatilità recente
    hourly_df['Vol_rolling'] = hourly_df['Return'].rolling(window=window).std()
    hourly_df['Vol_rolling_prev'] = hourly_df['Vol_rolling'].shift(1)
    hourly_df.dropna(inplace=True)

    # 3. Historical Labeling
    conditions = [
        (hourly_df['Return'] > hourly_df['Vol_rolling_prev']),
        (hourly_df['Return'] < -hourly_df['Vol_rolling_prev'])
    ]
    choices = ['Bull', 'Bear']
    hourly_df['State'] = np.select(conditions, choices, default='Sideways')
    
    print(f"Conteggio Stati Storici:")
    print(hourly_df['State'].value_counts())

    # 4. Markov Transition Matrix
    def calculate_transition_matrix(states):
        states_shifted = states.shift(-1)
        df_trans = pd.DataFrame({'From': states, 'To': states_shifted}).dropna()
        mat = pd.crosstab(df_trans['From'], df_trans['To'], normalize='index')
        order = ['Bear', 'Sideways', 'Bull']
        mat = mat.reindex(index=order, columns=order).fillna(0)
        return mat

    current_matrix = calculate_transition_matrix(hourly_df['State'])
    print("\n--- Step 4: Matrice di Transizione Attuale (1h) ---")
    print(current_matrix.round(4))

    # 5. Stickiness Score (Diagonale della matrice)
    print("\n--- Step 5: Analisi della Persistenza (Stickiness) ---")
    stickiness = np.diag(current_matrix)
    for state, stick in zip(['Bear', 'Sideways', 'Bull'], stickiness):
        print(f"  {state}: {stick:.2%}")

    # 6. Matrix Squaring & Cubing (Previsioni a 2 e 3 ore)
    M = current_matrix.values
    M2 = np.linalg.matrix_power(M, 2)
    M3 = np.linalg.matrix_power(M, 3)

    M2_df = pd.DataFrame(M2, index=current_matrix.index, columns=current_matrix.columns)
    M3_df = pd.DataFrame(M3, index=current_matrix.index, columns=current_matrix.columns)

    print("\n--- Step 6: Previsioni a 2 Ore (M^2) ---")
    print(M2_df.round(4))
    print("\n--- Step 6: Previsioni a 3 Ore (M^3) ---")
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
    # Facciamo una simulazione walk forward dinamica.
    # Per ogni barra (dopo un periodo di riscaldamento), calcoliamo la matrice usando solo i dati passati,
    # generiamo il segnale per l'ora successiva e valutiamo se è corretto (direzione del rendimento successivo).
    warmup = 500  # Finestra di riscaldamento per avere matrici stabili
    wf_results = []
    
    # Pre-allocazione per velocità
    states_series = hourly_df['State']
    returns_series = hourly_df['Return']
    
    for t in range(warmup, len(hourly_df) - 1):
        # Storico disponibile fino a t
        past_states = states_series.iloc[:t+1]
        current_state = past_states.iloc[-1]
        
        # Calcolo matrice di transizione sul passato
        states_shifted = past_states.shift(-1)
        df_trans = pd.DataFrame({'From': past_states, 'To': states_shifted}).dropna()
        
        # Se non ci sono abbastanza dati o transazioni, saltiamo
        if len(df_trans) < 100:
            continue
            
        mat = pd.crosstab(df_trans['From'], df_trans['To'], normalize='index')
        order = ['Bear', 'Sideways', 'Bull']
        mat = mat.reindex(index=order, columns=order).fillna(0)
        
        # Probabilità per t+1
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
    print(f"  Barre simulate nel Walk-Forward: {len(wf_df)}")
    print(f"  Direzioni previste corrette (Hit Rate): {hit_rate:.2%}")

    # 9. HMM Confirmation & Final Outputs
    print("\n--- Step 8 & 10: Generazione Segnale Odierno e Conferma HMM ---")
    
    # Calcolo stato attuale
    current_state = hourly_df['State'].iloc[-1]
    last_time = hourly_df.index[-1]
    print(f"  Stato deterministico attuale ({last_time}): {current_state}")
    
    probs_tomorrow = current_matrix.loc[current_state]
    p_bull = probs_tomorrow['Bull']
    p_bear = probs_tomorrow['Bear']
    signal_value = p_bull - p_bear
    direction = "Long" if signal_value > 0 else "Short" if signal_value < 0 else "Neutral"
    
    # HMM
    returns = hourly_df['Return'].values.reshape(-1, 1)
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
    global_alignment = (hourly_df['State'] == [hmm_mapping[s] for s in hmm_states]).mean()
    
    hmm_traffic_light = "VERDE" if hmm_current_label == current_state else "ROSSO"
    
    print("\n==================================================")
    print("                 OUTPUT RICHIESTO")
    print("==================================================")
    print(f"Data/Ora Ultima Barra: {last_time}")
    print(f"Prezzo di Chiusura:    {hourly_df['Close'].iloc[-1]:.2f}\n")
    print("1. MATRICE DI TRANSIZIONE ATTUALE:")
    print(current_matrix.round(4))
    print(f"\n2. SEGNALE OPERATIVO PER PROSSIMA ORA:")
    print(f"   -> Direzione: {direction}")
    print(f"   -> Forza del Segnale (Size): {abs(signal_value):.2%}")
    print(f"\n3. CONFERMA HMM:")
    print(f"   -> Semaforo HMM: {hmm_traffic_light}")
    print(f"   -> Stato Deterministico: {current_state} | Stato HMM: {hmm_current_label}")
    print(f"   -> Allineamento Globale: {global_alignment:.2%}")
    print("==================================================")

if __name__ == "__main__":
    main()
