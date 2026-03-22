import json
import sqlite3
from datetime import datetime

import streamlit as st
from fpdf import FPDF

from industry_configs import INDUSTRY_CONFIGS
from pricing_engine import calculate_quote

# ──────────────────────────────────────────────
# PAGE CONFIG
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="ARLO • Trade Quoting",
    page_icon="⚡",
    layout="centered"
)

# ──────────────────────────────────────────────
# DATABASE (LOCAL SQLITE)
# ──────────────────────────────────────────────
@st.cache_resource
def get_db():
    conn = sqlite3.connect("arlo.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            industry TEXT,
            final_ex REAL,
            final_inc REAL,
            created_at TEXT
        )
    """)
    conn.commit()

init_db()

# ──────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────
AUTH_USERS = st.secrets["auth"]["AUTHORIZED_USERS"]
BUSINESS_MAP = st.secrets["auth"]["business_names"]

# ──────────────────────────────────────────────
# SESSION
# ──────────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None
if "boq" not in st.session_state:
    st.session_state.boq = []

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def clean_phone(p):
    return "".join([c for c in str(p) if c.isdigit()])

# ──────────────────────────────────────────────
# SAFE PDF
# ──────────────────────────────────────────────
def make_pdf(quote, user_name, cfg, final_ex, final_inc):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "QUOTE", ln=True)

    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Client: {user_name}", ln=True)
    pdf.cell(0, 6, f"Industry: {cfg['label']}", ln=True)
    pdf.cell(0, 6, f"Date: {datetime.now().strftime('%d %B %Y')}", ln=True)

    pdf.ln(8)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Items", ln=True)

    pdf.set_font("Arial", "", 10)
    for item in quote["boq_snapshot"]:
        pdf.cell(0, 6, f"- {item['name']}", ln=True)
        pdf.cell(
            0, 6,
            f"Labour: R {item['labour_sell']:.2f} | Material: R {item['material_sell']:.2f}",
            ln=True
        )

    pdf.ln(10)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, f"Total (ex VAT): R {final_ex:.2f}", ln=True)
    pdf.cell(0, 8, f"Total (incl VAT): R {final_inc:.2f}", ln=True)

    pdf.ln(10)

    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, "Payment terms: 50% deposit, balance on completion. Valid 14 days.")

    return pdf.output(dest="S").encode("latin-1")

# ──────────────────────────────────────────────
# LOGIN
# ──────────────────────────────────────────────
if not st.session_state.user:
    st.title("ARLO PRICING ASSISTANT ⚡ Trade Quoting")

    phone_input = st.text_input("WhatsApp Number", placeholder="e.g. 0721234567")
    phone = clean_phone(phone_input)

    if st.button("Login"):
        if phone in AUTH_USERS:
            st.session_state.user = phone
            st.rerun()
        else:
            st.error("Not authorised. Please use your registered number.")

    st.stop()

# ──────────────────────────────────────────────
# USER GREETING + SIDEBAR INFO
# ──────────────────────────────────────────────
user_phone = st.session_state.user
user_name = BUSINESS_MAP.get(user_phone, user_phone)

# Nice greeting banner
st.markdown(
    f"""
    <div style="
        background: linear-gradient(135deg, #1e3a8a, #3b82f6);
        color: white;
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 28px;
        text-align: center;
    ">
        <h2 style="margin: 0; font-size: 2.1rem;">👋 Welcome back, {user_name}!</h2>
        <p style="margin: 12px 0 0; font-size: 1.1rem; opacity: 0.95;">
            Ready to create another sharp quote? ⚡
        </p>
    </div>
    """,
    unsafe_allow_html=True
)

st.sidebar.markdown(f"**Logged in as**  \n{user_name}")
st.sidebar.markdown(f"Phone: `{user_phone}`")

# ──────────────────────────────────────────────
# INDUSTRY
# ──────────────────────────────────────────────
industry = st.selectbox(
    "Industry",
    list(INDUSTRY_CONFIGS.keys()),
    format_func=lambda x: INDUSTRY_CONFIGS[x]["label"]
)

cfg = INDUSTRY_CONFIGS[industry]

# ──────────────────────────────────────────────
# INPUTS
# ──────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

monthly_cost = col1.number_input(
    "Monthly Cost (R)",
    value=float(cfg["default_monthly_cost"]),
    step=1000.0,
    min_value=0.0
)

billable_hours = col2.number_input(
    "Billable Hours / Month",
    value=float(cfg["default_billable_hours"]),
    step=5.0,
    min_value=1.0
)

profit = col3.slider(
    "Profit Multiplier",
    1.1,
    3.0,
    float(cfg["default_profit_multiplier"]),
    step=0.1
)

# ──────────────────────────────────────────────
# ITEMS (with basic persistence fix)
# ──────────────────────────────────────────────
st.subheader("Items")

if st.button("➕ Add Item"):
    st.session_state.boq.append({"name": "", "hours": 1.0, "material": 0.0})
    st.rerun()

updated_boq = []
for i in range(len(st.session_state.boq)):
    st.subheader(f"Item {i+1}")

    name = st.text_input("Description", value=st.session_state.boq[i]["name"], key=f"name_{i}")
    hours = st.number_input("Hours", value=st.session_state.boq[i]["hours"], min_value=0.0, step=0.25, key=f"h_{i}")
    mat = st.number_input("Material (R)", value=st.session_state.boq[i]["material"], min_value=0.0, step=50.0, key=f"m_{i}")

    updated_boq.append({"name": name, "hours": hours, "material": mat})

    if st.button("🗑 Remove", key=f"del_{i}"):
        del st.session_state.boq[i]
        st.rerun()

st.session_state.boq = updated_boq

# Prepare items for calculation engine
items = [
    {
        "name": it["name"],
        "labour_hours": it["hours"],
        "material_cost": it["material"]
    }
    for it in st.session_state.boq
    if it["name"].strip()  # skip empty descriptions
]

# ──────────────────────────────────────────────
# CALCULATION & OUTPUT
# ──────────────────────────────────────────────
if items:
    quote = calculate_quote(
        items,
        cfg,
        monthly_cost,
        billable_hours,
        profit
    )

    if not quote or "error" in quote:
        st.error("Calculation failed — check pricing engine")
        st.stop()

    final_ex = quote["final_price"]
    final_inc = round(final_ex * 1.15, 2)

    st.markdown("---")
    col_a, col_b = st.columns([3, 2])

    with col_a:
        st.metric("Total ex VAT", f"R {final_ex:,.2f}")
        st.metric("Total incl VAT (15%)", f"R {final_inc:,.2f}")

    with col_b:
        col_save, col_pdf = st.columns(2)

        if col_save.button("💾 Save Quote"):
            conn = get_db()
            conn.execute(
                "INSERT INTO quotes (phone, industry, final_ex, final_inc, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_phone, industry, final_ex, final_inc, datetime.now().isoformat())
            )
            conn.commit()
            st.success("Quote saved!")

        pdf_bytes = make_pdf(quote, user_name, cfg, final_ex, final_inc)

        col_pdf.download_button(
            label="📄 Download PDF",
            data=pdf_bytes,
            file_name=f"ARLO_Quote_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )

else:
    st.info("Add at least one item with a description to see the quote.")

st.caption("ARLO • Built for South African tradespeople • Valid quotes 14 days")