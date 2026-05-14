import pandas as pd
import plotly.graph_objects as go
import os

def carica_dati_btp(path):
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, sep='\t', header=None, names=['timestamp', 'price', 'volume'], parse_dates=['timestamp'])
        df.set_index('timestamp', inplace=True)
        return df
    except:
        return None

def genera_volume_profile_mensile(num_mesi=6, sett_per_mese=4):
    fig = go.Figure()
    
    settimana_corrente = 2
    x_labels = []
    
    for m in range(num_mesi):
        lista_df = []
        for s in range(settimana_corrente, settimana_corrente + sett_per_mese):
            filename = f'PULITO_btp_trasformato_week_{s}.txt'
            df_s = carica_dati_btp(filename)
            if df_s is not None:
                lista_df.append(df_s)
        
        if not lista_df:
            settimana_corrente += sett_per_mese
            continue
            
        df_mese = pd.concat(lista_df).sort_index()
        
        c_open = df_mese['price'].iloc[0]
        c_high = df_mese['price'].max()
        c_low = df_mese['price'].min()
        c_close = df_mese['price'].iloc[-1]
        data_inizio = df_mese.index[0].strftime('%b %Y')
        x_labels.append(data_inizio)
        
        price_bin_size = 0.01 
        df_mese['price_bin'] = (df_mese['price'] / price_bin_size).round() * price_bin_size
        vp = df_mese.groupby('price_bin')['volume'].sum()
        vp_max = vp.max()
        
        x_base = m
        volumes_norm = (vp / vp_max) * 0.8
        
        color = 'rgba(0, 255, 127, 0.5)' if c_close >= c_open else 'rgba(255, 69, 0, 0.5)'

        # 1. Istogrammi con SpikeLines attivate
        fig.add_trace(go.Bar(
            y=vp.index,
            x=volumes_norm,
            base=x_base + 0.05,
            orientation='h',
            marker=dict(color=color, line=dict(width=0)),
            hovertext=[f"Mese: {data_inizio}<br>Prezzo: {p:.2f}<br>Volume: {int(v)}" for p, v in vp.items()],
            hoverinfo='text',
            showlegend=False,
            width=price_bin_size * 0.9
        ))

        # 2. Candela OHLC
        fig.add_trace(go.Candlestick(
            x=[x_base],
            open=[c_open],
            high=[c_high],
            low=[c_low],
            close=[c_close],
            increasing_line_color='#00FF7F',
            decreasing_line_color='#FF4500',
            name=f'Candela {data_inizio}',
            showlegend=False
        ))
        
        settimana_corrente += sett_per_mese

    fig.update_layout(
        title=dict(text='BTP MONTHLY VOLUME PROFILE - PRO TRADING SUITE', font=dict(size=22, color='white')),
        template='plotly_dark',
        paper_bgcolor='#0a0a0a', # Ancora più scuro per contrasto pro
        plot_bgcolor='#0a0a0a',
        xaxis=dict(
            tickvals=list(range(len(x_labels))),
            ticktext=x_labels,
            gridcolor='#1e1e1e',
            tickfont=dict(color='white'),
            range=[-0.3, num_mesi - 0.2],
            showspikes=True, # Attiva asse orizzontale (spikeline)
            spikemode='across',
            spikethickness=1,
            spikedash='dash',
            spikecolor='#555555'
        ),
        yaxis=dict(
            side='right',
            gridcolor='#1e1e1e',
            tickfont=dict(color='white'),
            autorange=True,
            fixedrange=False,
            showspikes=True, # Attiva asse verticale (spikeline)
            spikemode='across',
            spikethickness=1,
            spikedash='dash',
            spikecolor='#555555'
        ),
        dragmode=False,
        hovermode='closest',
        height=900,
        margin=dict(l=10, r=60, t=80, b=50),
        xaxis_rangeslider_visible=False,
        bargap=0
    )

    config = {'displayModeBar': False}
    html_content = fig.to_html(config=config, include_plotlyjs='cdn')
    
    css_fix = """
    <style>
        .js-plotly-plot .plotly .cursor-crosshair { cursor: default !important; }
        .js-plotly-plot .plotly .drag { cursor: default !important; }
        .nsewdrag { cursor: default !important; }
        .hoverlayer .hovertext rect { fill: #1e1e1e !important; stroke: #FFB90F !important; }
        .hoverlayer .hovertext text { fill: #FFB90F !important; font-family: 'Courier New', monospace !important; font-weight: bold !important; }
    </style>
    """
    html_content = html_content.replace('</head>', css_fix + '</head>')

    output_file = 'btp_volume_profile_mensile.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"Grafico aggiornato con assi dinamici (SpikeLines) stile professionale.")

if __name__ == "__main__":
    genera_volume_profile_mensile()
