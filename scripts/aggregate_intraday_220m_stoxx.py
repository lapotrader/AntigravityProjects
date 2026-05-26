import pandas as pd
import numpy as np
import datetime
import os

def aggregate_to_220m_bars(input_file, output_file):
    print(f"Lettura del file '{input_file}' in corso...")
    
    df = pd.read_csv(input_file, sep=',', header=0)
    
    df['Data'] = df['Date'].astype(str) + ' ' + df['Time'].astype(str)
    df['Data'] = pd.to_datetime(df['Data'], format='%Y%m%d %H:%M:%S')
    
    df = df.set_index('Data')
    df = df.sort_index()
    
    # Filtro solo la sessione 08:00 - 19:00 (come DAX, BTP, BUND)
    df = df.between_time('08:00', '18:59')
    
    print(f"Righe dopo il filtro orario: {len(df)}")
    
    if len(df) == 0:
        print("Nessun dato trovato nell'orario specificato!")
        return
        
    df['DateStr'] = df.index.date
    
    aggregated_bars = []
    
    for date_str, daily_group in df.groupby('DateStr'):
        # 3 barre da 220 minuti (3 ore e 40 min)
        # Barra 1: 08:00 - 11:40
        bar1 = daily_group.between_time('08:00', '11:39')
        if not bar1.empty:
            o = bar1['Open'].iloc[0]
            h = bar1['High'].max()
            l = bar1['Low'].min()
            c = bar1['Close'].iloc[-1]
            v = bar1['Volume'].sum()
            t = pd.Timestamp(f"{date_str} 08:00:00")
            aggregated_bars.append({'Data': t, 'Open': o, 'High': h, 'Low': l, 'Close': c, 'Volume': v})
            
        # Barra 2: 11:40 - 15:20
        bar2 = daily_group.between_time('11:40', '15:19')
        if not bar2.empty:
            o = bar2['Open'].iloc[0]
            h = bar2['High'].max()
            l = bar2['Low'].min()
            c = bar2['Close'].iloc[-1]
            v = bar2['Volume'].sum()
            t = pd.Timestamp(f"{date_str} 11:40:00")
            aggregated_bars.append({'Data': t, 'Open': o, 'High': h, 'Low': l, 'Close': c, 'Volume': v})
            
        # Barra 3: 15:20 - 19:00
        bar3 = daily_group.between_time('15:20', '18:59')
        if not bar3.empty:
            o = bar3['Open'].iloc[0]
            h = bar3['High'].max()
            l = bar3['Low'].min()
            c = bar3['Close'].iloc[-1]
            v = bar3['Volume'].sum()
            t = pd.Timestamp(f"{date_str} 15:20:00")
            aggregated_bars.append({'Data': t, 'Open': o, 'High': h, 'Low': l, 'Close': c, 'Volume': v})
            
    res_df = pd.DataFrame(aggregated_bars)
    
    res_df['Data'] = res_df['Data'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    res_df = res_df[['Data', 'Open', 'High', 'Low', 'Close', 'Volume']]
    
    res_df.to_csv(output_file, sep='\t', index=False)
    
    print(f"Aggregazione completata. Totale barre a 220 minuti generate: {len(res_df)}")
    print(f"Dati salvati in: '{output_file}'")
    
if __name__ == '__main__':
    input_filename = "2026.5.21EUSIDXEUR-M1-No Session.csv"
    output_filename = "stoxx_220m.txt"
    aggregate_to_220m_bars(input_filename, output_filename)
