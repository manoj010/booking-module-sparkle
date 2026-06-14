{
    "name": "Sparkle Booking Flow",
    "summary": "Full-screen website booking flow for cleaning services",
    "version": "18.0.1.0.0",
    "category": "Website",
    "author": "Custom",
    "license": "LGPL-3",
    "depends": [
        "appointment",
        "calendar",
        "product",
        "web",
        "website",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/service_products.xml",
        "views/sparkle_booking_views.xml",
        "views/website_templates.xml",
    ],
    "post_init_hook": "post_init_hook",
    "assets": {
        "web.assets_frontend": [
            "sparkle_booking_flow/static/src/booking_flow/booking_flow.scss",
            "sparkle_booking_flow/static/src/booking_flow/booking_flow.xml",
            "sparkle_booking_flow/static/src/booking_flow/booking_flow.js",
        ],
    },
    "application": True,
    "installable": True,
}
