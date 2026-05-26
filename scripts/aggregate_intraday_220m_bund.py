import pandas as pd
import numpy as np
import glob
import re
import os

def extract_number(filename):
    match = re.search(r'week_(\d+)\.txt', filename)
    return int(match.group(1)) if match else 999999

def main():
    files = glob.glob('PULITO_bund_trasformato_week_*.txt')
    # Ordina i file numericamente in base al numero di settimana
    files = sorted(files, key=extract_number)
    print(f"Trovati {len(files)} file settimanali da elaborare.")
    
    all_bars = []
    
    for idx, filepath in enumerate(files):
        print(f"Elaborazione file {idx+1}/{len(files)}: {filepath}...")
        try:
            df = pd.read_csv(filepath, sep='\t', header=None, names=['timestamp', 'price', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Estrarre la data e i minuti dall'apertura delle 08:00
            df['date'] = df['timestamp'].dt.date
            df['minutes_since_08'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute - 8 * 60
            
            # Filtrare solo i dati all'interno della sessione 08:00 - 19:00 (0 - 660 minuti)
            df = df[(df['minutes_since_08'] >= 0) & (df['minutes_since_08'] <= 660)].copy()
            
            # Assegnare ciascuna riga a uno dei 3 bin da 220 minuti:
            # Bin 0: 08:00 - 11:40 (0 - 220 minuti)
            # Bin 1: 11:40 - 15:20 (220 - 440 minuti)
            # Bin 2: 15:20 - 19:00 (440 - 660 minuti)
            df['bin'] = pd.cut(df['minutes_since_08'], 
                               bins=[-1, 220, 440, 661], 
                               labels=[0, 1, 2],
                               right=False)
            
            # Raggruppare per data e bin
            grouped = df.groupby(['date', 'bin'], observed=False)
            
            # Calcolare OHLCV
            bars = grouped.agg(
                open=('price', 'first'),
                high=('price', 'max'),
                low=('price', 'min'),
                close=('price', 'last'),
                volume=('volume', 'sum')
            ).reset_index()
            
            # Rimuovere i bin in cui non ci sono dati (se presenti)
            bars = bars.dropna(subset=['open'])
            all_bars.append(bars)
            
        except Exception as e:
            print(f"Errore nell'elaborazione del file {filepath}: {e}")
            
    if not all_bars:
        print("Nessun dato elaborato.")
        return
        
    final_df = pd.concat(all_bars, ignore_index=True)
    
    # Ordinamento per data e bin
    final_df['date'] = pd.to_datetime(final_df['date'])
    final_df = final_df.sort_values(by=['date', 'bin']).reset_index(drop=True)
    
    # Creare una colonna timestamp rappresentativa dell'inizio della barra
    # Bin 0 -> 08:00, Bin 1 -> 11:40, Bin 2 -> 15:20
    def get_bin_time(row):
        bin_val = row['bin']
        if bin_val == 0:
            offset = pd.Timedelta(hours=8)
        elif bin_val == 1:
            offset = pd.Timedelta(hours=11, minutes=40)
        else:
            offset = pd.Timedelta(hours=15, minutes=20)
        return row['date'] + offset
        
    final_df['data'] = final_df.apply(get_bin_time, axis=1)
    
    # Tenere solo le colonne standard
    final_df = final_df[['data', 'open', 'high', 'low', 'close', 'volume']]
    
    # Salvare su file
    output_filepath = 'bund_220m.txt'
    final_df.to_csv(output_filepath, sep='\t', index=False)
    print(f"\nAggregazione completata con successo! Salvate {len(final_df)} barre da 220 minuti in '{output_filepath}'.")
    
if __name__ == '__main__':
    main()
