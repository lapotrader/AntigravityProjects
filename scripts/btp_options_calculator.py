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

    print("Calculating forward 20-day excursions...")
    window = 20
    daily_df['Forward_Max_High'] = daily_df['High'].rolling(window=window, min_periods=window).max().shift(-window)
    daily_df['Forward_Min_Low'] = daily_df['Low'].rolling(window=window, min_periods=window).min().shift(-window)

    valid_df = daily_df.dropna(subset=['Forward_Max_High', 'Forward_Min_Low']).copy()
    valid_df['Run_up'] = (valid_df['Forward_Max_High'] - valid_df['Close']) / valid_df['Close']
    valid_df['Drawdown'] = (valid_df['Forward_Min_Low'] - valid_df['Close']) / valid_df['Close']

    percentiles_conf = [0.68, 0.80, 0.90, 0.95]
    results = []
    
    for conf in percentiles_conf:
        run_up_q = valid_df['Run_up'].quantile(conf)
        drawdown_q = valid_df['Drawdown'].quantile(1 - conf)
        
        results.append({
            'Confidence': f"{conf*100:.0f}%",
            'Run_up_Pct': run_up_q,
            'Drawdown_Pct': drawdown_q
        })

    results_df = pd.DataFrame(results).set_index('Confidence')
    
    # OUTPUTS
    print("\n==================================================")
    print("      CALCOLATORE STRIKE OPZIONI (20 GIORNI)")
    print("==================================================")
    
    last_close = daily_df['Close'].iloc[-1]
    last_date = daily_df.index[-1].date()
    print(f"\nPrezzo Odierno ({last_date}): {last_close:.2f}")

    print("\n--- 1. Livelli Operativi (Short Strangle) ---")
    for conf in percentiles_conf:
        run_up_q = results_df.loc[f"{conf*100:.0f}%", 'Run_up_Pct']
        drawdown_q = results_df.loc[f"{conf*100:.0f}%", 'Drawdown_Pct']
        call_strike = last_close * (1 + run_up_q)
        put_strike = last_close * (1 + drawdown_q)
        print(f"[{conf*100:.0f}%] -> Vendi CALL: {call_strike:.2f} | Vendi PUT: {put_strike:.2f}")

    print("\n--- 2. Analisi del Rischio Direzionale (Skew) ---")
    # Estraiamo le asimmetrie sul livello chiave del 90%
    run_up_90 = results_df.loc['90%', 'Run_up_Pct']
    draw_down_90 = abs(results_df.loc['90%', 'Drawdown_Pct'])
    
    # Se il Drawdown è storicamente più profondo del Run_up, il rischio pende verso la PUT
    skewness = draw_down_90 - run_up_90 
    
    if skewness > 0.002: # Soglia di tolleranza
        print(">> ALLARME RISCHIO: LATO PUT (RIBASSO)")
        print("   Il mercato ha storicamente 'code' ribassiste più violente dei rialzi.")
        print("   Se hai opzioni aperte, il lato debole da monitorare attentamente è la PUT.")
        print("   Azione: Se il prezzo scende rapidamente, preparati a rollare la Put o comprare coperture.")
    elif skewness < -0.002:
        print(">> ALLARME RISCHIO: LATO CALL (RIALZO)")
        print("   Il mercato ha 'code' rialziste più esplosive.")
        print("   Sorveglia il lato CALL se hai posizioni aperte.")
    else:
        print(">> RISCHIO BILANCIATO")
        print("   L'escursione massima attesa al rialzo e al ribasso è simmetrica.")
        print("   Entrambi i lati sono ugualmente al sicuro.")
        
    print(f"\n[Dettaglio Skew al 90%: Escursione UP = +{run_up_90*100:.2f}%, Escursione DOWN = -{draw_down_90*100:.2f}%]")
    print("==================================================")

if __name__ == "__main__":
    main()
