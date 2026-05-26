import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

filepath = os.path.join('dati', 'bund_220m.txt')
df = pd.read_csv(filepath, sep='\t')
df.columns = [col.strip().lower() for col in df.columns]
df['data'] = pd.to_datetime(df['data'])
df = df.sort_values('data').reset_index(drop=True)
for col in ['high', 'low', 'open', 'close', 'volume']:
    if col in df.columns:
        df[col] = df[col].astype(float)

period = 20
multiplier = 1.5

high = df['high']
low = df['low']
close = df['close']

tr1 = high - low
tr2 = (high - close.shift(1)).abs()
tr3 = (low - close.shift(1)).abs()
df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()
df['hl2'] = (high + low) / 2
df['basic_ub'] = df['hl2'] + multiplier * df['atr']
df['basic_lb'] = df['hl2'] - multiplier * df['atr']

n = len(df)
final_ub = np.zeros(n)
final_lb = np.zeros(n)
supertrend = np.zeros(n)
direction = np.ones(n)

for i in range(n):
    if i == 0:
        final_ub[i] = df['basic_ub'].iloc[i]
        final_lb[i] = df['basic_lb'].iloc[i]
        supertrend[i] = final_ub[i]
        direction[i] = -1
        continue
    prev_close = df['close'].iloc[i-1]
    prev_final_ub = final_ub[i-1]
    prev_final_lb = final_lb[i-1]
    if df['basic_ub'].iloc[i] < prev_final_ub or prev_close > prev_final_ub:
        final_ub[i] = df['basic_ub'].iloc[i]
    else:
        final_ub[i] = prev_final_ub
    if df['basic_lb'].iloc[i] > prev_final_lb or prev_close < prev_final_lb:
        final_lb[i] = df['basic_lb'].iloc[i]
    else:
        final_lb[i] = prev_final_lb
    prev_supertrend = supertrend[i-1]
    if prev_supertrend == prev_final_ub:
        if df['close'].iloc[i] > final_ub[i]:
            supertrend[i] = final_lb[i]
            direction[i] = 1
        else:
            supertrend[i] = final_ub[i]
            direction[i] = -1
    else:
        if df['close'].iloc[i] < final_lb[i]:
            supertrend[i] = final_ub[i]
            direction[i] = -1
        else:
            supertrend[i] = final_lb[i]
            direction[i] = 1

df['supertrend'] = supertrend
df['direction'] = direction

df['prev_dir'] = df['direction'].shift(1)

entry_long_idx = set(df[(df['prev_dir'] == -1) & (df['direction'] == 1)].index)
entry_short_idx = set(df[(df['prev_dir'] == 1) & (df['direction'] == -1)].index)

# Build hover text for each candle including entry signal
hover_texts = []
for i in range(len(df)):
    base = f'O:{df["open"].iloc[i]:.2f} H:{df["high"].iloc[i]:.2f} L:{df["low"].iloc[i]:.2f} C:{df["close"].iloc[i]:.2f}'
    if i in entry_long_idx:
        hover_texts.append(f'{base}<br><span style="color:#00E676">▲ LONG @ {df["close"].iloc[i]:.2f}</span>')
    elif i in entry_short_idx:
        hover_texts.append(f'{base}<br><span style="color:#FF1744">▼ SHORT @ {df["close"].iloc[i]:.2f}</span>')
    else:
        hover_texts.append(base)

price_range = df['close'].max() - df['close'].min()
arrow_offset = price_range * 0.008

entry_long_idx_list = sorted(entry_long_idx)
entry_short_idx_list = sorted(entry_short_idx)

entry_long_x = df.loc[entry_long_idx_list, 'data']
entry_long_y_arrow = df.loc[entry_long_idx_list, 'close'].values - arrow_offset
entry_prices_long = df.loc[entry_long_idx_list, 'close'].values

entry_short_x = df.loc[entry_short_idx_list, 'data']
entry_short_y_arrow = df.loc[entry_short_idx_list, 'close'].values + arrow_offset
entry_prices_short = df.loc[entry_short_idx_list, 'close'].values

fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=df['data'],
    open=df['open'],
    high=df['high'],
    low=df['low'],
    close=df['close'],
    increasing_line_color='#26a69a',
    decreasing_line_color='#ef5350',
    name='BUND 220M',
    text=hover_texts,
    hovertemplate='%{text}<extra></extra>',
    showlegend=False
))

uptrend_mask = df['direction'] == 1
downtrend_mask = df['direction'] == -1

fig.add_trace(go.Scatter(
    x=df.loc[uptrend_mask, 'data'],
    y=df.loc[uptrend_mask, 'supertrend'],
    mode='lines',
    line=dict(color='#66BB6A', width=2),
    name='SuperTrend UP',
    hoverinfo='skip',
    showlegend=False
))
fig.add_trace(go.Scatter(
    x=df.loc[downtrend_mask, 'data'],
    y=df.loc[downtrend_mask, 'supertrend'],
    mode='lines',
    line=dict(color='#ef5350', width=2),
    name='SuperTrend DOWN',
    hoverinfo='skip',
    showlegend=False
))

fig.add_trace(go.Scatter(
    x=entry_long_x,
    y=entry_long_y_arrow,
    mode='markers+text',
    marker=dict(
        symbol='triangle-up',
        size=16,
        color='#00E676',
        line=dict(color='white', width=1.5)
    ),
    text=[f'{p:.2f}' for p in entry_prices_long],
    textposition='bottom center',
    textfont=dict(color='#00E676', size=10, family='Consolas', weight='bold'),
    hoverinfo='skip',
    showlegend=False
))

fig.add_trace(go.Scatter(
    x=entry_short_x,
    y=entry_short_y_arrow,
    mode='markers+text',
    marker=dict(
        symbol='triangle-down',
        size=16,
        color='#FF1744',
        line=dict(color='white', width=1.5)
    ),
    text=[f'{p:.2f}' for p in entry_prices_short],
    textposition='top center',
    textfont=dict(color='#FF1744', size=10, family='Consolas', weight='bold'),
    hoverinfo='skip',
    showlegend=False
))

fig.update_layout(
    title=dict(
        text=f'BUND 220M — SuperTrend({period}, {multiplier})',
        font=dict(size=22, color='#e0e0e0')
    ),
    template='plotly_dark',
    paper_bgcolor='#0d0d0d',
    plot_bgcolor='#0d0d0d',
    height=800,
    margin=dict(l=60, r=60, t=80, b=50),
    xaxis_rangeslider_visible=False,
    hovermode='x unified',
    hoverdistance=100,
    spikedistance=1000,
    hoverlabel=dict(
        bgcolor='#1a1a1a',
        font=dict(color='#fff', size=12, family='Consolas'),
        bordercolor='#444',
        namelength=-1
    ),
    dragmode='zoom',
    showlegend=False
)

hide_gaps = [
    dict(bounds=["sat", "mon"]),
    dict(bounds=[19, 8], pattern="hour")
]

fig.update_yaxes(
    gridcolor='#1e1e1e',
    tickfont=dict(color='#aaa', size=11),
    title=dict(text='Prezzo', font=dict(color='#aaa')),
    showspikes=True,
    spikemode='across',
    spikesnap='cursor',
    spikedash='solid',
    spikecolor='#888888',
    spikethickness=1
)
fig.update_xaxes(
    gridcolor='#1e1e1e',
    tickfont=dict(color='#aaa', size=11),
    rangebreaks=hide_gaps,
    rangeslider=dict(visible=False),
    showspikes=True,
    spikemode='across',
    spikesnap='cursor',
    spikedash='solid',
    spikecolor='#888888',
    spikethickness=1,
    rangeselector=dict(
        buttons=list([
            dict(count=1, label='1M', step='month', stepmode='backward'),
            dict(count=3, label='3M', step='month', stepmode='backward'),
            dict(count=6, label='6M', step='month', stepmode='backward'),
            dict(count=1, label='1Y', step='year', stepmode='backward'),
            dict(label='ALL', step='all')
        ]),
        bgcolor='#1a1a1a',
        activecolor='#333333',
        font=dict(color='#ccc', size=10)
    )
)

output_path = os.path.join('outputhtml', 'bund_220m_supertrend_chart.html')
os.makedirs('outputhtml', exist_ok=True)
fig.write_html(output_path, config={
    'scrollZoom': True,
    'displayModeBar': True,
    'modeBarButtonsToRemove': ['lasso2d', 'select2d', 'pan2d'],
    'displaylogo': False,
    'responsive': True
})
print(f'Grafico salvato: {output_path}')
print(f'Candele: {len(df)}')
print(f'Entry Long: {len(entry_long_idx)}')
print(f'Entry Short: {len(entry_short_idx)}')
