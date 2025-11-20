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
