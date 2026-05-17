import streamlit as st
import pandas as pd
import os
import yfinance as yf

st.set_page_config(layout="wide")
st.write("### 🧊 PORTFOLIO INCOME COCKPIT")
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
        price_dict[t_up] = {"price": 0.0, "currency": "CAD", "annual_div": 0.0}
        
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
                    recent_365d = div_series.loc[div_series.index >= (pd.Timestamp.now() - pd.Timedelta(days=365))]
                    if not recent_365d.empty:
                        price_dict[t_up]["annual_div"] = float(recent_365d.sum())
                    else:
                        price_dict[t_up]["annual_div"] = float(div_series.iloc[-4:].sum())
        except Exception:
            pass
    return price_dict, usd_cad_rate

# --- SIDEBAR RESTORE ENGINE ---
st.sidebar.header("🔄 Restore Data")
uploaded_file = st.sidebar.file_uploader("📂 Upload Backup CSV", type=["csv"])

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
            fallback_df.columns = ["Ticker", "Broker", "Account", "Shares"]
            fallback_df.to_csv(CSV_FILE, index=False)
            st.sidebar.success("✅ Layout Restored Successfully!")
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

# --- MAIN DISPLAY ENGINE ---
df_inv = load_data()

if not df_inv.empty:
    unique_tickers = list(df_inv["Ticker"].unique())
    with st.spinner("🔄 Loading Market Data..."):
        market_data, usd_cad_rate = get_market_data(unique_tickers)
    
    df_inv["Raw Price"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"price": 0.0})["price"])
    df_inv["Currency"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"currency": "CAD"})["currency"])
    df_inv["Annual Div"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"annual_div": 0.0})["annual_div"])
    
    df_inv["Price CAD"] = df_inv.apply(lambda r: 1.00 if r["Raw Price"] == 0.0 else (r["Raw Price"] * usd_cad_rate if r["Currency"] == "USD" else r["Raw Price"]), axis=1)
    df_inv["Total Value CAD"] = df_inv["Shares"] * df_inv["Price CAD"]
    
    df_inv["Income CAD"] = df_inv.apply(lambda r: (float(r["Shares"]) * float(r["Annual Div"]) * usd_cad_rate) if r["Currency"] == "USD" else (float(r["Shares"]) * float(r["Annual Div"])), axis=1)
    
    total_net_worth = df_inv["Total Value CAD"].sum()
    total_dividends = df_inv["Income CAD"].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Net Worth (CAD)", f"${total_net_worth:,.2f}")
    c2.metric("Projected Annual Dividends", f"${total_dividends:,.2f}")
    c3.metric("USDCAD FX Rate", f"${usd_cad_rate:.4f}")
    
    st.markdown("---")
    st.write("#### 🏆 Consolidated Portfolio Ledger")
    
    df_display = df_inv.copy()
    df_display = df_display.sort_values(by="Total Value CAD", ascending=False)
    st.dataframe(df_display[["Ticker", "Broker", "Account", "Shares", "Total Value CAD", "Income CAD"]], use_container_width=True, hide_index=True)
else:
    st.info("Your inventory database file is currently empty on this server branch. Upload your backup file to restore.")
