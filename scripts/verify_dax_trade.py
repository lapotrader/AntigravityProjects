import pandas as pd
import numpy as np
from optimize_supertrend_220m_dax import load_data, calculate_supertrend

def main():
    df = load_data('dax_220m.txt')
    ma_series = df['close'].rolling(window=50).mean()
    
    period = 10
    mult = 4.0
    tp_multiplier = 3.0
    
    df = calculate_supertrend(df, period, mult)
    
    in_position = False
    pos_type = None
    entry_price = 0.0
    entry_idx = 0
    tp_level = 0.0
    
    print("Cerco il primo trade per la configurazione MA=50, ST=10, ST_Mult=4.0, TP=3.0...\n")
    
    for i in range(21, len(df)):
        prev_dir = df['direction'].iloc[i-1]
        prev_prev_dir = df['direction'].iloc[i-2] if i >= 2 else prev_dir
        
        current_date = df['data'].iloc[i]
        current_open = df['open'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        current_supertrend = df['supertrend'].iloc[i]
        
        # Gestione posizione
        if in_position:
            if pos_type == 'long':
                if current_high >= tp_level:
                    pnl_points = tp_level - entry_price
                    pnl_eur = (pnl_points * 25.0) - 6.0
                    print(f"--- USCITA LONG IN TAKE PROFIT ---")
                    print(f"Data/Ora uscita: {current_date}")
                    print(f"Prezzo di uscita (Take Profit toccato): {tp_level:.2f}")
                    print(f"High della barra di uscita: {current_high:.2f}")
                    print(f"Punti lordi guadagnati: {pnl_points:.2f}")
                    print(f"Controvalore (Punti * 25): {pnl_points * 25.0:.2f} EUR")
                    print(f"Commissioni sottratte: 6.0 EUR")
                    print(f"Net Profit finale del trade: {pnl_eur:.2f} EUR")
                    break
                elif current_close < current_supertrend:
                    pnl_points = current_close - entry_price
                    pnl_eur = (pnl_points * 25.0) - 6.0
                    print(f"--- USCITA LONG IN STOP/REVERSE ---")
                    print(f"Data/Ora uscita: {current_date}")
                    print(f"Prezzo di uscita (Close < ST): {current_close:.2f}")
                    print(f"Supertrend alla barra: {current_supertrend:.2f}")
                    print(f"Punti lordi: {pnl_points:.2f}")
                    print(f"Controvalore (Punti * 25): {pnl_points * 25.0:.2f} EUR")
                    print(f"Commissioni sottratte: 6.0 EUR")
                    print(f"Net Profit finale del trade: {pnl_eur:.2f} EUR")
                    break
            elif pos_type == 'short':
                if current_low <= tp_level:
                    pnl_points = entry_price - tp_level
                    pnl_eur = (pnl_points * 25.0) - 6.0
                    print(f"--- USCITA SHORT IN TAKE PROFIT ---")
                    print(f"Data/Ora uscita: {current_date}")
                    print(f"Prezzo di uscita (Take Profit toccato): {tp_level:.2f}")
                    print(f"Low della barra di uscita: {current_low:.2f}")
                    print(f"Punti lordi guadagnati: {pnl_points:.2f}")
                    print(f"Controvalore (Punti * 25): {pnl_points * 25.0:.2f} EUR")
                    print(f"Commissioni sottratte: 6.0 EUR")
                    print(f"Net Profit finale del trade: {pnl_eur:.2f} EUR")
                    break
                elif current_close > current_supertrend:
                    pnl_points = entry_price - current_close
                    pnl_eur = (pnl_points * 25.0) - 6.0
                    print(f"--- USCITA SHORT IN STOP/REVERSE ---")
                    print(f"Data/Ora uscita: {current_date}")
                    print(f"Prezzo di uscita (Close > ST): {current_close:.2f}")
                    print(f"Supertrend alla barra: {current_supertrend:.2f}")
                    print(f"Punti lordi: {pnl_points:.2f}")
                    print(f"Controvalore (Punti * 25): {pnl_points * 25.0:.2f} EUR")
                    print(f"Commissioni sottratte: 6.0 EUR")
                    print(f"Net Profit finale del trade: {pnl_eur:.2f} EUR")
                    break
                    
        # Nuovi Ingressi
        if not in_position:
            close_prev = df['close'].iloc[i-1]
            ma_val_prev = ma_series.iloc[i-1] if ma_series is not None else None
            
            allow_long = True
            allow_short = True
            
            if ma_val_prev is not None and not np.isnan(ma_val_prev):
                allow_long = close_prev > ma_val_prev
                allow_short = close_prev < ma_val_prev
            
            if prev_dir == 1 and prev_prev_dir == -1 and allow_long:
                in_position = True
                pos_type = 'long'
                entry_price = current_open
                entry_idx = i
                tp_level = entry_price + tp_multiplier * df['atr'].iloc[i-1]
                print(f"--- INGRESSO LONG ---")
                print(f"Data/Ora: {current_date}")
                print(f"Prezzo Entrata (Open della barra successiva al segnale): {entry_price:.2f}")
                print(f"Valore ATR precedente: {df['atr'].iloc[i-1]:.2f}")
                print(f"Livello Take Profit calcolato: {tp_level:.2f}")
                print(f"Distanza TP in punti: {tp_level - entry_price:.2f}\n")
                
            elif prev_dir == -1 and prev_prev_dir == 1 and allow_short:
                in_position = True
                pos_type = 'short'
                entry_price = current_open
                entry_idx = i
                tp_level = entry_price - tp_multiplier * df['atr'].iloc[i-1]
                print(f"--- INGRESSO SHORT ---")
                print(f"Data/Ora: {current_date}")
                print(f"Prezzo Entrata (Open della barra successiva al segnale): {entry_price:.2f}")
                print(f"Valore ATR precedente: {df['atr'].iloc[i-1]:.2f}")
                print(f"Livello Take Profit calcolato: {tp_level:.2f}")
                print(f"Distanza TP in punti: {entry_price - tp_level:.2f}\n")

if __name__ == '__main__':
    main()
