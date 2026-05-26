# Modifica fatta da G
import pandas as pd
import plotly.graph_objects as go
import os

def carica_dati_btp(path):
    if not os.path.exists(path):
        print(f"Errore: Il file '{path}' non esiste.")
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
        print(f"Errore durante la lettura: {e}")
        return None

# Caricamento diretto per il test
file_test = 'PULITO_btp_trasformato_week_2.txt'
df = carica_dati_btp(file_test)

if df is not None:
    # --- ELABORAZIONE DATI ---
    timeframe = '60min'
    price_bin_size = 0.02
    
    df_resampled = df.resample(timeframe).agg({
        'price': 'ohlc',
        'volume': 'sum'
    })
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
        textfont={"size": 11, "family": "Courier New, monospace", "color": "#FFB90F"},
        colorscale=[[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']],
        showscale=False,
        name='Footprint',
        xgap=0, ygap=0
    ))

    fig.add_trace(go.Scatter(
        x=df_resampled.index,
        y=df_resampled['close'],
        mode='markers',
        marker=dict(symbol='line-ns-open', size=10, color='white', opacity=0.3),
        name='Close Marker'
    ))

    fig.update_layout(
        title=dict(text=f'BTP FOOTPRINT TEST - {file_test} ({timeframe})', font=dict(size=18, color='white')),
        paper_bgcolor='#121212',
        plot_bgcolor='#121212',
        dragmode='pan',
        xaxis_rangeslider_visible=False,
        height=850,
        showlegend=False,
        margin=dict(l=10, r=60, t=50, b=10),
        yaxis=dict(side='right', gridcolor='#222222', tickfont=dict(color='white'), showgrid=True),
        xaxis=dict(gridcolor='#222222', tickfont=dict(color='white'), showgrid=True, dtick=60*60*1000)
    )
    
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"]), dict(bounds=[18, 8], pattern="hour")])

    # Salvataggio come HTML per visualizzazione
    output_html = 'btp_footprint_test.html'
    fig.write_html(output_html)
    print(f"Grafico salvato in {output_html}")
else:
    print("Errore nel caricamento del file di test.")
