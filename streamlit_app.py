import streamlit as st
import pandas as pd
import os

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

# --- 3. SIDEBAR: DATA CONTROLS & OVERRIDE FORM ---
st.sidebar.header("🔄 Adjust Holdings")

# --- NEW: CLOUD DATA INSURANCE SECTION ---
st.sidebar.markdown("### 💾 Cloud Data Backup")
df_current = load_data()

# 1. Download Backup Button
if not df_current.empty:
    csv_download = df_current.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        label="📥 Download Inventory CSV",
        data=csv_download,
        file_name="portfolio_inventory.csv",
        mime="text/csv",
        use_container_width=True
    )

# 2. Upload/Restore Backup Button
uploaded_file = st.sidebar.file_uploader("📂 Restore Backup from PC", type=["csv"])
if uploaded_file is not None:
    try:
        restore_df = pd.read_csv(uploaded_file)
        # Verify columns match
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
    ticker = st.text_input("Ticker Symbol").upper().strip()
    
    broker = st.selectbox("Brokerage / Location", 
                          ["TD Waterhouse", "Wealthsimple", "Interactive Brokers", "DRIP / Transfer Agent", "Other"])
    
    account = st.selectbox("Account Type", ["RRSP", "TFSA", "Non-Reg", "Crypto", "Direct Registered"])
    
    # 6 decimal places for exact DRIP tracking accuracy
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
    
    # Auto-delete 0 share positions
    df = df[df['Shares'] > 0]
    df.to_csv(CSV_FILE, index=False)
    st.rerun()

# --- 4. DISPLAY ENGINE ---
df_inv = load_data()

if not df_inv.empty:
    # Use columns for layout
    col1, col2 = st.columns(2)
    col1.metric("Total Positions", len(df_inv))
    col2.metric("Locations Tracked", len(df_inv["Broker"].unique()))

    st.markdown("### 📋 Current Inventory")
    
    df_display = df_inv.sort_values(by=["Broker", "Ticker"])
    
    # Render interactive, mobile-scrollable data table
    st.dataframe(df_display.style.format({"Shares": "{:.6f}"}), 
                  use_container_width=True, 
                  hide_index=True)

    # --- SUMMARY BUCKETS (Responsive Stack) ---
    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.write("#### 📂 Shares by Account")
        # Summing fractional DRIP shares perfectly
        acct_summary = df_inv.groupby("Account")["Shares"].sum().reset_index()
        st.dataframe(acct_summary.style.format({"Shares": "{:.6f}"}), use_container_width=True, hide_index=True)
        
    with c2:
        st.write("#### 🏦 Shares by Location")
        broker_summary = df_inv.groupby("Broker")["Shares"].sum().reset_index()
        st.dataframe(broker_summary.style.format({"Shares": "{:.6f}"}), use_container_width=True, hide_index=True)
else:
    st.info("Your inventory is currently empty. Use the sidebar to log your first set of shares or upload a backup file.")
