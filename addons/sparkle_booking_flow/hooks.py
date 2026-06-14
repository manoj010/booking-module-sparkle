DEFAULT_SERVICE_PRODUCTS = [
    {
        "name": "Carpet & Upholstery Cleaning",
        "description_sale": "Professional steam and dry cleaning.",
        "sparkle_icon_class": "fa fa-object-group",
        "list_price": 45.0,
        "sparkle_duration_minutes": 90,
        "sequence": 10,
    },
    {
        "name": "Water Damage Restoration",
        "description_sale": "Professional steam and dry cleaning.",
        "sparkle_icon_class": "fa fa-tint",
        "list_price": 85.0,
        "sparkle_duration_minutes": 120,
        "sequence": 20,
    },
    {
        "name": "End Of Lease Cleaning",
        "description_sale": "Professional steam and dry cleaning.",
        "sparkle_icon_class": "fa fa-paint-brush",
        "list_price": 120.0,
        "sparkle_duration_minutes": 180,
        "sequence": 30,
    },
    {
        "name": "Commercial Premises Cleaning",
        "description_sale": "Professional steam and dry cleaning.",
        "sparkle_icon_class": "fa fa-building-o",
        "list_price": 95.0,
        "sparkle_duration_minutes": 150,
        "sequence": 40,
    },
    {
        "name": "Mould Removal & Remediation",
        "description_sale": "Professional steam and dry cleaning.",
        "sparkle_icon_class": "fa fa-fire-extinguisher",
        "list_price": 75.0,
        "sparkle_duration_minutes": 120,
        "sequence": 50,
    },
    {
        "name": "Builders & Post-Reno Cleaning",
        "description_sale": "Professional steam and dry cleaning.",
        "sparkle_icon_class": "fa fa-truck",
        "list_price": 110.0,
        "sparkle_duration_minutes": 180,
        "sequence": 60,
    },
]


def post_init_hook(env):
    ProductTemplate = env["product.template"].sudo()
    if ProductTemplate.search_count([("sparkle_bookable_service", "=", True)]):
        return

    products = []
    for values in DEFAULT_SERVICE_PRODUCTS:
        products.append(
            {
                **values,
                "type": "service",
                "sale_ok": True,
                "purchase_ok": False,
                "sparkle_bookable_service": True,
            }
        )
    ProductTemplate.create(products)
