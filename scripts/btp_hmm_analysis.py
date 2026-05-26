import pandas as pd
import numpy as np
from hmmlearn import hmm
import warnings
warnings.filterwarnings('ignore')

def main():
    # 1. Data Ingestion
    print("Loading data...")
    file_path = "dati/btp 2023-25.txt"
    # Dati tick: 2023-03-20 08:01:30	117.04	254
    df = pd.read_csv(file_path, sep='\t', header=None, names=['Datetime', 'Price', 'Volume'])
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df.set_index('Datetime', inplace=True)

    # Aggregazione giornaliera estraendo la chiusura (Close)
    print("Resampling to daily frequency...")
    daily_df = df['Price'].resample('B').last().dropna().to_frame(name='Close')
    daily_df['Return'] = daily_df['Close'].pct_change()

    # 2. Adaptive Regime Definition (Soglia dinamica 1 Deviazione Standard sui 20gg)
    print("Defining regimes...")
    daily_df['Vol_20'] = daily_df['Return'].rolling(window=20).std()
    
    # Shift per evitare look-ahead bias nell'etichettatura giornaliera
    daily_df['Vol_20_prev'] = daily_df['Vol_20'].shift(1)
    daily_df.dropna(inplace=True)

    # 3. Historical Labeling
    conditions = [
        (daily_df['Return'] > daily_df['Vol_20_prev']),
        (daily_df['Return'] < -daily_df['Vol_20_prev'])
    ]
    choices = ['Bull', 'Bear']
    daily_df['State'] = np.select(conditions, choices, default='Sideways')

    print(f"Total days analyzed: {len(daily_df)}")
    print(f"State counts:\n{daily_df['State'].value_counts()}")

    # 4. Markov Transition Matrix
    def calculate_transition_matrix(states):
        states_shifted = states.shift(-1)
        df_trans = pd.DataFrame({'From': states, 'To': states_shifted}).dropna()
        mat = pd.crosstab(df_trans['From'], df_trans['To'], normalize='index')
        
        # Ordine fisso per le colonne e le righe
        order = ['Bear', 'Sideways', 'Bull']
        mat = mat.reindex(index=order, columns=order).fillna(0)
        return mat

    print("\n--- 1. Matrice di transizione attuale ---")
    current_matrix = calculate_transition_matrix(daily_df['State'])
    print(current_matrix.round(4))

    # 5. Stickiness Score (Inerzia sulla diagonale)
    print("\n--- Stickiness Score (Inerzia degli stati) ---")
    stickiness = np.diag(current_matrix)
    for state, stick in zip(['Bear', 'Sideways', 'Bull'], stickiness):
        print(f"{state}: {stick:.2%}")

    # 6. Matrix Squaring & Cubing
    M = current_matrix.values
    M2 = np.linalg.matrix_power(M, 2)
    M3 = np.linalg.matrix_power(M, 3)

    M2_df = pd.DataFrame(M2, index=current_matrix.index, columns=current_matrix.columns)
    M3_df = pd.DataFrame(M3, index=current_matrix.index, columns=current_matrix.columns)

    print("\n--- Previsioni a 2 Giorni (M^2) ---")
    print(M2_df.round(4))
    print("\n--- Previsioni a 3 Giorni (M^3) ---")
    print(M3_df.round(4))

    # 7. Stationary Distribution (Convergenza a lungo termine)
    print("\n--- Stationary Distribution ---")
    eigenvals, eigenvecs = np.linalg.eig(M.T)
    idx = np.isclose(eigenvals, 1)
    if any(idx):
        stationary = eigenvecs[:, idx][:, 0].real
        stationary = stationary / np.sum(stationary)
        stat_df = pd.Series(stationary, index=current_matrix.index)
        print(stat_df.round(4))
    else:
        print("Non è stata trovata convergenza esatta a 1")

    # 8. Signal Generation & Walk Forward Mitigation
    print("\n--- 2. & 3. Probabilità e Segnale Odierno ---")
    # Il walk-forward completo calcolerebbe giorno per giorno, ma qui
    # mostriamo la valutazione dell'ultimo giorno senza usare dati futuri.
    current_state = daily_df['State'].iloc[-1]
    print(f"Stato Odierno ({daily_df.index[-1].date()}): {current_state}")

    probs_tomorrow = current_matrix.loc[current_state]
    print(f"Probabilità per Domani ({current_state} -> ...):")
    print(probs_tomorrow.round(4))

    p_bull = probs_tomorrow['Bull']
    p_bear = probs_tomorrow['Bear']

    signal_value = p_bull - p_bear
    direction = "Long" if signal_value > 0 else "Short" if signal_value < 0 else "Neutral"
    strength = abs(signal_value)

    print(f"-> Direzione Segnale: {direction}")
    print(f"-> Forza del Segnale (Size): {strength:.2%}")

    # 9 & 10. HMM Confirmation
    print("\n--- 4. HMM Confirmation ---")
    returns = daily_df['Return'].values.reshape(-1, 1)
    
    # Fit di un modello Hidden Markov a 3 stati
    model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=1000, random_state=42)
    model.fit(returns)
    hmm_states = model.predict(returns)
    daily_df['HMM_State'] = hmm_states

    # Associa gli stati HMM (0,1,2) a Bull, Bear, Sideways in base alle medie dei ritorni
    means = model.means_.flatten()
    state_order = np.argsort(means)
    bear_state_idx = state_order[0]
    sideways_state_idx = state_order[1]
    bull_state_idx = state_order[2]

    hmm_mapping = {
        bear_state_idx: 'Bear',
        sideways_state_idx: 'Sideways',
        bull_state_idx: 'Bull'
    }

    daily_df['HMM_Label'] = daily_df['HMM_State'].map(hmm_mapping)
    hmm_current = daily_df['HMM_Label'].iloc[-1]
    
    match = (daily_df['State'] == daily_df['HMM_Label']).mean()
    print(f"Allineamento Globale (Deterministico vs HMM): {match:.2%}")

    if hmm_current == current_state:
        print("-> Semaforo HMM: VERDE")
        print(f"   (Conferma: L'HMM concorda sullo stato odierno '{current_state}')")
    else:
        print("-> Semaforo HMM: ROSSO")
        print(f"   (Discordanza: Deterministico dice '{current_state}', ma HMM vede '{hmm_current}')")

if __name__ == "__main__":
    main()
