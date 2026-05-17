import streamlit as st
import pandas as pd
import os
import yfinance as yf

# --- 1. SETUP ENGINE ---
st.set_page_config(layout="wide", page_title="Outside Cup Portfolio")
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

# --- 2. STANDALONE RESTORE UTILITIES ---
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

uploaded_file = st.sidebar.file_uploader(label="📂 Restore Backup CSV", type=["csv"])
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
            st.sidebar.success("✅ Layout Restored!")
            st.rerun()
    except Exception as e:
        st.sidebar.error(f"Error: {e}")

st.sidebar.markdown("---")

# --- 3. ROW EDITING CONTROLS ---
st.sidebar.subheader("🔄 Adjust Individual Rows")
with st.sidebar.form(key="update_form", clear_on_submit=True):
    ticker = st.text_input(label="Ticker Symbol").upper().strip()
    brk_opts = ["TD Waterhouse", "Wealthsimple", "Interactive Brokers", "DRIP / Transfer Agent", "Other"]
    broker = st.selectbox(label="Brokerage", options=brk_opts)
    acct_opts = ["RRSP", "TFSA", "Non-Reg", "Crypto", "Direct Registered"]
    account = st.selectbox(label="Account Type", options=acct_opts)
    new_shares = st.number_input(label="Shares / Cash Amount", step=0.01, format="%.2f")
    submit_button = st.form_submit_button(label="Update Row Entry")

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

# --- 4. CORE PIPELINE RUNTIME ---
df_inv = load_data()

if not df_inv.empty:
    unique_tickers = list(df_inv["Ticker"].unique())
    with st.spinner("🔄 Refreshing Ledger Infrastructure..."):
        market_data, usd_cad_rate = get_market_data(unique_tickers)
    
    df_inv["Raw Price"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"price": 0.0})["price"])
    df_inv["Currency"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"currency": "CAD"})["currency"])
    df_inv["Annual Div per Share"] = df_inv["Ticker"].apply(lambda x: market_data.get(x, {"annual_div": 0.0})["annual_div"])
    
    df_inv["Price (CAD)"] = df_inv.apply(lambda r: 1.00 if r["Raw Price"] == 0.0 else (r["Raw Price"] * usd_cad_rate if r["Currency"] == "USD" else r["Raw Price"]), axis=1)
    df_inv["Total Value (CAD)"] = df_inv["Shares"] * df_inv["Price (CAD)"]
    df_inv["Annual Income (CAD)"] = df_inv.apply(lambda r: (float(r["Shares"]) * float(r["Annual Div per Share"]) * usd_cad_rate) if r["Currency"] == "USD" else (float(r["Shares"]) * float(r["Annual Div per Share"])), axis=1)
    
    total_portfolio_value = df_inv["Total Value (CAD)"].sum()
    total_dividends = df_inv["Annual Income (CAD)"].sum()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        with st.container(border=True):
            st.write("TOTAL PORTFOLIO (CAD)")
            st.subheader(f"${total_portfolio_value:,.2f}")
    with col2:
        with st.container(border=True):
            st.write("PROJECTED ANNUAL DIVIDENDS")
            st.subheader(f"${total_dividends:,.2f}")
    with col3:
        with st.container(border=True):
            st.write("FX RATE (USD/CAD)")
            st.subheader(f"${usd_cad_rate:.4f}")
    with col4:
        with st.container(border=True):
            st.write("TOTAL ASSET ROWS")
            st.subheader(f"{len(df_inv)}")

    st.markdown("---")

    st.markdown("### 🏆 Top 20 Consolidated Global Holdings")
    df_top = df_inv.groupby(["Ticker", "Currency", "Raw Price", "Price (CAD)"]).agg({"Shares": "sum", "Total Value (CAD)": "sum"}).reset_index()
    df_top["Portfolio Weight"] = (df_top["Total Value (CAD)"] / total_portfolio_value) * 100
    df_top = df_top.sort_values(by="Total Value (CAD)", ascending=False).head(20)
    df_top["Live Price"] = df_top.apply(lambda r: "Manual Override" if r["Raw Price"] == 0.0 else f"${r['Raw Price']:,.2f} {r['Currency']}", axis=1)
    st.dataframe(df_top[["Ticker", "Shares", "Live Price", "Total Value (CAD)", "Portfolio Weight"]].style.format({"Shares": "{:.6f}", "Total Value (CAD)": "${:,.2f}", "Portfolio Weight": "{:.2f}%"}), use_container_width=True, hide_index=True)

    st.markdown("### 📅 Recent Dividend History (Last Distributions)")
    df_div_log = pd.DataFrame([t.upper().strip() for t in unique_tickers], columns=["Ticker"])
    df_div_log["Last Payout"] = df_div_log["Ticker"].apply(lambda x: market_data.get(x, {}).get("last_div_amt", 0.0))
    df_div_log["Currency"] = df_div_log["Ticker"].apply(lambda x: market_data.get(x, {}).get("currency", "CAD"))
    df_div_log["Payment Date"] = df_div_log["Ticker"].apply(lambda x: market_data.get(x, {}).get("last_div_date", "N/A"))
    df_div_log = df_div_log[df_div_log["Last Payout"] > 0]
    
    if not df_div_log.empty:
        shares_map = df_inv.groupby("Ticker")["Shares"].sum().to_dict()
        df_div_log["Total Shares Held"] = df_div_log["Ticker"].map(shares_map)
        df_div_log["Estimated Payout"] = df_div_log["Last Payout"] * df_div_log["Total Shares Held"]
        df_div_log["Distribution Amount"] = df_div_log.apply(lambda r: f"${r['Last Payout']:,.4f}", axis=1)
        df_div_log["Total Cash Received"] = df_div_log.apply(lambda r: f"${r['Estimated Payout']:,.2f}", axis=1)
        df_div_log = df_div_log.sort_values(by="Payment Date", ascending=False)
        st.dataframe(df_div_log[["Ticker", "Distribution Amount", "Total Shares Held", "Total Cash Received", "Payment Date"]].style.format({"Total Shares Held": "{:,.2f}"}), use_container_width=True, hide_index=True)
    else:
        st.info("No active dividend histories detected.")

    st.markdown("---")
    st.markdown("### 📋 Complete Location & Account Breakdown")
    df_display = df_inv.copy()
    df_display["Live Price"] = df_display.apply(lambda r: "Manual Override" if r["Raw Price"] == 0.0 else f"${r['Raw Price']:,.2f} {r['Currency']}", axis=1)
    df_display = df_display.sort_values(by=["Broker", "Ticker"])
    st.dataframe(df_display[["Ticker", "Broker", "Account", "Shares", "Live Price", "Total Value (CAD)"]].style.format({"Shares": "{:.6f}", "Total Value (CAD)": "${:,.2f}"}), use_container_width=True, hide_index=True)

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
    st.info("Your inventory database file is currently empty. Upload your backup file to restore.")
