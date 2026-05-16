import streamlit as st
import pandas as pd
import os
import yfinance as yf

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Portfolio Inventory")

# Custom Neon Blue Styling + Header & Mobile Responsiveness
st.markdown("""
    <style>
    .stApp { background-color: #050505; }
    
    /* Force Headers into Crisp Neon Blue */
    h1, h2, h3, .main-header {
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

# Main Title Header
st.write("### 🧊 TOTAL INVESTMENT PORTFOLIO (CAD GLOBAL VIEW)")
st.markdown("---")

# --- 2. DATA HANDLING ---
CSV_FILE = "portfolio_inventory.csv"

def load_data():
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        return pd.read_csv(CSV_FILE)
    return pd.DataFrame(columns=["Ticker", "Broker", "Account", "Shares"])

# Helper function to get live prices and handle currency/cash tracking
@st.cache_data(ttl=60)
def get_market_data(tickers_list):
    price_dict = {}
    
    # Always fetch the live USD/CAD conversion rate first
    try:
        fx = yf.Ticker("USDCAD=X")
        fx_data = fx.history(period='5d')
        usd_cad_rate = fx_data['Close'].iloc[-1] if not fx_data.empty else 1.40
    except Exception:
        usd_cad_rate = 1.40
        
    for t in tickers_list:
        t_upper = str(t).strip().upper()
        
        # 1. Smart Cash Check
        if t_upper == "TCSH" or "CASH" in t_upper:
            price_dict[t] = {"price": 1.00, "currency": "USD" if t_upper.startswith("USD") else "CAD"}
            continue
            
        # 2. Standard Equity Price Lookup
        try:
            ticker_data = yf.Ticker(t_upper)
            todays_data = ticker_data.history(period='5d')
            if not todays_data.empty:
                live_price = todays_data['Close'].iloc[-1]
                currency = "CAD" if (".TO" in t_upper or ".V" in t_upper) else "USD"
                price_dict[t] = {"price": live_price, "currency": currency}
            else:
                price_dict[t] = {"price": 0.0, "currency": "CAD"}
        except Exception:
            price_dict[t] = {"price": 0.0, "currency": "CAD"}
            
    return price_dict, usd_cad_rate

# --- 3. SIDEBAR: DATA CONTROLS & OVERRIDE FORM ---
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
st.sidebar.info("💡 For Cash: Use 'CADCASH' for Canadian cash, or 'USDCASH' for US cash balances.")

with st.sidebar.form(key="update_form", clear_on_submit=True):
    ticker = st.text_input("Ticker Symbol (e.g. VEQT.TO, VT, CADCASH)").upper().strip()
    broker = st.selectbox("Brokerage / Location", ["TD Waterhouse", "Wealthsimple", "Interactive Brokers", "DRIP / Transfer Agent", "Other"])
    account = st.selectbox("Account Type", ["RRSP", "TFSA", "Non-Reg", "Crypto", "Direct Registered"])
    new_shares = st.number_input("Total Shares / Cash Amount", min_value=0.0, step=0.000001, format="%.6f")
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
    
    df = df[df['Shares'] > 0]
    df.to_csv(CSV_FILE, index=False)
    st.rerun()

# --- 4. DISPLAY ENGINE & MULTI-CURRENCY CALCULATOR ---
df_inv = load_data()

if not df_inv.empty:
    unique_tickers = list(df_inv["Ticker"].unique())
    
    with st.spinner("🔄 Updating Live Market & FX Rates..."):
        market_data, usd_cad_rate = get_market_data(unique_tickers)
    
    df_inv["Raw Price"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"price": 0.0})["price"])
    df_inv["Currency"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"currency": "CAD"})["currency"])
    
    df_inv["Price (CAD)"] = df_inv.apply(
        lambda r: r["Raw Price"] * usd_cad_rate if r["Currency"] == "USD" else r["Raw Price"], axis=1
    )
    df_inv["Total Value (CAD)"] = df_inv["Shares"] * df_inv["Price (CAD)"]

    total_portfolio_value_cad = df_inv["Total Value (CAD)"].sum()
    unique_assets = len(df_inv["Ticker"].unique())
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Net Worth (CAD)", f"${total_portfolio_value_cad:,.2f}")
    col2.metric("FX Rate (USD/CAD)", f"${usd_cad_rate:.4f}")
    col3.metric("Total Asset Rows", len(df_inv))

    st.markdown("### 📋 Current Valuation Inventory")
    
    df_display = df_inv.copy()
    df_display["Live Price"] = df_display.apply(lambda r: f"${r['Raw Price']:,.2f} {r['Currency']}", axis=1)
    df_display = df_display.sort_values(by=["Broker", "Ticker"])
    
    st.dataframe(
        df_display[[ "Ticker", "Broker", "Account", "Shares", "Live Price", "Total Value (CAD)" ]].style.format({
            "Shares": "{:.6f}",
            "Total Value (CAD)": "${:,.2f}"
        }), 
        use_container_width=True, 
        hide_index=True
    )

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
