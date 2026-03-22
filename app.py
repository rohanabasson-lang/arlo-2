import io
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
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 950px; }
        .stButton > button { height: 3.2rem; font-size: 1.05rem; }
        .internal-box { background-color: #f0f2f6; padding: 1rem; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────────
@st.cache_resource
def get_db():
    conn = sqlite3.connect("arlo.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            industry TEXT,
            item_count INTEGER,
            final_ex_vat REAL,
            final_inc_vat REAL,
            discount_pct REAL DEFAULT 0,
            boq_json TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()

init_db()

# ──────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────
AUTH_USERS = st.secrets["auth"]["AUTHORIZED_USERS"]
ADMIN_NUMS = st.secrets["auth"]["ADMIN_NUMBERS"]
BUSINESS_MAP = st.secrets["auth"]["business_names"]

# ──────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────
if "user" not in st.session_state:
    st.session_state.user = None
if "boq" not in st.session_state:
    st.session_state.boq = []
if "current_page" not in st.session_state:
    st.session_state.current_page = "New Quote"

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def clean_phone(value: str) -> str:
    return "".join(ch for ch in str(value).strip() if ch.isdigit())

def reset_boq():
    st.session_state.boq = []

# ──────────────────────────────────────────────
# SIMPLIFIED PDF (NO MARGIN, NO OTHER PRICES)
# ──────────────────────────────────────────────
def make_pdf(quote: dict, user_name: str, cfg: dict, final_ex: float, final_inc: float, discount_pct: float) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 12, "QUOTE", ln=True, align="C")

    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"Client: {user_name}", ln=True)
    pdf.cell(0, 8, f"Industry: {cfg['label']}", ln=True)
    pdf.cell(0, 8, f"Date: {datetime.now().strftime('%d %B %Y')}", ln=True)

    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Items / Services", ln=True)

    pdf.set_font("Arial", "", 10)
    for item in quote["boq_snapshot"]:
        pdf.multi_cell(0, 7, f"• {item['name']}")
        pdf.cell(0, 7,
                 f"   Qty: {item.get('quantity', 1):.0f} × "
                 f"Labour: R {item['labour_sell']:,.2f} | "
                 f"Material: R {item['material_sell']:,.2f}",
                 ln=True)
        pdf.ln(2)

    pdf.ln(8)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 12, f"FINAL QUOTE (ex VAT):   R {final_ex:,.2f}", ln=True)
    pdf.cell(0, 12, f"FINAL QUOTE (incl. 15% VAT): R {final_inc:,.2f}", ln=True)

    if discount_pct > 0:
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 8, f"Discount applied: {discount_pct:.1f}%", ln=True)

    pdf.ln(15)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 6,
        "Payment terms: 50% deposit on acceptance, balance on completion.\n"
        "Valid for 14 days.\n\nThank you for choosing us!")

    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1")
    return pdf_bytes

# ──────────────────────────────────────────────
# LOGIN
# ──────────────────────────────────────────────
if not st.session_state.user:
    st.title("ARLO ⚡")
    st.markdown("### Professional Trade Quoting")
    phone_raw = st.text_input("WhatsApp Number", placeholder="0659994443")
    phone = clean_phone(phone_raw)

    if st.button("Sign In", type="primary", use_container_width=True):
        if phone in AUTH_USERS:
            st.session_state.user = phone
            st.rerun()
        else:
            st.error("Number not authorized")
    st.stop()

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
user_phone = st.session_state.user
user_name = BUSINESS_MAP.get(user_phone, user_phone)
is_admin = user_phone in ADMIN_NUMS

with st.sidebar:
    st.markdown(f"**👋 {user_name}**")
    st.caption(user_phone)
    st.divider()
    page = st.radio("Menu", ["New Quote", "My Quotes"], horizontal=True)
    st.session_state.current_page = page
    st.divider()
    if st.button("Clear Current Items", use_container_width=True):
        reset_boq()
        st.rerun()
    if st.button("Log Out", use_container_width=True):
        st.session_state.user = None
        st.session_state.boq = []
        st.rerun()

# ──────────────────────────────────────────────
# NEW QUOTE PAGE
# ──────────────────────────────────────────────
if page == "New Quote":
    st.header("New Quote")

    industry = st.selectbox(
        "Industry",
        options=list(INDUSTRY_CONFIGS.keys()),
        format_func=lambda k: INDUSTRY_CONFIGS[k]["label"]
    )
    cfg = INDUSTRY_CONFIGS[industry]

    col1, col2, col3 = st.columns(3)
    monthly_cost = col1.number_input("Monthly Cost (R)", value=float(cfg["default_monthly_cost"]), step=500.0)
    billable_hours = col2.number_input("Billable Hours", value=float(cfg["default_billable_hours"]), step=5.0)
    profit_mult = col3.slider("Profit Multiplier", 1.10, 3.00, float(cfg["default_profit_multiplier"]), 0.05)

    c1, c2, c3 = st.columns(3)
    use_callout = c1.checkbox("Include Call-out Fee", value=bool(cfg["uses_callout"]))
    callout_fee = c2.number_input("Call-out Fee (R)", value=float(cfg["default_callout_fee"]), step=50.0, disabled=not use_callout)
    after_hours = c3.checkbox("After-hours / Emergency", value=False)

    enforce_min_margin = st.checkbox("Enforce Minimum Margin", value=False)

    st.subheader("Items / Services")

    if st.button("➕ Add New Item", use_container_width=True):
        st.session_state.boq.append({"name": "", "quantity": 1.0, "hours": 1.0, "material": 0.0})
        st.rerun()

    items_for_calc = []
    for i in range(len(st.session_state.boq)):
        with st.expander(f"Item {i+1}", expanded=True):
            top_left, top_right = st.columns([5, 1])
            st.session_state.boq[i]["name"] = top_left.text_input("Description", value=st.session_state.boq[i].get("name", ""), key=f"name_{i}")

            row1, row2, row3 = st.columns(3)
            st.session_state.boq[i]["quantity"] = row1.number_input("Qty", value=float(st.session_state.boq[i].get("quantity", 1.0)), min_value=0.1, step=0.5, key=f"qty_{i}")
            st.session_state.boq[i]["hours"] = row2.number_input("Hours per unit", value=float(st.session_state.boq[i].get("hours", 1.0)), min_value=0.1, step=0.25, key=f"hours_{i}")
            st.session_state.boq[i]["material"] = row3.number_input("Material per unit (ex VAT)", value=float(st.session_state.boq[i].get("material", 0.0)), min_value=0.0, step=100.0, key=f"mat_{i}")

            if top_right.button("🗑", key=f"del_{i}"):
                del st.session_state.boq[i]
                st.rerun()

            items_for_calc.append({
                "name": st.session_state.boq[i]["name"] or f"Item {i+1}",
                "labour_hours": st.session_state.boq[i]["quantity"] * st.session_state.boq[i]["hours"],
                "material_cost": st.session_state.boq[i]["quantity"] * st.session_state.boq[i]["material"],
                "quantity": st.session_state.boq[i]["quantity"]
            })

    if items_for_calc:
        quote = calculate_quote(
            boq_items=items_for_calc,
            config=cfg,
            monthly_cost=float(monthly_cost),
            billable_hours=float(billable_hours),
            profit_multiplier=float(profit_mult),
            callout_fee=float(callout_fee) if use_callout else 0.0,
            after_hours=bool(after_hours),
            enforce_min_margin=enforce_min_margin
        )

        if "error" in quote:
            st.error(quote["error"])
            st.stop()

        # INTERNAL REFERENCE ONLY
        target = quote["final_price"]
        rec = round(target * 0.92, 2)
        walk = round(target * 0.80, 2)

        with st.expander("🔒 Internal Pricing Reference (do NOT show client)", expanded=False):
            st.metric("Target", f"R {target:,.2f}")
            st.metric("Recommended", f"R {rec:,.2f}", delta="-8%")
            st.metric("Walk-away", f"R {walk:,.2f}", delta="-20%", delta_color="inverse")

        # ─── USER SELECTS FINAL PRICE ───
        st.subheader("Select Final Quote Price (ex VAT)")

        choice = st.radio(
            "Price level",
            ["Recommended", "Target", "Walk-away", "Custom"],
            horizontal=True,
            index=0
        )

        discount_pct = st.slider("Discount (%)", 0.0, 25.0, 0.0, 0.5, format="%.1f%%")

        if choice == "Recommended":
            base = rec
        elif choice == "Target":
            base = target
        elif choice == "Walk-away":
            base = walk
        else:
            base = st.number_input("Custom price (ex VAT)", value=float(rec), step=100.0, format="%.2f")

        final_ex = round(base * (1 - discount_pct / 100), 2)
        final_inc = round(final_ex * 1.15, 2)

        st.divider()
        st.metric("**FINAL QUOTE ex VAT**", f"R {final_ex:,.2f}")
        st.metric("**incl. 15% VAT**", f"R {final_inc:,.2f}")
        if discount_pct > 0:
            st.caption(f"Discount: {discount_pct:.1f}% applied")

        col1, col2 = st.columns(2)

        if col1.button("💾 Save Quote", type="primary", use_container_width=True):
            conn = get_db()
            conn.execute("""
                INSERT INTO quotes (phone, industry, item_count, final_ex_vat, final_inc_vat, discount_pct, boq_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_phone, industry, len(items_for_calc), final_ex, final_inc, discount_pct,
                  json.dumps(st.session_state.boq), datetime.now().isoformat()))
            conn.commit()
            st.success("Quote saved successfully")

        pdf_bytes = make_pdf(quote, user_name, cfg, final_ex, final_inc, discount_pct)
        col2.download_button(
            "📄 Download PDF",
            data=pdf_bytes,
            file_name=f"ARLO_Quote_{industry}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    else:
        st.info("Add at least one item to generate a quote.")

# ──────────────────────────────────────────────
# MY QUOTES PAGE
# ──────────────────────────────────────────────
else:
    st.header("My Saved Quotes")
    conn = get_db()
    if is_admin:
        rows = conn.execute("SELECT * FROM quotes ORDER BY created_at DESC LIMIT 50").fetchall()
    else:
        rows = conn.execute("SELECT * FROM quotes WHERE phone = ? ORDER BY created_at DESC LIMIT 30", (user_phone,)).fetchall()

    if not rows:
        st.info("No quotes saved yet.")
    else:
        for row in rows:
            created = row["created_at"][:16].replace("T", " ")
            with st.expander(f"{row['industry']} • R {row['final_inc_vat']:,.2f} • {created}"):
                st.write(f"**Final ex VAT:** R {row['final_ex_vat']:,.2f}")
                st.write(f"**Final incl. VAT:** R {row['final_inc_vat']:,.2f}")
                st.write(f"**Discount used:** {row['discount_pct']:.1f}%")
                st.write(f"**Items:** {row['item_count']}")
                if is_admin:
                    st.caption(f"User: {row['phone']}")