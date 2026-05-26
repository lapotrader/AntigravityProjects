import pandas as pd
import numpy as np

def main():
    filepath = '2026.5.20DEUIDXEUR-M1-No Session.csv'
    print(f"Elaborazione file: {filepath}...")
    
    try:
        df = pd.read_csv(filepath)
        # Converti Date e Time in un unico timestamp
        # La colonna Date è int come 20230102, Time è string come "01:15:00"
        df['timestamp'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'])
        
        df['date'] = df['timestamp'].dt.date
        df['minutes_since_08'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute - 8 * 60
        
        # Filtrare solo i dati all'interno della sessione 08:00 - 19:00 (0 - 660 minuti)
        df = df[(df['minutes_since_08'] >= 0) & (df['minutes_since_08'] <= 660)].copy()
        
        # Assegnare ciascuna riga a uno dei 3 bin da 220 minuti:
        df['bin'] = pd.cut(df['minutes_since_08'], 
                           bins=[-1, 220, 440, 661], 
                           labels=[0, 1, 2],
                           right=False)
        
        # Raggruppare per data e bin
        grouped = df.groupby(['date', 'bin'], observed=False)
        
        # Calcolare OHLCV
        bars = grouped.agg(
            open=('Open', 'first'),
            high=('High', 'max'),
            low=('Low', 'min'),
            close=('Close', 'last'),
            volume=('Volume', 'sum')
        ).reset_index()
        
        bars = bars.dropna(subset=['open'])
        
        # Creare una colonna timestamp rappresentativa dell'inizio della barra
        def get_bin_time(row):
            bin_val = row['bin']
            if bin_val == 0:
                offset = pd.Timedelta(hours=8)
            elif bin_val == 1:
                offset = pd.Timedelta(hours=11, minutes=40)
            else:
                offset = pd.Timedelta(hours=15, minutes=20)
            return pd.Timestamp(row['date']) + offset
            
        bars['data'] = bars.apply(get_bin_time, axis=1)
        
        # Tenere solo le colonne standard
        bars = bars[['data', 'open', 'high', 'low', 'close', 'volume']]
        
        # Salvare su file
        output_filepath = 'dax_220m.txt'
        bars.to_csv(output_filepath, sep='\t', index=False)
        print(f"\nAggregazione completata con successo! Salvate {len(bars)} barre da 220 minuti in '{output_filepath}'.")
        
    except Exception as e:
        print(f"Errore nell'elaborazione: {e}")

if __name__ == '__main__':
    main()
