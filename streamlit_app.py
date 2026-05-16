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

# Re-engineered using hyper-fast metadata endpoints to guarantee dividend lookup execution
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
                
                # 2. OPTIMIZED FAST INFO ENDPOINT: Grab pre-calculated corporate statistics directly
                info_data = ticker_data.info
                if info_data:
                    # Snag trailing dividend rate or generic rate flags
                    div_rate = info_data.get("dividendRate") or info_data.get("trailingAnnualDividendRate") or 0.0
                    price_dict[t_upper]["annual_div"] = float(div_rate)
                    
                    # Capture exact most recent distribution specs safely
                    last_div_value = info_data.get("lastDividendValue")
                    if last_div_value:
                        price_dict[t_upper]["last_div_amt"] = float(last_div_value)
                        
                        # Convert raw epoch payment date timestamps into clean text formats
                        last_div_date_epoch = info_data.get("lastDividendDate")
                        if last_div_date_epoch:
                            price_dict[t_upper]["last_div_date"] = pd.to_datetime(last_div_date_epoch, unit='s').strftime('%Y-%m-%d')
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
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Net Worth (CAD)", f"${total_portfolio_value_cad:,.2f}")
    col2.metric("Projected Annual Dividends", f"${total_annual_dividends_cad:,.2f}")
    col3.metric("FX Rate (USD/CAD)", f"${usd_cad_rate:.4f}")
    col4.metric("Total Asset Rows", len(df_
