import streamlit as st
import pandas as pd
import os
import yfinance as yf

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Portfolio Inventory")

# Custom Neon Blue Styling + Mobile Responsiveness
st.markdown("""
    <style>
    .stApp { background-color: #050505; }
    
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
    
    /* Mobile-specific adjustments via Media Query */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        div[data-testid="stMetric"] {
            padding: 12px;
        }
    }
    </style>
    """, unsafe_allow_html=True)

st.write(f"### 🧊 TOTAL INVESTMENT PORTFOLIO")
st.markdown("---")

# --- 2. DATA HANDLING ---
CSV_FILE = "portfolio_inventory.csv"

def load_data():
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        return pd.read_csv(CSV_FILE)
    return pd.DataFrame(columns=["Ticker", "Broker", "Account", "Shares"])

# Helper function to get real-time price
def get_live_prices(tickers):
    price_dict = {}
    for t in tickers:
        try:
            # Handle crypto or generic assets cleanly
            ticker_clean = t.strip().upper()
            ticker_data = yf.Ticker(ticker_clean)
            # Fetch latest close price
            todays_data = ticker_data.history(period='1d')
            if not todays_data.empty:
                price_dict[t] = todays_data['Close'].iloc[-1]
            else:
                price_dict[t] = 0.0
        except Exception:
            price_dict[t] = 0.0
    return price_dict

# --- 3. SIDEBAR: DATA CONTROLS & OVERRIDE FORM ---
st.sidebar.header("🔄 Adjust Holdings")

# Cloud Data Backup Section
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
st.sidebar.info("Enter a ticker and account to update the total share count.")

with st.sidebar.form(key="update_form", clear_on_submit=True):
    ticker = st.text_input("Ticker Symbol (e.g. XUS.TO, BTC-USD)").upper().strip()
    
    broker = st.selectbox("Brokerage / Location", 
                          ["TD Waterhouse", "Wealthsimple", "Interactive Brokers", "DRIP / Transfer Agent", "Other"])
    
    account = st.selectbox("Account Type", ["RRSP", "TFSA", "Non-Reg", "Crypto", "Direct Registered"])
    
    new_shares = st.number_input("New Total Share Count", min_value=0.0, step=0.000001, format="%.6f")
    
    submit_button = st.form_submit_button(label="Update Inventory")

if submit_button and ticker:
    df = load_data()
    mask = (df['Ticker'] == ticker) & (df['Account'] == account) & (df['Broker'] == broker)
    
    if mask.any():
        df.loc[mask, 'Shares'] = new_shares
        st.sidebar.success(f"Updated {ticker} to {new_shares:.6f} shares.")
    else:
        new_row = pd.DataFrame([{"Ticker": ticker, "Broker": broker, "Account": account, "Shares": new_shares}])
        df = pd.concat([df, new_row], ignore_index=True)
        st.sidebar.success(f"Added {ticker}: {new_shares:.6f} shares.")
    
    df = df[df['Shares'] > 0]
    df.to_csv(CSV_FILE, index=False)
    st.rerun()

# --- 4. DISPLAY ENGINE & VALUE CALCULATOR ---
df_inv = load_data()

if not df_inv.empty:
    # Fetch live prices for all distinct tickers in our portfolio
    unique_tickers = df_inv["Ticker"].unique()
    with st.spinner("🔄 Fetching Live Market Prices..."):
        live_prices = get_live_prices(unique_tickers)
    
    # Map pricing and calculate values
    df_inv["Price"] = df_inv["Ticker"].map(live_prices)
    df_inv["Total Value"] = df_inv["Shares"] * df_inv["Price"]

    # Main Metrics Rows
    total_portfolio_value = df_inv["Total Value"].sum()
    unique_assets = len(df_inv["Ticker"].unique())
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Portfolio Value", f"${total_portfolio_value:,.2f}")
    col2.metric("Distinct Assets", unique_assets)
    col3.metric("Locations Tracked", len(df_inv["Broker"].unique()))

    st.markdown("### 📋 Current Valuation Inventory")
    
    df_display = df_inv.sort_values(by=["Broker", "Ticker"])
    
    # Render rich data table with price and total value calculations
    st.dataframe(
        df_display.style.format({
            "Shares": "{:.6f}",
            "Price": "${:,.2f}",
            "Total Value": "${:,.2f}"
        }), 
        use_container_width=True, 
        hide_index=True
    )

    # --- SUMMARY BUCKETS (Responsive Stack) ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("#### 📂 Valuation by Account")
        acct_summary = df_inv.groupby("Account")["Total Value"].sum().reset_index()
        st.dataframe(acct_summary.style.format({"Total Value": "${:,.2f}"}), use_container_width=True, hide_index=True)
        
    with c2:
        st.write("#### 🏦 Valuation by Location")
        broker_summary = df_inv.groupby("Broker")["Total Value"].sum().reset_index()
        st.dataframe(broker_summary.style.format({"Total Value": "${:,.2f}"}), use_container_width=True, hide_index=True)
else:
    st.info("Your inventory is currently empty. Use the sidebar to log your first set of shares or upload a backup file.")
