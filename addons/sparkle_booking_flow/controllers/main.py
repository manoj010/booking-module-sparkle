from odoo import fields, http
from odoo.exceptions import ValidationError
from odoo.http import request


class SparkleBookingController(http.Controller):
    @http.route("/sparkle-booking/services", type="json", auth="public", website=True)
    def services(self):
        return request.env["sparkle.booking"].sudo().get_website_service_payloads()

    @http.route("/sparkle-booking/availability", type="json", auth="public", website=True)
    def availability(self, **payload):
        product_id = self._safe_int(payload.get("service_id"))
        booking_date = self._parse_booking_date(payload.get("date"))
        if not product_id or not booking_date:
            return {"success": False, "message": "Please choose a service and date.", "slots": []}

        today = fields.Date.context_today(request.env.user)
        if booking_date < today:
            return {"success": False, "message": "Please choose today or a future date.", "slots": []}

        slots = request.env["sparkle.booking"].sudo().get_website_availability(
            product_id,
            booking_date,
            request.session.get("timezone"),
        )
        return {"success": True, "slots": self._public_slot_payloads(slots)}

    @http.route(
        "/sparkle-booking/create",
        type="json",
        auth="public",
        website=True,
        csrf=False,
    )
    def create_booking(self, **payload):
        values = dict(payload)
        values["timezone"] = request.session.get("timezone")
        try:
            booking = request.env["sparkle.booking"].sudo().create_from_website(values)
        except ValidationError as error:
            return {"success": False, "message": error.args[0] if error.args else str(error)}

        return {
            "success": True,
            "booking_id": booking.id,
            "calendar_event_id": booking.calendar_event_id.id,
            "crm_lead_id": booking.crm_lead_id.id,
            "download_url": booking.get_download_url(),
            "message": "Your cleaning service has been successfully booked.",
        }

    @http.route("/sparkle-booking/<int:booking_id>/calendar.ics", type="http", auth="public", website=True)
    def download_calendar(self, booking_id, access_token=None, **kwargs):
        booking = request.env["sparkle.booking"].sudo().browse(booking_id).exists()
        if not booking or booking.access_token != access_token:
            return request.not_found()

        content = self._booking_ics(booking)
        return request.make_response(
            content,
            [
                ("Content-Type", "text/calendar; charset=utf-8"),
                ("Content-Disposition", 'attachment; filename="sparkle-booking-%s.ics"' % booking.id),
            ],
        )

    def _safe_int(self, value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _parse_booking_date(self, value):
        try:
            return fields.Date.to_date(value)
        except Exception:
            return False

    def _public_slot_payloads(self, slots):
        return [
            {
                "key": slot["key"],
                "label": slot["label"],
                "start": slot["start"],
                "duration": slot["duration"],
                "staff_user_id": slot["staff_user_id"],
            }
            for slot in slots
        ]

    def _booking_ics(self, booking):
        def fmt(value):
            return fields.Datetime.to_datetime(value).strftime("%Y%m%dT%H%M%SZ")

        def esc(value):
            return (value or "").replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")

        summary = "Sparkle Booking: %s" % booking.product_id.display_name
        description = "Customer: %s\\nEmail: %s\\nPhone: %s" % (
            booking.customer_name,
            booking.email,
            booking.phone or "",
        )
        if booking.message:
            description += "\\nMessage: %s" % booking.message
        return "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Sparkle Booking//EN",
                "BEGIN:VEVENT",
                "UID:sparkle-booking-%s@%s" % (booking.id, request.httprequest.host or "localhost"),
                "DTSTAMP:%s" % fields.Datetime.to_datetime(fields.Datetime.now()).strftime("%Y%m%dT%H%M%SZ"),
                "DTSTART:%s" % fmt(booking.booking_start),
                "DTEND:%s" % fmt(booking.booking_stop),
                "SUMMARY:%s" % esc(summary),
                "DESCRIPTION:%s" % esc(description),
                "LOCATION:%s" % esc(booking.location),
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )
