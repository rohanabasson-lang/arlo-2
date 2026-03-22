import json
import sqlite3
from datetime import datetime

import streamlit as st
from fpdf import FPDF

from industry_configs import INDUSTRY_CONFIGS
from pricing_engine import calculate_quote

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
MAX_FREE_QUOTES = 15

st.set_page_config(
    page_title="ARLO Pricing Assistant",
    page_icon="⚡",
    layout="centered"
)

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
# SESSION STATE
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

def get_quote_count(phone):
    conn = get_db()
    return conn.execute(
        "SELECT COUNT(*) FROM quotes WHERE phone = ?",
        (phone,)
    ).fetchone()[0]

# ──────────────────────────────────────────────
# PDF (Improved)
# ──────────────────────────────────────────────
def make_pdf(quote, user_name, cfg, final_ex, final_inc, discount_pct):
    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ARLO QUOTE", ln=True, align="C")

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Client: {user_name}", ln=True)
    pdf.cell(0, 8, f"Industry: {cfg['label']}", ln=True)
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%d %b %Y')}", ln=True)

    pdf.ln(10)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 8, "Bill of Quantities", ln=True)

    pdf.set_font("Helvetica", "", 10)
    for item in quote.get("boq_snapshot", []):
        pdf.cell(0, 6, f"• {item.get('name', 'Unnamed item')}", ln=True)
        pdf.cell(
            0, 6,
            f"   Qty: {item.get('quantity', 1)} × Labour: R {item.get('labour_sell', 0):.2f} | Material: R {item.get('material_sell', 0):.2f}",
            ln=True
        )

    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Total ex VAT:          R {final_ex:,.2f}", ln=True)
    pdf.cell(0, 8, f"Total incl VAT (15%):  R {final_inc:,.2f}", ln=True)

    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "Thank you for choosing ARLO — built for profit.", ln=True)

    return pdf.output(dest="S").encode("latin-1")

# ──────────────────────────────────────────────
# LOGIN
# ──────────────────────────────────────────────
if not st.session_state.user:
    st.title("ARLO Pricing Assistant ⚡")

    phone_input = st.text_input("WhatsApp Number", placeholder="0721234567")
    phone = clean_phone(phone_input)

    if st.button("Sign In", use_container_width=True):
        if phone in AUTH_USERS:
            st.session_state.user = phone
            st.rerun()
        else:
            st.error("Not authorised")

    st.stop()

# ──────────────────────────────────────────────
# USER DASHBOARD
# ──────────────────────────────────────────────
user_phone = st.session_state.user
user_name = BUSINESS_MAP.get(user_phone, user_phone)

st.markdown(f"""
<div style="background:#111827;padding:20px;border-radius:12px;margin-bottom:20px;">
<h3 style="color:white;">👋 Welcome back, {user_name}</h3>
<p style="color:#9CA3AF;">Let’s build a profitable quote.</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# PAYWALL
# ──────────────────────────────────────────────
quote_count = get_quote_count(user_phone)

st.caption(f"Quotes used: **{quote_count}/{MAX_FREE_QUOTES}**")

if quote_count >= MAX_FREE_QUOTES:
    st.error("🚫 Free limit reached (15 quotes)")
    st.markdown("""
### 🔓 Upgrade to ARLO Pro
- Unlimited quotes  
- Advanced pricing engine  
- Priority support  
💰 Only R99/month  
""")
    st.stop()

# ──────────────────────────────────────────────
# INDUSTRY + SETTINGS
# ──────────────────────────────────────────────
industry = st.selectbox(
    "Industry",
    list(INDUSTRY_CONFIGS.keys()),
    format_func=lambda x: INDUSTRY_CONFIGS[x]["label"]
)

cfg = INDUSTRY_CONFIGS[industry]

col1, col2, col3 = st.columns(3)
monthly_cost = col1.number_input("Monthly Overhead (R)", value=float(cfg["default_monthly_cost"]), step=100.0)
billable_hours = col2.number_input("Billable Hours / Month", value=float(cfg["default_billable_hours"]), step=10.0)
profit = col3.slider("Profit Multiplier", 1.1, 3.5, float(cfg["default_profit_multiplier"]))

# ──────────────────────────────────────────────
# BOQ — FIXED & FULLY PERSISTENT
# ──────────────────────────────────────────────
st.subheader("📋 Bill of Quantities")

c1, c2 = st.columns([3, 1])
if c1.button("➕ Add Item", use_container_width=True):
    st.session_state.boq.append({"name": "", "quantity": 1, "hours": 1.0, "material": 0.0})
    st.rerun()

if c2.button("🗑️ Clear All", use_container_width=True):
    if st.session_state.boq:
        st.session_state.boq = []
        st.rerun()

# ────── Sync loop with safe delete ──────
updated_boq = []
to_delete = None

for i in range(len(st.session_state.boq)):
    item = st.session_state.boq[i]

    st.subheader(f"Item {i+1}")

    name = st.text_input("Description", value=item["name"], key=f"name_{i}")
    qty = st.number_input("Qty", value=item["quantity"], min_value=1, step=1, key=f"qty_{i}")
    hours = st.number_input("Hours per unit", value=item["hours"], min_value=0.0, step=0.25, key=f"hours_{i}")
    mat = st.number_input("Material per unit (R)", value=item["material"], min_value=0.0, step=10.0, key=f"mat_{i}")

    updated_boq.append({
        "name": name,
        "quantity": qty,
        "hours": hours,
        "material": mat
    })

    if st.button("🗑️ Delete", key=f"del_{i}", help="Remove this item"):
        to_delete = i

# Apply changes
if to_delete is not None:
    del updated_boq[to_delete]
    st.session_state.boq = updated_boq
    st.rerun()
else:
    st.session_state.boq = updated_boq

# Prepare clean items list for engine
items = [
    {
        "name": it["name"],
        "labour_hours": it["quantity"] * it["hours"],
        "material_cost": it["quantity"] * it["material"],
        "quantity": it["quantity"]
    }
    for it in st.session_state.boq
    if it["name"].strip()
]

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

    # Show breakdown
    with st.expander("📊 Cost Breakdown & Details", expanded=False):
        st.json(quote)

    target = quote["final_price"]
    rec = round(target * 0.92, 2)
    walk = round(target * 0.80, 2)

    st.subheader("Select Price Level")

    choice = st.radio(
        "Price Level",
        ["Recommended", "Target", "Walk-away", "Custom"],
        horizontal=True,
        label_visibility="collapsed"
    )

    discount = st.slider("Discount %", 0.0, 25.0, 0.0, step=0.5)

    if choice == "Recommended":
        base = rec
    elif choice == "Target":
        base = target
    elif choice == "Walk-away":
        base = walk
    else:
        base = st.number_input("Custom Price (ex VAT)", value=float(rec), step=100.0)

    final_ex = round(base * (1 - discount / 100), 2)
    final_inc = round(final_ex * 1.15, 2)

    st.metric("Final Price (ex VAT)", f"R {final_ex:,.2f}")
    st.metric("Final Price (incl VAT)", f"R {final_inc:,.2f}")

    col1, col2 = st.columns(2)

    if col1.button("💾 Save Quote", use_container_width=True):
        conn = get_db()
        conn.execute(
            "INSERT INTO quotes (phone, industry, final_ex, final_inc, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_phone, industry, final_ex, final_inc, datetime.now().isoformat())
        )
        conn.commit()
        st.success("Quote saved to database!")

    pdf_bytes = make_pdf(quote, user_name, cfg, final_ex, final_inc, discount)

    col2.download_button(
        label="📄 Download PDF",
        data=pdf_bytes,
        file_name=f"ARLO_Quote_{industry}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

else:
    st.info("Add at least one item with a description to start calculating.")

st.caption("ARLO Pricing Assistant — built for South African contractors")