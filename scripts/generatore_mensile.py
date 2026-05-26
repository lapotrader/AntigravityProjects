import pandas as pd
import plotly.graph_objects as go
import os

def carica_dati_btp(path):
    if not os.path.exists(path):
        print(f"Avviso: Il file '{path}' non esiste.")
        return None
    try:
        df = pd.read_csv(
            path, 
            sep='\t', 
            header=None, 
            names=['timestamp', 'price', 'volume'], 
            parse_dates=['timestamp']
        )
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"Errore durante la lettura di {path}: {e}")
        return None

def genera_grafico_mensile(lista_settimane, nome_output):
    print(f"Generazione {nome_output}...")
    lista_df = []
    for num in lista_settimane:
        filename = f'PULITO_btp_trasformato_week_{num}.txt'
        df_temp = carica_dati_btp(filename)
        if df_temp is not None:
            lista_df.append(df_temp)
    
    if not lista_df:
        print(f"Nessun dato per {nome_output}")
        return

    df = pd.concat(lista_df).sort_index()
    
    # --- ELABORAZIONE ---
    timeframe = '60min'
    price_bin_size = 0.02
    
    df_resampled = df.resample(timeframe).agg({'price': 'ohlc', 'volume': 'sum'})
    df_resampled.columns = ['open', 'high', 'low', 'close', 'volume_total']
    df_resampled.dropna(subset=['close'], inplace=True)

    df['price_bin'] = (df['price'] / price_bin_size).round() * price_bin_size
    vp_data = df.groupby([pd.Grouper(freq=timeframe), 'price_bin'])['volume'].sum().reset_index()
    vp_pivot = vp_data.pivot(index='price_bin', columns='timestamp', values='volume')
    text_values = vp_pivot.apply(lambda x: x.map(lambda v: f"{int(v)}" if pd.notnull(v) and v > 0 else "")).values

    # --- CREAZIONE GRAFICO ---
    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        x=vp_pivot.columns,
        y=vp_pivot.index,
        z=vp_pivot.values,
        text=text_values,
        texttemplate="%{text}", 
        textfont={"size": 10, "family": "Courier New, monospace", "color": "#FFB90F"},
        colorscale=[[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']],
        showscale=False,
        name='Footprint',
        xgap=0, ygap=0
    ))

    fig.add_trace(go.Scatter(
        x=df_resampled.index,
        y=df_resampled['close'],
        mode='markers',
        marker=dict(symbol='line-ns-open', size=8, color='white', opacity=0.3),
        name='Close Marker'
    ))

    fig.update_layout(
        title=dict(text=f'BTP FOOTPRINT - {nome_output.replace(".html", "").upper()}', font=dict(size=18, color='white')),
        paper_bgcolor='#121212',
        plot_bgcolor='#121212',
        dragmode='pan',
        xaxis_rangeslider_visible=False,
        height=900,
        showlegend=False,
        margin=dict(l=10, r=60, t=50, b=10),
        yaxis=dict(side='right', gridcolor='#222222', tickfont=dict(color='white'), showgrid=True),
        xaxis=dict(gridcolor='#222222', tickfont=dict(color='white'), showgrid=True, dtick=4*60*60*1000) # Tick ogni 4 ore per pulizia
    )
    
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[18, 8], pattern="hour")])

    fig.write_html(nome_output)
    print(f"Completato: {nome_output}")

# --- ESECUZIONE PER 6 MESI ---
settimana_inizio = 2
for i in range(6):
    mese_num = i + 1
    settimane = list(range(settimana_inizio, settimana_inizio + 4))
    nome_file = f'btp_footprint_mese_{mese_num}.html'
    genera_grafico_mensile(settimane, nome_file)
    settimana_inizio += 4

print("\n--- TUTTI I GRAFICI MENSILI SONO STATI GENERATI ---")
