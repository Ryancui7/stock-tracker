import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# ---------------------------------------------------------
# 1. 页面基本设置
# ---------------------------------------------------------
st.set_page_config(page_title="我的股票操盘记录", layout="wide", page_icon="📈")
st.title("📈 股票投资组合监控 (Pro Ver.)")

# ---------------------------------------------------------
# 2. 数据状态初始化
# ---------------------------------------------------------
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = [
        {
            "Account": "Main", "ISIN": "US0378331005", "Ticker": "AAPL", "Name": "Apple Inc",
            "Enter Date": date(2023, 1, 15), "GICS": "Info Tech",
            "Shares": 100, "Entry Price": 150.00,
            "Price Target": 200.00, "Loss Limit": 140.00,
            "Beta 180D": 1.2
        },
        {
            "Account": "Main", "ISIN": "US5949181045", "Ticker": "MSFT", "Name": "Microsoft",
            "Enter Date": date(2023, 3, 10), "GICS": "Info Tech",
            "Shares": 50, "Entry Price": 280.00,
            "Price Target": 400.00, "Loss Limit": 260.00,
            "Beta 180D": 0.9
        }
    ]

if 'history' not in st.session_state:
    st.session_state.history = []

# ---------------------------------------------------------
# 3. 核心逻辑：获取数据与计算
# ---------------------------------------------------------
def get_portfolio_data():
    if not st.session_state.portfolio:
        return pd.DataFrame(), 0.0, 0.0

    df = pd.DataFrame(st.session_state.portfolio)
    
    # 获取实时价格
    ticker_list = df['Ticker'].unique().tolist()
    if ticker_list:
        try:
            tickers = yf.Tickers(" ".join(ticker_list))
            # 简单处理：如果只有一个股票，yfinance返回格式不同，需容错
            current_prices = {}
            for t in ticker_list:
                try:
                    price = tickers.tickers[t].history(period="1d")['Close'].iloc[-1]
                    current_prices[t] = price
                except:
                    current_prices[t] = 0.0 # 获取失败
        except:
            current_prices = {t: 0.0 for t in ticker_list}
    
    # 将价格映射回 DataFrame
    df['Last Price'] = df['Ticker'].map(current_prices).fillna(df['Entry Price'])
    
    # 核心计算
    df['Market Value'] = df['Last Price'] * df['Shares']
    df['Unrealized PnL'] = (df['Last Price'] - df['Entry Price']) * df['Shares']
    df['% Change'] = ((df['Last Price'] - df['Entry Price']) / df['Entry Price'])
    
    total_value = df['Market Value'].sum()
    total_pnl = df['Unrealized PnL'].sum()
    
    # 计算权重和警报
    if total_value > 0:
        df['Net Weight'] = df['Market Value'] / total_value
    else:
        df['Net Weight'] = 0

    # 警报逻辑
    def check_alert(row):
        if row['Last Price'] >= row['Price Target']: return "💰止盈"
        if row['Last Price'] <= row['Loss Limit']: return "🛑止损"
        return "OK"

    df['Status'] = df.apply(check_alert, axis=1)
    
    # 整理列的顺序，把重要的放前面
    display_cols = [
        "Account", "Ticker", "Shares", "Entry Price", "Last Price", 
        "Unrealized PnL", "% Change", "Net Weight", "Status", 
        "Price Target", "Loss Limit", "Enter Date"
    ]
    
    return df[display_cols], total_value, total_pnl

# ---------------------------------------------------------
# 4. 界面展示
# ---------------------------------------------------------

# --- 顶部仪表盘 ---
df_display, total_val, total_unrealized = get_portfolio_data()

col1, col2, col3 = st.columns(3)
col1.metric("总持仓市值 (Total Value)", f"${total_val:,.2f}")
col2.metric("总浮动盈亏 (Unrealized PnL)", f"${total_unrealized:,.2f}", 
            delta_color="normal" if total_unrealized >= 0 else "inverse")
col3.button("🔄 刷新行情", on_click=st.rerun)

st.divider()

# --- 侧边栏：操作区 ---
with st.sidebar:
    st.header("📝 交易操作台")
    
    with st.expander("买入 / 建仓", expanded=True):
        new_ticker = st.text_input("Ticker", value="NVDA").upper()
        new_shares = st.number_input("Shares", min_value=1, value=10)
        new_price = st.number_input("Price", value=100.0)
        new_target = st.number_input("Target", value=150.0)
        new_stop = st.number_input("Stop Loss", value=90.0)
        
        if st.button("确认买入", use_container_width=True):
            new_trade = {
                "Account": "Main", "ISIN": "N/A", "Ticker": new_ticker, 
                "Name": new_ticker, "Enter Date": date.today(), "GICS": "Unknown",
                "Shares": new_shares, "Entry Price": new_price,
                "Price Target": new_target, "Loss Limit": new_stop, "Beta 180D": 1.0
            }
            st.session_state.portfolio.append(new_trade)
            st.success(f"已买入 {new_ticker}")
            st.rerun()

# --- 主表格区域 ---
st.subheader("📊 持仓监控 (Active Positions)")

if not df_display.empty:
    # 这里是关键：使用 column_config 来美化表格
    # 比如显示成进度条、显示货币符号、控制小数位
    
    # 平仓选择器
    positions_to_close = st.multiselect("选择要平仓的股票:", df_display['Ticker'].unique())
    
    if positions_to_close and st.button("📉 对选中的股票执行平仓 (Sell)"):
        # 简单的平仓逻辑：从 portfolio 移到 history
        # 实际情况可能需要部分平仓，这里先做全部平仓演示
        remaining = []
        for item in st.session_state.portfolio:
            if item['Ticker'] in positions_to_close:
                # 记录到历史
                close_price = df_display[df_display['Ticker'] == item['Ticker']]['Last Price'].values[0]
                pnl = (close_price - item['Entry Price']) * item['Shares']
                history_item = item.copy()
                history_item['Exit Price'] = close_price
                history_item['Exit Date'] = date.today()
                history_item['Realized PnL'] = pnl
                st.session_state.history.append(history_item)
                st.toast(f"已平仓 {item['Ticker']}，盈利: ${pnl:.2f}")
            else:
                remaining.append(item)
        st.session_state.portfolio = remaining
        st.rerun()

    st.dataframe(
        df_display,
        use_container_width=True,
        column_config={
            "Entry Price": st.column_config.NumberColumn("成本价", format="$%.2f"),
            "Last Price": st.column_config.NumberColumn("现价", format="$%.2f"),
            "Unrealized PnL": st.column_config.NumberColumn("浮动盈亏", format="$%.2f"),
            "% Change": st.column_config.NumberColumn("涨跌幅", format="%.2f%%"),
            "Net Weight": st.column_config.ProgressColumn("仓位占比", format="%.1f%%", min_value=0, max_value=1),
            "Price Target": st.column_config.NumberColumn("止盈目标", format="$%.2f"),
            "Loss Limit": st.column_config.NumberColumn("止损线", format="$%.2f"),
            "Enter Date": st.column_config.DateColumn("建仓日期", format="YYYY-MM-DD"),
        },
        height=400
    )

else:
    st.info("当前空仓，请在左侧添加交易。")

# --- 历史记录 ---
if st.session_state.history:
    st.markdown("---")
    st.subheader("📚 历史盈亏 (History)")
    df_hist = pd.DataFrame(st.session_state.history)
    st.dataframe(
        df_hist[['Ticker', 'Exit Date', 'Realized PnL', 'Shares', 'Entry Price', 'Exit Price']],
        use_container_width=True,
        column_config={
            "Realized PnL": st.column_config.NumberColumn("已结盈亏", format="$%.2f"),
            "Entry Price": st.column_config.NumberColumn(format="$%.2f"),
            "Exit Price": st.column_config.NumberColumn(format="$%.2f"),
        }
    )
