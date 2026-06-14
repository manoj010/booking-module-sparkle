from odoo import Command, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    sparkle_bookable_service = fields.Boolean(
        string="Bookable in Sparkle Flow",
        help="Show this service product in the Sparkle website booking flow.",
    )
    sparkle_icon_class = fields.Char(
        string="Sparkle Icon Class",
        default="fa fa-sparkles",
        help="Font Awesome class used in the Sparkle booking flow.",
    )
    sparkle_duration_minutes = fields.Integer(
        string="Sparkle Duration",
        default=60,
        help="Default calendar event duration when this service is booked.",
    )
    sparkle_appointment_type_id = fields.Many2one(
        "appointment.type",
        string="Sparkle Appointment Type",
        help="Odoo Appointment Type used to compute available booking slots for this service.",
    )

    def init(self):
        self._sync_sparkle_appointment_types()

    def _sync_sparkle_appointment_types(self):
        products = self.env["product.template"].sudo().search(
            [
                ("sparkle_bookable_service", "=", True),
                ("type", "=", "service"),
                ("sale_ok", "=", True),
            ]
        )
        admin_user = self.env.ref("base.user_admin", raise_if_not_found=False) or self.env.user
        for product in products:
            duration_hours = (product.sparkle_duration_minutes or 60) / 60
            appointment_type = product.sparkle_appointment_type_id
            if not appointment_type:
                appointment_type = self.env["appointment.type"].sudo().create(
                    {
                        "name": product.name,
                        "appointment_duration": duration_hours,
                        "appointment_tz": admin_user.tz or "UTC",
                        "assign_method": "time_auto_assign",
                        "schedule_based_on": "users",
                        "staff_user_ids": [Command.set(admin_user.ids)],
                        "min_schedule_hours": 1.0,
                        "max_schedule_days": 30,
                        "message_intro": product.description_sale or "",
                    }
                )
                product.sparkle_appointment_type_id = appointment_type.id
            else:
                appointment_type.write(
                    {
                        "name": product.name,
                        "appointment_duration": duration_hours,
                        "message_intro": product.description_sale or "",
                    }
                )

            if not appointment_type.slot_ids:
                appointment_type.write(
                    {
                        "slot_ids": [
                            Command.create(
                                {
                                    "weekday": weekday,
                                    "start_hour": 9.0,
                                    "end_hour": 18.0,
                                }
                            )
                            for weekday in ["1", "2", "3", "4", "5", "6"]
                        ]
                    }
                )


class SparkleBooking(models.Model):
    _name = "sparkle.booking"
    _description = "Sparkle Booking"
    _order = "create_date desc"

    product_id = fields.Many2one(
        "product.product",
        string="Service Product",
        required=True,
        domain="[('type', '=', 'service'), ('sale_ok', '=', True)]",
    )
    partner_id = fields.Many2one("res.partner", string="Customer")
    calendar_event_id = fields.Many2one("calendar.event", string="Calendar Event", readonly=True)
    appointment_type_id = fields.Many2one("appointment.type", string="Appointment Type", readonly=True)
    customer_name = fields.Char(required=True)
    email = fields.Char(required=True)
    phone = fields.Char()
    location = fields.Char()
    message = fields.Text()
    booking_start = fields.Datetime(string="Booking Start")
    booking_stop = fields.Datetime(string="Booking End")
    price = fields.Float()
    payment_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("failed", "Failed"),
        ],
        default="pending",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    notes = fields.Text()
