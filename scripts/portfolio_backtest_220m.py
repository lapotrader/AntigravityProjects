import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

COMMISSION = 0.006  # 6 EUR per trade in points (1 point = 1000 EUR)

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

def run_strategy(df, period, multiplier, tp_multiplier, ma_period, portfolio_dd_constraint=None):
    df = df.copy()
    df = calculate_supertrend(df, period, multiplier)

    if ma_period:
        ma_col = f'sma{ma_period}'
        df[ma_col] = df['close'].rolling(window=ma_period).mean()
    else:
        ma_col = None

    trades = []
    in_position = False
    pos_type = None
    entry_price = 0.0
    entry_idx = 0
    tp_level = 0.0

    # Invece di cumulare l'equity iterativamente, creiamo una colonna di PnL per barra (per semplificare il merge)
    pnl_per_bar = [0.0] * len(df)

    for i in range(len(df)):
        if i < max(21, ma_period if ma_period else 0):
            continue

        prev_dir = df['direction'].iloc[i-1]
        prev_prev_dir = df['direction'].iloc[i-2] if i >= 2 else prev_dir

        current_date = df['data'].iloc[i]
        current_open = df['open'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        current_supertrend = df['supertrend'].iloc[i]

        # Controlla se il portfolio drawdown constraint è attivo
        can_trade = True
        if portfolio_dd_constraint is not None and i < len(portfolio_dd_constraint):
            can_trade = portfolio_dd_constraint.iloc[i] < 5.0  # 5% threshold

        # 1. Gestione posizione aperta
        if in_position:
            if pos_type == 'long':
                if current_high >= tp_level:
                    pnl = (tp_level - entry_price) - COMMISSION
                    pnl_per_bar[i] = pnl * 1000  # PnL in EUR sulla barra di chiusura
                    trades.append({'type': 'Long', 'pnl_eur': pnl * 1000})
                    in_position = False
                    pos_type = None
                elif current_close < current_supertrend:
                    pnl = (current_close - entry_price) - COMMISSION
                    pnl_per_bar[i] = pnl * 1000
                    trades.append({'type': 'Long', 'pnl_eur': pnl * 1000})
                    in_position = False
                    pos_type = None

            elif pos_type == 'short':
                if current_low <= tp_level:
                    pnl = (entry_price - tp_level) - COMMISSION
                    pnl_per_bar[i] = pnl * 1000
                    trades.append({'type': 'Short', 'pnl_eur': pnl * 1000})
                    in_position = False
                    pos_type = None
                elif current_close > current_supertrend:
                    pnl = (entry_price - current_close) - COMMISSION
                    pnl_per_bar[i] = pnl * 1000
                    trades.append({'type': 'Short', 'pnl_eur': pnl * 1000})
                    in_position = False
                    pos_type = None

        # 2. Nuovi Ingressi (solo se portfolio drawdown < 5%)
        if not in_position and can_trade:
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
    print("Caricamento dati BTP e BUND per sincronizzazione...")
    df_btp_full = load_and_filter_data('btp_220m.txt')
    df_bund_full = load_and_filter_data('bund_220m.txt')

    # Sincronizzazione dei periodi (intersezione)
    start_date = max(df_btp_full['data'].min(), df_bund_full['data'].min())
    end_date = min(df_btp_full['data'].max(), df_bund_full['data'].max())

    print(f"Periodo di intersezione comune: dal {start_date} al {end_date}")

    df_btp = load_and_filter_data('btp_220m.txt', start_date, end_date)
    df_bund = load_and_filter_data('bund_220m.txt', start_date, end_date)

    # PASS 1: Calcola portfolio equity SENZA constraint
    print("PASS 1: Calcolo portfolio equity baseline (senza constraint)...")
    res_btp_base, trades_btp_base = run_strategy(df_btp, period=20, multiplier=3.0, tp_multiplier=1.0, ma_period=21)
    res_bund_base, trades_bund_base = run_strategy(df_bund, period=20, multiplier=1.5, tp_multiplier=999.0, ma_period=50)

    btp_pnl_base = res_btp_base[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'btp_pnl'})
    bund_pnl_base = res_bund_base[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'bund_pnl'})
    port_df_base = pd.merge(btp_pnl_base, bund_pnl_base, on='data', how='outer').fillna(0)
    port_df_base = port_df_base.sort_values('data').reset_index(drop=True)
    port_df_base['total_pnl'] = port_df_base['btp_pnl'] + port_df_base['bund_pnl']
    port_df_base['portfolio_equity'] = port_df_base['total_pnl'].cumsum()

    # Calcola drawdown del portfolio
    cum_max = port_df_base['portfolio_equity'].cummax()
    port_drawdown = (cum_max - port_df_base['portfolio_equity']) / cum_max.abs() * 100
    port_drawdown = port_drawdown.fillna(0)

    print(f"Portfolio max drawdown: {port_drawdown.max():.2f}%")

    # PASS 2: Ricalcola CON constraint al 5%
    print("PASS 2: Ricalcolo con MAX 5% DRAWDOWN CONSTRAINT su portfolio...")
    res_btp, trades_btp = run_strategy(df_btp, period=20, multiplier=3.0, tp_multiplier=1.0, ma_period=21,
                                      portfolio_dd_constraint=port_drawdown)
    res_bund, trades_bund = run_strategy(df_bund, period=20, multiplier=1.5, tp_multiplier=999.0, ma_period=50,
                                       portfolio_dd_constraint=port_drawdown)
    
    # Combiniamo i risultati su base data
    portfolio = pd.DataFrame({'data': pd.date_range(start=start_date, end=end_date, freq='min')})
    # Poichè le date/time sono esatte, usiamo merge per allineare

    btp_pnl = res_btp[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'btp_pnl'})
    bund_pnl = res_bund[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'bund_pnl'})

    port_df = pd.merge(btp_pnl, bund_pnl, on='data', how='outer').fillna(0)
    port_df = port_df.sort_values('data').reset_index(drop=True)

    port_df['total_pnl'] = port_df['btp_pnl'] + port_df['bund_pnl']

    # Equity curve cumulate
    port_df['btp_equity'] = port_df['btp_pnl'].cumsum()
    port_df['bund_equity'] = port_df['bund_pnl'].cumsum()
    port_df['portfolio_equity'] = port_df['total_pnl'].cumsum()
    port_df['portfolio_drawdown_pct'] = port_drawdown

    # Statistiche BTP
    btp_profit = port_df['btp_equity'].iloc[-1]
    btp_dd = calc_drawdown(port_df['btp_equity'])
    btp_pf = sum(t['pnl_eur'] for t in trades_btp if t['pnl_eur']>0) / abs(sum(t['pnl_eur'] for t in trades_btp if t['pnl_eur']<=0)) if sum(t['pnl_eur'] for t in trades_btp if t['pnl_eur']<=0) != 0 else float('inf')
    btp_trades = len(trades_btp)

    # Statistiche BUND
    bund_profit = port_df['bund_equity'].iloc[-1]
    bund_dd = calc_drawdown(port_df['bund_equity'])
    bund_pf = sum(t['pnl_eur'] for t in trades_bund if t['pnl_eur']>0) / abs(sum(t['pnl_eur'] for t in trades_bund if t['pnl_eur']<=0)) if sum(t['pnl_eur'] for t in trades_bund if t['pnl_eur']<=0) != 0 else float('inf')
    bund_trades = len(trades_bund)

    # Statistiche PORTAFOGLIO
    port_profit = port_df['portfolio_equity'].iloc[-1]
    port_dd = calc_drawdown(port_df['portfolio_equity'])

    all_trades = trades_btp + trades_bund
    port_pf = sum(t['pnl_eur'] for t in all_trades if t['pnl_eur']>0) / abs(sum(t['pnl_eur'] for t in all_trades if t['pnl_eur']<=0)) if sum(t['pnl_eur'] for t in all_trades if t['pnl_eur']<=0) != 0 else float('inf')
    port_trades = len(all_trades)

    print("\n========= RISULTATI CON MAX 5% PORTFOLIO DRAWDOWN CONSTRAINT =========")
    print(f"[ BTP ] Profitto: {btp_profit:,.2f} € | Max DD: {btp_dd:,.2f} € | Ratio: {btp_profit/btp_dd if btp_dd>0 else 0:.2f} | PF: {btp_pf:.2f} | Tr: {btp_trades}")
    print(f"[BUND ] Profitto: {bund_profit:,.2f} € | Max DD: {bund_dd:,.2f} € | Ratio: {bund_profit/bund_dd if bund_dd>0 else 0:.2f} | PF: {bund_pf:.2f} | Tr: {bund_trades}")
    print(f"[PORT.] Profitto: {port_profit:,.2f} € | Max DD: {port_dd:,.2f} € | Ratio: {port_profit/port_dd if port_dd>0 else 0:.2f} | PF: {port_pf:.2f} | Tr: {port_trades}")
    print(f"Max Portfolio Drawdown: {port_drawdown.max():.2f}%")
    
    # Grafico HTML con 2 subplot
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        row_heights=[0.7, 0.3],
        subplot_titles=("Equity Curve - Portfolio Combinato vs Singoli Asset", "Portfolio Drawdown (%) - MAX CONSTRAINT 5%")
    )

    fig.add_trace(go.Scatter(x=port_df['data'], y=port_df['portfolio_equity'],
                             mode='lines', line=dict(color='#00FF7F', width=3),
                             name=f'Portafoglio Combinato (Net: {port_profit:,.0f}€, DD: {port_dd:,.0f}€)',
                             fill='tozeroy', fillcolor='rgba(0, 255, 127, 0.1)'),
                  row=1, col=1)

    fig.add_trace(go.Scatter(x=port_df['data'], y=port_df['btp_equity'],
                             mode='lines', line=dict(color='#FFB90F', width=1.5, dash='dot'),
                             name=f'Solo BTP (Net: {btp_profit:,.0f}€, DD: {btp_dd:,.0f}€)'),
                  row=1, col=1)

    fig.add_trace(go.Scatter(x=port_df['data'], y=port_df['bund_equity'],
                             mode='lines', line=dict(color='#00F2FE', width=1.5, dash='dot'),
                             name=f'Solo BUND (Net: {bund_profit:,.0f}€, DD: {bund_dd:,.0f}€)'),
                  row=1, col=1)

    # Drawdown curve
    fig.add_trace(go.Scatter(x=port_df['data'], y=port_df['portfolio_drawdown_pct'],
                             mode='lines', line=dict(color='#FF6B6B', width=2),
                             fill='tozeroy', fillcolor='rgba(255, 107, 107, 0.2)',
                             name='Portfolio Drawdown %'),
                  row=2, col=1)

    # Linea constraint 5%
    fig.add_hline(y=5.0, line_dash='dash', line_color='red', line_width=2,
                  annotation_text='Max Drawdown 5%', annotation_position='right',
                  row=2, col=1)

    fig.update_layout(
        title=dict(
            text=f"PORTAFOGLIO COMBINATO: BTP + BUND (220M) - MAX 5% PORTFOLIO DRAWDOWN CONSTRAINT",
            font=dict(size=20, color='white')
        ),
        template='plotly_dark',
        paper_bgcolor='#0a0a0a',
        plot_bgcolor='#0a0a0a',
        height=1000,
        margin=dict(l=50, r=50, t=80, b=50),
        xaxis_rangeslider_visible=False,
        legend=dict(x=0.02, y=0.98, bgcolor='rgba(0,0,0,0.5)', bordercolor='white', borderwidth=1)
    )

    fig.update_yaxes(gridcolor='#1e1e1e', title_text='Equity (EUR)', row=1, col=1)
    fig.update_yaxes(gridcolor='#1e1e1e', title_text='Drawdown %', row=2, col=1)
    fig.update_xaxes(gridcolor='#1e1e1e', row=1, col=1)
    fig.update_xaxes(gridcolor='#1e1e1e', row=2, col=1)
    
    output_filename = 'portfolio_combined_backtest.html'
    fig.write_html(output_filename, config={'scrollZoom': True})
    print(f"Report interattivo del portafoglio salvato con successo in '{output_filename}'.")

if __name__ == '__main__':
    main()
