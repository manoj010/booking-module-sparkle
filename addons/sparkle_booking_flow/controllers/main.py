from datetime import datetime, timedelta

import pytz

from odoo import fields
from odoo import http
from odoo.http import request
from odoo.tools import html_escape


class SparkleBookingController(http.Controller):
    @http.route("/sparkle-booking/services", type="json", auth="public", website=True)
    def services(self):
        products = request.env["product.template"].sudo().search(
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
                "icon_class": product.sparkle_icon_class or "fa fa-sparkles",
                "price": product.list_price,
                "duration_minutes": product.sparkle_duration_minutes,
                "appointment_type_id": product.sparkle_appointment_type_id.id,
            }
            for product in products
            if product.product_variant_id and product.sparkle_appointment_type_id
        ]

    @http.route("/sparkle-booking/availability", type="json", auth="public", website=True)
    def availability(self, **payload):
        product_id = self._safe_int(payload.get("service_id"))
        booking_date = self._parse_booking_date(payload.get("date"))
        if not product_id or not booking_date:
            return {"success": False, "message": "Please choose a service and date.", "slots": []}

        today = fields.Date.context_today(request.env.user)
        if booking_date < today:
            return {"success": False, "message": "Please choose today or a future date.", "slots": []}

        product = request.env["product.product"].sudo().browse(product_id)
        if not self._is_bookable_product(product):
            return {"success": False, "message": "Please choose an available service.", "slots": []}

        slots = self._get_appointment_slot_payloads(product, booking_date)
        return {"success": True, "slots": [slot["label"] for slot in slots]}

    @http.route(
        "/sparkle-booking/create",
        type="json",
        auth="public",
        website=True,
        csrf=False,
    )
    def create_booking(self, **payload):
        product_id = self._safe_int(payload.get("service_id"))
        customer_name = (payload.get("customer_name") or "").strip()
        email = (payload.get("email") or "").strip()
        phone = (payload.get("phone") or "").strip()

        if not product_id or not customer_name or not email or not phone:
            return {
                "success": False,
                "message": "Please complete service, name, email, and phone.",
            }

        product = request.env["product.product"].sudo().browse(product_id)
        if not self._is_bookable_product(product):
            return {"success": False, "message": "Please choose an available service."}

        booking_start_local = self._parse_booking_start(payload.get("booking_start"))
        if not booking_start_local:
            return {"success": False, "message": "Please choose a future appointment time."}

        available_slots = self._get_appointment_slot_payloads(product, booking_start_local.date())
        selected_slot = next(
            (slot for slot in available_slots if slot["label"] == booking_start_local.strftime("%I:%M %p")),
            None,
        )
        if not selected_slot:
            return {"success": False, "message": "Please choose an available time."}

        partner = self._find_or_create_partner(customer_name, email, phone)
        appointment_type = product.product_tmpl_id.sparkle_appointment_type_id.sudo()
        duration_hours = selected_slot["duration"]
        booking_start = selected_slot["start_utc"]
        booking_stop = booking_start + timedelta(hours=duration_hours)
        price = product.product_tmpl_id.list_price

        Booking = request.env["sparkle.booking"].sudo()
        booking = Booking.create(
            {
                "product_id": product.id,
                "partner_id": partner.id,
                "appointment_type_id": appointment_type.id,
                "customer_name": customer_name,
                "email": email,
                "phone": phone,
                "location": (payload.get("location") or "").strip(),
                "message": (payload.get("message") or "").strip(),
                "booking_start": booking_start,
                "booking_stop": booking_stop,
                "price": price,
                "payment_status": "pending",
                "state": "confirmed",
            }
        )
        event = self._create_appointment_event(booking, product, partner, selected_slot)
        booking.calendar_event_id = event.id
        return {
            "success": True,
            "booking_id": booking.id,
            "calendar_event_id": event.id,
            "message": "Your cleaning service has been successfully booked.",
        }

    def _safe_int(self, value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _is_bookable_product(self, product):
        return (
            product.exists()
            and product.active
            and product.type == "service"
            and product.sale_ok
            and product.product_tmpl_id.sparkle_bookable_service
            and product.product_tmpl_id.sparkle_appointment_type_id
        )

    def _parse_booking_date(self, value):
        try:
            return fields.Date.to_date(value)
        except Exception:
            return False

    def _parse_booking_start(self, value):
        if not value:
            return False
        normalized = value.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            try:
                return fields.Datetime.to_datetime(value)
            except Exception:
                return False

    def _get_appointment_slot_payloads(self, product, booking_date):
        appointment_type = product.product_tmpl_id.sparkle_appointment_type_id.sudo()
        timezone = self._get_appointment_timezone(appointment_type)
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
                        if not appointment_type._check_appointment_is_valid_slot(
                            request.env["res.users"].sudo().browse(slot.get("staff_user_id")),
                            request.env["appointment.resource"].sudo(),
                            1,
                            timezone,
                            pytz.utc.localize(start_utc),
                            duration,
                        ):
                            continue
                        payloads.append(
                            {
                                "label": start_local.strftime("%I:%M %p"),
                                "start_local": start_local,
                                "start_utc": start_utc,
                                "duration": duration,
                                "staff_user_id": slot.get("staff_user_id"),
                            }
                        )
        return payloads

    def _get_appointment_timezone(self, appointment_type):
        return request.session.get("timezone") or appointment_type.appointment_tz or "UTC"

    def _local_to_utc(self, value, timezone):
        tz = pytz.timezone(timezone)
        localized = tz.localize(value)
        return localized.astimezone(pytz.utc).replace(tzinfo=None)

    def _find_or_create_partner(self, name, email, phone):
        Partner = request.env["res.partner"].sudo()
        partner = Partner.search([("email", "=", email)], limit=1)
        if partner:
            partner.write({"phone": phone or partner.phone})
            return partner
        return Partner.create({"name": name, "email": email, "phone": phone})

    def _create_appointment_event(self, booking, product, partner, slot):
        appointment_type = booking.appointment_type_id.sudo()
        staff_user = request.env["res.users"].sudo().browse(slot.get("staff_user_id"))
        event_values = appointment_type._prepare_calendar_event_values(
            1,
            [],
            slot["duration"],
            request.env["appointment.invite"].sudo(),
            request.env["res.partner"].sudo(),
            booking.customer_name,
            partner,
            staff_user,
            booking.booking_start,
            booking.booking_stop,
        )
        description_parts = [
            "<p><strong>Service:</strong> %s</p>" % html_escape(product.display_name),
            "<p><strong>Customer:</strong> %s</p>" % html_escape(booking.customer_name),
            "<p><strong>Email:</strong> %s</p>" % html_escape(booking.email),
            "<p><strong>Phone:</strong> %s</p>" % html_escape(booking.phone or ""),
        ]
        if booking.message:
            description_parts.append("<p><strong>Message:</strong><br/>%s</p>" % html_escape(booking.message))

        event_values.update(
            {
                "description": "".join(description_parts),
                "location": booking.location or event_values.get("location"),
                "res_model_id": request.env["ir.model"].sudo()._get_id("sparkle.booking"),
                "res_id": booking.id,
                "show_as": "busy",
            }
        )
        return request.env["calendar.event"].sudo().create(event_values)
