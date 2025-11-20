import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, date

# ---------------------------------------------------------
# 1. 页面设置
# ---------------------------------------------------------
st.set_page_config(page_title="我的股票操盘系统", layout="wide", page_icon="📈")
st.title("📈 股票投资组合管理系统 (Pro V4.0)")

# ---------------------------------------------------------
# 2. 状态初始化
# ---------------------------------------------------------
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

if 'history' not in st.session_state:
    st.session_state.history = []

# ---------------------------------------------------------
# 3. 辅助功能：自动补充信息 (Beta & Sector)
# ---------------------------------------------------------
def enrich_ticker_data(ticker):
    """自动去 Yahoo 获取该股票的 Sector 和 Beta"""
    try:
        info = yf.Ticker(ticker).info
        # 获取行业，如果没有则显示 Unknown
        sector = info.get('sector', 'Unknown')
        # 获取Beta，如果没有则默认为 1.0
        beta = info.get('beta', 1.0)
        # 有时候API返回None，做个容错
        if beta is None: beta = 1.0
        return sector, beta
    except:
        return 'Unknown', 1.0

# ---------------------------------------------------------
# 4. 核心逻辑：数据处理与计算
# ---------------------------------------------------------
def get_portfolio_data():
    if not st.session_state.portfolio:
        return pd.DataFrame(), 0.0, 0.0, 0.0

    df = pd.DataFrame(st.session_state.portfolio)

    # --- 自动补全缺失的 Sector 和 Beta ---
    # 如果数据里没有Sector列，或者Beta是默认值，尝试自动修复
    # 注意：为了不卡顿，这里只对"Unknown"的进行联网查询
    for index, row in df.iterrows():
        if row.get('Sector') == 'Unknown' or row.get('Sector') is None:
            sec, b = enrich_ticker_data(row['Ticker'])
            # 更新 session state，这样下次不用再查
            st.session_state.portfolio[index]['Sector'] = sec
            # 如果原来手动填的Beta是1.0(默认)，且查到了新Beta，则更新
            if st.session_state.portfolio[index]['Beta'] == 1.0 and b != 1.0:
                st.session_state.portfolio[index]['Beta'] = b

    # 重新加载DataFrame以包含更新
    df = pd.DataFrame(st.session_state.portfolio)

    # 1. 获取实时价格
    ticker_list = df['Ticker'].unique().tolist()
    current_prices = {}
    
    if ticker_list:
        try:
            tickers = yf.Tickers(" ".join(ticker_list))
            for t in ticker_list:
                try:
                    price = tickers.tickers[t].history(period="1d")['Close'].iloc[-1]
                    current_prices[t] = price
                except:
                    current_prices[t] = 0.0
        except:
            pass
    
    # 2. 计算各项指标
    df['Last Price'] = df['Ticker'].map(current_prices).fillna(0.0)
    # 价格容错
    df['Last Price'] = df.apply(lambda x: x['Entry Price'] if x['Last Price'] <= 0 else x['Last Price'], axis=1)
    
    df['Market Value'] = df['Last Price'] * df['Shares']
    df['Unrealized PnL'] = (df['Last Price'] - df['Entry Price']) * df['Shares']
    df['% Change'] = ((df['Last Price'] - df['Entry Price']) / df['Entry Price'])
    
    total_value = df['Market Value'].sum()
    total_pnl = df['Unrealized PnL'].sum()
    
    # 权重
    df['Net Weight'] = df.apply(lambda x: x['Market Value'] / total_value if total_value > 0 else 0, axis=1)
    
    # 组合 Beta
    portfolio_beta = (df['Beta'] * df['Net Weight']).sum()

    # 状态
    def check_alert(row):
        if row['Last Price'] >= row['Price Target']: return "💰止盈"
        if row['Last Price'] <= row['Loss Limit']: return "🛑止损"
        return "OK"
    df['Status'] = df.apply(check_alert, axis=1)

    return df, total_value, total_pnl, portfolio_beta

# 执行计算
df_display, total_val, total_unrealized, port_beta = get_portfolio_data()

# ---------------------------------------------------------
# 5. 顶部仪表盘
# ---------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("总持仓市值", f"${total_val:,.0f}")
c2.metric("总浮动盈亏", f"${total_unrealized:,.0f}", delta_color="normal" if total_unrealized >= 0 else "inverse")
c3.metric("组合 Beta", f"{port_beta:.2f}")
if c4.button("🔄 刷新行情"):
    st.rerun()

st.divider()

# ---------------------------------------------------------
# 6. 图表分析 (新功能：Sector Chart)
# ---------------------------------------------------------
if not df_display.empty:
    st.subheader("📊 仓位分布分析")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # 行业分布饼图
        fig_sector = px.pie(df_display, values='Market Value', names='Sector', 
                            title='行业风险敞口 (Sector Exposure)', hole=0.4)
        st.plotly_chart(fig_sector, use_container_width=True)
    
    with col_chart2:
        # 个股占比树状图
        fig_tree = px.treemap(df_display, path=['Sector', 'Ticker'], values='Market Value',
                              title='持仓热力图 (Portfolio Heatmap)')
        st.plotly_chart(fig_tree, use_container_width=True)

# ---------------------------------------------------------
# 7. 侧边栏：录入交易
# ---------------------------------------------------------
with st.sidebar:
    st.header("📝 录入新持仓")
    st.info("✨ 股票添加后，系统会自动尝试查找 Beta 和 行业。")
    
    with st.form("add_trade_form"):
        input_ticker = st.text_input("Ticker", "NVDA").upper()
        input_date = st.date_input("Date", date.today())
        input_shares = st.number_input("Shares", min_value=1, value=10)
        input_price = st.number_input("Price", value=100.0)
        input_target = st.number_input("Target", value=150.0)
        input_stop = st.number_input("Stop Loss", value=90.0)
        
        submitted = st.form_submit_button("确认添加")
        if submitted:
            # 初始添加时，Sector和Beta设为默认，交给主逻辑去自动更新
            new_trade = {
                "Account": "Main", "Ticker": input_ticker, "Enter Date": input_date,
                "Shares": input_shares, "Entry Price": input_price,
                "Price Target": input_target, "Loss Limit": input_stop,
                "Beta": 1.0, "Sector": "Unknown" 
            }
            st.session_state.portfolio.append(new_trade)
            st.success(f"已添加 {input_ticker}")
            st.rerun()

# ---------------------------------------------------------
# 8. 主界面：持仓表格
# ---------------------------------------------------------
st.subheader("💼 当前持仓 (Active)")

if not df_display.empty:
    # 显示主要表格
    show_cols = ["Ticker", "Sector", "Shares", "Entry Price", "Last Price", "Unrealized PnL", 
                 "% Change", "Net Weight", "Beta", "Status"]
    
    st.dataframe(
        df_display[show_cols],
        use_container_width=True,
        column_config={
            "Entry Price": st.column_config.NumberColumn(format="$%.2f"),
            "Last Price": st.column_config.NumberColumn(format="$%.2f"),
            "Unrealized PnL": st.column_config.NumberColumn(format="$%.2f"),
            "% Change": st.column_config.NumberColumn(format="%.2f%%"),
            "Net Weight": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=1),
            "Beta": st.column_config.NumberColumn(format="%.2f"),
        }
    )
    
    # --- 核心功能升级：部分卖出/平仓 ---
    st.markdown("### 📉 卖出操作台")
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        
        # 1. 选择股票
        sell_ticker = c1.selectbox("选择要操作的股票", options=df_display['Ticker'].unique())
        
        # 找到该股票当前的持仓信息
        current_holding = df_display[df_display['Ticker'] == sell_ticker].iloc[0]
        max_shares = int(current_holding['Shares'])
        
        # 2. 选择数量 (支持部分卖出)
        sell_shares = c2.number_input(f"卖出股数 (持有: {max_shares})", 
                                      min_value=1, max_value=max_shares, value=max_shares)
        
        # 3. 执行按钮
        if c3.button("确认卖出", type="primary", use_container_width=True):
            # 逻辑处理
            for i, item in enumerate(st.session_state.portfolio):
                if item['Ticker'] == sell_ticker:
                    
                    # 计算盈亏
                    exit_price = current_holding['Last Price']
                    realized_pnl = (exit_price - item['Entry Price']) * sell_shares
                    
                    # 创建历史记录条目
                    history_item = item.copy()
                    history_item['Shares'] = sell_shares
                    history_item['Exit Price'] = exit_price
                    history_item['Exit Date'] = date.today()
                    history_item['Realized PnL'] = realized_pnl
                    
                    # 添加到历史
                    st.session_state.history.append(history_item)
                    
                    # 更新持仓
                    if sell_shares == item['Shares']:
                        # 全部卖出：删除该条目
                        st.session_state.portfolio.pop(i)
                    else:
                        # 部分卖出：修改剩余股数
                        st.session_state.portfolio[i]['Shares'] -= sell_shares
                    
                    st.success(f"成功卖出 {sell_ticker} {sell_shares}股，盈利 ${realized_pnl:.2f}")
                    st.rerun()
                    break

else:
    st.info("暂无持仓")

# ---------------------------------------------------------
# 9. 历史记录与撤销功能 (Undo)
# ---------------------------------------------------------
if st.session_state.history:
    st.divider()
    st.subheader("📚 历史记录 (History) & 撤销")
    
    hist_df = pd.DataFrame(st.session_state.history)
    
    # 显示历史表格
    st.dataframe(
        hist_df[['Ticker', 'Exit Date', 'Shares', 'Entry Price', 'Exit Price', 'Realized PnL']],
        use_container_width=True,
        column_config={
            "Realized PnL": st.column_config.NumberColumn(format="$%.2f"),
            "Exit Price": st.column_config.NumberColumn(format="$%.2f"),
            "Entry Price": st.column_config.NumberColumn(format="$%.2f"),
        }
    )
    
    # --- 撤销功能 ---
    with st.expander("↩️ 撤销误操作 (Undo Sell)"):
        st.warning("注意：撤销会将记录从历史移回持仓，并恢复原来的成本价。")
        # 创建一个选项列表，显示 Ticker 和 卖出时间、股数
        undo_options = [f"{i}: {row['Ticker']} ({row['Shares']}股) @ {row['Exit Date']}" 
                        for i, row in hist_df.iterrows()]
        
        selected_undo = st.selectbox("选择要撤销的记录", options=undo_options)
        
        if st.button("执行撤销 (Revert)"):
            if selected_undo:
                index_to_revert = int(selected_undo.split(":")[0])
                
                # 获取要撤回的项目
                item_to_revert = st.session_state.history[index_to_revert]
                
                # 检查现在的持仓里是否还有这个股票
                # 如果有，合并股数；如果没有，新建条目
                found = False
                for port_item in st.session_state.portfolio:
                    if port_item['Ticker'] == item_to_revert['Ticker'] and port_item['Account'] == item_to_revert['Account']:
                        port_item['Shares'] += item_to_revert['Shares']
                        found = True
                        break
                
                if not found:
                    # 清理掉历史特有的字段，变回持仓格式
                    reverted_item = item_to_revert.copy()
                    del reverted_item['Exit Price']
                    del reverted_item['Exit Date']
                    del reverted_item['Realized PnL']
                    st.session_state.portfolio.append(reverted_item)
                
                # 从历史中删除
                st.session_state.history.pop(index_to_revert)
                
                st.success("撤销成功！股票已回到持仓列表。")
                st.rerun()
