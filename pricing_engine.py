# ============================================
# ARLO PRICING ENGINE (FULL PRODUCTION VERSION)
# ============================================

def apply_tiered_markup(cost: float, tiers: list) -> float:
    for low, high, markup in tiers:
        if low <= cost < high:
            return cost * (1 + markup)
    return cost * 1.25  # fallback


def calculate_quote(
    boq_items: list,
    config: dict,
    monthly_cost: float,
    billable_hours: float,
    profit_multiplier: float,
    callout_fee: float = 0,
    after_hours: bool = False,
    vat_rate: float = 0.15,
    enforce_min_margin: bool = False
):
    """
    FULL ENGINE – exactly as you provided
    """
    # ─── VALIDATION ─────────────────────────────
    if billable_hours <= 0:
        return {"error": "Billable hours cannot be zero"}

    if not boq_items:
        return {"error": "No BOQ items provided"}

    # ─── RISK BUFFER ────────────────────────────
    risk_buffer = config.get("risk_buffer", 0.05)
    cost_per_hour = (monthly_cost / billable_hours) * (1 + risk_buffer)

    # ─── LABOUR RATE ────────────────────────────
    base_labour_rate = cost_per_hour * profit_multiplier
    labour_rate = (
        base_labour_rate * config.get("after_hours_multiplier", 1.0)
        if after_hours
        else base_labour_rate
    )

    # ─── INITIALISE TOTALS ──────────────────────
    total_labour_sell = 0.0
    total_material_sell = 0.0
    total_material_cost = 0.0
    total_labour_hours = 0.0
    boq_snapshot = []

    # ─── PROCESS BOQ ITEMS ──────────────────────
    for item in boq_items:
        hours = float(item.get("labour_hours", 0))
        mat_cost = float(item.get("material_cost", 0))

        labour_sell = hours * labour_rate
        material_sell = apply_tiered_markup(
            mat_cost,
            config["material_markup_tiers"]
        )

        total_labour_sell += labour_sell
        total_material_sell += material_sell
        total_material_cost += mat_cost
        total_labour_hours += hours

        boq_snapshot.append({
            "name": item.get("name", "Unnamed Item"),
            "labour_hours": round(hours, 2),
            "labour_sell": round(labour_sell, 2),
            "material_cost": round(mat_cost, 2),
            "material_sell": round(material_sell, 2),
            "line_total": round(labour_sell + material_sell, 2)
        })

    # ─── CALLOUT LOGIC ──────────────────────────
    effective_callout = callout_fee if config.get("uses_callout", False) else 0

    if config.get("callout_includes_first_hour", False) and total_labour_hours >= 1:
        total_labour_sell -= labour_rate
        total_labour_sell = max(total_labour_sell, 0)

    # ─── TOTALS ─────────────────────────────────
    total_direct = total_labour_sell + total_material_sell
    final_price = total_direct + effective_callout

    # ─── MIN INVOICE ────────────────────────────
    min_invoice = config.get("default_min_invoice", 0)
    if final_price < min_invoice:
        final_price = min_invoice

    # ─── TRUE COST ──────────────────────────────
    base_cost_per_hour = monthly_cost / billable_hours
    estimated_labour_cost = base_cost_per_hour * total_labour_hours
    true_cost = total_material_cost + estimated_labour_cost + effective_callout

    # ─── MARGIN ─────────────────────────────────
    margin = (final_price - true_cost) / final_price if final_price > 0 else 0

    # ─── MIN MARGIN ENFORCEMENT ─────────────────
    if enforce_min_margin:
        min_margin = config.get("min_margin", 0.3)
        if margin < min_margin:
            final_price = true_cost / (1 - min_margin)
            margin = (final_price - true_cost) / final_price

    # ─── VAT ────────────────────────────────────
    final_price = round(final_price, 2)
    final_price_incl_vat = round(final_price * (1 + vat_rate), 2)

    return {
        "total_labour": round(total_labour_sell, 2),
        "total_material_sell": round(total_material_sell, 2),
        "total_material_cost": round(total_material_cost, 2),
        "callout_fee": round(effective_callout, 2),

        "final_price": final_price,                    # ← this becomes our TARGET
        "final_price_incl_vat": final_price_incl_vat,

        "margin_percent": round(margin * 100, 1),

        "boq_snapshot": boq_snapshot,

        "applied_labour_rate": round(labour_rate, 2),
        "total_labour_hours": round(total_labour_hours, 2),
    }