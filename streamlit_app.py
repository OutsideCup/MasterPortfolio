import streamlit as st
import pandas as pd
import os
import yfinance as yf

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Portfolio Inventory")

st.markdown("""
    <style>
    .stApp { background-color: #050505; }
    
    /* Force Headers into Crisp Neon Blue */
    h1, h2, h3, h4, .main-header {
        color: #00FFFF !important;
        font-weight: 700 !important;
        text-shadow: 0 0 5px rgba(0, 255, 255, 0.3);
    }
    
    /* Neon Metric Styling */
    div[data-testid="stMetric"] {
        background-color: #000000;
        border: 2px solid #00FFFF;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 10px;
    }
    label[data-testid="stMetricLabel"] { color: #BBBBBB !important; text-transform: uppercase; }
    div[data-testid="stMetricValue"] { color: #00FFFF !important; }
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        div[data-testid="stMetric"] { padding: 12px; }
    }
    </style>
    """, unsafe_allow_html=True)

st.write(f"### 🧊 TOTAL INVESTMENT PORTFOLIO (CAD GLOBAL VIEW)")
st.markdown("---")

# --- 2. DATA HANDLING ---
CSV_FILE = "portfolio_inventory.csv"

def load_data():
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        df = pd.read_csv(CSV_FILE)
        if not df.empty:
            df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
        return df
    return pd.DataFrame(columns=["Ticker", "Broker", "Account", "Shares"])

# Re-engineered using standard fast_info metadata endpoints to avoid API blocking
@st.cache_data(ttl=60)
def get_market_data(tickers_list):
    price_dict = {}
    
    try:
        fx = yf.Ticker("USDCAD=X")
        fx_data = fx.history(period='5d')
        usd_cad_rate = fx_data['Close'].iloc[-1] if not fx_data.empty else 1.40
    except Exception:
        usd_cad_rate = 1.40
        
    for t in tickers_list:
        t_upper = str(t).strip().upper()
        
        # Absolute structural default fallback array
        price_dict[t_upper] = {
            "price": 0.0, 
            "currency": "CAD", 
            "annual_div": 0.0, 
            "last_div_amt": 0.0, 
            "last_div_date": "N/A"
        }
        
        if t_upper == "TCSH" or "CASH" in t_upper:
            price_dict[t_upper]["price"] = 1.00
            price_dict[t_upper]["currency"] = "USD" if t_upper.startswith("USD") else "CAD"
            continue
            
        try:
            ticker_data = yf.Ticker(t_upper)
            
            # 1. Capture pricing data using standard history window
            todays_data = ticker_data.history(period='5d')
            if not todays_data.empty:
                price_dict[t_upper]["price"] = todays_data['Close'].iloc[-1]
                
                if (".TO" in t_upper) or (".V" in t_upper) or (t_upper.endswith("-CAD")):
                    price_dict[t_upper]["currency"] = "CAD"
                else:
                    price_dict[t_upper]["currency"] = "USD"
                
                # 2. BULLETPROOF FAST_INFO LOOKUP: Safely reads annual fields without authentication flags
                fast_meta = ticker_data.fast_info
                if fast_meta:
                    div_yield_pct = fast_meta.get("dividend_yield", 0.0)
                    # If a yield percentage exists, multiply by stock price to extract annual payout rate
                    if div_yield_pct and div_yield_pct > 0:
                        price_dict[t_upper]["annual_div"] = price_dict[t_upper]["price"] * div_yield_pct
                
                # 3. BACKUP RECENT LOG LOOKUP: Grabs the standalone latest single dividend value distribution specs
                div_series = ticker_data.dividends
                if div_series is not None and not div_series.empty:
                    price_dict[t_upper]["last_div_amt"] = float(div_series.iloc[-1])
                    price_dict[t_upper]["last_div_date"] = div_series.index[-1].strftime('%Y-%m-%d')
                    # Double-check fallback for index funds that mask fast_info yields
                    if price_dict[t_upper]["annual_div"] == 0.0:
                        recent_1y = div_series.last('365d')
                        price_dict[t_upper]["annual_div"] = recent_1y.sum() if not recent_1y.empty else 0.0
        except Exception:
            pass
            
    return price_dict, usd_cad_rate

# --- 3. SIDEBAR: DATA CONTROLS & FORM ---
st.sidebar.header("🔄 Adjust Holdings")

st.sidebar.markdown("### 💾 Cloud Data Backup")
df_current = load_data()

if not df_current.empty:
    csv_download = df_current.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="📥 Download Inventory CSV",
        data=csv_download,
        file_name="portfolio_inventory.csv",
        mime="text/csv",
        use_container_width=True
    )

uploaded_file = st.sidebar.file_uploader("📂 Restore Backup from PC", type=["csv"])
if uploaded_file is not None:
    try:
        restore_df = pd.read_csv(uploaded_file)
        if list(restore_df.columns) == ["Ticker", "Broker", "Account", "Shares"]:
            restore_df.to_csv(CSV_FILE, index=False)
            st.sidebar.success("✅ Inventory Restored Successfully!")
            st.rerun()
        else:
            st.sidebar.error("❌ Invalid file format.")
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

st.sidebar.markdown("---")

with st.sidebar.form(key="update_form", clear_on_submit=True):
    ticker = st.text_input("Ticker Symbol").upper().strip()
    broker = st.selectbox("Brokerage / Location", ["TD Waterhouse", "Wealthsimple", "Interactive Brokers", "DRIP / Transfer Agent", "Other"])
    account = st.selectbox("Account Type", ["RRSP", "TFSA", "Non-Reg", "Crypto", "Direct Registered"])
    new_shares = st.number_input("Total Shares / Cash Amount", step=0.000001, format="%.6f")
    submit_button = st.form_submit_button(label="Update Inventory")

if submit_button and ticker:
    df = load_data()
    ticker_clean = ticker.upper().strip()
    mask = (df['Ticker'] == ticker_clean) & (df['Account'] == account) & (df['Broker'] == broker)
    
    if mask.any():
        df.loc[mask, 'Shares'] = new_shares
        st.sidebar.success(f"Updated {ticker_clean} to {new_shares:.6f}.")
    else:
        new_row = pd.DataFrame([{"Ticker": ticker_clean, "Broker": broker, "Account": account, "Shares": new_shares}])
        df = pd.concat([df, new_row], ignore_index=True)
        st.sidebar.success(f"Added {ticker_clean}: {new_shares:.6f}.")
    
    df = df[df['Shares'] != 0]
    df.to_csv(CSV_FILE, index=False)
    st.rerun()

# --- 4. DISPLAY ENGINE & MULTI-CURRENCY CALCULATOR ---
df_inv = load_data()

if not df_inv.empty:
    unique_tickers = list(df_inv["Ticker"].unique())
    
    with st.spinner("🔄 Fetching Live Market & Dividend Data..."):
        market_data, usd_cad_rate = get_market_data(unique_tickers)
    
    df_inv["Raw Price"] = df_inv["Ticker"].apply(lambda x: market_data.get(x.upper().strip(), {"price": 0.0})["price"])
    df_inv["Currency"] = df_inv["Ticker"].apply(lambda x: market_data.get(x.upper().strip(), {"currency": "CAD"})["currency"])
    df_inv["Annual Div per Share"] = df_inv["Ticker"].apply(lambda x: market_data.get(x.upper().strip(), {"annual_div": 0.0})["annual_div"])
    
    df_inv["Price (CAD)"] = df_inv.apply(
        lambda r: 1.00 if r["Raw Price"] == 0.0 
        else (r["Raw Price"] * usd_cad_rate if r["Currency"] == "USD" else r["Raw Price"]), axis=1
    )
    df_inv["Total Value (CAD)"] = df_inv["Shares"] * df_inv["Price (CAD)"]
    
    df_inv["Annual Income (CAD)"] = df_inv.apply(
        lambda r: (r["Shares"] * r["Annual Div per Share"] * usd_cad_rate) if r["Currency"] == "USD"
        else (r["Shares"] * r["Annual Div per Share"]), axis=1
    )

    total_portfolio_value_cad = df_inv["Total Value (CAD)"].sum()
    total_annual_dividends_cad = df_inv["Annual Income (CAD)"].sum()
    
    # TYPO REPAIRED COMPLETELY HERE
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Net Worth (CAD)", f"${total_portfolio_value_cad:,.2f}")
    col2.metric("Projected Annual Dividends", f"${total_annual_dividends_cad:,.2f}")
    col3.metric("FX Rate (USD/CAD)", f"${usd_cad_rate:.4f}")
    col4.metric("Total Asset Rows", len(df_inv))

    # --- 🏆 TOP 20 GLOBAL HOLDINGS CONSOLIDATOR ---
    st.markdown("### 🏆 Top 20 Consolidated Global Holdings")
    
    df_top = df_inv.groupby(["Ticker", "Currency", "Raw Price", "Price (CAD)"]).agg({
        "Shares": "sum",
        "Total Value (CAD)": "sum"
    }).reset_index()
    
    df_top["Portfolio Weight"] = (df_top["Total Value (CAD)"] / total_portfolio_value_cad) * 100
    df_top = df_top.sort_values(by="Total Value (CAD)", ascending=False).head(20)
    
    df_top["Live Price"] = df_top.apply(
        lambda r: "Manual Override" if r["Raw Price"] == 0.0 else f"${r['Raw Price']:,.2f} {r['Currency']}", axis=1
    )
    
    st.dataframe(
        df_top[["Ticker", "Shares", "Live Price", "Total Value (CAD)", "Portfolio Weight"]].style.format({
            "Shares": "{:.6f}",
            "Total Value (CAD)": "${:,.2f}",
            "Portfolio Weight": "{:.2f}%"
        }),
        use_container_width=True,
        hide_index=True
    )

    # --- 📅 RECENT DIVIDEND HISTORY LOG ---
    st.markdown("### 📅 Recent Dividend History (Last Distributions)")
    
    df_div_log = pd.DataFrame([t.upper().strip() for t in unique_tickers], columns=["Ticker"])
    df_div_log["Last Dividend Payout"] = df_div_log["Ticker"].apply(lambda x: market_data.get(x, {}).get("last_div_amt", 0.0))
    df_div_log["Currency"] = df_div_log["Ticker"].apply(lambda x: market_data.get(x, {}).get("currency", "CAD"))
    df_div_log["Payment Date"] = df_div_log["Ticker"].apply(lambda x: market_data.get(x, {}).get("last_div_date", "N/A"))
    
    df_div_log = df_div_log[df_div_log["Last Dividend Payout"] > 0]
    
    if not df_div_log.empty:
        df_div_log["Distribution Amount"] = df_div_log.apply(lambda r: f"${r['Last Dividend Payout']:,.4f} {r['Currency']}", axis=1)
        df_div_log = df_div_log.sort_values(by="Payment Date", ascending=False)
        
        st.dataframe(
            df_div_log[["Ticker", "Distribution Amount", "Payment Date"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No active dividend histories detected among current portfolio ticker symbols.")

    # --- 5. DETAILED ACCOUNT BREAKDOWNS ---
    st.markdown("---")
    st.markdown("### 📋 Complete Location & Account Breakdown")
    
    df_display = df_inv.copy()
    df_display["Live Price"] = df_display.apply(
        lambda r: "Manual Override" if r["Raw Price"] == 0.0 else f"${r['Raw Price']:,.2f} {r['Currency']}", axis=1
    )
    df_display = df_display.sort_values(by=["Broker", "Ticker"])
    
    st.dataframe(
        df_display[[ "Ticker", "Broker", "Account", "Shares", "Live Price", "Total Value (CAD)" ]].style.format({
            "Shares": "{:.6f}",
            "Total Value (CAD)": "${:,.2f}"
        }), 
        use_container_width=True, 
        hide_index=True
    )

    # --- 6. SUMMARY BUCKETS ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("#### 📂 Valuation by Account (CAD)")
        acct_summary = df_inv.groupby("Account")["Total Value (CAD)"].sum().reset_index()
        st.dataframe(acct_summary.style.format({"Total Value (CAD)": "${:,.2f}"}), use_container_width=True, hide_index=True)
        
    with c2:
        st.write("#### 🏦 Valuation by Location (CAD)")
        broker_summary = df_inv.groupby("Broker")["Total Value (CAD)"].sum().reset_index()
        st.dataframe(broker_summary.style.format({"Total Value (CAD)": "${:,.2f}"}), use_container_width=True, hide_index=True)
else:
    st.info("Your inventory is currently empty. Use the sidebar to log your first set of shares or upload a backup file.")
