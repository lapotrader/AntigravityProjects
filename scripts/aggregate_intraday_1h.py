import pandas as pd
import numpy as np
import glob
import re
import os

def extract_number(filename):
    match = re.search(r'week_(\d+)\.txt', filename)
    return int(match.group(1)) if match else 999999

def main():
    files = glob.glob('PULITO_btp_trasformato_week_*.txt')
    # Ordina i file numericamente in base al numero di settimana
    files = sorted(files, key=extract_number)
    print(f"Trovati {len(files)} file settimanali da elaborare.")
    
    all_bars = []
    
    for idx, filepath in enumerate(files):
        print(f"Elaborazione file {idx+1}/{len(files)}: {filepath}...")
        try:
            df = pd.read_csv(filepath, sep='\t', header=None, names=['timestamp', 'price', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Calcolo minuti dall'apertura delle 08:00
            df['date'] = df['timestamp'].dt.date
            df['minutes_since_08'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute - 8 * 60
            
            # Filtrare solo i dati all'interno della sessione 08:00 - 19:00 (0 - 660 minuti)
            df = df[(df['minutes_since_08'] >= 0) & (df['minutes_since_08'] <= 660)].copy()
            
            # Estrarre l'ora
            df['hour'] = df['timestamp'].dt.hour
            
            # Se ci sono tick esattamente alle 19:00:00, li includiamo nella barra delle 18:00
            df.loc[df['hour'] == 19, 'hour'] = 18
            
            # Raggruppare per data e ora
            grouped = df.groupby(['date', 'hour'], observed=False)
            
            # Calcolare OHLCV per ogni ora
            bars = grouped.agg(
                open=('price', 'first'),
                high=('price', 'max'),
                low=('price', 'min'),
                close=('price', 'last'),
                volume=('volume', 'sum')
            ).reset_index()
            
            # Rimuovere barre vuote
            bars = bars.dropna(subset=['open'])
            all_bars.append(bars)
            
        except Exception as e:
            print(f"Errore nell'elaborazione del file {filepath}: {e}")
            
    if not all_bars:
        print("Nessun dato elaborato.")
        return
        
    final_df = pd.concat(all_bars, ignore_index=True)
    
    # Ordinamento per data e ora
    final_df['date'] = pd.to_datetime(final_df['date'])
    final_df = final_df.sort_values(by=['date', 'hour']).reset_index(drop=True)
    
    # Creare la colonna timestamp 'data' rappresentativa dell'inizio della barra
    # Ad esempio: 2023-05-15 08:00:00
    def get_bar_time(row):
        offset = pd.Timedelta(hours=int(row['hour']))
        return row['date'] + offset
        
    final_df['data'] = final_df.apply(get_bar_time, axis=1)
    
    # Tenere solo le colonne standard ordinate
    final_df = final_df[['data', 'open', 'high', 'low', 'close', 'volume']]
    
    # Salvare su file
    output_filepath = 'btp_1h.txt'
    final_df.to_csv(output_filepath, sep='\t', index=False)
    print(f"\nAggregazione completata! Salvate {len(final_df)} barre orarie in '{output_filepath}'.")
    
if __name__ == '__main__':
    main()
