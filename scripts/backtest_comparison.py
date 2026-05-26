import pandas as pd
import numpy as np
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

def calculate_supertrend(df, period=20, multiplier=2.0):
    high = df['high']
    low = df['low']
    close = df['close']
    
    # True Range (TR)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    df['tr'] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Average True Range (ATR) - Wilder's RMA
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
    return df

def run_backtest(df, tp_multiplier=999.0, trade_type='both', ma_col=None):
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
                    pnl = tp_level - entry_price
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
                    pnl = current_close - entry_price
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
                    pnl = entry_price - tp_level
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
                    pnl = entry_price - current_close
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
            'net_profit_eur': 0.0, 'max_drawdown_eur': 0.0
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
        'max_drawdown_eur': max_drawdown_eur
    }

def print_comparison_table(results_list):
    res_df = pd.DataFrame(results_list)
    print("\n" + "="*80)
    print("CONFRONTO PERFORMANCE SUPERTREND: TIMEFRAME 220M VS 1H")
    print("="*80)
    print(res_df.to_string(index=False))
    print("="*80 + "\n")

def main():
    timeframes = {
        '220 Minuti': 'btp_220m.txt',
        '1 Ora': 'btp_1h.txt'
    }
    
    configurations = [
        # { 'name': 'Conf 1 (ST 20, 1.5, SMA 21, No TP)', 'st_period': 20, 'st_multiplier': 1.5, 'ma': 21, 'tp': 999.0 },
        # { 'name': 'Conf 2 (ST 20, 3.0, SMA 21, TP 1.0)', 'st_period': 20, 'st_multiplier': 3.0, 'ma': 21, 'tp': 1.0 },
        # { 'name': 'Conf 3 (ST 20, 3.0, No SMA, TP 1.0)', 'st_period': 20, 'st_multiplier': 3.0, 'ma': None, 'tp': 1.0 },
        { 'name': 'ST(20, 1.5) + SMA 21 (No TP)', 'st_period': 20, 'st_multiplier': 1.5, 'ma': 21, 'tp': 999.0 },
        { 'name': 'ST(20, 3.0) + SMA 21 + TP 1.0', 'st_period': 20, 'st_multiplier': 3.0, 'ma': 21, 'tp': 1.0 },
        { 'name': 'ST(20, 3.0) (No SMA) + TP 1.0', 'st_period': 20, 'st_multiplier': 3.0, 'ma': None, 'tp': 1.0 }
    ]
    
    comparison_results = []
    
    for tf_name, file_path in timeframes.items():
        print(f"Caricamento dati per timeframe {tf_name} ({file_path})...")
        df_raw = load_data(file_path)
        
        for conf in configurations:
            df = df_raw.copy()
            df = calculate_supertrend(df, period=conf['st_period'], multiplier=conf['st_multiplier'])
            
            # Calcolo SMA se specificato
            ma_col = None
            if conf['ma'] is not None:
                ma_col = f'sma{conf["ma"]}'
                df[ma_col] = df['close'].rolling(window=conf['ma']).mean()
                
            trades, df_res = run_backtest(df, tp_multiplier=conf['tp'], trade_type='both', ma_col=ma_col)
            stats = calculate_statistics(trades, df_res)
            
            comparison_results.append({
                'Timeframe': tf_name,
                'Strategia': conf['name'],
                'Trades': stats['total_trades'],
                'Win Rate': f"{stats['win_rate']:.1f}%",
                'PF': f"{stats['profit_factor']:.2f}",
                'Net Profit (€)': f"{stats['net_profit_eur']:,.2f} €",
                'Max DD (€)': f"{stats['max_drawdown_eur']:,.2f} €"
            })
            
    print_comparison_table(comparison_results)

if __name__ == '__main__':
    main()
