import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from fpdf import FPDF

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="ARLO Pricing Engine",
    page_icon="🏗️",
    layout="wide"
)

DB_PATH = "arlo.db"

ADMIN_NUMBERS = ["0659994443", "0736826931"]

AUTHORIZED_USERS = {
    "0795659007": "Ahluma Construction and Trading",
    "0815555088": "Ben Lutumba Construction",
    "0626011810": "Imabacon Projects",
    "0829980714": "Orion Shades and Steel Worx",
    "0730434326": "TAAL Projects and Civil Contractors",
    "0693794420": "Tripoli Private Investigators Security Systems Pty Ltd",
    "0631172296": "Volts and Amps Engineering (Solar/Electrical)",
    "0828431430": "Marz Construction",
    "0792001200": "Comma Group Pty Ltd",
    "0678201965": "JMF Construction",
    "0768976484": "Kusasa Projects and Maintenance Pty Ltd",
    "0731196550": "Energon Holdings Pty Ltd",
    "0678866227": "Reliable Painters Pty Ltd",
    "0656611289": "Lenyakallo Projects",
    "0730970027": "Myc-services Construction Pty Ltd",
    "0678250880": "NBH Construction Pty Ltd",
    "0795970690": "Bra Joe Steelworks and Construction",
    "0719152903": "Jobfellas",
    "0799722549": "Wiseinn Landscapes",
    "0787247849": "M S Kathide",
    "0660548678": "Ngwenya Property Rehab",
    "0672567151": "Ipotau Projects",
    "0659994443": "The Profit Prophet (Admin)",
    "0736826931": "Rohan Basson (Admin)",
    "0699307681": "Apex Electro Dynamics",
    "0686807333": "Boneh Projects",
    "0722396885": "Power Water Solutions",
    "0620136344": "Loyal Construction",
    "0660417821": "Handyman Andries",
    "0718357947": "Champion Renovations"
}

# =========================================================
# STYLING
# =========================================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1100px;
    }
    .stMetric {
        background: #0f172a;
        border: 1px solid #1e293b;
        padding: 14px;
        border-radius: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# DB SETUP
# =========================================================
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL;")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_phone TEXT,
    client_name TEXT,
    project TEXT,
    total_direct_cost REAL,
    labour_portion REAL,
    material_portion REAL,
    overhead_pct REAL,
    overhead_amount REAL,
    total_cost REAL,
    price REAL,
    suggested REAL,
    profit REAL,
    margin REAL,
    walk_away REAL,
    timestamp TEXT
)
""")
conn.commit()

# =========================================================
# HELPERS
# =========================================================
def save_quote(data: tuple) -> None:
    c.execute("""
    INSERT INTO quotes (
        user_phone, client_name, project,
        total_direct_cost, labour_portion, material_portion,
        overhead_pct, overhead_amount, total_cost,
        price, suggested, profit, margin, walk_away, timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data)
    conn.commit()

def get_user_quotes(phone: str) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT * FROM quotes WHERE user_phone=? ORDER BY id DESC",
        conn,
        params=(phone,)
    )

def get_all_quotes() -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT * FROM quotes ORDER BY id DESC",
        conn
    )

def make_pdf_bytes(
    user_name: str,
    project_name: str,
    total_direct_cost: float,
    labour_portion: float,
    material_portion: float,
    overhead_pct: float,
    overhead_amount: float,
    total_cost: float,
    price: float,
    suggested: float,
    profit: float,
    margin: float,
    walk_away: float,
    items: list[dict],
) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Arial", "B", 16)
    pdf.cell(190, 10, "ARLO QUOTATION", ln=True, align="C")

    pdf.ln(4)
    pdf.set_font("Arial", size=11)
    pdf.cell(190, 8, f"Client: {user_name}", ln=True)
    pdf.cell(190, 8, f"Project / Service: {project_name}", ln=True)
    pdf.cell(190, 8, f"Date: {datetime.now().strftime('%Y-%m-%d')}", ln=True)
    valid_until = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    pdf.cell(190, 8, f"Valid until: {valid_until}", ln=True)

    pdf.ln(8)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 8, "Price Summary", ln=True)

    pdf.set_font("Arial", size=11)
    summary_text = (
        f"Total Price (excl. VAT): R{price:,.0f}\n"
        f"VAT @ 15% will be added where applicable.\n"
        f"Amount due (incl. VAT): R{price * 1.15:,.0f}"
    )
    pdf.multi_cell(180, 7, summary_text)

    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 8, "Project Breakdown", ln=True)

    pdf.set_font("Arial", size=10)
    for idx, item in enumerate(items, start=1):
        name = item['name'] if item['name'] else f"Line {idx}"
        line = f"{idx}. {name} — Qty: {item['qty']:,.2f} | Rate: R{item['rate']:,.0f} | Subtotal: R{item['cost']:,.0f}"
        pdf.multi_cell(170, 6, line)
        pdf.ln(1)

    pdf.ln(8)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 8, "Pricing Build-Up", ln=True)

    pdf.set_font("Arial", size=11)
    build_up_text = (
        f"Total Direct Costs (from items):       R{total_direct_cost:,.0f}\n"
        f"Overhead ({overhead_pct:.1f}%):                 R{overhead_amount:,.0f}\n"
        f"───────────────────────────────────────\n"
        f"Total Cost:                              R{total_cost:,.0f}\n"
        f"Profit / Margin ({margin:.1f}%):          R{profit:,.0f}\n"
        f"───────────────────────────────────────\n"
        f"Total Price (excl. VAT):           **R{price:,.0f}**"
    )
    pdf.multi_cell(180, 7, build_up_text)

    pdf.ln(12)
    footer = (
        "Prepared by ARLO – The Profit Prophet\n\n"
        "Payment Terms: 50% deposit on acceptance, balance on completion.\n"
        "Inclusions: As detailed above.\n"
        "Exclusions: Variations, additional work, unforeseen conditions.\n"
        "All prices exclude VAT unless stated otherwise."
    )
    pdf.multi_cell(180, 7, footer)

    pdf_output = pdf.output(dest='S').encode('latin-1', errors='ignore')
    return pdf_output

# =========================================================
# SESSION STATE
# =========================================================
if "items" not in st.session_state:
    st.session_state.items = []

if "last_saved_key" not in st.session_state:
    st.session_state.last_saved_key = None

# =========================================================
# HEADER
# =========================================================
st.title("🏗️ ARLO Pricing Engine")
st.caption("Clear. Profitable. Multi-industry quoting.")

# =========================================================
# AUTHENTICATION
# =========================================================
user_phone = st.text_input("WhatsApp number", placeholder="e.g. 0659994443")

if not user_phone:
    st.info("Enter your number to continue.")
    st.stop()

user_phone = user_phone.strip()

if user_phone not in AUTHORIZED_USERS:
    st.error("Number not authorized.")
    st.stop()

user_name = AUTHORIZED_USERS[user_phone]
is_admin = user_phone in ADMIN_NUMBERS

st.success(f"Welcome back, {user_name}")
if is_admin:
    st.info("Admin mode active")

# =========================================================
# PROJECT / SERVICE
# =========================================================
project_name = st.text_input("Project / Service Name", value="General Scope")

# =========================================================
# LINE ITEMS
# =========================================================
st.subheader("📋 Project Items")

col_a, col_b = st.columns(2)
with col_a:
    if st.button("➕ Add Line", use_container_width=True):
        st.session_state.items.append({
            "name": "",
            "qty": 1.0,
            "rate": 0.0,
            "labour_pct": 50
        })
        st.rerun()

with col_b:
    if st.button("🧹 Clear / New", use_container_width=True):
        st.session_state.items = []
        st.session_state.last_saved_key = None
        st.rerun()

total_direct_cost = 0.0
labour_portion = 0.0
material_portion = 0.0
item_snapshot = []

for i, line in enumerate(st.session_state.items):
    with st.expander(f"Line {i+1}", expanded=True):
        c1, c2, c3 = st.columns(3)
        line["name"] = c1.text_input("Description", value=line["name"], key=f"name_{i}")
        line["qty"]  = c2.number_input("Quantity", min_value=0.0, value=float(line["qty"]), step=0.1, key=f"qty_{i}")
        line["rate"] = c3.number_input("Unit Rate", min_value=0.0, value=float(line["rate"]), step=10.0, key=f"rate_{i}")

        line["labour_pct"] = st.slider("Labour portion %", 0, 100, int(line["labour_pct"]), key=f"lab_{i}")

        cost = float(line["qty"]) * float(line["rate"])
        labour_cost   = cost * (line["labour_pct"] / 100)
        material_cost = cost - labour_cost

        total_direct_cost += cost
        labour_portion    += labour_cost
        material_portion  += material_cost

        item_snapshot.append({
            "name": line["name"] if line["name"] else f"Line {i+1}",
            "qty": float(line["qty"]),
            "rate": float(line["rate"]),
            "cost": cost,
        })

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Line Total", f"R{cost:,.0f}")
        mc2.metric("Labour", f"R{labour_cost:,.0f}")
        mc3.metric("Material/Other", f"R{material_cost:,.0f}")

        if st.button("🗑 Remove", key=f"del_{i}"):
            st.session_state.items.pop(i)
            st.rerun()

st.divider()

# =========================================================
# PRICING
# =========================================================
st.subheader("⚙️ Markup & Margin")

c1, c2 = st.columns(2)
with c1:
    overhead_pct = st.number_input("Overhead / Business %", 0.0, 100.0, 20.0, step=0.5, format="%.1f")
with c2:
    margin_pct = st.number_input("Desired Margin %", 1.0, 99.0, 30.0, step=0.5, format="%.1f")

if total_direct_cost <= 0:
    st.info("Add at least one line item to see pricing.")
    st.stop()

overhead_amount = total_direct_cost * (overhead_pct / 100)
total_cost = total_direct_cost + overhead_amount
price      = total_cost / (1 - margin_pct / 100)
suggested  = price * 0.95
profit     = price - total_cost
margin     = (profit / price) * 100 if price > 0 else 0
walk_away  = total_cost * 1.25

# =========================================================
# RESULTS
# =========================================================
st.subheader("📊 Summary")

cols1 = st.columns(3)
cols1[0].metric("Direct Costs", f"R{total_direct_cost:,.0f}")
cols1[1].metric("Labour Portion", f"R{labour_portion:,.0f}")
cols1[2].metric("Material / Other", f"R{material_portion:,.0f}")

cols2 = st.columns(3)
cols2[0].metric("Overhead", f"R{overhead_amount:,.0f}")
cols2[1].metric("Total Cost", f"R{total_cost:,.0f}")
cols2[2].metric("Expected Profit", f"R{profit:,.0f}")

cols3 = st.columns(3)
cols3[0].metric("Target Price", f"R{price:,.0f}")
cols3[1].metric("Suggested Price", f"R{suggested:,.0f}")
cols3[2].metric("Walk-away", f"R{walk_away:,.0f}")

st.metric("Achieved Margin", f"{margin:.1f}%", delta_color="normal")

if margin < 15:
    st.error("Margin very low — high risk")
elif margin < 25:
    st.warning("Margin quite thin — be cautious")
else:
    st.success("Healthy margin range")

# =========================================================
# ACTIONS
# =========================================================
act1, act2 = st.columns(2)

quote_key = (user_phone, project_name, round(total_cost,2), round(price,2), round(margin,2), len(item_snapshot))

with act1:
    if st.button("💾 Save Quote", use_container_width=True):
        if st.session_state.last_saved_key == quote_key:
            st.info("Already saved (no changes detected)")
        else:
            save_quote((
                user_phone, user_name, project_name,
                total_direct_cost, labour_portion, material_portion,
                float(overhead_pct), overhead_amount, total_cost,
                price, suggested, profit, margin, walk_away,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            st.session_state.last_saved_key = quote_key
            st.success("Quote saved")

with act2:
    pdf_data = make_pdf_bytes(
        user_name, project_name,
        total_direct_cost, labour_portion, material_portion,
        float(overhead_pct), overhead_amount, total_cost,
        price, suggested, profit, margin, walk_away,
        item_snapshot
    )
    st.download_button(
        "📄 Download Quotation",
        pdf_data,
        file_name=f"ARLO_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

# =========================================================
# DISCOUNT
# =========================================================
st.subheader("🔻 Quick Discount Check")
disc = st.slider("Discount %", 0, 25, 0)

if disc > 0:
    new_price = price * (1 - disc/100)
    new_profit = new_price - total_cost
    new_margin = (new_profit / new_price)*100 if new_price > 0 else 0
    st.warning(f"After {disc}% discount:\n\nPrice: **R{new_price:,.0f}**\nProfit: R{new_profit:,.0f}\nMargin: {new_margin:.1f}%")

# =========================================================
# HISTORY
# =========================================================
st.subheader("📜 Quote History")

if is_admin:
    quotes_df = get_all_quotes()
else:
    quotes_df = get_user_quotes(user_phone)

if quotes_df.empty:
    st.info("No saved quotes yet")
else:
    for _, r in quotes_df.iterrows():
        with st.expander(f"{r['timestamp']} — R{r['price']:,.0f}"):
            st.write(f"**Client** {r['client_name']}")
            st.write(f"**Project/Service** {r['project']}")
            st.write(f"Total Cost: R{r['total_cost']:,.0f}")
            st.write(f"Profit: R{r['profit']:,.0f}")
            st.write(f"Margin: {r['margin']:.1f}%")
            st.write(f"Suggested: R{r['suggested']:,.0f}")

st.markdown("---")
st.caption("ARLO • Multi-industry Pricing • v1.2")