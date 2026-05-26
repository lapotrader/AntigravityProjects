import pandas as pd
import numpy as np

def main():
    print("Loading data...")
    file_path = "dati/btp 2023-25.txt"
    df = pd.read_csv(file_path, sep='\t', header=None, names=['Datetime', 'Price', 'Volume'])
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df.set_index('Datetime', inplace=True)

    print("Resampling to OHLC daily frequency...")
    daily_df = df['Price'].resample('B').agg(['first', 'max', 'min', 'last'])
    daily_df.columns = ['Open', 'High', 'Low', 'Close']
    daily_df.dropna(inplace=True)

    window = 20
    # Calcoliamo prima i massimi e minimi futuri reali per ogni giorno, 
    # che useremo per verificare se l'opzione è stata sfondata.
    daily_df['Future_Max_High'] = daily_df['High'].rolling(window=window, min_periods=window).max().shift(-window)
    daily_df['Future_Min_Low'] = daily_df['Low'].rolling(window=window, min_periods=window).min().shift(-window)

    # Vogliamo testare un Win Rate del 90% (o 80%)
    conf = 0.90
    warmup_period = 250
    
    total_days = len(daily_df)
    
    if total_days < warmup_period + window:
        print("Dataset troppo piccolo per questo backtest.")
        return

    results = []
    
    print(f"Inizio simulazione Walk-Forward (Target Win Rate {conf*100:.0f}%, dal giorno {warmup_period})...")

    for t in range(warmup_period, total_days - window):
        current_date = daily_df.index[t]
        current_close = daily_df['Close'].iloc[t]
        
        # 1. STORICO DISPONIBILE AL TEMPO t (Senza look-ahead bias)
        # Prendiamo solo i dati da 0 a t. 
        # NOTA BENE: Le escursioni storiche possono essere calcolate solo sui trade che si sono GIÀ conclusi prima del giorno t.
        # Quindi la finestra reale passata valida finisce a t - window.
        
        past_slice = daily_df.iloc[:t].copy()
        
        # Calcoliamo storicamente cosa era successo
        past_slice['Past_Future_High'] = past_slice['High'].rolling(window=window, min_periods=window).max().shift(-window)
        past_slice['Past_Future_Low'] = past_slice['Low'].rolling(window=window, min_periods=window).min().shift(-window)
        
        # Rimuoviamo gli ultimi 20 giorni dello slice passato perché 'guarderebbero' al presente/futuro
        valid_past = past_slice.dropna(subset=['Past_Future_High', 'Past_Future_Low']).copy()
        
        valid_past['Run_up'] = (valid_past['Past_Future_High'] - valid_past['Close']) / valid_past['Close']
        valid_past['Drawdown'] = (valid_past['Past_Future_Low'] - valid_past['Close']) / valid_past['Close']
        
        # Calcolo dei percentili empirici sul VERO passato
        run_up_q = valid_past['Run_up'].quantile(conf)
        drawdown_q = valid_past['Drawdown'].quantile(1 - conf)
        
        # 2. DEFINIZIONE DEGLI STRIKE
        call_strike = current_close * (1 + run_up_q)
        put_strike = current_close * (1 + drawdown_q)
        
        # 3. VERIFICA SUL FUTURO (Che avverrà da t+1 a t+20)
        actual_future_high = daily_df['Future_Max_High'].iloc[t]
        actual_future_low = daily_df['Future_Min_Low'].iloc[t]
        
        # Verifica violazioni
        call_breached = actual_future_high >= call_strike
        put_breached = actual_future_low <= put_strike
        
        is_win = not (call_breached or put_breached)
        
        results.append({
            'Date': current_date,
            'Close': current_close,
            'Call_Strike': call_strike,
            'Put_Strike': put_strike,
            'Future_High': actual_future_high,
            'Future_Low': actual_future_low,
            'Call_Breached': call_breached,
            'Put_Breached': put_breached,
            'Win': is_win
        })

    res_df = pd.DataFrame(results)
    
    total_trades = len(res_df)
    wins = res_df['Win'].sum()
    real_win_rate = wins / total_trades
    
    call_breaches = res_df['Call_Breached'].sum()
    put_breaches = res_df['Put_Breached'].sum()
    
    print("\n=========================================================")
    print("RISULTATI BACKTEST WALK-FORWARD SHORT STRANGLE 20 GIORNI")
    print("=========================================================")
    print(f"Giorni di Warm-up: {warmup_period}")
    print(f"Trades Simulati: {total_trades} (Trade giornalieri sovrapposti)")
    print(f"Target Win Rate Desiderato (Statistico): {conf*100:.1f}%")
    print(f"---------------------------------------------------------")
    print(f"WIN RATE REALE OTTENUTO: {real_win_rate*100:.2f}%")
    print(f"Totale Vittorie (Premio 100%): {wins}")
    print(f"Totale Sconfitte (Violazione): {total_trades - wins}")
    print(f"  - Violazioni al rialzo (Call colpita): {call_breaches} ({call_breaches/total_trades*100:.1f}%)")
    print(f"  - Violazioni al ribasso (Put colpita): {put_breaches} ({put_breaches/total_trades*100:.1f}%)")
    print("=========================================================\n")

if __name__ == "__main__":
    main()
