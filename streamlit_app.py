import streamlit as st
import pandas as pd
import os
import yfinance as yf

# --- 1. SETUP & CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Portfolio Income Cockpit")
st.write("### 🧊 TOTAL INVESTMENT PORTFOLIO (CAD GLOBAL VIEW)")
st.markdown("---")

CSV_FILE = "portfolio_inventory.csv"

def load_data():
    if os.path.exists(CSV_FILE) and os.path.getsize(CSV_FILE) > 0:
        df = pd.read_csv(CSV_FILE)
        if not df.empty:
            df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
            df["Shares"] = pd.to_numeric(df["Shares"], errors='coerce').fillna(0.0)
        return df
    return pd.DataFrame(columns=["Ticker", "Broker", "Account", "Shares"])

@st.cache_data(ttl=60)
def get_market_data(tickers_list):
    price_dict = {}
    try:
        fx = yf.Ticker("USDCAD=X").history(period='5d')
        usd_cad_rate = fx['Close'].iloc[-1] if not fx.empty else 1.40
    except Exception:
        usd_cad_rate = 1.40
        
    for t in tickers_list:
        t_up = str(t).strip().upper()
        price_dict[t_up] = {
            "price": 0.0, "currency": "CAD", 
            "annual_div": 0.0, "last_div_amt": 0.0, 
            "last_div_date": "N/A"
        }
        
        if t_up in ["TCSH", "CASH", "OPTIONS", "CADCASH", "USDCASH"]:
            price_dict[t_up]["price"] = 1.00
            price_dict[t_up]["currency"] = "USD" if t_up.startswith("USD") else "CAD"
            continue
            
        try:
            ticker_data = yf.Ticker(t_up)
            todays_data = ticker_data.history(period='5d')
            if not todays_data.empty:
                price_dict[t_up]["price"] = todays_data['Close'].iloc[-1]
                if (".TO" in t_up) or (".V" in t_up) or (t_up.endswith("-CAD")):
                    price_dict[t_up]["currency"] = "CAD"
                else:
                    price_dict[t_up]["currency"] = "USD"
                
                div_series = ticker_data.dividends
                if div_series is not None and not div_series.empty:
                    price_dict[t_up]["last_div_amt"] = float(div_series.iloc[-1])
                    price_dict[t_up]["last_div_date"] = div_series.index[-1].strftime('%Y-%m-%d')
                    price_dict[t_up]["annual_div"] = float(div_series.iloc[-4:].sum())
        except Exception:
            pass
    return price_dict, usd_cad_rate

# --- 2. SIDEBAR MANDATORY UPLOAD SYSTEMS (STANDALONE ENGINE) ---
st.sidebar.header("📥 Data Management")
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

uploaded_file = st.sidebar.file_uploader("📂 Restore Backup CSV", type=["csv"])
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
            st.sidebar.success("✅ Restored Successfully!")
            st.rerun()
        elif len(restore_df.columns) >= 4:
            fallback_df = restore_df.iloc[:, :4].copy()
            fallback_df.columns =
