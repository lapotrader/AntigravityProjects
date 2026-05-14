import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import tkinter as tk
from tkinter import filedialog

def seleziona_file():
    """Apre una finestra di dialogo per selezionare uno o più file .txt"""
    root = tk.Tk()
    root.withdraw()  # Nasconde la finestra principale di tkinter
    percorsi = filedialog.askopenfilenames(
        title='Seleziona i file BTP da caricare',
        filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
    )
    return percorsi

def carica_dati_btp(path):
    """
    Carica i dati BTP da disco.
    Utilizziamo parse_dates per convertire automaticamente i timestamp.
    """
    if not os.path.exists(path):
        print(f"Errore: Il file '{path}' non esiste.")
        return None

    # Carichiamo il file:
    # - sep='\t' perché i dati sono separati da TAB (necessario dato che il timestamp ha uno spazio interno)
    # - names definisce i nomi delle colonne
    # - parse_dates indica a pandas di trattare la prima colonna come data/ora
    try:
        df = pd.read_csv(
            path, 
            sep='\t', 
            header=None, 
            names=['timestamp', 'price', 'volume'], 
            parse_dates=['timestamp']
        )
        
        # Impostiamo il timestamp come indice per facilitare l'analisi temporale
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"Errore durante la lettura: {e}")
        return None

# Esecuzione del caricamento
percorsi_selezionati = seleziona_file()

if percorsi_selezionati:
    lista_df = []
    for percorso in percorsi_selezionati:
        df_temp = carica_dati_btp(percorso)
        if df_temp is not None:
            lista_df.append(df_temp)
    
    if lista_df:
        # Uniamo tutti i file in un unico DataFrame e ordiniamo per data (indice)
        df = pd.concat(lista_df).sort_index()
        
        print(f"Caricati correttamente {len(lista_df)} file. Prime righe:")
        print(df.head())

        # --- ELABORAZIONE DATI PER IL GRAFICO ---
        timeframe = '60min'
        price_bin_size = 0.02 # Aumentato leggermente per migliorare la leggibilità e velocità
        
        # 1. Resampling standard per OHLC (riferimento)
        df_resampled = df.resample(timeframe).agg({
            'price': 'ohlc',
            'volume': 'sum'
        })
        df_resampled.columns = ['open', 'high', 'low', 'close', 'volume_total']
        df_resampled.dropna(subset=['close'], inplace=True)

        # 2. Calcolo del Volume Profile per ogni candela
        df['price_bin'] = (df['price'] / price_bin_size).round() * price_bin_size
        vp_data = df.groupby([pd.Grouper(freq=timeframe), 'price_bin'])['volume'].sum().reset_index()
        
        # Creiamo la matrice Pivot per la Heatmap
        vp_pivot = vp_data.pivot(index='price_bin', columns='timestamp', values='volume')
        
        # PREPARAZIONE TESTO PULITO: Solo numeri dove c'è volume, altrimenti vuoto
        # Questo evita di vedere "NaN" o "0" sul grafico
        text_values = vp_pivot.apply(lambda x: x.map(lambda v: f"{int(v)}" if pd.notnull(v) and v > 0 else "")).values

        # --- CREAZIONE GRAFICO OTTIMIZZATO ---
        fig = go.Figure()

        # 1. Heatmap "Fantasma" (Sfondo invisibile, solo testo)
        # Questa tecnica è la più veloce e pulita per mostrare solo i numeri
        fig.add_trace(go.Heatmap(
            x=vp_pivot.columns,
            y=vp_pivot.index,
            z=vp_pivot.values,
            text=text_values,
            texttemplate="%{text}", 
            textfont={"size": 11, "family": "Courier New, monospace", "color": "#FFB90F"}, # Colore Ambra tipo terminale
            colorscale=[[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']], # Sfondo 100% trasparente
            showscale=False,
            name='Footprint',
            xgap=0, ygap=0
        ))

        # 2. Linea discreta per il corpo della candela
        fig.add_trace(go.Scatter(
            x=df_resampled.index,
            y=df_resampled['close'],
            mode='markers',
            marker=dict(symbol='line-ns-open', size=10, color='white', opacity=0.3),
            name='Close Marker'
        ))

        # Personalizzazione del layout (Elegante e Veloce)
        fig.update_layout(
            title=dict(
                text=f'BTP FOOTPRINT - {timeframe}',
                font=dict(size=18, color='white')
            ),
            paper_bgcolor='#121212', # Grigio antracite professionale
            plot_bgcolor='#121212',
            dragmode='pan', # Attiva la manina per spostare il grafico
            xaxis_rangeslider_visible=False,
            height=850,
            showlegend=False,
            margin=dict(l=10, r=60, t=50, b=10),
            yaxis=dict(
                side='right',
                gridcolor='#222222',
                tickfont=dict(color='white'),
                showgrid=True
            ),
            xaxis=dict(
                gridcolor='#222222',
                tickfont=dict(color='white'),
                showgrid=True,
                dtick=60*60*1000
            )
        )
        
        # Rimuove i buchi temporali
        fig.update_xaxes(
            rangebreaks=[
                dict(bounds=["sat", "mon"]),
                dict(bounds=[18, 8], pattern="hour"),
            ]
        )

        fig.show(config={'scrollZoom': True})
    else:
        print("Nessun dato valido trovato nei file selezionati.")
else:
    print("Nessun file selezionato.")
