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
    files = sorted(files, key=extract_number)
    print(f"Trovati {len(files)} file settimanali da elaborare.")
    
    all_bars = []
    
    for idx, filepath in enumerate(files):
        print(f"Elaborazione file {idx+1}/{len(files)}: {filepath}...")
        try:
            df = pd.read_csv(filepath, sep='\t', header=None, names=['timestamp', 'price', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            df['date'] = df['timestamp'].dt.date
            df['minutes_since_08'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute - 8 * 60
            
            df = df[(df['minutes_since_08'] >= 0) & (df['minutes_since_08'] <= 660)].copy()
            
            df['bin'] = pd.cut(df['minutes_since_08'], 
                               bins=[-1, 180, 360, 661], 
                               labels=[0, 1, 2],
                               right=False)
            
            grouped = df.groupby(['date', 'bin'], observed=False)
            
            bars = grouped.agg(
                open=('price', 'first'),
                high=('price', 'max'),
                low=('price', 'min'),
                close=('price', 'last'),
                volume=('volume', 'sum')
            ).reset_index()
            
            bars = bars.dropna(subset=['open'])
            all_bars.append(bars)
            
        except Exception as e:
            print(f"Errore nell'elaborazione del file {filepath}: {e}")
            
    if not all_bars:
        print("Nessun dato elaborato.")
        return
        
    final_df = pd.concat(all_bars, ignore_index=True)
    
    final_df['date'] = pd.to_datetime(final_df['date'])
    final_df = final_df.sort_values(by=['date', 'bin']).reset_index(drop=True)
    
    def get_bin_time(row):
        bin_val = row['bin']
        if bin_val == 0:
            offset = pd.Timedelta(hours=8)
        elif bin_val == 1:
            offset = pd.Timedelta(hours=11)
        else:
            offset = pd.Timedelta(hours=14)
        return row['date'] + offset
        
    final_df['data'] = final_df.apply(get_bin_time, axis=1)
    
    final_df = final_df[['data', 'open', 'high', 'low', 'close', 'volume']]
    
    output_filepath = 'btp3h.txt'
    final_df.to_csv(output_filepath, sep='\t', index=False)
    print(f"\nAggregazione completata con successo! Salvate {len(final_df)} barre da 3 ore in '{output_filepath}'.")
    
if __name__ == '__main__':
    main()
