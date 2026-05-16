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

st.write(f"### 🧊 TOTAL INVESTMENT PORTFOLIO (CAD GLOBAL VIEW)")
st.markdown("---")

# --- 2. DATA HANDLING ---
CSV_FILE = "portfolio_inventory.csv"

def load_data():
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        return pd.read_csv(CSV_FILE)
    return pd.DataFrame(columns=["Ticker", "Broker", "Account", "Shares"])

# Helper function to get live prices and handle currency/cash tracking
@st.cache_data(ttl=300)  # Cache prices for 5 minutes to keep it snappy
def get_market_data(tickers):
    price_dict = {}
    
    # Always fetch the live USD/CAD conversion rate first
    try:
        fx = yf.Ticker("USDCAD=X")
        fx_data = fx.history(period='1d')
        usd_cad_rate = fx_data['Close'].iloc[-1] if not fx_data.empty else 1.40
    except Exception:
        usd_cad_rate = 1.40 # Solid safety baseline if the feed hits a snag
        
    for t in tickers:
        t_upper = t.strip().upper()
        
        # 1. Smart Cash Check (Locks cash values so they do not fluctuate)
        if t_upper == "TCSH" or "CASH" in t_upper:
            price_dict[t] = {"price": 1.00, "currency": "USD" if t_upper.startswith("USD") else "CAD"}
            continue
            
        # 2. Standard Equity Price Lookup
        try:
            ticker_data = yf.Ticker(t_upper)
            todays_data = ticker_data.history(period='1d')
            if not todays_data.empty:
                live_price = todays_data['Close'].iloc[-1]
                # Determine currency based on ticker suffix
                currency = "CAD" if (".TO" in t_upper or ".V" in t_upper) else "USD"
                price_dict[t] = {"price": live_price, "currency": currency}
            else:
                price_dict[t] = {"price": 0.0, "currency": "CAD"}
        except Exception:
            price_dict[t] = {"price": 0.0, "currency": "CAD"}
            
    return price_dict, usd_cad_rate

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
st.sidebar.info("💡 For Cash: Use 'CADCASH' or 'TCSH' for Canadian cash, or 'USDCASH' for US cash balances.")

with st.sidebar.form(key="update_form", clear_on_submit=True):
    ticker = st.text_input("Ticker Symbol (e.g. VEQT.TO, VT, CADCASH)").upper().strip()
    
    broker = st.selectbox("Brokerage / Location", 
                          ["TD Waterhouse", "Wealthsimple", "Interactive Brokers", "DRIP / Transfer Agent", "Other"])
    
    account = st.selectbox("Account Type", ["RRSP", "TFSA", "Non-Reg", "Crypto", "Direct Registered"])
    
    new_shares = st.number_input("Total Shares / Cash Amount", min_value=0.0, step=0.000001, format="%.6f")
    
    submit_button = st.form_submit_button(label="Update Inventory")

if submit_button and ticker:
    df = load_data()
    mask = (df['Ticker'] == ticker) & (df['Account'] == account) & (df['Broker'] == broker)
    
    if mask.any():
        df.loc[mask, 'Shares'] = new_shares
        st.sidebar.success(f"Updated {ticker} to {new_shares:.6f}.")
    else:
        new_row = pd.DataFrame([{"Ticker": ticker, "Broker": broker, "Account": account, "Shares": new_shares}])
        df = pd.concat([df, new_row], ignore_index=True)
        st.sidebar.success(f"Added {ticker}: {new_shares:.6f}.")
    
    df = df[df['Shares'] > 0]
    df.to_csv(CSV_FILE, index=False)
    st.rerun()

# --- 4. DISPLAY ENGINE & MULTI-CURRENCY CALCULATOR ---
df_inv = load_data()

if not df_
