import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

def load_data(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Il file '{filepath}' non esiste.")
        
    df = pd.read_csv(filepath, sep='\t')
    df.columns = [col.strip().lower() for col in df.columns]
    
    try:
        df['data'] = pd.to_datetime(df['data'])
    except Exception:
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
        
    df = df.sort_values('data').reset_index(drop=True)
    numeric_cols = ['high', 'low', 'open', 'close', 'volume']
    for col in numeric_cols:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
            else:
                df[col] = df[col].astype(float)
                
    return df

def calculate_supertrend(df, period=20, multiplier=3.0):
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # ATR Wilder (RMA)
    df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()
    df['hl2'] = (high + low) / 2
    
    df['basic_ub'] = df['hl2'] + multiplier * df['atr']
    df['basic_lb'] = df['hl2'] - multiplier * df['atr']
    
    final_ub = [0.0] * len(df)
    final_lb = [0.0] * len(df)
    supertrend = [0.0] * len(df)
    direction = [1] * len(df)
    
    for i in range(len(df)):
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
    return df

def run_backtest(df, tp_multiplier=1.0, trade_type='both', ma_col=None):
    trades = []
    in_position = False
    pos_type = None
    entry_price = 0.0
    entry_idx = 0
    tp_level = 0.0
    
    equity_curve = []
    current_equity = 0.0
    
    for i in range(len(df)):
        if i < 21:
            equity_curve.append(0.0)
            continue
            
        prev_dir = df['direction'].iloc[i-1]
        prev_prev_dir = df['direction'].iloc[i-2] if i >= 2 else prev_dir
        
        current_date = df['data'].iloc[i]
        current_open = df['open'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        current_supertrend = df['supertrend'].iloc[i]
        
        # 1. Gestione posizione aperta
        if in_position:
            if pos_type == 'long':
                if current_high >= tp_level:
                    pnl = (tp_level - entry_price) - 0.006
                    current_equity += pnl
                    trades.append({
                        'type': 'Long', 'entry_date': df['data'].iloc[entry_idx],
                        'entry_price': entry_price, 'exit_date': current_date,
                        'exit_price': tp_level, 'exit_reason': 'Take Profit',
                        'pnl': pnl, 'pnl_eur': pnl * 1000, 'duration': i - entry_idx
                    })
                    in_position = False
                    pos_type = None
                elif current_close < current_supertrend:
                    pnl = (current_close - entry_price) - 0.006
                    current_equity += pnl
                    trades.append({
                        'type': 'Long', 'entry_date': df['data'].iloc[entry_idx],
                        'entry_price': entry_price, 'exit_date': current_date,
                        'exit_price': current_close, 'exit_reason': 'Supertrend Stop',
                        'pnl': pnl, 'pnl_eur': pnl * 1000, 'duration': i - entry_idx
                    })
                    in_position = False
                    pos_type = None
                    
            elif pos_type == 'short':
                if current_low <= tp_level:
                    pnl = (entry_price - tp_level) - 0.006
                    current_equity += pnl
                    trades.append({
                        'type': 'Short', 'entry_date': df['data'].iloc[entry_idx],
                        'entry_price': entry_price, 'exit_date': current_date,
                        'exit_price': tp_level, 'exit_reason': 'Take Profit',
                        'pnl': pnl, 'pnl_eur': pnl * 1000, 'duration': i - entry_idx
                    })
                    in_position = False
                    pos_type = None
                elif current_close > current_supertrend:
                    pnl = (entry_price - current_close) - 0.006
                    current_equity += pnl
                    trades.append({
                        'type': 'Short', 'entry_date': df['data'].iloc[entry_idx],
                        'entry_price': entry_price, 'exit_date': current_date,
                        'exit_price': current_close, 'exit_reason': 'Supertrend Stop',
                        'pnl': pnl, 'pnl_eur': pnl * 1000, 'duration': i - entry_idx
                    })
                    in_position = False
                    pos_type = None
                    
        # 2. Nuovi Ingressi
        if not in_position:
            close_prev = df['close'].iloc[i-1]
            ma_val_prev = df[ma_col].iloc[i-1] if ma_col is not None and ma_col in df.columns else None
            
            allow_long = True
            allow_short = True
            
            if ma_val_prev is not None and not np.isnan(ma_val_prev):
                allow_long = close_prev > ma_val_prev
                allow_short = close_prev < ma_val_prev
                
            if prev_dir == 1 and prev_prev_dir == -1 and (trade_type in ['both', 'long_only']) and allow_long:
                in_position = True
                pos_type = 'long'
                entry_price = current_open
                entry_idx = i
                atr_at_entry = df['atr'].iloc[i-1]
                tp_level = entry_price + tp_multiplier * atr_at_entry
                
            elif prev_dir == -1 and prev_prev_dir == 1 and (trade_type in ['both', 'short_only']) and allow_short:
                in_position = True
                pos_type = 'short'
                entry_price = current_open
                entry_idx = i
                atr_at_entry = df['atr'].iloc[i-1]
                tp_level = entry_price - tp_multiplier * atr_at_entry
                
        equity_curve.append(current_equity)
        
    df['equity'] = equity_curve
    return trades, df

def calculate_statistics(trades, df):
    if not trades:
        return {
            'total_trades': 0, 'win_rate': 0.0, 'profit_factor': 0.0,
            'net_profit_eur': 0.0, 'max_drawdown_eur': 0.0,
            'winning_trades': 0, 'losing_trades': 0, 'avg_duration': 0.0
        }
        
    trades_df = pd.DataFrame(trades)
    total_trades = len(trades_df)
    winning_trades = trades_df[trades_df['pnl'] > 0]
    losing_trades = trades_df[trades_df['pnl'] <= 0]
    
    win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
    gross_profit = winning_trades['pnl_eur'].sum()
    gross_loss = abs(losing_trades['pnl_eur'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    net_profit_eur = trades_df['pnl_eur'].sum()
    
    equity_series = df['equity'] * 1000
    cum_max = equity_series.cummax()
    drawdown = cum_max - equity_series
    max_drawdown_eur = drawdown.max()
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'net_profit_eur': net_profit_eur,
        'max_drawdown_eur': max_drawdown_eur,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'avg_duration': trades_df['duration'].mean() if not trades_df.empty else 0
    }

def main():
    filepath = 'bund_220m.txt'
    print("Caricamento dati...")
    df = load_data(filepath)
    
    # Parametri Ottimali (stessi usati per il BTP 220 Minuti)
    period = 20
    multiplier = 1.5
    tp_multiplier = 999.0
    ma_period = 50
    
    print(f"Calcolo Supertrend({period}, {multiplier})...")
    df = calculate_supertrend(df, period=period, multiplier=multiplier)
    
    ma_col = f'sma{ma_period}'
    print(f"Calcolo Filtro SMA {ma_period}...")
    df[ma_col] = df['close'].rolling(window=ma_period).mean()
    
    # Esecuzione Backtest con Filtro SMA
    print("Esecuzione backtest con SMA...")
    trades, df_result = run_backtest(df, tp_multiplier=tp_multiplier, trade_type='both', ma_col=ma_col)
    stats = calculate_statistics(trades, df_result)
    
    # Esecuzione Backtest senza Filtro SMA (di controllo)
    print("Esecuzione backtest senza SMA...")
    trades_no_ma, df_result_no_ma = run_backtest(df, tp_multiplier=tp_multiplier, trade_type='both', ma_col=None)
    stats_no_ma = calculate_statistics(trades_no_ma, df_result_no_ma)
    
    print(f"\n================ STATISTICHE CON SMA {ma_period} ================")
    print(f"Operazioni Totali:     {stats['total_trades']}")
    print(f"Percentuale Vincenti:  {stats['win_rate']:.2f}% ({stats['winning_trades']} W / {stats['losing_trades']} L)")
    print(f"Profit Factor:         {stats['profit_factor']:.2f}")
    print(f"Net Profit (EUR):      {stats['net_profit_eur']:,.2f} €")
    print(f"Max Drawdown (EUR):    {stats['max_drawdown_eur']:,.2f} €")
    print(f"Durata Media (Barre):  {stats['avg_duration']:.1f}")
    
    # Generazione grafico Plotly
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        subplot_titles=(f"Prezzo BUND 220M, ST({period}, {multiplier}), SMA {ma_period} e Operazioni", "Curva di Equity (EUR)")
    )
    
    # 1. Candlestick Prezzo
    fig.add_trace(
        go.Candlestick(
            x=df_result['data'],
            open=df_result['open'],
            high=df_result['high'],
            low=df_result['low'],
            close=df_result['close'],
            increasing_line_color='#00FF7F',
            decreasing_line_color='#FF4500',
            name='BUND 220M'
        ),
        row=1, col=1
    )
    
    # 2. Linea SMA
    fig.add_trace(
        go.Scatter(
            x=df_result['data'], y=df_result[ma_col],
            line=dict(color='#00F2FE', width=1.5, dash='dashdot'),
            name=f'Filtro SMA {ma_period}'
        ),
        row=1, col=1
    )
    
    # 3. Operazioni
    entry_long_x = [t['entry_date'] for t in trades if t['type'] == 'Long']
    entry_long_y = [t['entry_price'] for t in trades if t['type'] == 'Long']
    exit_long_x = [t['exit_date'] for t in trades if t['type'] == 'Long']
    exit_long_y = [t['exit_price'] for t in trades if t['type'] == 'Long']
    
    entry_short_x = [t['entry_date'] for t in trades if t['type'] == 'Short']
    entry_short_y = [t['entry_price'] for t in trades if t['type'] == 'Short']
    exit_short_x = [t['exit_date'] for t in trades if t['type'] == 'Short']
    exit_short_y = [t['exit_price'] for t in trades if t['type'] == 'Short']
    
    fig.add_trace(
        go.Scatter(
            x=entry_long_x, y=entry_long_y,
            mode='markers',
            marker=dict(symbol='triangle-up', size=11, color='lime', line=dict(color='black', width=1)),
            name='Buy (Long)',
            hovertext='Ingresso Long'
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=exit_long_x, y=exit_long_y,
            mode='markers',
            marker=dict(symbol='x', size=9, color='gold', line=dict(color='black', width=1)),
            name='Exit (Long)',
            hovertext='Uscita Long'
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=entry_short_x, y=entry_short_y,
            mode='markers',
            marker=dict(symbol='triangle-down', size=11, color='red', line=dict(color='black', width=1)),
            name='Sell (Short)',
            hovertext='Ingresso Short'
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=exit_short_x, y=exit_short_y,
            mode='markers',
            marker=dict(symbol='x', size=9, color='magenta', line=dict(color='black', width=1)),
            name='Exit (Short)',
            hovertext='Uscita Short'
        ),
        row=1, col=1
    )
    
    # 4. Equity Curve
    fig.add_trace(
        go.Scatter(
            x=df_result['data'],
            y=df_result['equity'] * 1000,
            line=dict(color='#FFB90F', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(255, 185, 15, 0.1)',
            name=f'Equity Con SMA {ma_period} (EUR)'
        ),
        row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df_result_no_ma['data'],
            y=df_result_no_ma['equity'] * 1000,
            line=dict(color='gray', width=1.5, dash='dash'),
            name='Equity Senza SMA (EUR)'
        ),
        row=2, col=1
    )
    
    fig.update_layout(
        title=dict(
            text=f'BUND 220M SUPERTREND BACKTEST - NET PROFIT: {stats["net_profit_eur"]:,.2f} €',
            font=dict(size=20, color='white')
        ),
        template='plotly_dark',
        paper_bgcolor='#0a0a0a',
        plot_bgcolor='#0a0a0a',
        height=950,
        margin=dict(l=50, r=50, t=80, b=50),
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )
    
    hide_gaps = [
        dict(bounds=["sat", "mon"]),
        dict(bounds=[19, 8], pattern="hour")
    ]
    
    fig.update_yaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), row=1, col=1)
    fig.update_yaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), row=2, col=1)
    fig.update_xaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), rangebreaks=hide_gaps, row=1, col=1)
    fig.update_xaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), rangebreaks=hide_gaps, row=2, col=1)
    
    output_filename = 'bund_220m_optimized_backtest.html'
    fig.write_html(output_filename, config={'scrollZoom': True})
    print(f"Report interattivo salvato con successo in '{output_filename}'.")

if __name__ == '__main__':
    main()
