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
    # 预设一些数据方便演示
    st.session_state.portfolio = [
        {
            "Account": "Main", "Ticker": "AAPL", "Enter Date": date(2023, 1, 15), 
            "Shares": 100, "Entry Price": 150.00, "Price Target": 200.00, "Loss Limit": 140.00,
            "Beta": 1.20
        },
        {
            "Account": "Main", "Ticker": "MSFT", "Enter Date": date(2023, 3, 10), 
            "Shares": 50, "Entry Price": 280.00, "Price Target": 400.00, "Loss Limit": 260.00,
            "Beta": 0.90
        }
    ]

if 'history' not in st.session_state:
    st.session_state.history = []

# ---------------------------------------------------------
# 3. 核心逻辑：获取数据与计算
# ---------------------------------------------------------
def get_portfolio_data():
    if not st.session_state.portfolio:
        return pd.DataFrame(), 0.0, 0.0, 0.0

    df = pd.DataFrame(st.session_state.portfolio)
    
    # 1. 获取实时价格
    ticker_list = df['Ticker'].unique().tolist()
    current_prices = {}
    
    if ticker_list:
        try:
            # 批量获取数据
            tickers = yf.Tickers(" ".join(ticker_list))
            for t in ticker_list:
                try:
                    # 尝试获取最新收盘价
                    price = tickers.tickers[t].history(period="1d")['Close'].iloc[-1]
                    current_prices[t] = price
                except:
                    current_prices[t] = 0.0
        except:
            pass
    
    # 2. 映射价格
    # 如果获取失败（比如盘前盘后API不稳定），暂时用成本价代替，防止报错
    df['Last Price'] = df['Ticker'].map(current_prices).fillna(0.0)
    df['Last Price'] = df.apply(lambda x: x['Entry Price'] if x['Last Price'] == 0 else x['Last Price'], axis=1)
    
    # 3. 核心指标计算
    df['Market Value'] = df['Last Price'] * df['Shares']
    df['Unrealized PnL'] = (df['Last Price'] - df['Entry Price']) * df['Shares']
    df['% Change'] = ((df['Last Price'] - df['Entry Price']) / df['Entry Price'])
    
    total_value = df['Market Value'].sum()
    total_pnl = df['Unrealized PnL'].sum()
    
    # 4. 权重与组合Beta计算
    if total_value > 0:
        df['Net Weight'] = df['Market Value'] / total_value
    else:
        df['Net Weight'] = 0

    # 组合 Beta = Sum(个股Beta * 个股权重)
    portfolio_beta = (df['Beta'] * df['Net Weight']).sum()

    # 5. 状态警报
    def check_alert(row):
        if row['Last Price'] >= row['Price Target']: return "💰止盈"
        if row['Last Price'] <= row['Loss Limit']: return "🛑止损"
        return "OK"

    df['Status'] = df.apply(check_alert, axis=1)
    
    # 6. 整理显示顺序
    display_cols = [
        "Ticker", "Shares", "Entry Price", "Last Price", 
        "Unrealized PnL", "% Change", "Net Weight", "Beta", 
        "Status", "Price Target", "Loss Limit", "Enter Date"
    ]
    
    return df[display_cols], total_value, total_pnl, portfolio_beta

# 获取计算后的数据
df_display, total_val, total_unrealized, port_beta = get_portfolio_data()

# ---------------------------------------------------------
# 4. 界面展示 - 顶部仪表盘
# ---------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("总持仓市值 (Total Value)", f"${total_val:,.2f}")
col2.metric("总浮动盈亏 (Unrealized PnL)", f"${total_unrealized:,.2f}", 
            delta_color="normal" if total_unrealized >= 0 else "inverse")
col3.metric("组合 Beta (Weighted)", f"{port_beta:.2f}")

# 修复了黄色警告：将 st.rerun() 放在按钮判断内部，而不是 callback
if col4.button("🔄 刷新实时行情"):
    st.rerun()

st.divider()

# ---------------------------------------------------------
# 5. 侧边栏：录入旧持仓 / 新交易
# ---------------------------------------------------------
with st.sidebar:
    st.header("📝 录入交易 (Add Trade)")
    st.info("💡 如果是之前的持仓，请修改日期为当时的买入时间。")
    
    input_ticker = st.text_input("股票代码 (Ticker)", value="NVDA").upper()
    input_date = st.date_input("建仓日期 (Entry Date)", value=date.today())
    
    c1, c2 = st.columns(2)
    input_shares = c1.number_input("股数 (Shares)", min_value=1, value=10)
    input_price = c2.number_input("成本价 (Entry Price)", value=100.0)
    
    c3, c4 = st.columns(2)
    input_target = c3.number_input("止盈价 (Target)", value=150.0)
    input_stop = c4.number_input("止损价 (Stop)", value=90.0)
    
    input_beta = st.number_input("个股 Beta (180D)", value=1.0, help="可在 Yahoo Finance 上查询该股票的 Beta 值")
    
    if st.button("确认添加 / 录入旧仓", use_container_width=True):
        new_trade = {
            "Account": "Main", 
            "Ticker": input_ticker, 
            "Enter Date": input_date,
            "Shares": input_shares, 
            "Entry Price": input_price,
            "Price Target": input_target, 
            "Loss Limit": input_stop,
            "Beta": input_beta
        }
        st.session_state.portfolio.append(new_trade)
        st.success(f"已添加 {input_ticker}")
        st.rerun()

# ---------------------------------------------------------
# 6. 主界面 - 卖出操作区
# ---------------------------------------------------------
st.subheader("💼 仓位管理 (Position Management)")

if not df_display.empty:
    # 使用 expander 把卖出操作折叠起来，保持界面整洁
    with st.expander("📉 点击这里进行【平仓 / 卖出】操作", expanded=True):
        
        # 多选框：选择要卖出的股票
        sell_tickers = st.multiselect(
            "选择要平仓的股票 (Select to Sell):", 
            options=df_display['Ticker'].unique()
        )
        
        if sell_tickers:
            st.warning(f"⚠️ 即将平仓: {', '.join(sell_tickers)}")
            if st.button("确认卖出 (Confirm Sell)"):
                remaining_portfolio = []
                for item in st.session_state.portfolio:
                    if item['Ticker'] in sell_tickers:
                        # 1. 找到当前价格用于结算
                        current_row = df_display[df_display['Ticker'] == item['Ticker']].iloc[0]
                        exit_price = current_row['Last Price']
                        
                        # 2. 计算最终盈亏
                        realized_pnl = (exit_price - item['Entry Price']) * item['Shares']
                        
                        # 3. 记录到历史
                        history_record = item.copy()
                        history_record['Exit Date'] = date.today()
                        history_record['Exit Price'] = exit_price
                        history_record['Realized PnL'] = realized_pnl
                        st.session_state.history.append(history_record)
                        
                        st.toast(f"✅ {item['Ticker']} 已平仓，最终盈亏: ${realized_pnl:.2f}")
                    else:
                        remaining_portfolio.append(item)
                
                # 更新持仓并刷新
                st.session_state.portfolio = remaining_portfolio
                st.rerun()

# ---------------------------------------------------------
# 7. 主界面 - 持仓表格
# ---------------------------------------------------------
if not df_display.empty:
    st.dataframe(
        df_display,
        use_container_width=True,
        column_config={
            "Entry Price": st.column_config.NumberColumn("成本", format="$%.2f"),
            "Last Price": st.column_config.NumberColumn("现价", format="$%.2f"),
            "Unrealized PnL": st.column_config.NumberColumn("浮盈/亏", format="$%.2f"),
            "% Change": st.column_config.NumberColumn("涨跌幅", format="%.2f%%"),
            "Net Weight": st.column_config.ProgressColumn("仓位占比", format="%.1f%%", min_value=0, max_value=1),
            "Beta": st.column_config.NumberColumn("Beta", format="%.2f"),
            "Enter Date": st.column_config.DateColumn("建仓日", format="YYYY-MM-DD"),
        },
        height=400
    )
else:
    st.info("📭 当前没有持仓。请在左侧侧边栏录入交易。")

# ---------------------------------------------------------
# 8. 底部 - 历史记录
# ---------------------------------------------------------
if st.session_state.history:
    st.markdown("---")
    st.subheader("📚 历史交易记录 (History)")
    
    hist_df = pd.DataFrame(st.session_state.history)
    # 计算历史总盈亏
    total_realized = hist_df['Realized PnL'].sum()
    st.metric("历史已结总盈亏 (Total Realized PnL)", f"${total_realized:,.2f}")
    
    st.dataframe(
        hist_df[['Ticker', 'Enter Date', 'Exit Date', 'Shares', 'Entry Price', 'Exit Price', 'Realized PnL']],
        use_container_width=True,
        column_config={
            "Entry Price": st.column_config.NumberColumn("买入价", format="$%.2f"),
            "Exit Price": st.column_config.NumberColumn("卖出价", format="$%.2f"),
            "Realized PnL": st.column_config.NumberColumn("最终盈亏", format="$%.2f"),
            "Enter Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "Exit Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
        }
    )
