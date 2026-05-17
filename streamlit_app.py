import streamlit as st
import pandas as pd
import os
import yfinance as yf

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Portfolio Inventory")

st.markdown("""
    <style>
    .stApp { background-color: #050505; }
    h1, h2, h3, h4, .main-header {
        color: #00FFFF !important;
        font-weight: 700 !important;
    }
    div[data-testid="stMetric"] {
        background-color: #000000;
        border: 2px solid #00FFFF;
        border-radius: 12px;
        padding: 20px;
    }
    label[data-testid="stMetricLabel"] { color: #BBBBBB !important; }
    div[data-testid="stMetricValue"] { color: #00FFFF !important; }
    </style>
    """, unsafe_allow_html=True)

st.write("### 🧊 TOTAL INVESTMENT PORTFOLIO (CAD GLOBAL VIEW)")
st.markdown("---")

# --- 2. DATA HANDLING ---
CSV_FILE = "portfolio_inventory.csv"

def load_data():
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        df = pd.read_csv(CSV_FILE)
        if not df.empty:
            df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
            df["Shares"] = pd.to_numeric(df["Shares"], errors='coerce')
            df["Shares"] = df["Shares"].fillna(0.0)
        return df
    return pd.DataFrame(columns=["Ticker", "Broker", "Account", "Shares"])

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
        price_dict[t_upper] = {
            "price": 0.0, "currency": "CAD", 
            "annual_div": 0.0, "last_div_amt": 0.0, 
            "last_div_date": "N/A"
        }
        
        if t_upper in ["TCSH", "CASH", "OPTIONS", "CADCASH", "USDCASH"]:
            price_dict[t_upper]["price"] = 1.00
            price_dict[t_upper]["currency"] = "USD" if t_upper.startswith("USD") else "CAD"
            continue
            
        try:
            ticker_data = yf.Ticker(t_upper)
            todays_data = ticker_data.history(period='5d')
            if not todays_data.empty:
                price_dict[t_upper]["price"] = todays_data['Close'].iloc[-1]
                if (".TO" in t_upper) or (".V" in t_upper) or (t_upper.endswith("-CAD")):
                    price_dict[t_upper]["currency"] = "CAD"
                else:
                    price_dict[t_upper]["currency"] = "USD"
                
                div_series = ticker_data.dividends
                if div_series is not None and not div_series.empty:
                    price_dict[t_upper]["last_div_amt"] = float(div_series.iloc[-1])
                    price_dict[t_upper]["last_div_date"] = div_series.index[-1].strftime('%Y-%m-%d')
                    
                    recent_365d = div_series.loc[div_series.index >= (pd.Timestamp.now() - pd.Timedelta(days=365))]
                    if not recent_365d.empty:
                        price_dict[t_upper]["annual_div"] = float(recent_365d.sum())
                    else:
                        price_dict[t_upper]["annual_div"] = float(div_series.iloc[-4:].sum())
        except Exception:
            pass
    return price_dict, usd_cad_rate

# --- 3. SIDEBAR: DATA CONTROLS & FORM ---
st.sidebar.header("🔄 Adjust Holdings")
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
        restore_df.columns = [str(col).strip().upper() for col in restore_df.columns]
        
        col_map = {"TICKER": "Ticker", "BROKER": "Broker", "ACCOUNT": "Account", "SHARES": "Shares"}
        found_cols = {orig: target for orig, target in col_map.items() if orig in restore_df.columns}
        
        if len(found_cols) == 4:
            clean_df = restore_df[list(found_cols.keys())].copy()
            clean_df.columns = [found_cols[c] for c in clean_df.columns]
            clean_df.to_csv(CSV_FILE, index=False)
            st.sidebar.success("✅ Inventory Restored Successfully!")
            st.rerun()
        else:
            if len(restore_df.columns) >= 4:
                fallback_df = restore_df.iloc[:, :4].copy()
                fallback_df.columns = ["Ticker", "Broker", "Account", "Shares"]
                fallback_df.to_csv(CSV_FILE, index=False)
                st.sidebar.success("✅ Layout Restored Successfully!")
                st.rerun()
            else:
                st.sidebar.error("❌ Column mismatch format error.")
    except Exception as e:
        st.sidebar.error(f"Error reading file: {e}")

st.sidebar.markdown("---")

with st.sidebar.form(key="update_form", clear_on_submit=True):
    ticker = st.text_input("Ticker Symbol").upper().strip()
    broker = st.selectbox("Brokerage", ["TD Waterhouse", "Wealthsimple", "Interactive Brokers", "DRIP / Transfer Agent", "Other"])
    account = st.selectbox("Account Type", ["RRSP", "TFSA", "Non-Reg", "Crypto", "Direct Registered"])
    new_shares = st.number_input("Total Shares / Cash Amount", step=0.000001, format="%.6f")
    submit_button = st.form_submit_button(label="Update Inventory")

if submit_button and ticker:
    df = load_data()
    ticker_clean = ticker.upper().strip()
    mask = (df['Ticker'] == ticker_clean) & (df['Account'] == account) & (df['Broker'] == broker)
    
    if mask.any():
        df.loc[mask, 'Shares'] = new_shares
    else:
        new_row = pd.DataFrame([{"Ticker": ticker_clean, "Broker": broker, "Account": account, "Shares": new_shares}])
        df = pd.concat([df, new_row], ignore_index=True)
        
    df = df[df['Shares'] != 0]
    df.to_csv(CSV_FILE, index=False)
    st.rerun()

# --- 4. DISPLAY ENGINE & MULTI-CURRENCY CALCULATOR ---
df_inv = load_data()

if not df_inv.empty:
    df_inv["Ticker"] = df_inv["Ticker"].astype(str).str.strip().str.upper()
    unique_tickers = list(df_inv["Ticker"].unique())
    
    with st.spinner("🔄 Fetching Live Market Data..."):
        market_data, usd_cad_rate = get_market_data(unique_tickers)
    
    df_inv["Raw Price"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"price": 0.0})["price"])
    df_inv["Currency"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"currency": "CAD"})["currency"])
    df_inv["Annual Div per Share"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"annual_div": 0.0})["annual_div"])
    
    df_inv["Price (CAD)"] = df_inv.apply(
        lambda r: 1.00 if r["Raw Price"] == 0.0 
        else (r["Raw Price"] * usd_cad_rate if r["Currency"] == "USD" else r["Raw Price"]), axis=1
    )
    df_inv["Total Value (CAD)"] = df_inv["Shares"] * df_inv["Price (CAD)"]
    
    df_inv["Annual Income (CAD)"] = df_inv.apply(
        lambda r: (float(r["Shares"]) * float(r["Annual Div per Share"]) * usd_cad_rate) if r["Currency"] == "USD"
        else (float(r["Shares"]) * float(r["Annual Div per Share"])), axis=1
    )

    total_portfolio_value_cad = df_inv["Total Value (CAD)"].sum()
    total_annual_dividends_cad = df_inv["Annual Income (CAD)"].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Net Worth (CAD)", f"${total_portfolio_value_cad:,.2f}")
    col2.metric("Projected Annual Dividends", f"${total_annual_dividends_cad:,.2f}")
    col3.metric("FX Rate (USD/CAD)", f"${usd_cad_rate:.4f}")
    col4.metric("Total Asset Rows", len(df_inv))

    # --- 🏆 TOP 20 GLOBAL HOLDINGS CONSOLIDATOR ---
    st.markdown("### 🏆 Top 20 Consolidated Global Holdings")
    
    df_top = df_inv.groupby(["Ticker", "Currency", "Raw Price", "Price (CAD)"]).agg({
        "Shares
