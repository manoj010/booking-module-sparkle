from datetime import timedelta
from uuid import uuid4
import pytz

from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape


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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._prepare_sparkle_appointment_values(vals)
        products = super().create(vals_list)
        products._sync_sparkle_appointment_types()
        return products

    def write(self, vals):
        if vals.get("sparkle_bookable_service"):
            for product in self:
                write_vals = dict(vals)
                if not product.sparkle_appointment_type_id and not write_vals.get("sparkle_appointment_type_id"):
                    self._prepare_sparkle_appointment_values(write_vals, product)
                super(ProductTemplate, product).write(write_vals)
            self._sync_sparkle_appointment_types()
            return True
        result = super().write(vals)
        if {
            "name",
            "description_sale",
            "sparkle_duration_minutes",
            "sparkle_appointment_type_id",
            "sparkle_bookable_service",
        } & set(vals):
            self._sync_sparkle_appointment_types()
        return result

    @api.constrains("sparkle_bookable_service", "sparkle_duration_minutes")
    def _check_sparkle_bookable_service_setup(self):
        for product in self:
            if not product.sparkle_bookable_service:
                continue
            if product.sparkle_duration_minutes <= 0:
                raise ValidationError("Bookable Sparkle services must have a positive duration.")

    def init(self):
        self._configure_sparkle_company_currency()
        self._sync_sparkle_appointment_types()

    def _configure_sparkle_company_currency(self):
        aud = self.env.ref("base.AUD", raise_if_not_found=False)
        company = self.env.ref("base.main_company", raise_if_not_found=False)
        if aud and company:
            aud.sudo().write({"active": True, "symbol": "A$"})
            company.sudo().write({"currency_id": aud.id})

    def action_open_sparkle_appointment_type(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Appointment Type",
            "res_model": "appointment.type",
            "view_mode": "form",
            "res_id": self.sparkle_appointment_type_id.id,
            "target": "current",
        }

    def action_sync_sparkle_appointment_type(self):
        self._sync_sparkle_appointment_types()
        return True

    @api.model
    def _prepare_sparkle_appointment_values(self, vals, product=False):
        if not vals.get("sparkle_bookable_service"):
            return
        if vals.get("sparkle_appointment_type_id"):
            return
        admin_user = self.env.ref("base.user_admin", raise_if_not_found=False) or self.env.user
        name = vals.get("name") or (product and product.name) or "Sparkle Service"
        duration_minutes = vals.get("sparkle_duration_minutes") or (product and product.sparkle_duration_minutes) or 60
        appointment_type = self.env["appointment.type"].sudo().create(
            {
                "name": name,
                "appointment_duration": duration_minutes / 60,
                "appointment_tz": admin_user.tz or "UTC",
                "assign_method": "time_auto_assign",
                "schedule_based_on": "users",
                "staff_user_ids": [Command.set(admin_user.ids)],
                "min_schedule_hours": 1.0,
                "max_schedule_days": 30,
                "message_intro": vals.get("description_sale") or (product and product.description_sale) or "",
                "slot_ids": [
                    Command.create(
                        {
                            "weekday": weekday,
                            "start_hour": 9.0,
                            "end_hour": 18.0,
                        }
                    )
                    for weekday in ["1", "2", "3", "4", "5", "6"]
                ],
            }
        )
        vals["sparkle_appointment_type_id"] = appointment_type.id

    def _sync_sparkle_appointment_types(self):
        products = self.filtered("sparkle_bookable_service")
        if not products:
            products = self.env["product.template"].sudo().search(
                [
                    ("sparkle_bookable_service", "=", True),
                    ("type", "=", "service"),
                    ("sale_ok", "=", True),
                ]
            )
        admin_user = self.env.ref("base.user_admin", raise_if_not_found=False) or self.env.user
        for product in products:
            if product.type != "service" or not product.sale_ok:
                continue
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
    _inherit = ["mail.thread", "mail.activity.mixin"]
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
    crm_lead_id = fields.Many2one("crm.lead", string="CRM Lead", readonly=True)
    access_token = fields.Char(default=lambda self: uuid4().hex, readonly=True, copy=False)
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
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    notes = fields.Text()

    @api.model
    def get_website_service_payloads(self):
        products = self.env["product.template"].sudo().search(
            [
                ("sparkle_bookable_service", "=", True),
                ("type", "=", "service"),
                ("sale_ok", "=", True),
                ("active", "=", True),
            ],
            order="sequence, id",
        )
        return [
            {
                "id": product.product_variant_id.id,
                "name": product.name,
                "description": product.description_sale or "",
                "category_id": product.categ_id.id,
                "category_name": product.categ_id.name,
                "icon_class": product.sparkle_icon_class or "fa fa-sparkles",
                "image_url": "/web/image/product.template/%s/image_512" % product.id if product.image_1920 else "",
                "price": product.list_price,
                "duration_minutes": product.sparkle_duration_minutes,
                "appointment_type_id": product.sparkle_appointment_type_id.id,
            }
            for product in products
            if product.product_variant_id and product.sparkle_appointment_type_id
        ]

    @api.model
    def get_website_availability(self, product_id, booking_date, timezone=False):
        product = self.env["product.product"].sudo().browse(product_id)
        if not self._is_bookable_product(product):
            return []
        return self._get_appointment_slot_payloads(product, booking_date, timezone)

    @api.model
    def create_from_website(self, values):
        product_id = self._safe_int(values.get("service_id"))
        customer_name = (values.get("customer_name") or "").strip()
        email = (values.get("email") or "").strip()
        phone = (values.get("phone") or "").strip()
        booking_date = self._parse_booking_date(values.get("date"))
        slot_key = (values.get("slot_key") or "").strip()
        timezone = values.get("timezone")

        if not product_id or not customer_name or not email or not phone:
            raise ValidationError("Please complete service, name, email, and phone.")
        if not booking_date or not slot_key:
            raise ValidationError("Please choose an appointment date and time.")

        product = self.env["product.product"].sudo().browse(product_id)
        if not self._is_bookable_product(product):
            raise ValidationError("Please choose an available service.")

        selected_slot = self._find_appointment_slot(product, booking_date, slot_key, timezone)
        if not selected_slot:
            raise ValidationError("Please choose an available time.")

        partner = self._find_or_create_partner(customer_name, email, phone)
        appointment_type = product.product_tmpl_id.sparkle_appointment_type_id.sudo()
        booking_start = selected_slot["start_utc"]
        booking_stop = booking_start + timedelta(hours=selected_slot["duration"])

        booking = self.sudo().create(
            {
                "product_id": product.id,
                "partner_id": partner.id,
                "appointment_type_id": appointment_type.id,
                "customer_name": customer_name,
                "email": email,
                "phone": phone,
                "location": (values.get("location") or "").strip(),
                "message": (values.get("message") or "").strip(),
                "booking_start": booking_start,
                "booking_stop": booking_stop,
                "price": product.product_tmpl_id.list_price,
                "payment_status": "pending",
                "state": "confirmed",
            }
        )
        event = booking._create_appointment_event(selected_slot)
        booking.calendar_event_id = event.id
        booking.action_create_or_update_crm_lead()
        return booking

    @api.model
    def _safe_int(self, value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @api.model
    def _parse_booking_date(self, value):
        try:
            return fields.Date.to_date(value)
        except Exception:
            return False

    @api.model
    def _is_bookable_product(self, product):
        return (
            product.exists()
            and product.active
            and product.type == "service"
            and product.sale_ok
            and product.product_tmpl_id.sparkle_bookable_service
            and product.product_tmpl_id.sparkle_appointment_type_id
        )

    @api.model
    def _get_appointment_slot_payloads(self, product, booking_date, timezone=False):
        appointment_type = product.product_tmpl_id.sparkle_appointment_type_id.sudo()
        timezone = self._get_appointment_timezone(appointment_type, timezone)
        months = appointment_type._get_appointment_slots(timezone, asked_capacity=1)
        payloads = []
        for month in months:
            for week in month.get("weeks", []):
                for day in week:
                    if day.get("day") != booking_date:
                        continue
                    for slot in day.get("slots", []):
                        start_local = fields.Datetime.from_string(slot["datetime"])
                        duration = float(slot["slot_duration"])
                        start_utc = self._local_to_utc(start_local, timezone)
                        staff_user = self.env["res.users"].sudo().browse(slot.get("staff_user_id"))
                        if not appointment_type._check_appointment_is_valid_slot(
                            staff_user,
                            self.env["appointment.resource"].sudo(),
                            1,
                            timezone,
                            pytz.utc.localize(start_utc),
                            duration,
                        ):
                            continue
                        staff_user_id = slot.get("staff_user_id") or 0
                        start_key = fields.Datetime.to_string(start_utc)
                        payloads.append(
                            {
                                "key": "%s|%s|%s" % (start_key, duration, staff_user_id),
                                "label": start_local.strftime("%I:%M %p"),
                                "start": start_key,
                                "duration": duration,
                                "staff_user_id": staff_user_id,
                                "timezone": timezone,
                                "start_local": start_local,
                                "start_utc": start_utc,
                            }
                        )
        return payloads

    @api.model
    def _find_appointment_slot(self, product, booking_date, slot_key, timezone=False):
        return next(
            (
                slot
                for slot in self._get_appointment_slot_payloads(product, booking_date, timezone)
                if slot["key"] == slot_key
            ),
            False,
        )

    @api.model
    def _get_appointment_timezone(self, appointment_type, timezone=False):
        return timezone or appointment_type.appointment_tz or "UTC"

    @api.model
    def _local_to_utc(self, value, timezone):
        tz = pytz.timezone(timezone)
        localized = tz.localize(value)
        return localized.astimezone(pytz.utc).replace(tzinfo=None)

    @api.model
    def _find_or_create_partner(self, name, email, phone):
        Partner = self.env["res.partner"].sudo()
        partner = Partner.search([("email", "=", email)], limit=1)
        if partner:
            partner.write({"phone": phone or partner.phone})
            return partner
        return Partner.create({"name": name, "email": email, "phone": phone})

    def _create_appointment_event(self, slot):
        self.ensure_one()
        appointment_type = self.appointment_type_id.sudo()
        staff_user = self.env["res.users"].sudo().browse(slot.get("staff_user_id"))
        event_values = appointment_type._prepare_calendar_event_values(
            1,
            [],
            slot["duration"],
            self.env["appointment.invite"].sudo(),
            self.env["res.partner"].sudo(),
            self.customer_name,
            self.partner_id,
            staff_user,
            self.booking_start,
            self.booking_stop,
        )
        description_parts = [
            "<p><strong>Service:</strong> %s</p>" % html_escape(self.product_id.display_name),
            "<p><strong>Customer:</strong> %s</p>" % html_escape(self.customer_name),
            "<p><strong>Email:</strong> %s</p>" % html_escape(self.email),
            "<p><strong>Phone:</strong> %s</p>" % html_escape(self.phone or ""),
        ]
        if self.message:
            description_parts.append("<p><strong>Message:</strong><br/>%s</p>" % html_escape(self.message))

        event_values.update(
            {
                "description": "".join(description_parts),
                "location": self.location or event_values.get("location"),
                "res_model_id": self.env["ir.model"].sudo()._get_id("sparkle.booking"),
                "res_id": self.id,
                "show_as": "busy",
            }
        )
        return self.env["calendar.event"].sudo().create(event_values)

    def get_pdf_download_url(self):
        self.ensure_one()
        return "/sparkle-booking/%s/pdf?access_token=%s" % (self.id, self.access_token)


    def action_confirm_booking(self):
        for booking in self:
            booking.write({"state": "confirmed"})
            if booking.calendar_event_id:
                booking.calendar_event_id.with_context(active_test=False).write(
                    {
                        "active": True,
                        "appointment_status": "booked",
                    }
                )
            if booking.crm_lead_id:
                booking.crm_lead_id.write({"active": True})
            booking.message_post(body="Booking confirmed.")
        return True

    def action_cancel_booking(self):
        lost_reason = self._get_cancelled_booking_lost_reason()
        for booking in self:
            booking.write({"state": "cancelled"})
            if booking.calendar_event_id:
                booking.calendar_event_id.with_context(active_test=False).write(
                    {
                        "active": False,
                        "appointment_status": "cancelled",
                    }
                )
            if booking.crm_lead_id:
                booking.crm_lead_id.write(
                    {
                        "active": False,
                        "probability": 0,
                        "lost_reason_id": lost_reason.id,
                    }
                )
            booking.message_post(body="Booking cancelled. Linked appointment was cancelled and CRM opportunity was marked lost.")
        return True

    def action_mark_done(self):
        for booking in self:
            booking.write({"state": "done"})
            if booking.calendar_event_id:
                booking.calendar_event_id.with_context(active_test=False).write(
                    {
                        "active": True,
                        "appointment_status": "attended",
                    }
                )
            if booking.crm_lead_id:
                booking.crm_lead_id.write({"active": True, "probability": 100})
            booking.message_post(body="Booking marked done.")
        return True

    def action_create_or_update_crm_lead(self):
        action = False
        for booking in self:
            values = booking._prepare_crm_lead_values()
            if booking.crm_lead_id:
                booking.crm_lead_id.write(values)
                booking.message_post(body="CRM opportunity updated: %s" % html_escape(booking.crm_lead_id.display_name))
            else:
                lead = self.env["crm.lead"].sudo().create(values)
                booking.crm_lead_id = lead.id
                booking.message_post(body="CRM opportunity created: %s" % html_escape(lead.display_name))
            action = booking.action_open_crm_lead()
        return action or True

    def action_open_appointment_event(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Appointment",
            "res_model": "calendar.event",
            "view_mode": "form",
            "res_id": self.calendar_event_id.id,
            "target": "current",
            "context": {"active_test": False},
        }

    def action_open_crm_lead(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "CRM Opportunity",
            "res_model": "crm.lead",
            "view_mode": "form",
            "res_id": self.crm_lead_id.id,
            "target": "current",
            "context": {"active_test": False},
        }

    def action_open_customer(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Customer",
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.partner_id.id,
            "target": "current",
        }

    def _prepare_crm_lead_values(self):
        self.ensure_one()
        source = self._get_website_booking_source()
        description_parts = [
            "<p><strong>Service:</strong> %s</p>" % html_escape(self.product_id.display_name),
            "<p><strong>Appointment:</strong> %s</p>" % html_escape(fields.Datetime.to_string(self.booking_start)),
            "<p><strong>Customer:</strong> %s</p>" % html_escape(self.customer_name),
            "<p><strong>Email:</strong> %s</p>" % html_escape(self.email),
            "<p><strong>Phone:</strong> %s</p>" % html_escape(self.phone or ""),
        ]
        if self.location:
            description_parts.append("<p><strong>Location:</strong> %s</p>" % html_escape(self.location))
        if self.message:
            description_parts.append("<p><strong>Message:</strong><br/>%s</p>" % html_escape(self.message))
        return {
            "name": "Website Booking: %s" % self.product_id.display_name,
            "type": "opportunity",
            "partner_id": self.partner_id.id,
            "contact_name": self.customer_name,
            "email_from": self.email,
            "phone": self.phone,
            "expected_revenue": self.price,
            "source_id": source.id,
            "description": "".join(description_parts),
            "active": True,
            "lost_reason_id": False,
        }

    def _get_website_booking_source(self):
        source = self.env.ref("sparkle_booking_flow.sparkle_booking_source_website", raise_if_not_found=False)
        if source:
            return source.sudo()
        return self.env["utm.source"].sudo().search([("name", "=", "Website Booking")], limit=1) or self.env[
            "utm.source"
        ].sudo().create({"name": "Website Booking"})

    def _get_cancelled_booking_lost_reason(self):
        LostReason = self.env["crm.lost.reason"].sudo()
        return LostReason.search([("name", "=", "Cancelled Booking")], limit=1) or LostReason.create(
            {"name": "Cancelled Booking"}
        )
