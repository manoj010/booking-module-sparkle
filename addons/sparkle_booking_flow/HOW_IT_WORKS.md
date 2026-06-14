# Sparkle Booking Flow

This Odoo 18 addon adds a full-screen website booking flow for cleaning services. Service choices are Odoo service products, and available times are computed by Odoo Appointment.

## What It Adds

- A website overlay booking flow opened by any button or link with the class `js_open_sparkle_booking`.
- Website service choices powered by Odoo `product.template` / `product.product`.
- Odoo Appointment Types linked to each bookable service product.
- A backend app menu named `Sparkle Booking`.
- A backend booking model named `sparkle.booking`.
- Sparkle-specific product fields for website visibility, icon class, duration, and Appointment Type.
- Public JSON routes for loading bookable services, loading Appointment-backed slots, and creating bookings.
- Appointment calendar events created from confirmed bookings.
- A mock payment step that saves bookings with `payment_status = pending`.

## User Flow

1. A visitor clicks a website button with `.js_open_sparkle_booking`.
2. The overlay slides up over the current page.
3. The visitor selects a bookable Odoo service product.
4. The visitor selects an available Odoo Appointment slot using the custom Sparkle calendar UI.
5. The visitor enters contact details.
6. The visitor confirms the mock payment step.
7. Odoo creates or reuses a `res.partner`.
8. Odoo creates a `sparkle.booking` record.
9. Odoo creates a linked Appointment `calendar.event`.
10. The success screen appears.
11. The visitor clicks `Finish` and is redirected to `/`.

## Service Products

Go to:

```text
Sparkle Booking -> Service Products
```

Products appear in the booking flow when:

- `Product Type` is `Service`
- `Sales` is enabled
- `Bookable in Sparkle Flow` is enabled
- `Sparkle Appointment Type` is set
- the product is active

Sparkle-specific product fields:

- `Bookable in Sparkle Flow`: controls website visibility.
- `Sparkle Icon Class`: Font Awesome class shown in the booking flow.
- `Sparkle Duration`: default duration used when syncing Appointment Types.
- `Sparkle Appointment Type`: Odoo Appointment Type used for availability and booked events.

The module syncs missing Appointment Types during module updates, so existing service products become Appointment-backed without reinstalling the module.

## Booking Records

Submitted bookings are stored under:

```text
Sparkle Booking -> Bookings
```

The booking stores the selected service product, customer contact, Appointment Type, linked calendar event, booking start/end, product price, payment status, state, and notes.

New website bookings are created as:

```text
state = confirmed
payment_status = pending
```

## Appointment Slots

The website calendar remains custom-styled, but its available time buttons come from Odoo Appointment.

For each selected service/date, `/sparkle-booking/availability` calls the linked `appointment.type` slot engine and returns labels for the Sparkle UI:

```json
{
  "success": true,
  "slots": ["09:00 AM", "10:30 AM", "02:00 PM", "03:30 PM"]
}
```

When the visitor submits, the selected time is validated again against the Appointment Type before any booking is created.

## Appointment Events

Every confirmed website booking creates a linked Appointment `calendar.event`.

The event:

- belongs to the service product's Appointment Type
- has Odoo Appointment status
- uses Appointment attendees and reminders
- includes the customer as the booker/attendee
- links back to the `sparkle.booking` record

## Docker Appointment Addons

This setup mounts only the Appointment pieces needed by this repo:

```text
../odoo-18/custom_addons/enterprise/appointment -> /mnt/sparkle-appointment-addons/appointment
../odoo-18/custom_addons/custom/gantt_view -> /mnt/sparkle-appointment-addons/gantt_view
```

The Odoo config includes `/mnt/sparkle-appointment-addons` in `addons_path`.

## Updating After Code Changes

For this Docker setup, update the module with:

```powershell
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d sparkle-cleaning-db -u sparkle_booking_flow --db_host=db --db_user=odoo --db_password=odoo --stop-after-init
```

Then restart Odoo or refresh assets as needed.
