# Sparkle Booking Flow

This Odoo 18 addon provides a custom full-screen Sparkle website booking flow while using Odoo standard apps for the business objects behind it.

The frontend keeps the Sparkle styling. The backend uses Odoo Products, Appointment, Calendar, and CRM.

## What It Adds

- A website overlay opened by any button or link with the class `js_open_sparkle_booking`.
- Website service choices powered by Odoo service products.
- Optional service images and product category filtering in the Sparkle UI.
- Odoo Appointment Types linked to bookable service products.
- Stable Appointment slot payloads so the frontend submits an exact slot key, not only a time label.
- Confirmed `sparkle.booking` records for website submissions.
- Linked Odoo Appointment `calendar.event` records.
- Linked Odoo CRM opportunities with source `Website Booking`.
- Tokenized booking PDF download from the success screen.
- Backend workflow buttons for confirming, cancelling, completing, and opening linked records.

## User Flow

1. A visitor clicks a website button with `.js_open_sparkle_booking`.
2. The Sparkle overlay opens over the current website page.
3. The visitor filters/selects an Odoo service product.
4. The visitor selects a date and a stable Odoo Appointment slot.
5. The visitor enters contact details.
6. The visitor confirms the current pay-later/mock payment step.
7. `sparkle.booking.create_from_website()` creates or reuses the customer partner.
8. Odoo creates the `sparkle.booking` record.
9. Odoo creates the linked Appointment `calendar.event`.
10. Odoo creates or updates the linked CRM opportunity.
11. The success screen confirms the booking and offers a booking PDF download.
12. Admin staff follow up with the customer by phone or email from the booking/CRM lead.

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
- `Sparkle Icon Class`: Font Awesome fallback shown when no product image is uploaded.
- `Sparkle Duration`: duration used when syncing Appointment Types.
- `Sparkle Appointment Type`: Odoo Appointment Type used for availability and booked events.

The service product form also includes image upload, category, and buttons to generate/sync or open the linked Appointment Type.

## Booking Creation

The public controller is intentionally thin:

- `/sparkle-booking/services` asks `sparkle.booking` for product payloads.
- `/sparkle-booking/availability` asks `sparkle.booking` for Appointment-backed slot payloads.
- `/sparkle-booking/create` calls `sparkle.booking.create_from_website()`.

The model owns the reusable creation logic:

- partner lookup/creation
- slot re-validation
- booking creation
- appointment event creation
- CRM lead creation/update
- PDF download URL creation

This keeps the website route small and makes the booking behavior reusable from backend actions, tests, imports, or future APIs.

## Appointment Slots

The website calendar remains custom-styled, but available times come from Odoo Appointment.

The availability route returns stable slot objects:

```json
{
  "success": true,
  "slots": [
    {
      "key": "2026-06-17 03:15:00|1.5|2",
      "label": "09:00 AM",
      "start": "2026-06-17 03:15:00",
      "duration": 1.5,
      "staff_user_id": 2
    }
  ]
}
```

The Sparkle UI displays `label`, but submits `key`. The backend rechecks that exact slot before creating any booking.

## Booking Records

Submitted bookings are stored under:

```text
Sparkle Booking -> Bookings
```

New website bookings are created as:

```text
state = confirmed
payment_status = pending
```

Backend actions:

- `Confirm`: marks the booking confirmed and the appointment booked.
- `Cancel`: cancels the booking, archives the appointment event, and marks the CRM opportunity lost.
- `Mark Done`: marks the booking done, sets the appointment status to checked-in/attended, and sets CRM probability to 100.
- `Create/Update CRM Lead`: creates or refreshes the linked opportunity.
- Smart buttons open the customer, appointment event, and CRM lead.

## Appointment Events

Every confirmed website booking creates a linked Appointment `calendar.event`.

The event:

- belongs to the service product's Appointment Type
- has Odoo Appointment status `booked`
- uses Appointment attendees and reminders
- includes the customer as the booker/attendee
- links back to the `sparkle.booking` record

## CRM

Every new website booking creates a CRM opportunity:

- source: `Website Booking`
- customer/contact fields from the booking
- expected revenue from the product price
- description with service, appointment, location, and message

Bookings and CRM opportunities can be opened from each other through backend links/actions.

## Customer Follow-Up

This version does not create customer portal accounts, customer passwords, or confirmation emails.

The customer only enters details in the Sparkle booking form. The success screen includes a tokenized PDF download for that booking. Admin staff then use:

- `Sparkle Booking -> Bookings`
- `Sparkle Booking -> CRM Leads`
- the linked customer contact

to call or email the customer manually.

The public PDF route is:

```text
/sparkle-booking/<booking_id>/pdf?access_token=<token>
```

The token is generated per booking and returned only after successful booking creation.

## Docker External Addons

This project mounts required external addons from:

```text
./external_addons -> /mnt/external-addons
```

Required external addons:

- `appointment`
- `appointment_crm`
- `website_appointment_crm`
- `gantt_view`

The Odoo config includes `/mnt/external-addons` in `addons_path`.

## Updating After Code Changes

For this Docker setup, update the module with:

```powershell
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d sparkle-cleaning-db -u sparkle_booking_flow --db_host=db --db_user=odoo --db_password=odoo --stop-after-init
```

Then restart Odoo so Python controllers are refreshed:

```powershell
docker compose restart odoo
```
