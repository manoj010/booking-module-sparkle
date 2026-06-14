from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request


class SparkleBookingPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "sparkle_booking_count" in counters:
            values["sparkle_booking_count"] = request.env["sparkle.booking"].sudo().search_count(
                self._get_sparkle_booking_domain()
            )
        return values

    @http.route(["/my/sparkle-bookings"], type="http", auth="user", website=True)
    def portal_my_sparkle_bookings(self, **kwargs):
        bookings = request.env["sparkle.booking"].sudo().search(
            self._get_sparkle_booking_domain(),
            order="booking_start desc, id desc",
        )
        return request.render(
            "sparkle_booking_flow.portal_my_sparkle_bookings",
            {
                "bookings": bookings,
                "page_name": "sparkle_bookings",
            },
        )

    @http.route(["/my/sparkle-bookings/<int:booking_id>"], type="http", auth="user", website=True)
    def portal_my_sparkle_booking(self, booking_id, **kwargs):
        booking = request.env["sparkle.booking"].sudo().search(
            [("id", "=", booking_id)] + self._get_sparkle_booking_domain(),
            limit=1,
        )
        if not booking:
            return request.not_found()
        return request.render(
            "sparkle_booking_flow.portal_my_sparkle_booking",
            {
                "booking": booking,
                "page_name": "sparkle_bookings",
            },
        )

    def _get_sparkle_booking_domain(self):
        partner = request.env.user.partner_id.commercial_partner_id
        return [("partner_id", "child_of", partner.id)]
