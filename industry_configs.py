# industry_configs.py
# Industry-specific settings for ARLO quoting engine
# All monetary values in ZAR (South African Rand)

INDUSTRY_CONFIGS = {
    "Electrician": {
        "label": "Electrician / Electrical Services",
        "uses_callout": True,
        "callout_includes_first_hour": True,           # Call-out fee already covers first labour hour
        "after_hours_multiplier": 1.5,
        "material_markup_tiers": [                     # (cost_from, cost_to, markup_multiplier)
            (0, 200, 1.0),                             # 100% markup on very small purchases
            (200, 1000, 0.6),
            (1000, 5000, 0.4),
            (5000, float("inf"), 0.275)
        ],
        "default_monthly_cost": 20000.0,
        "default_billable_hours": 100.0,
        "default_profit_multiplier": 1.6,
        "default_callout_fee": 650.0,
        "default_min_invoice": 650.0,
        "min_margin": 0.30,                            # 30% minimum enforced margin (if enabled)
        "risk_buffer": 0.05                            # 5% risk loading on labour cost
    },

    "Plumbing": {
        "label": "Plumbing / Bathroom Specialist",
        "uses_callout": True,
        "callout_includes_first_hour": False,
        "after_hours_multiplier": 1.4,
        "material_markup_tiers": [
            (0, 300, 0.9),
            (300, 1500, 0.5),
            (1500, float("inf"), 0.3)
        ],
        "default_monthly_cost": 18000.0,
        "default_billable_hours": 110.0,
        "default_profit_multiplier": 1.55,
        "default_callout_fee": 600.0,
        "default_min_invoice": 700.0,
        "min_margin": 0.30,
        "risk_buffer": 0.05
    },

    "Landscaping": {
        "label": "Landscaping / Garden Services",
        "uses_callout": False,                         # Usually no call-out for landscaping
        "callout_includes_first_hour": False,
        "after_hours_multiplier": 1.2,
        "material_markup_tiers": [
            (0, 500, 0.8),
            (500, 2000, 0.5),
            (2000, float("inf"), 0.3)
        ],
        "default_monthly_cost": 15000.0,
        "default_billable_hours": 120.0,
        "default_profit_multiplier": 1.7,
        "default_callout_fee": 0.0,
        "default_min_invoice": 800.0,
        "min_margin": 0.30,
        "risk_buffer": 0.05
    },

    "Construction": {
        "label": "Construction / Building Contractor",
        "uses_callout": True,
        "callout_includes_first_hour": False,
        "after_hours_multiplier": 1.75,
        "material_markup_tiers": [
            (0, 1000, 0.6),
            (1000, 5000, 0.4),
            (5000, float("inf"), 0.25)
        ],
        "default_monthly_cost": 45000.0,
        "default_billable_hours": 85.0,
        "default_profit_multiplier": 1.7,
        "default_callout_fee": 850.0,
        "default_min_invoice": 1500.0,
        "min_margin": 0.35,                            # Higher min margin due to project scale/risk
        "risk_buffer": 0.10                            # Higher risk buffer for construction
    }
}