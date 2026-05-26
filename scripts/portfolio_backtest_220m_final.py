import pandas as pd
import numpy as np
import plotly.graph_objects as go
import os

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def load_and_filter_data(filepath, start_date=None, end_date=None):
    """Load a tab‑separated historical file, convert numeric columns and optionally filter by date."""
    df = pd.read_csv(filepath, sep='\t')
    df.columns = [c.strip().lower() for c in df.columns]
    # Parse date column (named 'data' in the generated 220m files)
    try:
        df['data'] = pd.to_datetime(df['data'])
    except Exception:
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    # Ensure numeric columns are float
    for col in ['high', 'low', 'open', 'close', 'volume']:
        if col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(',', '.').astype(float)
            else:
                df[col] = df[col].astype(float)
    # Optional date window
    if start_date:
        df = df[df['data'] >= start_date]
    if end_date:
        df = df[df['data'] <= end_date]
    return df.sort_values('data').reset_index(drop=True)

# ---------------------------------------------------------------------------
# Supertrend implementation (identical to earlier scripts)
# ---------------------------------------------------------------------------

def calculate_supertrend(df, period, multiplier):
    high, low, close = df['high'], df['low'], df['close']
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
        # Upper band
        if df['basic_ub'].iloc[i] < prev_final_ub or prev_close > prev_final_ub:
            final_ub[i] = df['basic_ub'].iloc[i]
        else:
            final_ub[i] = prev_final_ub
        # Lower band
        if df['basic_lb'].iloc[i] > prev_final_lb or prev_close < prev_final_lb:
            final_lb[i] = df['basic_lb'].iloc[i]
        else:
            final_lb[i] = prev_final_lb
        # Supertrend direction
        prev_super = supertrend[i-1]
        if prev_super == prev_final_ub:
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

# ---------------------------------------------------------------------------
# Strategy runner – generic but with per‑instrument scaling
# ---------------------------------------------------------------------------

PER_POINT = {
    'minidax': 5.0,
    'btp': 1000.0,
    'bund': 1000.0,
    'stoxx': 10.0
}
COMMISSION = 6.0  # 3 € + 3 € per trade (same for all instruments)

def run_strategy(df, period, multiplier, tp_multiplier, ma_period, instrument='bund'):
    df = df.copy()
    df = calculate_supertrend(df, period, multiplier)
    ma_col = None
    if ma_period and str(ma_period) != 'None':
        ma_col = f'sma{ma_period}'
        df[ma_col] = df['close'].rolling(window=int(ma_period)).mean()
    # Tracking
    trades = []
    in_position = False
    pos_type = None
    entry_price = 0.0
    tp_level = 0.0
    pnl_per_bar = [0.0] * len(df)
    for i in range(len(df)):
        # Need enough historic data for SMA if used
        min_idx = max(21, int(ma_period) if ma_col else 0)
        if i < min_idx:
            continue
        prev_dir = df['direction'].iloc[i-1]
        prev_prev_dir = df['direction'].iloc[i-2] if i >= 2 else prev_dir
        cur_open = df['open'].iloc[i]
        cur_high = df['high'].iloc[i]
        cur_low = df['low'].iloc[i]
        cur_close = df['close'].iloc[i]
        cur_super = df['supertrend'].iloc[i]
        if in_position:
            pnl = 0.0
            closed = False
            if pos_type == 'long':
                if cur_high >= tp_level and tp_multiplier != 999.0:
                    pnl = ((tp_level - entry_price) * PER_POINT[instrument]) - COMMISSION
                    closed = True
                elif cur_close < cur_super:
                    pnl = ((cur_close - entry_price) * PER_POINT[instrument]) - COMMISSION
                    closed = True
            else:  # short
                if cur_low <= tp_level and tp_multiplier != 999.0:
                    pnl = ((entry_price - tp_level) * PER_POINT[instrument]) - COMMISSION
                    closed = True
                elif cur_close > cur_super:
                    pnl = ((entry_price - cur_close) * PER_POINT[instrument]) - COMMISSION
                    closed = True
            if closed:
                pnl_per_bar[i] = pnl
                trades.append({'type': 'Long' if pos_type == 'long' else 'Short', 'pnl_eur': pnl})
                in_position = False
                pos_type = None
        # Entry logic
        if not in_position:
            close_prev = df['close'].iloc[i-1]
            ma_prev = df[ma_col].iloc[i-1] if ma_col else None
            allow_long = True
            allow_short = True
            if ma_prev is not None and not np.isnan(ma_prev):
                allow_long = close_prev > ma_prev
                allow_short = close_prev < ma_prev
            if prev_dir == 1 and prev_prev_dir == -1 and allow_long:
                in_position = True
                pos_type = 'long'
                entry_price = cur_open
                atr = df['atr'].iloc[i-1]
                tp_level = entry_price + tp_multiplier * atr
            elif prev_dir == -1 and prev_prev_dir == 1 and allow_short:
                in_position = True
                pos_type = 'short'
                entry_price = cur_open
                atr = df['atr'].iloc[i-1]
                tp_level = entry_price - tp_multiplier * atr
    df['bar_pnl_eur'] = pnl_per_bar
    return df, trades

# ---------------------------------------------------------------------------
# Draw‑down helper
# ---------------------------------------------------------------------------

def calc_drawdown(equity_series):
    cum_max = equity_series.cummax()
    drawdown = cum_max - equity_series
    return drawdown.max() if not drawdown.empty else 0

# ---------------------------------------------------------------------------
# Main execution – synchronize all four instruments on the common date range
# ---------------------------------------------------------------------------

def main():
    print("Loading all data series …")
    btp = load_and_filter_data('btp_220m.txt')
    bund = load_and_filter_data('bund_220m.txt')
    dax = load_and_filter_data('dax_220m.txt')
    stoxx = load_and_filter_data('stoxx_220m.txt')
    # Find overlapping interval
    start = max(btp['data'].min(), bund['data'].min(), dax['data'].min(), stoxx['data'].min())
    end = min(btp['data'].max(), bund['data'].max(), dax['data'].max(), stoxx['data'].max())
    print(f"Common period: {start.date()} – {end.date()}")
    # Apply the common filter
    btp = load_and_filter_data('btp_220m.txt', start, end)
    bund = load_and_filter_data('bund_220m.txt', start, end)
    dax = load_and_filter_data('dax_220m.txt', start, end)
    stoxx = load_and_filter_data('stoxx_220m.txt', start, end)
    # -------------------------------------------------------------------
    # Run each instrument with the *best* configuration discovered earlier
    # -------------------------------------------------------------------
    print("Running BTP - ST(20,3.0) SMA21 TP=1.0 ...")
    res_btp, trades_btp = run_strategy(btp, period=20, multiplier=3.0, tp_multiplier=1.0, ma_period=21, instrument='btp')
    print("Running BUND - ST(20,1.5) SMA50 No TP ...")
    res_bund, trades_bund = run_strategy(bund, period=20, multiplier=1.5, tp_multiplier=999.0, ma_period=50, instrument='bund')
    print("Running MINIDAX - ST(10,4.0) SMA50 TP=3.0 ...")
    res_minidax, trades_minidax = run_strategy(dax, period=10, multiplier=4.0, tp_multiplier=3.0, ma_period=50, instrument='minidax')
    print("Running Euro-Stoxx - ST(10,4.0) SMA21 TP=1.0 ...")
    res_stoxx, trades_stoxx = run_strategy(stoxx, period=10, multiplier=4.0, tp_multiplier=1.0, ma_period=21, instrument='stoxx')
    # -------------------------------------------------------------------
    # Assemble a combined equity curve
    # -------------------------------------------------------------------
    btp_pnl = res_btp[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'btp_pnl'})
    bund_pnl = res_bund[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'bund_pnl'})
    minidax_pnl = res_minidax[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'minidax_pnl'})
    stoxx_pnl = res_stoxx[['data', 'bar_pnl_eur']].rename(columns={'bar_pnl_eur': 'stoxx_pnl'})
    port = pd.merge(btp_pnl, bund_pnl, on='data', how='outer')
    port = pd.merge(port, minidax_pnl, on='data', how='outer')
    port = pd.merge(port, stoxx_pnl, on='data', how='outer').fillna(0)
    port = port.sort_values('data').reset_index(drop=True)
    port['total_pnl'] = port[['btp_pnl', 'bund_pnl', 'minidax_pnl', 'stoxx_pnl']].sum(axis=1)
    # Cumulative equity per instrument and total
    port['btp_eq'] = port['btp_pnl'].cumsum()
    port['bund_eq'] = port['bund_pnl'].cumsum()
    port['minidax_eq'] = port['minidax_pnl'].cumsum()
    port['stoxx_eq'] = port['stoxx_pnl'].cumsum()
    port['portfolio_eq'] = port['total_pnl'].cumsum()
    # -------------------------------------------------------------------
    # Simple statistics helper
    # -------------------------------------------------------------------
    def stats(trades, equity_series):
        profit = equity_series.iloc[-1] if not equity_series.empty else 0
        dd = calc_drawdown(equity_series)
        gross = sum(t['pnl_eur'] for t in trades if t['pnl_eur'] > 0)
        loss = abs(sum(t['pnl_eur'] for t in trades if t['pnl_eur'] <= 0))
        pf = gross / loss if loss > 0 else float('inf')
        return profit, dd, pf, len(trades)
    btp_res = stats(trades_btp, port['btp_eq'])
    bund_res = stats(trades_bund, port['bund_eq'])
    minidax_res = stats(trades_minidax, port['minidax_eq'])
    stoxx_res = stats(trades_stoxx, port['stoxx_eq'])
    port_res = stats(trades_btp + trades_bund + trades_minidax + trades_stoxx, port['portfolio_eq'])
    # -------------------------------------------------------------------
    # Print summary
    # -------------------------------------------------------------------
    print("\n===== RISULTATI COMBINATI (periodo comune) =====")
    print(f"BTP     – Profit: {btp_res[0]:,.2f} € | DD: {btp_res[1]:,.2f} € | Ratio: {(btp_res[0]/btp_res[1]) if btp_res[1] else 0:.2f} | PF: {btp_res[2]:.2f} | Trades: {btp_res[3]}")
    print(f"BUND    – Profit: {bund_res[0]:,.2f} € | DD: {bund_res[1]:,.2f} € | Ratio: {(bund_res[0]/bund_res[1]) if bund_res[1] else 0:.2f} | PF: {bund_res[2]:.2f} | Trades: {bund_res[3]}")
    print(f"MINIDAX – Profit: {minidax_res[0]:,.2f} € | DD: {minidax_res[1]:,.2f} € | Ratio: {(minidax_res[0]/minidax_res[1]) if minidax_res[1] else 0:.2f} | PF: {minidax_res[2]:.2f} | Trades: {minidax_res[3]}")
    print(f"STOXX   – Profit: {stoxx_res[0]:,.2f} € | DD: {stoxx_res[1]:,.2f} € | Ratio: {(stoxx_res[0]/stoxx_res[1]) if stoxx_res[1] else 0:.2f} | PF: {stoxx_res[2]:.2f} | Trades: {stoxx_res[3]}")
    print(f"TOTAL   – Profit: {port_res[0]:,.2f} € | DD: {port_res[1]:,.2f} € | Ratio: {(port_res[0]/port_res[1]) if port_res[1] else 0:.2f} | PF: {port_res[2]:.2f} | Trades: {port_res[3]}")
    # -------------------------------------------------------------------
    # Interactive Plotly report
    # -------------------------------------------------------------------
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=port['data'], y=port['portfolio_eq'],
                             mode='lines', line=dict(color='#00FF7F', width=3),
                             name=f'Portfolio (Net {port_res[0]:,.0f} €, DD {port_res[1]:,.0f} €)',
                             fill='tozeroy', fillcolor='rgba(0,255,127,0.1)'))
    # Individual lines (thin, dotted)
    fig.add_trace(go.Scatter(x=port['data'], y=port['btp_eq'], mode='lines', line=dict(color='#FFB90F', width=1.5, dash='dot'), name='BTP'))
    fig.add_trace(go.Scatter(x=port['data'], y=port['bund_eq'], mode='lines', line=dict(color='#00F2FE', width=1.5, dash='dot'), name='BUND'))
    fig.add_trace(go.Scatter(x=port['data'], y=port['minidax_eq'], mode='lines', line=dict(color='#FF4500', width=1.5, dash='dot'), name='MINIDAX'))
    fig.add_trace(go.Scatter(x=port['data'], y=port['stoxx_eq'], mode='lines', line=dict(color='#FFD700', width=1.5, dash='dot'), name='Euro‑Stoxx'))
    fig.update_layout(
        title=dict(text='Portafoglio combinato BTP + BUND + MINIDAX + Euro‑Stoxx (220 min)', font=dict(size=22, color='white')),
        template='plotly_dark',
        paper_bgcolor='#0a0a0a', plot_bgcolor='#0a0a0a',
        height=800,
        xaxis=dict(title='Data', gridcolor='#1e1e1e'),
        yaxis=dict(title='Equity (€)', gridcolor='#1e1e1e'),
        legend=dict(x=0.02, y=0.98, bgcolor='rgba(0,0,0,0.5)', bordercolor='white', borderwidth=1)
    )
    out_file = 'portfolio_combined_4asset.html'
    fig.write_html(out_file, config={'scrollZoom': True})
    print(f"Report HTML salvato in '{out_file}'.")

if __name__ == '__main__':
    main()
