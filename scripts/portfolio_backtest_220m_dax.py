import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

def load_and_filter_data(filepath, start_date=None, end_date=None):
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
                
    if start_date:
        df = df[df['data'] >= start_date]
    if end_date:
        df = df[df['data'] <= end_date]
        
    return df.reset_index(drop=True)

def calculate_supertrend(df, period, multiplier):
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

def run_strategy(df, period, multiplier, tp_multiplier, ma_period, instrument='bund'):
    df = df.copy()
    df = calculate_supertrend(df, period, multiplier)
    
    if ma_period and str(ma_period) != 'None':
        ma_col = f'sma{ma_period}'
        df[ma_col] = df['close'].rolling(window=int(ma_period)).mean()
    else:
        ma_col = None
        
    trades = []
    in_position = False
    pos_type = None
    entry_price = 0.0
    entry_idx = 0
    tp_level = 0.0
    
    pnl_per_bar = [0.0] * len(df)
    
    for i in range(len(df)):
        if i < max(21, int(ma_period) if (ma_period and str(ma_period) != 'None') else 0):
            continue
            
        prev_dir = df['direction'].iloc[i-1]
        prev_prev_dir = df['direction'].iloc[i-2] if i >= 2 else prev_dir
        
        current_date = df['data'].iloc[i]
        current_open = df['open'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        current_supertrend = df['supertrend'].iloc[i]
        
        if in_position:
            pnl_eur = 0.0
            trade_closed = False
            
            if pos_type == 'long':
                if current_high >= tp_level and tp_multiplier != 999.0:
                    if instrument == 'dax':
                        pnl_eur = ((tp_level - entry_price) * 25.0) - 6.0
                    else:
                        pnl_eur = ((tp_level - entry_price) - 0.006) * 1000
                    trade_closed = True
                elif current_close < current_supertrend:
                    if instrument == 'dax':
                        pnl_eur = ((current_close - entry_price) * 25.0) - 6.0
                    else:
                        pnl_eur = ((current_close - entry_price) - 0.006) * 1000
                    trade_closed = True
            elif pos_type == 'short':
                if current_low <= tp_level and tp_multiplier != 999.0:
                    if instrument == 'dax':
                        pnl_eur = ((entry_price - tp_level) * 25.0) - 6.0
                    else:
                        pnl_eur = ((entry_price - tp_level) - 0.006) * 1000
                    trade_closed = True
                elif current_close > current_supertrend:
                    if instrument == 'dax':
                        pnl_eur = ((entry_price - current_close) * 25.0) - 6.0
                    else:
                        pnl_eur = ((entry_price - current_close) - 0.006) * 1000
                    trade_closed = True
                    
            if trade_closed:
                pnl_per_bar[i] = pnl_eur
                trades.append({'type': 'Long' if pos_type == 'long' else 'Short', 'pnl_eur': pnl_eur})
                in_position = False
                pos_type = None
                    
        if not in_position:
            close_prev = df['close'].iloc[i-1]
            ma_val_prev = df[ma_col].iloc[i-1] if ma_col else None
            
            allow_long = True
            allow_short = True
            
            if ma_val_prev is not None and not np.isnan(ma_val_prev):
                allow_long = close_prev > ma_val_prev
                allow_short = close_prev < ma_val_prev
                
            if prev_dir == 1 and prev_prev_dir == -1 and allow_long:
                in_position = True
                pos_type = 'long'
                entry_price = current_open
                entry_idx = i
                atr_at_entry = df['atr'].iloc[i-1]
                tp_level = entry_price + tp_multiplier * atr_at_entry
                
            elif prev_dir == -1 and prev_prev_dir == 1 and allow_short:
                in_position = True
                pos_type = 'short'
                entry_price = current_open
                entry_idx = i
                atr_at_entry = df['atr'].iloc[i-1]
                tp_level = entry_price - tp_multiplier * atr_at_entry
                
    df['bar_pnl_eur'] = pnl_per_bar
    return df, trades

def calc_drawdown(equity_series):
    cum_max = equity_series.cummax()
    drawdown = cum_max - equity_series
    return drawdown.max() if not drawdown.empty else 0

def main():
    print("Caricamento dati BTP, BUND e DAX per sincronizzazione...")
    df_btp_full = load_and_filter_data('btp_220m.txt')
    df_bund_full = load_and_filter_data('bund_220m.txt')
    df_dax_full = load_and_filter_data('dax_220m.txt')
    
    start_date = max(df_btp_full['data'].min(), df_bund_full['data'].min(), df_dax_full['data'].min())
    end_date = min(df_btp_full['data'].max(), df_bund_full['data'].max(), df_dax_full['data'].max())
    
    print(f"Periodo di intersezione comune: dal {start_date} al {end_date}")
    
    df_btp = load_and_filter_data('btp_220m.txt', start_date, end_date)
    df_bund = load_and_filter_data('bund_220m.txt', start_date, end_date)
    df_dax = load_and_filter_data('dax_220m.txt', start_date, end_date)
    
    print("Esecuzione strategia BTP (ST(20, 3.0), SMA 21, TP 1.0)...")
    res_btp, trades_btp = run_strategy(df_btp, period=20, multiplier=3.0, tp_multiplier=1.0, ma_period=21, instrument='btp')
    
    print("Esecuzione strategia BUND (ST(20, 1.5), SMA 50, No TP)...")
    res_bund, trades_bund = run_strategy(df_bund, period=20, multiplier=1.5, tp_multiplier=999.0, ma_period=50, instrument='bund')
    
    print("Esecuzione strategia DAX (ST(10, 4.0), SMA 100, TP 0.5)...")
    res_dax, trades_dax = run_strategy(df_dax, period=10, multiplier=4.0, tp_multiplier=0.5, ma_period=100, instrument='dax')
    
    btp_pnl = res_btp[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'btp_pnl'})
    bund_pnl = res_bund[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'bund_pnl'})
    dax_pnl = res_dax[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'dax_pnl'})
    
    port_df = pd.merge(btp_pnl, bund_pnl, on='data', how='outer')
    port_df = pd.merge(port_df, dax_pnl, on='data', how='outer').fillna(0)
    port_df = port_df.sort_values('data').reset_index(drop=True)
    
    port_df['total_pnl'] = port_df['btp_pnl'] + port_df['bund_pnl'] + port_df['dax_pnl']
    
    port_df['btp_equity'] = port_df['btp_pnl'].cumsum()
    port_df['bund_equity'] = port_df['bund_pnl'].cumsum()
    port_df['dax_equity'] = port_df['dax_pnl'].cumsum()
    port_df['portfolio_equity'] = port_df['total_pnl'].cumsum()
    
    def get_stats(trades, equity_series):
        profit = equity_series.iloc[-1] if not equity_series.empty else 0
        dd = calc_drawdown(equity_series)
        gw = sum(t['pnl_eur'] for t in trades if t['pnl_eur']>0)
        gl = abs(sum(t['pnl_eur'] for t in trades if t['pnl_eur']<=0))
        pf = gw / gl if gl > 0 else float('inf')
        return profit, dd, pf, len(trades)
        
    btp_profit, btp_dd, btp_pf, btp_trades = get_stats(trades_btp, port_df['btp_equity'])
    bund_profit, bund_dd, bund_pf, bund_trades = get_stats(trades_bund, port_df['bund_equity'])
    dax_profit, dax_dd, dax_pf, dax_trades = get_stats(trades_dax, port_df['dax_equity'])
    
    all_trades = trades_btp + trades_bund + trades_dax
    port_profit, port_dd, port_pf, port_trades = get_stats(all_trades, port_df['portfolio_equity'])
    
    print("\n========= RISULTATI SUL PERIODO COMUNE =========")
    print(f"[ BTP ] Profitto: {btp_profit:,.2f} € | Max DD: {btp_dd:,.2f} € | Ratio: {btp_profit/btp_dd if btp_dd>0 else 0:.2f} | PF: {btp_pf:.2f} | Tr: {btp_trades}")
    print(f"[BUND ] Profitto: {bund_profit:,.2f} € | Max DD: {bund_dd:,.2f} € | Ratio: {bund_profit/bund_dd if bund_dd>0 else 0:.2f} | PF: {bund_pf:.2f} | Tr: {bund_trades}")
    print(f"[ DAX ] Profitto: {dax_profit:,.2f} € | Max DD: {dax_dd:,.2f} € | Ratio: {dax_profit/dax_dd if dax_dd>0 else 0:.2f} | PF: {dax_pf:.2f} | Tr: {dax_trades}")
    print(f"[PORT.] Profitto: {port_profit:,.2f} € | Max DD: {port_dd:,.2f} € | Ratio: {port_profit/port_dd if port_dd>0 else 0:.2f} | PF: {port_pf:.2f} | Tr: {port_trades}")
    
    # Grafico HTML
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(x=port_df['data'], y=port_df['portfolio_equity'],
                             mode='lines', line=dict(color='#00FF7F', width=3),
                             name=f'Portafoglio BTP+BUND+DAX (Net: {port_profit:,.0f}€, DD: {port_dd:,.0f}€)',
                             fill='tozeroy', fillcolor='rgba(0, 255, 127, 0.1)'))
                             
    fig.add_trace(go.Scatter(x=port_df['data'], y=port_df['btp_equity'],
                             mode='lines', line=dict(color='#FFB90F', width=1.5, dash='dot'),
                             name=f'Solo BTP (Net: {btp_profit:,.0f}€, DD: {btp_dd:,.0f}€)'))
                             
    fig.add_trace(go.Scatter(x=port_df['data'], y=port_df['bund_equity'],
                             mode='lines', line=dict(color='#00F2FE', width=1.5, dash='dot'),
                             name=f'Solo BUND (Net: {bund_profit:,.0f}€, DD: {bund_dd:,.0f}€)'))
                             
    fig.add_trace(go.Scatter(x=port_df['data'], y=port_df['dax_equity'],
                             mode='lines', line=dict(color='#FF4500', width=1.5, dash='dot'),
                             name=f'Solo DAX (Net: {dax_profit:,.0f}€, DD: {dax_dd:,.0f}€)'))
                             
    fig.update_layout(
        title=dict(
            text=f"PORTAFOGLIO COMBINATO: BTP + BUND + DAX (220M)",
            font=dict(size=22, color='white')
        ),
        template='plotly_dark',
        paper_bgcolor='#0a0a0a',
        plot_bgcolor='#0a0a0a',
        height=800,
        margin=dict(l=50, r=50, t=80, b=50),
        xaxis=dict(gridcolor='#1e1e1e', title="Data"),
        yaxis=dict(gridcolor='#1e1e1e', title="Equity (EUR)"),
        legend=dict(x=0.02, y=0.98, bgcolor='rgba(0,0,0,0.5)', bordercolor='white', borderwidth=1)
    )
    
    output_filename = 'portfolio_combined_backtest_dax.html'
    fig.write_html(output_filename, config={'scrollZoom': True})
    print(f"Report interattivo del portafoglio salvato con successo in '{output_filename}'.")

if __name__ == '__main__':
    main()
