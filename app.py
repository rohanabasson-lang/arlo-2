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
    page_title="ARLO Pricing Assistant",
    page_icon="⚡",
    layout="centered"
)

# ──────────────────────────────────────────────
# STYLING (PREMIUM LOOK)
# ──────────────────────────────────────────────
st.markdown("""
<style>
.block-container {padding-top: 1.5rem; max-width: 900px;}
.stButton>button {height: 3rem; font-weight: 600;}
.metric-box {background:#111827;padding:15px;border-radius:10px;color:white;}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# DATABASE
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
def clean_phone(x):
    return "".join(c for c in str(x) if c.isdigit())

# ──────────────────────────────────────────────
# SAFE PDF
# ──────────────────────────────────────────────
def make_pdf(quote, user_name, cfg, final_ex, final_inc):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "ARLO QUOTE", ln=True)

    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Client: {user_name}", ln=True)
    pdf.cell(0, 6, f"Industry: {cfg['label']}", ln=True)
    pdf.cell(0, 6, f"Date: {datetime.now().strftime('%d %B %Y')}", ln=True)

    pdf.ln(6)

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
    pdf.cell(0, 8, f"Total ex VAT: R {final_ex:.2f}", ln=True)
    pdf.cell(0, 8, f"Total incl VAT: R {final_inc:.2f}", ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, "Payment terms: 50% deposit. Balance on completion.")

    return pdf.output(dest="S").encode("latin-1")

# ──────────────────────────────────────────────
# LOGIN
# ──────────────────────────────────────────────
if not st.session_state.user:
    st.title("ARLO Pricing Assistant ⚡")

    phone_input = st.text_input("Enter WhatsApp Number", placeholder="0721234567")
    phone = clean_phone(phone_input)

    if st.button("Sign In", use_container_width=True):
        if phone in AUTH_USERS:
            st.session_state.user = phone
            st.rerun()
        else:
            st.error("Number not authorised")

    st.stop()

# ──────────────────────────────────────────────
# USER CONTEXT
# ──────────────────────────────────────────────
user_phone = st.session_state.user
user_name = BUSINESS_MAP.get(user_phone, user_phone)

# 🔥 HERO HEADER
st.markdown(f"""
<div style="background:#111827;padding:18px;border-radius:12px;margin-bottom:20px;">
<h3 style="color:white;margin:0;">👋 Welcome back, {user_name}</h3>
<p style="color:#9CA3AF;margin:0;">Build smarter, more profitable quotes.</p>
</div>
""", unsafe_allow_html=True)

st.title("ARLO Pricing Assistant")

# ──────────────────────────────────────────────
# INDUSTRY
# ──────────────────────────────────────────────
industry = st.selectbox(
    "Select Industry",
    list(INDUSTRY_CONFIGS.keys()),
    format_func=lambda x: INDUSTRY_CONFIGS[x]["label"]
)

cfg = INDUSTRY_CONFIGS[industry]

# ──────────────────────────────────────────────
# PRICING SETTINGS
# ──────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

monthly_cost = col1.number_input(
    "Monthly Cost",
    value=float(cfg["default_monthly_cost"]),
    step=1000.0
)

billable_hours = col2.number_input(
    "Billable Hours",
    value=float(cfg["default_billable_hours"]),
    step=5.0
)

profit = col3.slider(
    "Profit Multiplier",
    1.1,
    3.0,
    float(cfg["default_profit_multiplier"])
)

# ──────────────────────────────────────────────
# ITEMS
# ──────────────────────────────────────────────
st.subheader("Items")

if st.button("➕ Add Item"):
    st.session_state.boq.append({"name": "", "hours": 1.0, "material": 0.0})
    st.rerun()

items = []

for i in range(len(st.session_state.boq)):
    st.markdown(f"**Item {i+1}**")

    name = st.text_input("Description", key=f"name{i}")
    hours = st.number_input("Hours", value=1.0, key=f"h{i}")
    material = st.number_input("Material Cost", value=0.0, key=f"m{i}")

    items.append({
        "name": name,
        "labour_hours": hours,
        "material_cost": material
    })

# ──────────────────────────────────────────────
# CALCULATION
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
        st.error("Calculation failed")
        st.stop()

    final_ex = quote["final_price"]
    final_inc = round(final_ex * 1.15, 2)

    st.subheader("Quote Summary")

    c1, c2 = st.columns(2)
    c1.metric("Ex VAT", f"R {final_ex:,.2f}")
    c2.metric("Incl VAT", f"R {final_inc:,.2f}")

    col1, col2 = st.columns(2)

    if col1.button("💾 Save Quote"):
        conn = get_db()
        conn.execute(
            "INSERT INTO quotes (phone, industry, final_ex, final_inc, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_phone, industry, final_ex, final_inc, datetime.now().isoformat())
        )
        conn.commit()
        st.success("Quote saved")

    pdf = make_pdf(quote, user_name, cfg, final_ex, final_inc)

    col2.download_button(
        "📄 Download PDF",
        pdf,
        file_name="arlo_quote.pdf",
        mime="application/pdf",
        use_container_width=True
    )

else:
    st.info("Add at least one item to generate a quote.")