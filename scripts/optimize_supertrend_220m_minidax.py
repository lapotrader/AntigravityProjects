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

# *** MINI DAX: 5 EUR per punto, commissioni 3+3=6 EUR ***
PER_POINT = 5.0
COMMISSION = 6.0

def run_backtest_ma(df, tp_multiplier, ma_series=None):
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
        current_open = df['open'].iloc[i]
        current_high = df['high'].iloc[i]
        current_low = df['low'].iloc[i]
        current_close = df['close'].iloc[i]
        current_supertrend = df['supertrend'].iloc[i]
        if in_position:
            if pos_type == 'long':
                if tp_multiplier != 999.0 and current_high >= tp_level:
                    pnl = ((tp_level - entry_price) * PER_POINT) - COMMISSION
                    current_equity += pnl
                    trades.append({'type': 'Long', 'pnl': pnl, 'duration': i - entry_idx})
                    in_position = False
                    pos_type = None
                elif current_close < current_supertrend:
                    pnl = ((current_close - entry_price) * PER_POINT) - COMMISSION
                    current_equity += pnl
                    trades.append({'type': 'Long', 'pnl': pnl, 'duration': i - entry_idx})
                    in_position = False
                    pos_type = None
            elif pos_type == 'short':
                if tp_multiplier != 999.0 and current_low <= tp_level:
                    pnl = ((entry_price - tp_level) * PER_POINT) - COMMISSION
                    current_equity += pnl
                    trades.append({'type': 'Short', 'pnl': pnl, 'duration': i - entry_idx})
                    in_position = False
                    pos_type = None
                elif current_close > current_supertrend:
                    pnl = ((entry_price - current_close) * PER_POINT) - COMMISSION
                    current_equity += pnl
                    trades.append({'type': 'Short', 'pnl': pnl, 'duration': i - entry_idx})
                    in_position = False
                    pos_type = None
        if not in_position:
            close_prev = df['close'].iloc[i-1]
            ma_val_prev = ma_series.iloc[i-1] if ma_series is not None else None
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
                tp_level = entry_price + tp_multiplier * df['atr'].iloc[i-1]
            elif prev_dir == -1 and prev_prev_dir == 1 and allow_short:
                in_position = True
                pos_type = 'short'
                entry_price = current_open
                entry_idx = i
                tp_level = entry_price - tp_multiplier * df['atr'].iloc[i-1]
        equity_curve.append(current_equity)
    equity_arr = np.array(equity_curve)
    cum_max = np.maximum.accumulate(equity_arr)
    drawdown = cum_max - equity_arr
    max_dd = drawdown.max() if len(drawdown) > 0 else 0
    return trades, current_equity, max_dd

def main():
    df = load_data('dax_220m.txt')
    print(f"Mini DAX - dati caricati: {len(df)} barre da {df['data'].iloc[0].date()} a {df['data'].iloc[-1].date()}")
    print(f"Valore punto: {PER_POINT} EUR | Commissioni: {COMMISSION} EUR")

    ma_dict = {
        21:    df['close'].rolling(window=21).mean(),
        50:    df['close'].rolling(window=50).mean(),
        100:   df['close'].rolling(window=100).mean(),
        200:   df['close'].rolling(window=200).mean(),
        'None': None
    }

    results = []
    periods = [10, 14, 20, 30]
    multipliers = [1.5, 2.0, 2.5, 3.0, 4.0]
    tps = [0.5, 1.0, 1.5, 2.0, 3.0, 999.0]
    ma_periods = ['None', 21, 50, 100, 200]

    total = len(periods) * len(multipliers) * len(tps) * len(ma_periods)
    print(f"Inizio ottimizzazione Mini DAX (220m) - {total} combinazioni...")

    count = 0
    for period in periods:
        for mult in multipliers:
            df_st = df.copy()
            df_st = calculate_supertrend(df_st, period, mult)
            for tp in tps:
                for ma_p in ma_periods:
                    ma_series = ma_dict[ma_p]
                    trades, final_profit, max_dd = run_backtest_ma(df_st, tp, ma_series)
                    count += 1
                    if len(trades) == 0:
                        continue
                    pnl_series = [t['pnl'] for t in trades]
                    wins = sum(1 for p in pnl_series if p > 0)
                    win_rate = (wins / len(trades)) * 100
                    gross_profit = sum(p for p in pnl_series if p > 0)
                    gross_loss = abs(sum(p for p in pnl_series if p <= 0))
                    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
                    results.append({
                        'MA Period': str(ma_p),
                        'ST Period': period,
                        'ST Multiplier': mult,
                        'TP Multiplier': tp if tp != 999.0 else 'No TP',
                        'Total Trades': len(trades),
                        'Win Rate (%)': round(win_rate, 1),
                        'Profit Factor': round(profit_factor, 2),
                        'Net Profit (EUR)': round(final_profit, 2),
                        'Max Drawdown (EUR)': round(max_dd, 2),
                        'Profit/DD Ratio': round(final_profit / max_dd, 2) if max_dd > 0 else 0
                    })

    print(f"Combinazioni elaborate: {count}")

    res_df = pd.DataFrame(results)
    res_df = res_df.sort_values(by='Profit/DD Ratio', ascending=False)
    res_df.to_csv('minidax_220m_optimization_results.csv', index=False)

    # HTML report
    html_table = res_df.head(100).to_html(index=False, float_format=lambda x: f"{x:,.2f}" if isinstance(x, float) else x, classes='data')

    html_template = f"""
    <html>
    <head>
        <title>Risultati Ottimizzazione Mini DAX 220M</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; margin: 40px; }}
            h1 {{ color: #00F2FE; text-align: center; }}
            h2 {{ color: #FFB90F; }}
            p {{ color: #aaa; }}
            table {{ border-collapse: collapse; width: 100%; margin-top: 20px; box-shadow: 0 0 20px rgba(0,0,0,0.5); }}
            th, td {{ padding: 10px 14px; text-align: right; border-bottom: 1px solid #333; }}
            th {{ background-color: #1e1e1e; color: #00F2FE; text-transform: uppercase; font-size: 11px; font-weight: bold; position: sticky; top: 0; }}
            tr:nth-child(even) {{ background-color: #1a1a1a; }}
            tr:hover {{ background-color: #2a2a2a; }}
        </style>
    </head>
    <body>
        <h1>&#128202; Risultati Ottimizzazione Mini DAX (220 Minuti)</h1>
        <p>Valore punto: 5 EUR | Commissioni: 6 EUR (3+3) | Dati: dax_220m.txt</p>
        <h2>&#127942; Top 100 Configurazioni (ordinate per Profit/DD Ratio)</h2>
        {html_table}
    </body>
    </html>
    """
    with open('minidax_220m_optimization_report.html', 'w', encoding='utf-8') as f:
        f.write(html_template)

    # Stampa top 20 a console
    print("\n===== TOP 20 CONFIGURAZIONI MINI DAX (Profit/DD Ratio) =====")
    print(f"{'Rank':>4} {'MA':>6} {'ST-P':>5} {'Mult':>5} {'TP':>6} {'Trades':>7} {'WR%':>6} {'PF':>6} {'Profit(EUR)':>12} {'DD(EUR)':>10} {'P/DD':>6}")
    print("-"*90)
    for rank, (_, row) in enumerate(res_df.head(20).iterrows(), 1):
        print(f"  {rank:>2}  {row['MA Period']:>6} {row['ST Period']:>5} {row['ST Multiplier']:>5.1f} {str(row['TP Multiplier']):>6} "
              f"{row['Total Trades']:>7} {row['Win Rate (%)']:>6.1f} {row['Profit Factor']:>6.2f} "
              f"{row['Net Profit (EUR)']:>12,.0f} {row['Max Drawdown (EUR)']:>10,.0f} {row['Profit/DD Ratio']:>6.2f}")

    print(f"\nReport HTML: minidax_220m_optimization_report.html")
    print(f"CSV completo: minidax_220m_optimization_results.csv")

if __name__ == '__main__':
    main()
