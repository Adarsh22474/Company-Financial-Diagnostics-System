import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False


st.set_page_config(page_title="Company Financial Diagnostics",layout="wide")
st.title("Company Financial Diagnostics System")
st.markdown("Analyze a company's financial performance, stability, and cash flow quality using historical financial statements.")
if not st.session_state.logged_in:
    st.subheader("Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if username.strip() and password.strip():
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Please enter valid credentials")

    st.stop()

url = st.text_input("Enter Screener Company URL", placeholder="https://www.screener.in/company/XXXX/", disabled=st.session_state.data_loaded)

if st.button("Analyze Company") and url:
    st.session_state.data_loaded = True


def clean_numeric_value(text):
    if text is None:
        return None

    text = text.replace("₹", "").replace(",", "").strip()

    if "Cr" in text:
        number = text.replace("Cr.", "").replace("Cr", "").strip()
        try:
            return float(number) * 10000000
        except:
            return None

    if text in ["", "-", "—"]:
        return None

    if "%" in text:
        return float(text.replace("%", ""))

    try:
        return float(text)
    except:
        return None


def clean_table_value(text):
    return clean_numeric_value(text.strip())


#------------------------------
# Company Name
# -----------------------------
def scrape_company_name(url):
    soup = BeautifulSoup(requests.get(url).text,"html.parser")
    division = soup.find("div", class_= "flex flex-space-between container hide-from-tablet-landscape" )
    name= division.find("h1",class_="h2 shrink-text").text.split()
    company_name = (" ".join(name))
    return company_name
    

def scrape_sector(url):
    soup = BeautifulSoup(requests.get(url).text, "html.parser")

    section = soup.find("section", id="peers")
    p = section.find("p", class_="sub")
    Broad_sector = p.find("a", title="Broad Sector")
    Sector =  p.find("a", title="Sector")
    Broad_Industry = p.find("a", title="Broad Industry")
    Industry = p.find("a", title="Industry")



    data = {
        "Broad Sector": Broad_sector ,
        "Sector": Sector ,
        "Broad Industry": Broad_Industry ,
        "Industry": Industry
    }

    return pd.DataFrame([data])  

# -----------------------------
# Top Ratios
# -----------------------------
def scrape_company_ratios(url, company):
    soup = BeautifulSoup(requests.get(url).text, "html.parser")

    ratios = soup.find("ul", id="top-ratios")
    data = []

    for li in ratios.find_all("li"):
        name = li.find("span", class_="name").text.strip()
        value_text = li.find("span", class_="value").text.strip()

        if "High / Low" in name:
            high, low = value_text.replace("₹", "").replace(",", "").split("/")
            data.append([company, "52W High", float(high)])
            data.append([company, "52W Low", float(low)])
        else:
            data.append([company, name, clean_numeric_value(value_text)])

    return pd.DataFrame(data, columns=["Company", "Metric", "Value"])



# -----------------------------
# Generic Financial Table Scraper
# -----------------------------
def scrape_financial_section(url, section_id, company):
    soup = BeautifulSoup(requests.get(url).text, "html.parser")

    section = soup.find("section", id=section_id)
    table = section.find("table")

    years = [th.text.replace("Mar ", "").replace("Sep ", "").strip()for th in table.find("thead").find_all("th")[1:]]

    records = []

    for row in table.find("tbody").find_all("tr"):
        cols = row.find_all("td")
        if len(cols) <= 1:
            continue

        metric = cols[0].text.strip()
        values = [clean_table_value(td.text) for td in cols[1:]]

        for year, value in zip(years, values):
            records.append({
                "Company": company,
                "Year": year,
                "Metric": metric,
                "Value": value
            })

    return pd.DataFrame(records)

# ---------------------------
# Yearly Shareholding Scraper
# ---------------------------

def scrape_yearly_shareholding(url, company):
    soup = BeautifulSoup(requests.get(url).text, "html.parser")
    
    yearly_div = soup.find("section",id ="shareholding").find("div", id="yearly-shp")
    table = yearly_div.find("table", class_="data-table")
    years = []
    for th in table.find("thead").find_all("th")[1:]:
        text = th.text.strip()
        year = text.split()[-1]  # "Mar 2017" → "2017"
        years.append(year)

    records = []

    for rows in table.find("tbody").find_all("tr"):
        cols = rows.find_all("td")
        if len(cols) <= 1:
            continue

        metric = cols[0].text.strip()
        values = [clean_table_value(td.text) for td in cols[1:]]

        for year, value in zip(years, values):
            records.append({
                "Company": company,
                "Year": year,
                "Metric": metric,
                "Value": value
            })

    return pd.DataFrame(records)

# -----------------------------
# Quarterly Profit & Loss Scraper
# -----------------------------
def scrape_pnl_quarterly(url, company):
    soup = BeautifulSoup(requests.get(url).text, "html.parser")

    section = soup.find("section", id="quarters")
    if section is None:
        return pd.DataFrame()

    table = section.find("table")
    thead = table.find("thead")
    tbody = table.find("tbody")

    quarters = []
    records = []

    # Extract quarters
    for th in thead.find_all("th")[1:]:
        quarters.append(th.text.strip())

    # Extract data
    for tr in tbody.find_all("tr"):
        cols = tr.find_all("td")
        if len(cols) <= 1:
            continue

        metric = cols[0].text.strip()
        values = [clean_table_value(td.text) for td in cols[1:]]

        for quarter, value in zip(quarters, values):
            records.append({
                "Company": company,
                "Quarter": quarter,
                "Metric": metric,
                "Value": value
            })

    df = pd.DataFrame(records)
    return (df.pivot_table( index=["Company", "Quarter"], columns="Metric",values="Value").reset_index())
 

# -----------------------------
# Pivot from long to wide format
# -----------------------------
def process_statement(df):
    return (
        df.pivot_table( index=["Company", "Year"], columns="Metric",values="Value").reset_index())


def get_ratio_value(ratios_df, metric_name):
    try:
        value = ratios_df.loc[ratios_df["Metric"] == metric_name, "Value"].values
        return value[0] if len(value) > 0 else None
    except:
        return None
    
def formatting(value, kind="num"):
    if kind == "currency":
        return f"{value/1e7:.2f} Crore"
    elif kind == "price":
        return f"{value:.2f}"
    elif kind == "percent":
        return f"{value:.2f}%"
    elif kind == "ratio":
        return f"{value:.2f}"
    return value

def safe_series(df, col):
    return df[col] if col in df.columns else None

def compute_growth(series):
    if series is None or series.dropna().empty:
        return None
    return series.pct_change() * 100

def clean_year_column(df):
    df = df.copy()

    # Convert to string and clean whitespace
    df["Year"] = df["Year"].astype(str).str.strip()

    # Extract 4-digit year only (e.g. 2016 from "2016\n18m")
    df["Year"] = df["Year"].str.extract(r"(\d{4})", expand=False)

    # Drop rows where year could not be extracted
    df = df.dropna(subset=["Year"])

    # Convert to int
    df["Year"] = df["Year"].astype(int)

    return df


if st.session_state.data_loaded and url:

    if "pnl_y_df" not in st.session_state:

        with st.spinner("Fetching company financial data..."):
                company_name = scrape_company_name(url)

                ratios_df = scrape_company_ratios(url, company_name)

                pnl_q_df = scrape_pnl_quarterly(url, company_name)

                pnl_y_raw = scrape_financial_section(url, "profit-loss", company_name)
                pnl_y_df = process_statement(pnl_y_raw)
                pnl_y_df.columns = (pnl_y_df.columns.str.replace(r"\s*\+\s*$", "", regex=True).str.strip())
                pnl_q_df.columns = ( pnl_q_df.columns.str.replace(r"\s*\+\s*$", "", regex=True).str.strip())



                balance_raw = scrape_financial_section(url, "balance-sheet", company_name)
                balance_df = process_statement(balance_raw)
                balance_df.columns = (balance_df.columns.str.replace(r"\s*\+\s*$","", regex=True).str.strip())

                cashflow_raw = scrape_financial_section(url, "cash-flow", company_name)
                cashflow_df = process_statement(cashflow_raw)
                cashflow_df.columns= (cashflow_df.columns.str.replace(r"\s*\+\s*$","", regex=True).str.strip())

                shareholding_raw = scrape_yearly_shareholding(url, company_name)
                shareholding_df = process_statement(shareholding_raw)
                shareholding_df.columns = (shareholding_df.columns.str.replace(r"\s*\+\s*$","", regex=True).str.strip())





        with st.sidebar:
            st.header("Analysis Controls")

            analysis_window = st.selectbox("Analysis Window",["Last Decade","Last 3 Years", "Last 5 Years","Last 7 Years"])

            if st.button("Reset Analysis"):
                st.session_state.data_loaded = False
                st.rerun()

            if st.button("Logout"):
                st.session_state.clear()
                st.rerun()

            pnl_y_df = clean_year_column(pnl_y_df)
            balance_df = clean_year_column(balance_df)
            cashflow_df = clean_year_column(cashflow_df)
            shareholding_df = clean_year_column(shareholding_df)


            max_year = pnl_y_df["Year"].max()

            if analysis_window == "Last Decade":
                start_year = max_year - 9
            elif analysis_window == "Last 3 Years":
                start_year = max_year - 2
            elif analysis_window == "Last 5 Years":
                start_year = max_year - 4
            elif analysis_window == "Last 7 Years":
                start_year = max_year - 6
            


            pnl_y_df = pnl_y_df[pnl_y_df["Year"] >= start_year]
            balance_df = balance_df[balance_df["Year"] >= start_year]
            cashflow_df = cashflow_df[cashflow_df["Year"] >= start_year]
            shareholding_df = shareholding_df[shareholding_df["Year"] >= start_year]


        tabs = st.tabs(["Dataset",
                        "Overview",
                        "Performance & Growth",
                        "Profitability & Efficiency",
                        "Financial Position",
                        "Cash Flow Quality",
                        "Shareholding",
                        "Executive Page",
                         "Exit Page" ])

        with tabs[0]:

            st.subheader("Company Fundamental Ratios")
            st.dataframe(ratios_df)
            st.subheader("Profit & Loss Quarterly")
            st.dataframe(pnl_q_df)
            st.subheader("Profit & Loss Yearly")
            st.dataframe(pnl_y_df)
            st.subheader("Yearly Balance Sheet")
            st.dataframe(balance_df)
            st.subheader("Yearly Cashflow")
            st.dataframe(cashflow_df)
            st.subheader("Yearly Shareholding")
            st.dataframe(shareholding_df)



        with tabs[1]:
            st.subheader("Company Overview")

            # --- Extract key ratios ---
            market_cap = get_ratio_value(ratios_df, "Market Cap")
            current_price = get_ratio_value(ratios_df, "Current Price")
            pe_ratio = get_ratio_value(ratios_df, "Stock P/E")
            roe = get_ratio_value(ratios_df, "ROE")
            roce = get_ratio_value(ratios_df, "ROCE")
            dividend_yield = get_ratio_value(ratios_df, "Dividend Yield")
            high_52w = get_ratio_value(ratios_df,"52W High")
            low_52w = get_ratio_value(ratios_df,"52W Low")
            face_value = get_ratio_value(ratios_df,"Face Value")
            book_value = get_ratio_value(ratios_df,"Book Value")
            roe_roce_gap = roe - roce if roe and roce else "NA"
            valuation_density = pe_ratio / roe if pe_ratio and roe else "NA"
            # --- Headline Metrics ---
            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Market Cap", formatting(market_cap,"currency") if market_cap else "NA")
            col2.metric("Current Price",formatting(current_price,"price")if current_price else "NA")
            col3.metric("P/E Ratio", formatting(pe_ratio,"ratio")if pe_ratio else "NA")
            col4.metric("Book Value", formatting(book_value,"price") if book_value else "NA")
            
            col5, col6, col7, col8 = st.columns(4)
            
            col5.metric("ROCE (%)", formatting(roce,"percent") if roce else "NA")
            col6.metric("Dividend Yield (%)", formatting(dividend_yield,"percent") if dividend_yield else "NA")
            col7.metric("ROE (%)", formatting(roe,"percent") if roe else "NA")
            col8.metric("ROE_ROCE_Gap",formatting(roe_roce_gap,"ratio") if roe_roce_gap else "NA")

            col9, col10, col11, col12 = st.columns(4)
            col9.metric("52W High", formatting(high_52w,"price") if high_52w else "NA")
            col10.metric("52W Low", formatting(low_52w,"price") if low_52w else "NA")
            col11.metric("Face Value",formatting( face_value,"price") if face_value else "NA")
            col12.metric("Valuation Density",formatting(valuation_density,'ratio') if valuation_density else "NA")

                # --- Automated Summary ---
            summary_points = []

            if roe and roe < 10:
                summary_points.append("The company demonstrates low return on equity.")
            elif roe <15:
                summary_points.append("Return on equity remains moderate.")
            else:
                summary_points.append("The company demonstrates strong return on equity")
    

            if roce > 18:
                summary_points.append("Capital is being employed efficiently.")
            elif roce > 12:
                summary_points.append("Capital efficiency appears average.")
            else:
                 summary_points.append("Capital efficiency appears meagre.")

            if dividend_yield and dividend_yield > 1:
                summary_points.append("The company provides regular income to shareholders.")

            if pe_ratio and pe_ratio > 30:
                summary_points.append("Valuation appears relatively high based on earnings.")

            if summary_points:
                st.markdown("### Key Observations")
                for point in summary_points:
                    st.text(f"• {point}")
            else:
                st.info("Insufficient ratio data to generate summary insights.")

        


        with tabs[2]:
            st.subheader("Performance & Growth")

            # ---------- YEARLY TRENDS ----------
            st.markdown("### Yearly Trends")

            yearly_cols = ["Year", "Sales", "Net Profit", "EPS in Rs"]
            yearly_available = [c for c in yearly_cols if c in pnl_y_df.columns]

            if len(yearly_available) >= 2:
                yearly_df = pnl_y_df[pnl_y_df.Year != "TTM"]
                yearly_df=yearly_df.sort_values("Year")
                
                colA, colB = st.columns(2)

                with colA:
                    if "Sales" in yearly_df.columns:
                        st.line_chart(yearly_df.set_index(yearly_df["Year"].astype(str))["Sales"])

                       
                    series = yearly_df["Sales"].dropna()
                    growth = series.pct_change().dropna()

                    if growth.mean() > 0.10:
                        direction = "strong growth"
                    elif growth.mean() > 0:
                        direction = "moderate growth"
                    else:
                        direction = "weak or negative growth"

                    volatility = growth.std()

                    if volatility < 0.05:
                        stability = "stable"
                    else:
                        stability = "volatile"

                    st.info(f"Revenue shows {direction} with relatively {stability} year-on-year performance.") 

                with colB:
                    if "Net Profit" in yearly_df.columns:
                        st.line_chart(yearly_df.set_index(yearly_df["Year"].astype(str))["Net Profit"])
                        profit_series = yearly_df["Net Profit"].dropna()
                        profit_growth = profit_series.pct_change().dropna()
                    if len(profit_series) >= 3:
                            if "Sales" in yearly_df.columns:
                                    sales_growth = yearly_df["Sales"].pct_change().dropna()

                                    if profit_growth.mean() > sales_growth.mean():
                                        st.success("Net profit growth outpaces revenue growth, indicating operating leverage and improving cost efficiency.")
                                    elif profit_growth.mean() < sales_growth.mean():
                                        st.warning("Net profit growth lags revenue growth, suggesting margin pressure or rising costs.")
                                    else:
                                        st.info("Net profit and revenue growth move broadly in line.")
                    else:
                        st.info("Insufficient data to assess net profit trend.")


                if "EPS in Rs" in yearly_df.columns:
                    st.line_chart(yearly_df.set_index(yearly_df["Year"].astype(str))["EPS in Rs"])
                    eps_series = yearly_df["EPS in Rs"].dropna()

                    if len(eps_series) >= 3:
                        eps_growth = eps_series.pct_change().dropna()
                        avg_eps_growth = eps_growth.mean()

                        if avg_eps_growth > 0:
                            st.success("Earnings per share show an upward trend, indicating that business growth is translating into shareholder returns.")
                        else:
                            st.warning("EPS growth remains muted despite business performance.")
                    else:
                        st.info("Insufficient data to assess EPS trend.")
                    


            # ---------- QUARTERLY TRENDS ----------
            st.markdown("### Quarterly Trends")

            q_cols = ["Quarter", "Sales", "Net Profit"]
            q_available = [c for c in q_cols if c in pnl_q_df.columns]

            if len(q_available) >= 2:
                q_df = pnl_q_df[q_available].copy()
                q_df["Quarter_dt"]=pd.to_datetime(q_df.Quarter,format = "%b %Y")
                q_df = q_df.sort_values("Quarter_dt")
                q_df.set_index("Quarter_dt")

                colC, colD = st.columns(2)

                with colC:
                    if "Sales" in q_df.columns:
                        st.line_chart(q_df.set_index("Quarter_dt")["Sales"])
                        q_sales = q_df["Sales"].dropna()

                        if len(q_sales) >= 4:
                            q_growth = q_sales.pct_change().dropna()

                            if q_growth.std() < 0.10:
                                st.success("Quarterly revenue shows relatively stable momentum with limited short-term volatility.")
                            else:
                                st.warning("Quarterly revenue exhibits noticeable volatility, indicating short-term demand fluctuations.")
                        else:
                            st.info("Limited quarterly data to assess revenue momentum.")
                       

                with colD:
                    if "Net Profit" in q_df.columns:
                        st.line_chart(q_df.set_index("Quarter_dt")["Net Profit"])
                        q_profit = q_df["Net Profit"].dropna()

                        if len(q_profit) >= 4:
                            q_profit_growth = q_profit.pct_change().dropna()

                            if q_profit_growth.mean() > 0:
                                st.success("Quarterly profits show improving momentum in recent periods.")
                            else:
                                st.warning("Quarterly profits appear uneven,suggesting sensitivity to costs or one-off factors.")
                        else:
                            st.info("Limited quarterly data to assess profit stability.")
                
        with tabs[3]:
            st.subheader("Profitability & Efficiency")
            yearly_df = pnl_y_df[pnl_y_df.Year != "TTM"].sort_values("Year")
            st.markdown("### Operating Profitability")
            

            
            if 'Operating Profit' in yearly_df.columns:
                st.area_chart(yearly_df.set_index(yearly_df["Year"].astype(str))["Operating Profit"])
                op_series = yearly_df["Operating Profit"].dropna()
                if len(op_series)>=3:
                    op_growth = op_series.pct_change().dropna()
                    if op_growth.mean() > 0:
                        st.success("Operating profits show an upward trend, indicating improving core business performance.")
                    else:
                        st.warning("Operating profit growth appears weak, suggesting pressure on core operations.")
            else:
                st.info("Insufficient data to assess operating profit trend.")
            
            if "OPM%" in yearly_df.columns:
                st.line_chart(yearly_df.set_index(yearly_df["Year"].astype(str))["OPM%"])
                margin_series = yearly_df["OPM%"].dropna()
                if len(margin_series) >= 3:
                    margin_change = margin_series.diff().dropna()
                    if margin_change.mean()>0:
                        st.success("Opearing margins are expanding over time, indicating improvement in cost efficiency or better pricing")
                    elif margin_change.mean()<0:
                        st.warning("Operating margins are contracting, suggesting rising costs or pricing pressure.")
                    else:
                        st.info("Operating margins remain broadly stable over time.")
                else:
                    st.info("Insufficient data to assess margin trend.")

            st.markdown("### Profit Conversion Efficiency")
            if "Net Profit" in yearly_df.columns and "Operating Profit" in yearly_df.columns:
                st.line_chart(yearly_df.set_index(yearly_df["Year"].astype(str))[["Operating Profit", "Net Profit"]])
                net_profit = yearly_df["Net Profit"].dropna()
                operating_profit = yearly_df["Operating Profit"].dropna()
                if len(net_profit) >= 3 and len(operating_profit) >= 3:
                    ratio = (net_profit / operating_profit).mean()
                    if ratio > 0.75:
                        st.success("A high proportion of operating profit converts into net profit, indicating efficient cost, interest, and tax management.")
                    else:
                        st.warning("Net profit conversion from operating profit is relatively low, suggesting leakage through interest, depreciation, or taxes.")


            st.markdown("### Return on Capital Employed")
            roe = ratios_df.loc[ratios_df["Metric"] == "ROE", "Value"]
            roce = ratios_df.loc[ratios_df["Metric"] == "ROCE", "Value"]
            col3, col4 = st.columns(2)

            with col3:
                if not roe.empty:
                     roe_value = roe.values[0]
                     st.metric("ROE (%)", roe_value)
                     if roe_value > 15:
                        st.success("Return on equity is strong, reflecting efficient use of shareholder capital.")
                     else:
                        st.warning("Return on equity is moderate, indicating scope for improved capital efficiency.")
            
            with col4:
                        if not roce.empty:
                            roce_value = roce.values[0]
                            st.metric("ROCE (%)", roce_value)

                            if roce_value > 15:
                                st.success("ROCE is healthy, indicating effective deployment of long-term capital.")
                            else:
                                st.warning("ROCE is relatively low, suggesting suboptimal capital utilization.")

            
        with tabs[4]:
            st.subheader("Financial Position")
            bs_df = balance_df.sort_values("Year")
            st.markdown("### Balance Sheet Scale")
            col1, col2 = st.columns(2)

            with col1:
                if "Total Assets" in bs_df.columns:
                    st.area_chart(bs_df.set_index(bs_df["Year"].astype(str))["Total Assets"])
                    assets = bs_df["Total Assets"].dropna()
                    if len(assets) >= 3:
                        assets_growth = assets.pct_change().dropna()
                        if assets.iloc[-1] > assets.iloc[0]:
                            st.success("Total assets have expanded over time, indicating growth in the company’s balance sheet size.")
                        else:
                            st.warning("Balance sheet size has remained flat, indicating limited asset expansion.")
                    else:
                        st.info("Insufficient data to assess asset growth")

            with col2:
                if "Total Liabilities" in bs_df.columns:
                    st.line_chart(bs_df.set_index(bs_df["Year"].astype(str))["Total Liabilities"])
                    liabilities = bs_df["Total Liabilities"].dropna()
                    if len(liabilities) >= 3:
                        liabilities_growth = liabilities.pct_change().dropna()
                        if liabilities.iloc[-1] > liabilities.iloc[0]:
                            st.warning("Total liabilities have increased over time, indicating rising financial obligations.")
                        else:
                            st.success("Total liabilities have remained stable, suggesting controlled financial risk.")
                    else:
                        st.info("Insufficient data to assess liability trend.")

            st.markdown("### Capital Structure & Leverage")
            if "Borrowings" in bs_df.columns:
                st.line_chart(bs_df.set_index(bs_df["Year"].astype(str))["Borrowings"])
                debt = bs_df["Borrowings"].dropna()
                if len(debt)>=3:
                    debt_growth = debt.pct_change().dropna()
                    if debt.iloc[-1] > debt.iloc[0]:
                        st.warning("Borrowings have increased over time, suggesting greater reliance on external funding.")
                    else:
                        st.success("Borrowings have reduced or remained stable, indicating improving balance sheet strength.")
                else:
                    st.caption("Insufficient data to assess leverage trend.")

            st.markdown("### Reserves & Financial Cushion")

            if "Reserves" in bs_df.columns:
                st.line_chart( bs_df.set_index(bs_df["Year"].astype(str))["Reserves"])
                reserves = bs_df["Reserves"].dropna()
                if len(reserves) >= 3:
                    reserves_growth = reserves.pct_change().dropna()
                    if reserves.iloc[-1] > reserves.iloc[0]:
                        st.success("Reserves have grown consistently, strengthening the company’s financial cushion.")
                    else:
                        st.warning("Reserves growth appears limited, reducing internal financial flexibility.")

                else:
                    st.info("Insufficient data to assess reserves trend.")
            

            st.markdown("### Funding Quality Assessment")

            if "Borrowings" in bs_df.columns and "Reserves" in bs_df.columns:
                        
                        comparison_df = pd.DataFrame({"Growth Type": ["Borrowings Growth", "Reserves Growth"],
                                                      "Average Growth Rate": [debt_growth.mean(),reserves_growth.mean()]}).dropna()

                        st.bar_chart(comparison_df.set_index("Growth Type"))

                        if debt_growth.mean() > reserves_growth.mean():
                            st.warning("Borrowings are growing faster than reserves, indicating debt-led balance sheet expansion.")
            
                        else:
                            st.success("Reserves are growing at least as fast as borrowings, indicating internally funded balance sheet strength.")



        with tabs[5]:
            st.subheader("Cash Flow Quality")
            cf_df = cashflow_df.sort_values("Year")

            st.markdown("### Operating Cash Flow Strength")

            if "Cash from Operating Activity" in cf_df.columns:
                st.area_chart(cf_df.set_index(cf_df["Year"].astype(str))["Cash from Operating Activity"])
                ocf = cf_df["Cash from Operating Activity"].dropna()
                if len(ocf) >= 3:
                    if ocf.iloc[-1] > ocf.iloc[0]:
                        st.success("Operating cash flows have strengthened over time, indicating improving cash-generating ability of core operations.")
                    else:
                        st.warning("Operating cash flows appear weak or inconsistent, raising concerns around earnings quality.")
                else:
                    st.info("Insufficient data to assess operating cash flow trend.")




            st.markdown("### Profit vs Cash Flow Quality")

            if "Cash from Operating Activity" in cf_df.columns and "Net Profit" in cf_df.columns:
                st.line_chart(cf_df.set_index(cf_df["Year"].astype(str))[["Net Profit", "Cash from Operating Activity"]])
                profit = cf_df["Net Profit"].dropna()
                ocf = cf_df["Cash from Operating Activity"].dropna()

                if len(profit) >= 3 and len(ocf) >= 3:
                    cash_conversion = (ocf / profit).mean()

                    if cash_conversion > 1:
                        st.success("Operating cash flows exceed accounting profits, indicating high earnings quality and conservative accounting.")
                    elif cash_conversion > 0.8:
                        st.info( "Operating cash flows broadly track profits, indicating reasonable earnings quality.")
                        
                    else:
                        st.warning("Operating cash flows lag profits, suggesting aggressive accounting or working capital stress.")
                        



            st.markdown("### Free Cash Flow Health")

            if "Cash from Operating Activity" in cf_df.columns and "Cash from Investing Activity" in cf_df.columns:
                cf_df["Free Cash Flow"] = (cf_df["Cash from Operating Activity"] + cf_df["Cash from Investing Activity"])

                st.line_chart( cf_df.set_index(cf_df["Year"].astype(str))["Free Cash Flow"])
                fcf = cf_df["Free Cash Flow"].dropna()

                if len(fcf) >= 3:
                    if fcf.mean() > 0:
                        st.success(
                            "Free cash flow is positive on average,indicating the business can fund growth internally.")
                    else:
                        st.warning(
                            "Free cash flow remains negative, suggesting dependence on external funding.")



            st.markdown("### Cash Flow Structure")

            required_cols = ["Cash from Operating Activity","Cash from Investing Activity","Cash from Financing Activity"]
            if all(col in cf_df.columns for col in required_cols):

                avg_cf_df = pd.DataFrame({"Cash Flow Type": ["Operating","Investing","Financing"],
                                        "Average Cash Flow": [cf_df["Cash from Operating Activity"].mean(),cf_df["Cash from Investing Activity"].mean(),cf_df["Cash from Financing Activity"].mean()]})
            

                st.bar_chart(avg_cf_df.set_index("Cash Flow Type")["Average Cash Flow"])

                if avg_cf_df.loc[0, "Average Cash Flow"] > 0:
                    st.success("Operating activities are the primary source of cash, which is a healthy cash flow structure.")
                else:
                    st.warning("Operating activities are not generating sufficient cash, raising concerns around business sustainability.")
    
        with tabs[6]:
            st.subheader("Shareholding Pattern")

            sh_df = shareholding_df.sort_values("Year")


            st.markdown("### Promoter Holding Trend")

            if "Promoters" in sh_df.columns:
                st.markdown("#### Promoter Shareholding (%)")
                st.line_chart(sh_df.set_index(sh_df["Year"].astype(str))["Promoters"])
                promoters = sh_df["Promoters"].dropna()

                if len(promoters) >= 3:
                    if promoters.iloc[-1] > promoters.iloc[0]:
                        st.success("Promoter holding has increased over time, indicating rising promoter confidence and commitment.")         
                    elif promoters.iloc[-1] < promoters.iloc[0]:
                        st.warning("Promoter holding has declined, which may indicate stake dilution or partial exit.")   
                    else:
                        st.info("Promoter holding has remained broadly stable.")
                else:
                    st.info("Insufficient data to assess promoter holding trend.")



            st.markdown("### Institutional Participation")

            col1, col2 = st.columns(2)

            with col1:
                if "FIIs" in sh_df.columns:
                    st.markdown("#### Foreign Institutional Holding (%)")
                    st.line_chart(sh_df.set_index(sh_df["Year"].astype(str))["FIIs"])
                    fii = sh_df["FIIs"].dropna()
                    if len(fii) >= 3:
                        if fii.iloc[-1] > fii.iloc[0]:
                            st.success("Foreign institutional participation has increased, reflecting improving global investor confidence.")
                        else:
                            st.warning("Foreign institutional holding has declined, possibly reflecting external risk aversion.")
                    else:
                        st.info("Insufficient data to assess FII trend.")


            with col2:
                if "DIIs" in sh_df.columns:
                    st.markdown("#### Domestic Institutional Holding (%)")
                    st.line_chart(sh_df.set_index(sh_df["Year"].astype(str))["DIIs"])
                    dii = sh_df["DIIs"].dropna()
                    if len(dii) >= 3:
                        if dii.iloc[-1] > dii.iloc[0]:
                            st.success("Domestic institutional holding has increased, indicating rising confidence among local professionals.")
                        else:
                            st.warning("Domestic institutional participation has weakened.")
                    else:
                        st.info("Insufficient data to assess DII trend.")


            st.markdown("### Public Shareholding")

            if "Public" in sh_df.columns:
                st.markdown("#### Public Shareholding (%)")
                st.area_chart(sh_df.set_index(sh_df["Year"].astype(str))["Public"])

                public = sh_df["Public"].dropna()

                if len(public) >= 3:
                    if public.iloc[-1] > public.iloc[0]:
                        st.info("Public shareholding has increased, indicating wider retail participation or promoter dilution.")
                    else:
                        st.info("Public shareholding has declined, possibly due to increased institutional ownership.")
                else:
                    st.info("Insufficient data to assess public shareholding trend.")


        with tabs[7]:
                st.subheader(f"Executive Financial Summary – {company_name}")

                strengths = []
                risks = []


                # 1. GROWTH QUALITY (0–20)

                growth_score = 14

                if "Sales" in pnl_y_df.columns and "Net Profit" in pnl_y_df.columns:
                    sales = pnl_y_df.sort_values("Year")["Sales"].dropna()
                    profit = pnl_y_df.sort_values("Year")["Net Profit"].dropna()

                    if len(sales) >= 3 and len(profit) >= 3:
                        if sales.iloc[-1] > sales.iloc[0] and profit.iloc[-1] > profit.iloc[0]:
                            growth_score = 16
                            strengths.append("Revenue and profits have grown consistently.")
                        elif sales.iloc[-1] > sales.iloc[0] and profit.iloc[-1] <= profit.iloc[0]:
                            growth_score = 10
                            risks.append("Revenue growth has not translated into profit growth.")
                        else:
                            growth_score = 8
                            risks.append("Business growth momentum appears weak or inconsistent.")


                # 2. PROFITABILITY & EFFICIENCY (0–20)

                profitability_score = 14

                is_cyclical = False

                if "OPM %" in pnl_y_df.columns:
                    margins = pnl_y_df.sort_values("Year")["OPM %"].dropna()

                    if len(margins) >= 3:
                        margin_change = margins.iloc[-1] - margins.iloc[0]

                        # Detect cyclicality via margin volatility
                        if margins.std() > 5:
                            is_cyclical = True

                        if margin_change > 1:
                            profitability_score = 16
                            strengths.append("Operating margins have expanded.")
                        elif margin_change >= -2:
                            profitability_score = 15
                            strengths.append("Operating margins have remained broadly stable.")
                        else:
                            profitability_score = 9
                            risks.append("Operating margins have seen sustained pressure.")

                # ---- ROE / ROCE quality boost ----
                roe = ratios_df.loc[ratios_df["Metric"] == "ROE", "Value"]
                roce = ratios_df.loc[ratios_df["Metric"] == "ROCE", "Value"]

                if not roe.empty and not roce.empty:
                    if roe.values[0] >= 18 and roce.values[0] >= 18:
                        profitability_score = min(profitability_score + 2, 20)
                        strengths.append("Strong ROE and ROCE indicate efficient capital usage.")


                # 3. FINANCIAL POSITION (0–20)

                balance_score = 14

                balance_df.columns = balance_df.columns.str.replace("+", "", regex=False).str.strip()

                if "Borrowings" in balance_df.columns and "Reserves" in balance_df.columns:
                    debt = balance_df["Borrowings"]
                    reserves = balance_df["Reserves"].dropna()

                    # Absolute (not %) leverage logic
                    if debt.isna().all() or debt.max(skipna=True) <= 0.1 * reserves.max():
                        balance_score = 18
                        strengths.append("Minimal leverage supported by a strong reserve base.")
                    else:
                        debt = debt.dropna()
                        if len(debt) >= 3 and len(reserves) >= 3:
                            if reserves.diff().mean() >= debt.diff().mean():
                                balance_score = 16
                                strengths.append("Balance sheet growth is largely internally funded.")
                            else:
                                balance_score = 9
                                risks.append("Borrowings are rising faster than internal reserves.")


                # 4. CASH FLOW QUALITY (0–20)

                cashflow_score = 15

                ocf_col = None
                for col in cashflow_df.columns:
                    if "operating" in col.lower() and "cash" in col.lower():
                        ocf_col = col
                        break

                if ocf_col and "Net Profit" in cashflow_df.columns:
                    ocf = cashflow_df.sort_values("Year")[ocf_col].dropna()
                    profit = cashflow_df.sort_values("Year")["Net Profit"].dropna()

                    if len(ocf) >= 3 and len(profit) >= 3:
                        if (ocf > profit).sum() >= len(ocf) - 1:
                            cashflow_score = 20
                            strengths.append("Operating cash flows consistently exceed reported profits.")
                        elif (ocf / profit).mean() >= 0.8:
                            cashflow_score = 17
                            strengths.append("Profits are well supported by operating cash flows.")
                        else:
                            cashflow_score = 9
                            risks.append("Weak cash conversion relative to reported profits.")


                # 5. GOVERNANCE & OWNERSHIP (0–20)

                governance_score = 14

                if "Promoters" in shareholding_df.columns:
                    promoters = shareholding_df.sort_values("Year")["Promoters"].dropna()

                    if len(promoters) >= 3:
                        change = promoters.iloc[-1] - promoters.iloc[0]

                        if change >= -1.0:
                            governance_score = 16
                            strengths.append("Promoter shareholding has remained broadly stable.")
                        else:
                            governance_score = 9
                            risks.append("Declining promoter shareholding observed.")


             

                confidence_score = (growth_score + profitability_score + balance_score + cashflow_score + governance_score )


                quality_checks = 0
                if cashflow_score >= 16:
                    quality_checks += 1
                if balance_score >= 15:
                    quality_checks += 1
                if profitability_score >= 14:
                    quality_checks += 1
                if governance_score >= 14:
                    quality_checks += 1

                if quality_checks >= 3 and not is_cyclical:
                    confidence_score += 10
                    strengths.append("The company exhibits characteristics of a high-quality, resilient business franchise.")

                # =========================================================
                # DISPLAY
                # =========================================================
                st.markdown("### Overall Financial Confidence")
                st.write(f"**Confidence Score:** {confidence_score}/100")

                if confidence_score >= 80:
                    st.success("Strong and sustainable financial profile.")
                elif confidence_score >= 60:
                    st.warning("Moderate financial strength with some areas to monitor.")
                else:
                    st.error("Weak sustainability and elevated financial risk.")

                st.markdown("### Key Strengths")
                for s in strengths[:5]:
                    st.write(f"• {s}")

                st.markdown("### Key Risks & Watchpoints")
                for r in risks[:5]:
                    st.write(f"• {r}")
        
        with tabs[8]:
            st.subheader("Exit & Session Summary")

            st.header(" Key KPIs Used in the Financial Diagnostic System")
            st.markdown("This page summarizes the key financial metrics analyzed across different dimensions to arrive at the final diagnostic insights.")
            st.divider()

            # Growth & Performance KPIs
            st.subheader(" Growth & Performance")
            st.markdown("""
            - Revenue (Yearly)
            - Revenue (Quarterly)
            - Net Profit (Yearly)
            - Net Profit (Quarterly)
            - Earnings Per Share (EPS)
            - Revenue Growth Trend
            - Profit Growth Trend
            """)

            # Profitability & Efficiency KPIs
            st.subheader(" Profitability & Efficiency")
            st.markdown("""
            - Operating Profit
            - Operating Margin
            - Net Profit Margin
            - Return on Equity (ROE)
            - Return on Capital Employed (ROCE)
            - Operating vs Net Profit Spread
            """)

            # Financial Position KPIs
            st.subheader("Financial Position (Balance Sheet)")
            st.markdown("""
            - Total Assets
            - Total Liabilities
            - Borrowings
            - Reserves & Surplus
            - Assets vs Liabilities Trend
            - Borrowings vs Reserves Trend
            """)

            # Cash Flow Quality KPIs
            st.subheader(" Cash Flow Quality")
            st.markdown("""
            - Operating Cash Flow (OCF)
            - Free Cash Flow (FCF)
            - Investing Cash Flow
            - Financing Cash Flow
            - Profit vs Cash Flow Alignment
            """)

            # Shareholding KPIs
            st.subheader(" Shareholding & Ownership")
            st.markdown("""
            - Promoter Holding (%)
            - Foreign Institutional Investors (FII %)
            - Domestic Institutional Investors (DII %)
            - Public Shareholding (%)
            - Ownership Stability Trend
            """)

            # Market & Return Context
            st.subheader(" Market & Return Context")
            st.markdown("""
            - Market Capitalization
            - Current Stock Price
            - Dividend Yield
            - Book Value per Share
            - 52-Week High / Low
            """)

            # Composite Indicators
            st.subheader(" Composite & Summary Indicators")
            st.markdown("""
            - Financial Confidence Score
            - Growth Consistency Indicator
            - Profitability Quality Indicator
            - Balance Sheet Strength Indicator
            - Cash Flow Sustainability Indicator
            """)

            st.divider()

            st.markdown("> *These KPIs collectively provide a structured, multi-dimensional view of a company's financial health across growth, profitability, stability, cash flow quality, and ownership.*")

            st.divider()

            st.markdown(
                """
                ### Thank You for Using the Company Financial Diagnostics System  

                You have successfully completed a structured financial analysis using:
                - Multi-year financial statements  
                - Cash flow diagnostics  
                - Balance sheet strength checks  
                - Ownership and governance signals  

                This tool is designed to support **analyst-style decision making**, not stock tips.
                """
            )

            st.divider()
            
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("🔄 Start New Analysis"):
                    st.session_state.data_loaded = False
                    st.rerun()

            with col2:
                if st.button("🔒 Logout"):
                    st.session_state.clear()
                    st.rerun()

            with col3:
                st.info("You may safely close this browser tab.")

            st.divider()
            st.caption("© Adarsh Gupta | Company Financial Diagnosis System")


