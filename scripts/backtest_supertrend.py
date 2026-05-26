# Ciao! Questo è un commento di prova inserito in diretta da Antigravity per mostrarti l'integrazione.
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

def load_data(filepath):
    """Carica e pulisce i dati BTP dal file di testo daily."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Il file '{filepath}' non esiste.")
        
    # Carica il file tab-separated
    df = pd.read_csv(filepath, sep='\t')
    # Pulisce i nomi delle colonne
    df.columns = [col.strip().lower() for col in df.columns]
    
    # Converte la colonna data
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df = df.sort_values('data').reset_index(drop=True)
    
    # Sostituisce la virgola con il punto e converte in float
    numeric_cols = ['high', 'low', 'open', 'close', 'volume']
    for col in numeric_cols:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
            else:
                df[col] = df[col].astype(float)
                
    return df

def calculate_supertrend(df, period=20, multiplier=2.0, atr_type='sma'):
    """Calcola l'indicatore Supertrend e l'ATR."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    # True Range (TR)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Average True Range (ATR)
    if atr_type == 'sma':
        df['atr'] = df['tr'].rolling(window=period).mean()
    elif atr_type == 'ema':
        df['atr'] = df['tr'].ewm(span=period, adjust=False).mean()
    else: # rma (Wilder)
        df['atr'] = df['tr'].ewm(alpha=1/period, adjust=False).mean()
        
    # HL2 (prezzo medio)
    df['hl2'] = (high + low) / 2
    
    df['basic_ub'] = df['hl2'] + multiplier * df['atr']
    df['basic_lb'] = df['hl2'] - multiplier * df['atr']
    
    final_ub = [0.0] * len(df)
    final_lb = [0.0] * len(df)
    supertrend = [0.0] * len(df)
    direction = [1] * len(df) # 1 = Long, -1 = Short
    
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
        
        # Final Upper Band
        if df['basic_ub'].iloc[i] < prev_final_ub or prev_close > prev_final_ub:
            final_ub[i] = df['basic_ub'].iloc[i]
        else:
            final_ub[i] = prev_final_ub
            
        # Final Lower Band
        if df['basic_lb'].iloc[i] > prev_final_lb or prev_close < prev_final_lb:
            final_lb[i] = df['basic_lb'].iloc[i]
        else:
            final_lb[i] = prev_final_lb
            
        # Supertrend direction logic
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
    df['final_ub'] = final_ub
    df['final_lb'] = final_lb
    
    return df

def run_backtest(df, tp_multiplier=1.0, trade_type='both', ma_col=None, max_drawdown_pct=5.0):
    """
    Esegue il backtest della strategia Supertrend.
    trade_type: 'both', 'long_only', 'short_only'
    max_drawdown_pct: Max drawdown threshold in percentuale (es: 5.0 per 5%). Stops trading when reached.
    """
    trades = []
    in_position = False
    pos_type = None # 'long' o 'short'
    entry_price = 0.0
    entry_idx = 0
    tp_level = 0.0
    atr_at_entry = 0.0

    equity = [0.0] * len(df)
    current_equity = 0.0
    peak_equity = 0.0

    # Per tracciare l'equity curva
    equity_curve = []
    drawdown_curve = []

    for i in range(len(df)):
        if i < 21: # Periodo di riscaldamento per ATR
            equity_curve.append(0.0)
            drawdown_curve.append(0.0)
            continue

        # Segnali del giorno precedente
        prev_dir = df['direction'].iloc[i-1]
        prev_prev_dir = df['direction'].iloc[i-2] if i >= 2 else prev_dir

        current_date = df['data'].iloc[i]
        current_open = df['open'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        current_supertrend = df['supertrend'].iloc[i]
        current_dir = df['direction'].iloc[i]

        # Calcola drawdown corrente
        if peak_equity > 0:
            current_drawdown_pct = ((peak_equity - current_equity) / peak_equity) * 100
        else:
            current_drawdown_pct = 0.0

        drawdown_curve.append(current_drawdown_pct)

        # 1. Gestione posizione aperta
        if in_position:
            if pos_type == 'long':
                # Verifica Take Profit (intraday)
                if current_high >= tp_level:
                    pnl = tp_level - entry_price
                    trades.append({
                        'type': 'Long',
                        'entry_date': df['data'].iloc[entry_idx],
                        'entry_price': entry_price,
                        'exit_date': current_date,
                        'exit_price': tp_level,
                        'exit_reason': 'Take Profit',
                        'pnl': pnl,
                        'pnl_eur': pnl * 1000, # 1 punto = 1000 EUR
                        'duration': i - entry_idx
                    })
                    current_equity += pnl
                    in_position = False
                    pos_type = None
                # Verifica Stop Loss (in chiusura)
                elif current_close < current_supertrend:
                    pnl = current_close - entry_price
                    trades.append({
                        'type': 'Long',
                        'entry_date': df['data'].iloc[entry_idx],
                        'entry_price': entry_price,
                        'exit_date': current_date,
                        'exit_price': current_close,
                        'exit_reason': 'Supertrend Stop',
                        'pnl': pnl,
                        'pnl_eur': pnl * 1000,
                        'duration': i - entry_idx
                    })
                    current_equity += pnl
                    in_position = False
                    pos_type = None
                    
            elif pos_type == 'short':
                # Verifica Take Profit (intraday)
                if current_low <= tp_level:
                    pnl = entry_price - tp_level
                    trades.append({
                        'type': 'Short',
                        'entry_date': df['data'].iloc[entry_idx],
                        'entry_price': entry_price,
                        'exit_date': current_date,
                        'exit_price': tp_level,
                        'exit_reason': 'Take Profit',
                        'pnl': pnl,
                        'pnl_eur': pnl * 1000,
                        'duration': i - entry_idx
                    })
                    current_equity += pnl
                    in_position = False
                    pos_type = None
                # Verifica Stop Loss (in chiusura)
                elif current_close > current_supertrend:
                    pnl = entry_price - current_close
                    trades.append({
                        'type': 'Short',
                        'entry_date': df['data'].iloc[entry_idx],
                        'entry_price': entry_price,
                        'exit_date': current_date,
                        'exit_price': current_close,
                        'exit_reason': 'Supertrend Stop',
                        'pnl': pnl,
                        'pnl_eur': pnl * 1000,
                        'duration': i - entry_idx
                    })
                    current_equity += pnl
                    in_position = False
                    pos_type = None
                    
        # 2. Nuovi Ingressi (solo se non siamo in posizione E drawdown < threshold)
        if not in_position and current_drawdown_pct < max_drawdown_pct:
            # Condizioni MA
            close_prev = df['close'].iloc[i-1]
            ma_val_prev = df[ma_col].iloc[i-1] if ma_col is not None and ma_col in df.columns else None

            allow_long = True
            allow_short = True

            if ma_val_prev is not None and not np.isnan(ma_val_prev):
                allow_long = close_prev > ma_val_prev
                allow_short = close_prev < ma_val_prev

            # Long Entry: Supertrend passa da rosso a verde AND close_prev > ma_prev
            if prev_dir == 1 and prev_prev_dir == -1 and (trade_type in ['both', 'long_only']) and allow_long:
                in_position = True
                pos_type = 'long'
                entry_price = current_open
                entry_idx = i
                atr_at_entry = df['atr'].iloc[i-1]
                tp_level = entry_price + tp_multiplier * atr_at_entry

            # Short Entry: Supertrend passa da verde a rosso AND close_prev < ma_prev
            elif prev_dir == -1 and prev_prev_dir == 1 and (trade_type in ['both', 'short_only']) and allow_short:
                in_position = True
                pos_type = 'short'
                entry_price = current_open
                entry_idx = i
                atr_at_entry = df['atr'].iloc[i-1]
                tp_level = entry_price - tp_multiplier * atr_at_entry

        # Aggiorna peak equity
        if current_equity > peak_equity:
            peak_equity = current_equity

        # Traccia l'equity corrente
        equity_curve.append(current_equity)
        
    df['equity'] = equity_curve
    df['drawdown_pct'] = drawdown_curve
    return trades, df

def calculate_statistics(trades, df):
    """Calcola le metriche di performance."""
    if not trades:
        return {
            'total_trades': 0, 'win_rate': 0.0, 'profit_factor': 0.0,
            'net_profit': 0.0, 'net_profit_eur': 0.0, 'avg_trade': 0.0, 'max_drawdown': 0.0
        }
        
    trades_df = pd.DataFrame(trades)
    
    total_trades = len(trades_df)
    winning_trades = trades_df[trades_df['pnl'] > 0]
    losing_trades = trades_df[trades_df['pnl'] <= 0]
    
    win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
    
    gross_profit = winning_trades['pnl'].sum()
    gross_loss = abs(losing_trades['pnl'].sum())
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    net_profit = trades_df['pnl'].sum()
    net_profit_eur = trades_df['pnl_eur'].sum()
    avg_trade = trades_df['pnl'].mean()
    
    # Massimo Drawdown
    equity_series = df['equity']
    cum_max = equity_series.cummax()
    drawdown = cum_max - equity_series
    max_drawdown = drawdown.max() # In punti
    max_drawdown_eur = max_drawdown * 1000
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'net_profit': net_profit,
        'net_profit_eur': net_profit_eur,
        'avg_trade': avg_trade,
        'avg_trade_eur': avg_trade * 1000,
        'max_drawdown': max_drawdown,
        'max_drawdown_eur': max_drawdown_eur,
        'winning_trades': len(winning_trades),
        'losing_trades': len(losing_trades),
        'avg_duration': trades_df['duration'].mean()
    }

def main():
    filepath = 'giornaliero btp.txt'
    print("Caricamento dati in corso...")
    df = load_data(filepath)
    print(f"Dati caricati: {len(df)} righe dal {df['data'].min().strftime('%d/%m/%Y')} al {df['data'].max().strftime('%d/%m/%Y')}.")
    
    # 1. Configurazione Parametri Standard
    period = 20
    multiplier = 1.5
    tp_multiplier = 999.0 # Nessun TP
    
    print(f"\nCalcolo Supertrend({period}, {multiplier})...")
    df = calculate_supertrend(df, period=period, multiplier=multiplier, atr_type='rma')
    
    print("\nCalcolo Media Mobile Semplice a 21 periodi (SMA 21)...")
    df['sma21'] = df['close'].rolling(window=21).mean()
    
    # 2. Esecuzione Backtest con Filtro SMA 21 (Strategia Vincitrice)
    print("Esecuzione backtest con Filtro SMA 21 (Strategia Vincitrice)...")
    trades, df_result = run_backtest(df, tp_multiplier=tp_multiplier, trade_type='both', ma_col='sma21', max_drawdown_pct=5.0)
    stats = calculate_statistics(trades, df_result)

    # 3. Esecuzione Backtest di riferimento senza Filtro SMA 21
    print("Esecuzione backtest di controllo senza Filtro SMA 21...")
    trades_no_ma, df_result_no_ma = run_backtest(df, tp_multiplier=tp_multiplier, trade_type='both', ma_col=None, max_drawdown_pct=5.0)
    stats_no_ma = calculate_statistics(trades_no_ma, df_result_no_ma)
    
    # Stampa i risultati nel terminale
    print("\n================ STATISTICHE STRATEGIA VINCENTE (CON SMA 21) ================")
    print(f"Operazioni Totali:     {stats['total_trades']}")
    print(f"Percentuale Vincenti:  {stats['win_rate']:.2f}% ({stats['winning_trades']} W / {stats['losing_trades']} L)")
    print(f"Profit Factor:         {stats['profit_factor']:.2f}")
    print(f"Net Profit (Punti):    {stats['net_profit']:.2f}")
    print(f"Net Profit (EUR):      {stats['net_profit_eur']:,.2f} €")
    print(f"Operazione Media:      {stats['avg_trade_eur']:.2f} €")
    print(f"Max Drawdown (Punti):  {stats['max_drawdown']:.2f}")
    print(f"Max Drawdown (EUR):    {stats['max_drawdown_eur']:,.2f} €")
    print(f"Durata Media (Giorni): {stats['avg_duration']:.1f}")
    print(f"MAX DRAWDOWN CONSTRAINT: 5% - Trading si ferma quando raggiunto")
    
    print("\n================ STATISTICHE DI CONTROLLO (SENZA FILTRO SMA 21) ================")
    print(f"Operazioni Totali:     {stats_no_ma['total_trades']}")
    print(f"Percentuale Vincenti:  {stats_no_ma['win_rate']:.2f}% ({stats_no_ma['winning_trades']} W / {stats_no_ma['losing_trades']} L)")
    print(f"Profit Factor:         {stats_no_ma['profit_factor']:.2f}")
    print(f"Net Profit (Punti):    {stats_no_ma['net_profit']:.2f}")
    print(f"Net Profit (EUR):      {stats_no_ma['net_profit_eur']:,.2f} €")
    print(f"Operazione Media:      {stats_no_ma['avg_trade_eur']:.2f} €")
    print(f"Max Drawdown (Punti):  {stats_no_ma['max_drawdown']:.2f}")
    print(f"Max Drawdown (EUR):    {stats_no_ma['max_drawdown_eur']:,.2f} €")
    print(f"Durata Media (Giorni): {stats_no_ma['avg_duration']:.1f}")

    # 4. Ottimizzazione del Multiplier TP (Tabella comparativa con SMA 21)
    print("\nOttimizzazione in corso (ricerca TP ottimale con filtro SMA 21 + constraint drawdown 5%)...")
    tp_mults = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 999.0]
    opt_results = []
    for tp in tp_mults:
        t_trades, t_df = run_backtest(df, tp_multiplier=tp, trade_type='both', ma_col='sma21', max_drawdown_pct=5.0)
        t_stats = calculate_statistics(t_trades, t_df)
        label = f"ATR x {tp}" if tp != 999.0 else "Solo Supertrend (No TP)"
        opt_results.append({
            'Configurazione': label,
            'Trades': t_stats['total_trades'],
            'Win Rate %': f"{t_stats['win_rate']:.1f}%",
            'Profit Factor': f"{t_stats['profit_factor']:.2f}",
            'Net Profit (€)': f"{t_stats['net_profit_eur']:,.2f} €",
            'Max Drawdown (€)': f"{t_stats['max_drawdown_eur']:,.2f} €"
        })
    opt_df = pd.DataFrame(opt_results)
    print(opt_df.to_string(index=False))

    # --- CREAZIONE GRAFICO INTERATTIVO ---
    # Creiamo un subplot: Sopra il prezzo con Supertrend e Trade, Sotto l'Equity Curve, In fondo il Drawdown
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=("Prezzo BTP, Supertrend(20, 1.5), SMA 21 e Operazioni", "Curva di Equity (EUR)", "Drawdown % (Max Constraint: 5%)")
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
            name='BTP Daily'
        ),
        row=1, col=1
    )
    
    # 2. Linea SMA 21
    fig.add_trace(
        go.Scatter(
            x=df_result['data'], y=df_result['sma21'],
            line=dict(color='#00F2FE', width=1.5, dash='dashdot'),
            name='Filtro SMA 21'
        ),
        row=1, col=1
    )
    
    # 3. Linea Supertrend
    # Per colorarla dinamicamente verde/rossa senza discontinuità, possiamo tracciare segmenti separati o usare una maschera
    # Più semplicemente, tracciamo la linea colorandola in base alla direzione
    # Per farlo pulito in Plotly, possiamo separare in due serie (Long ST e Short ST) con valori nulli quando non attivi
    st_long = df_result['supertrend'].copy()
    st_long[df_result['direction'] == -1] = np.nan
    st_short = df_result['supertrend'].copy()
    st_short[df_result['direction'] == 1] = np.nan
    
    fig.add_trace(
        go.Scatter(
            x=df_result['data'], y=st_long,
            line=dict(color='#00FF7F', width=2),
            name='Supertrend Long',
            connectgaps=False
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=df_result['data'], y=st_short,
            line=dict(color='#FF4500', width=2),
            name='Supertrend Short',
            connectgaps=False
        ),
        row=1, col=1
    )
    
    # 4. Segnali di Ingresso/Uscita sul grafico dei prezzi
    entry_long_x = []
    entry_long_y = []
    exit_long_x = []
    exit_long_y = []
    
    entry_short_x = []
    entry_short_y = []
    exit_short_x = []
    exit_short_y = []
    
    for t in trades:
        if t['type'] == 'Long':
            entry_long_x.append(t['entry_date'])
            entry_long_y.append(t['entry_price'])
            exit_long_x.append(t['exit_date'])
            exit_long_y.append(t['exit_price'])
        else:
            entry_short_x.append(t['entry_date'])
            entry_short_y.append(t['entry_price'])
            exit_short_x.append(t['exit_date'])
            exit_short_y.append(t['exit_price'])
            
    fig.add_trace(
        go.Scatter(
            x=entry_long_x, y=entry_long_y,
            mode='markers',
            marker=dict(symbol='triangle-up', size=10, color='lime', line=dict(color='black', width=1)),
            name='Buy (Long)',
            hovertext='Ingresso Long'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=exit_long_x, y=exit_long_y,
            mode='markers',
            marker=dict(symbol='x', size=8, color='gold', line=dict(color='black', width=1)),
            name='Exit (Long)',
            hovertext='Uscita Long'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=entry_short_x, y=entry_short_y,
            mode='markers',
            marker=dict(symbol='triangle-down', size=10, color='red', line=dict(color='black', width=1)),
            name='Sell (Short)',
            hovertext='Ingresso Short'
        ),
        row=1, col=1
    )
    
    fig.add_trace(
        go.Scatter(
            x=exit_short_x, y=exit_short_y,
            mode='markers',
            marker=dict(symbol='x', size=8, color='magenta', line=dict(color='black', width=1)),
            name='Exit (Short)',
            hovertext='Uscita Short'
        ),
        row=1, col=1
    )
    
    # 5. Equity Curve (Subplot 2)
    fig.add_trace(
        go.Scatter(
            x=df_result['data'],
            y=df_result['equity'] * 1000, # In EUR
            line=dict(color='#FFB90F', width=2.5),
            fill='tozeroy',
            fillcolor='rgba(255, 185, 15, 0.1)',
            name='Equity Con SMA 21 (EUR)'
        ),
        row=2, col=1
    )

    # Curva di equity senza SMA 21 per confronto
    fig.add_trace(
        go.Scatter(
            x=df_result_no_ma['data'],
            y=df_result_no_ma['equity'] * 1000,
            line=dict(color='gray', width=1.5, dash='dash'),
            name='Equity Senza SMA 21 (EUR)'
        ),
        row=2, col=1
    )

    # 6. Drawdown Curve (Subplot 3)
    fig.add_trace(
        go.Scatter(
            x=df_result['data'],
            y=df_result['drawdown_pct'],
            line=dict(color='#FF6B6B', width=2),
            fill='tozeroy',
            fillcolor='rgba(255, 107, 107, 0.2)',
            name='Drawdown %'
        ),
        row=3, col=1
    )

    # Linea del constraint al 5%
    fig.add_hline(y=5.0, line_dash='dash', line_color='red', line_width=2,
                  annotation_text='Max Drawdown 5%', annotation_position='right',
                  row=3, col=1)
    
    # Stile Layout
    fig.update_layout(
        title=dict(
            text='BTP SUPERTREND STRATEGY BACKTEST - DETAILED REPORT (CON SMA 21 + MAX 5% DRAWDOWN)',
            font=dict(size=20, color='white')
        ),
        template='plotly_dark',
        paper_bgcolor='#0a0a0a',
        plot_bgcolor='#0a0a0a',
        height=1200,
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

    fig.update_yaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), row=1, col=1)
    fig.update_yaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), title_text='Equity (€)', row=2, col=1)
    fig.update_yaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), title_text='Drawdown %', row=3, col=1)
    fig.update_xaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), row=1, col=1)
    fig.update_xaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), row=2, col=1)
    fig.update_xaxes(gridcolor='#1e1e1e', tickfont=dict(color='white'), row=3, col=1)
    
    # Salva il report in HTML
    output_filename = 'btp_supertrend_backtest.html'
    fig.write_html(output_filename, config={'scrollZoom': True})
    print(f"\nGrafico interattivo salvato con successo in '{output_filename}'.")
    
if __name__ == "__main__":
    main()
