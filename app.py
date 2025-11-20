
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, date

# ---------------------------------------------------------
# 1. 页面设置与标题
# ---------------------------------------------------------
st.set_page_config(page_title="我的股票操盘记录", layout="wide")
st.title("📈 股票投资组合与风险监控系统")

# ---------------------------------------------------------
# 2. 模拟数据库 (实际项目中我们会用 SQL 数据库)
# ---------------------------------------------------------
# 这里我们初始化一些示例数据，防止页面空白
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = [
        {
            "Account": "Main", "ISIN": "US0378331005", "Ticker": "AAPL", "Name": "Apple Inc",
            "Enter Date": date(2023, 1, 15), "GICS": "Info Tech",
            "Shares": 100, "Entry Price": 150.00,
            "Price Target": 200.00, "Loss Limit": 140.00,
            "Beta 180D": 1.2  # 这里的Beta暂时手动输入，实时计算需要下载大量历史数据
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
# 3. 核心功能：获取实时数据并计算指标
# ---------------------------------------------------------
def update_market_data(portfolio_data):
    updated_data = []
    total_portfolio_value = 0.0

    # 第一遍循环：获取价格并计算总市值，用于计算 Weight
    temp_calculations = []
    
    ticker_strings = " ".join([item['Ticker'] for item in portfolio_data])
    if not ticker_strings:
        return []
    
    # 批量下载数据以提高速度
    tickers = yf.Tickers(ticker_strings)
    
    for item in portfolio_data:
        symbol = item['Ticker']
        try:
            # 获取最新价格
            # 注意：yfinance 免费版可能有15分钟延迟
            current_price = tickers.tickers[symbol].history(period="1d")['Close'].iloc[-1]
        except:
            current_price = item['Entry Price'] # 如果获取失败，保持原价以免报错

        market_value = current_price * item['Shares']
        total_portfolio_value += market_value
        
        # 计算持有天数
        days_in_trade = (date.today() - item['Enter Date']).days
        
        temp_calculations.append({
            **item,
            "Last Price": current_price,
            "Market Value": market_value,
            "Days in Trade": days_in_trade
        })

    # 第二遍循环：计算权重、盈亏和警报
    for row in temp_calculations:
        unrealized_pnl = (row['Last Price'] - row['Entry Price']) * row['Shares']
        pct_change = ((row['Last Price'] - row['Entry Price']) / row['Entry Price']) * 100
        net_weight = (row['Market Value'] / total_portfolio_value) * 100 if total_portfolio_value > 0 else 0
        weighted_beta = row['Beta 180D'] * (net_weight / 100)

        # 检查警报
        alert = "🟢 正常"
        if row['Last Price'] >= row['Price Target']:
            alert = "💰 止盈提醒! (达标)"
        elif row['Last Price'] <= row['Loss Limit']:
            alert = "🛑 止损提醒! (破位)"

        updated_data.append({
            "Account": row['Account'],
            "ISIN": row['ISIN'],
            "Ticker": row['Ticker'],
            "Name": row['Name'],
            "Enter Date": row['Enter Date'],
            "Days": row['Days in Trade'],
            "Sector": row['GICS'],
            "Shares": row['Shares'],
            "Entry": row['Entry Price'],
            "Last": round(row['Last Price'], 2),
            "% Chg": f"{round(pct_change, 2)}%",
            "Unrealized PnL": round(unrealized_pnl, 2),
            "Net Weight": f"{round(net_weight, 2)}%",
            "Target": row['Price Target'],
            "Loss Lim": row['Loss Limit'],
            "Status": alert,
            "W. Beta": round(weighted_beta, 4)
        })
        
    return pd.DataFrame(updated_data), total_portfolio_value

# ---------------------------------------------------------
# 4. 页面布局与交互
# ---------------------------------------------------------

# 侧边栏：添加新交易
with st.sidebar:
    st.header("📝 记录新操作")
    input_ticker = st.text_input("股票代码 (例如 AAPL)", value="NVDA")
    input_shares = st.number_input("股数 (Units)", min_value=1, value=10)
    input_price = st.number_input("买入价格 (Entry)", min_value=0.1, value=100.0)
    input_target = st.number_input("止盈目标 (Target)", min_value=0.1, value=150.0)
    input_stop = st.number_input("止损线 (Loss Limit)", min_value=0.1, value=90.0)
    
    if st.button("添加持仓"):
        new_trade = {
            "Account": "Main", "ISIN": "N/A", "Ticker": input_ticker.upper(), 
            "Name": input_ticker.upper(), # 实际可以通过API获取全名
            "Enter Date": date.today(), "GICS": "Unknown",
            "Shares": input_shares, "Entry Price": input_price,
            "Price Target": input_target, "Loss Limit": input_stop,
            "Beta 180D": 1.0 # 默认值
        }
        st.session_state.portfolio.append(new_trade)
        st.success(f"已添加 {input_ticker}")

# 主界面：展示持仓表格
st.subheader("📊 当前持仓 (Active Portfolio)")

if st.button("🔄 刷新实时行情"):
    st.rerun()

if st.session_state.portfolio:
    df_portfolio, total_val = update_market_data(st.session_state.portfolio)
    
    # 高亮显示逻辑：如果状态包含止损或止盈，高亮该行
    def highlight_alerts(row):
        if "止损" in row['Status']:
            return ['background-color: #ffcccc'] * len(row) # 红色背景
        elif "止盈" in row['Status']:
            return ['background-color: #ccffcc'] * len(row) # 绿色背景
        else:
            return [''] * len(row)

    # 展示带有样式的表格
    st.dataframe(df_portfolio.style.apply(highlight_alerts, axis=1), use_container_width=True)
    st.metric("总资产净值 (Net Exposure)", f"${round(total_val, 2)}")
else:
    st.info("暂无持仓，请在左侧添加。")

st.write("---")

# 主界面：展示历史记录 (简单示例)
st.subheader("📚 历史操作记录 (Realized History)")
# 这里的逻辑是：当你卖出股票时，将数据从上面的portfolio移动到这里，并计算 Realized PnL
if st.session_state.history:
    st.dataframe(pd.DataFrame(st.session_state.history))
else:
    st.text("暂无已平仓的交易记录。")
