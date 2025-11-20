import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, date

# ---------------------------------------------------------
# 1. 页面设置
# ---------------------------------------------------------
st.set_page_config(page_title="我的股票操盘系统", layout="wide", page_icon="📈")
st.title("📈 股票投资组合管理系统 (Pro V5.0)")

# ---------------------------------------------------------
# 2. 状态初始化
# ---------------------------------------------------------
if 'portfolio' not in st.session_state:
    # 默认初始化一些数据，用户可以通过编辑模式删掉
    st.session_state.portfolio = [
        {
            "Account": "Main", "Ticker": "AAPL", "Enter Date": date(2023, 1, 15), 
            "Shares": 100, "Entry Price": 150.00, "Price Target": 200.00, "Loss Limit": 140.00,
            "Beta": 1.20, "Sector": "Information Technology"
        },
        {
            "Account": "Main", "Ticker": "MSFT", "Enter Date": date(2023, 3, 10), 
            "Shares": 50, "Entry Price": 280.00, "Price Target": 400.00, "Loss Limit": 260.00,
            "Beta": 0.90, "Sector": "Information Technology"
        }
    ]

if 'history' not in st.session_state:
    st.session_state.history = []

# ---------------------------------------------------------
# 3. 辅助功能
# ---------------------------------------------------------
def enrich_ticker_data(ticker):
    """自动补全 Sector 和 Beta"""
    try:
        info = yf.Ticker(ticker).info
        sector = info.get('sector', 'Unknown')
        beta = info.get('beta', 1.0)
        if beta is None: beta = 1.0
        return sector, beta
    except:
        return 'Unknown', 1.0

# ---------------------------------------------------------
# 4. 核心逻辑：计算与展示数据
# ---------------------------------------------------------
def get_portfolio_data():
    if not st.session_state.portfolio:
        return pd.DataFrame(), 0.0, 0.0, 0.0

    df = pd.DataFrame(st.session_state.portfolio)

    # 自动补全
    updated = False
    for index, row in df.iterrows():
        if 'Sector' not in row or row['Sector'] == 'Unknown' or pd.isna(row['Sector']):
            sec, b = enrich_ticker_data(row['Ticker'])
            st.session_state.portfolio[index]['Sector'] = sec
            if row.get('Beta', 1.0) == 1.0 and b != 1.0:
                st.session_state.portfolio[index]['Beta'] = b
            updated = True
    
    if updated:
        df = pd.DataFrame(st.session_state.portfolio)

    # 获取实时价格
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
    
    # 计算
    df['Last Price'] = df['Ticker'].map(current_prices).fillna(0.0)
    df['Last Price'] = df.apply(lambda x: x['Entry Price'] if x['Last Price'] <= 0 else x['Last Price'], axis=1)
    df['Market Value'] = df['Last Price'] * df['Shares']
    df['Unrealized PnL'] = (df['Last Price'] - df['Entry Price']) * df['Shares']
    df['% Change'] = ((df['Last Price'] - df['Entry Price']) / df['Entry Price'])
    
    total_value = df['Market Value'].sum()
    total_pnl = df['Unrealized PnL'].sum()
    
    df['Net Weight'] = df.apply(lambda x: x['Market Value'] / total_value if total_value > 0 else 0, axis=1)
    
    # 容错处理：确保 Beta 存在
    if 'Beta' not in df.columns: df['Beta'] = 1.0
    portfolio_beta = (df['Beta'] * df['Net Weight']).sum()

    def check_alert(row):
        if row['Last Price'] >= row['Price Target']: return "💰止盈"
        if row['Last Price'] <= row['Loss Limit']: return "🛑止损"
        return "OK"
    df['Status'] = df.apply(check_alert, axis=1)

    return df, total_value, total_pnl, portfolio_beta

# ---------------------------------------------------------
# 5. 界面布局
# ---------------------------------------------------------

# 开关：编辑模式
edit_mode = st.toggle("🛠️ 开启编辑模式 (Edit Mode)", value=False, help="开启后可以直接修改表格数据或删除行")

if edit_mode:
    # --- 编辑模式 ---
    st.warning("⚠️ 编辑模式：你可以直接在下方表格修改数据，或选中行并按 Delete 键删除股票。修改后会自动保存。")
    
    # 将当前 Session State 转换为 DataFrame 供编辑
    # 只展示核心输入字段，不展示计算字段（如 PnL）
    raw_df = pd.DataFrame(st.session_state.portfolio)
    
    # 确保列的顺序
    default_cols = ["Account", "Ticker", "Shares", "Entry Price", "Enter Date", "Price Target", "Loss Limit", "Beta", "Sector"]
    # 补齐可能缺失的列
    for c in default_cols:
        if c not in raw_df.columns: raw_df[c] = None
            
    edited_df = st.data_editor(
        raw_df[default_cols],
        num_rows="dynamic", # 允许添加和删除行
        use_container_width=True,
        key="editor",
        column_config={
            "Enter Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "Entry Price": st.column_config.NumberColumn(format="$%.2f"),
            "Ticker": st.column_config.TextColumn(validate="^[A-Za-z0-9]+$"),
        }
    )
    
    # 当用户修改表格时，同步回 session_state
    # 将编辑后的 DF 转回 list of dicts
    if not edited_df.equals(raw_df[default_cols]):
        # 简单的转换逻辑
        new_portfolio = edited_df.to_dict('records')
        st.session_state.portfolio = new_portfolio
        st.rerun()

else:
    # --- 视图模式 (Dashboard) ---
    
    # 计算数据
    df_display, total_val, total_unrealized, port_beta = get_portfolio_data()
    
    # 顶部指标
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("总持仓市值", f"${total_val:,.0f}")
    c2.metric("总浮动盈亏", f"${total_unrealized:,.0f}", delta_color="normal" if total_unrealized >= 0 else "inverse")
    c3.metric("组合 Beta", f"{port_beta:.2f}")
    if c4.button("🔄 刷新行情"):
        st.rerun()

    st.divider()

    if not df_display.empty:
        # 图表区域
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            fig_sector = px.pie(df_display, values='Market Value', names='Sector', title='行业风险分布 (Sector)', hole=0.4)
            st.plotly_chart(fig_sector, use_container_width=True)
        with col_chart2:
            fig_tree = px.treemap(df_display, path=['Sector', 'Ticker'], values='Market Value', title='持仓热力图 (Size by Value)')
            st.plotly_chart(fig_tree, use_container_width=True)

        # 主表格
        st.subheader("💼 持仓监控")
        st.dataframe(
            df_display[["Ticker", "Sector", "Shares", "Entry Price", "Last Price", "Unrealized PnL", "% Change", "Net Weight", "Beta", "Status"]],
            use_container_width=True,
            column_config={
                "Entry Price": st.column_config.NumberColumn(format="$%.2f"),
                "Last Price": st.column_config.NumberColumn(format="$%.2f"),
                "Unrealized PnL": st.column_config.NumberColumn(format="$%.2f"),
                "% Change": st.column_config.NumberColumn(format="%.2f%%"),
                "Net Weight": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=1),
            }
        )
        
        # 卖出操作区 (只在非空时显示)
        st.markdown("---")
        with st.expander("📉 卖出 / 减仓操作台", expanded=False):
            c_sell1, c_sell2, c_sell3 = st.columns([2, 2, 1])
            sell_ticker = c_sell1.selectbox("选择股票", options=df_display['Ticker'].unique())
            current_holding = df_display[df_display['Ticker'] == sell_ticker].iloc[0]
            max_shares = int(current_holding['Shares'])
            sell_shares = c_sell2.number_input(f"卖出数量 (Max: {max_shares})", min_value=1, max_value=max_shares, value=max_shares)
            
            if c_sell3.button("确认卖出", type="primary", use_container_width=True):
                # 执行卖出逻辑
                for i, item in enumerate(st.session_state.portfolio):
                    if item['Ticker'] == sell_ticker:
                        exit_price = current_holding['Last Price']
                        realized_pnl = (exit_price - item['Entry Price']) * sell_shares
                        
                        # 记录历史
                        hist_item = item.copy()
                        hist_item['Shares'] = sell_shares
                        hist_item['Exit Price'] = exit_price
                        hist_item['Exit Date'] = date.today()
                        hist_item['Realized PnL'] = realized_pnl
                        st.session_state.history.append(hist_item)
                        
                        # 更新持仓
                        if sell_shares == item['Shares']:
                            st.session_state.portfolio.pop(i)
                        else:
                            st.session_state.portfolio[i]['Shares'] -= sell_shares
                        
                        st.success(f"已卖出 {sell_ticker}")
                        st.rerun()
                        break

    else:
        st.info("📭 当前没有持仓。请打开右上角的【编辑模式】手动录入，或使用侧边栏添加。")

# ---------------------------------------------------------
# 6. 侧边栏与历史
# ---------------------------------------------------------
with st.sidebar:
    if not edit_mode:
        st.header("📝 快速录入")
        with st.form("quick_add"):
            t = st.text_input("Ticker", "NVDA").upper()
            s = st.number_input("Shares", 10)
            p = st.number_input("Price", 100.0)
            d = st.date_input("Date", date.today())
            if st.form_submit_button("添加"):
                st.session_state.portfolio.append({
                    "Account": "Main", "Ticker": t, "Shares": s, "Entry Price": p, 
                    "Enter Date": d, "Price Target": p*1.5, "Loss Limit": p*0.9, 
                    "Beta": 1.0, "Sector": "Unknown"
                })
                st.rerun()
    else:
        st.info("当前处于编辑模式，请直接在主界面的表格中进行修改。")

if st.session_state.history:
    st.divider()
    with st.expander("📚 历史交易与撤销 (History & Undo)"):
        hist_df = pd.DataFrame(st.session_state.history)
        st.dataframe(hist_df, use_container_width=True)
        
        undo_opts = [f"{i}: {r['Ticker']} - {r['Shares']}股" for i, r in hist_df.iterrows()]
        undo_sel = st.selectbox("选择撤销记录", undo_opts)
        if st.button("撤销此交易"):
            idx = int(undo_sel.split(":")[0])
            item = st.session_state.history[idx]
            # 恢复回持仓
            found = False
            for p in st.session_state.portfolio:
                if p['Ticker'] == item['Ticker']:
                    p['Shares'] += item['Shares']
                    found = True
            if not found:
                rev_item = item.copy()
                del rev_item['Exit Price'], rev_item['Exit Date'], rev_item['Realized PnL']
                st.session_state.portfolio.append(rev_item)
            st.session_state.history.pop(idx)
            st.rerun()
