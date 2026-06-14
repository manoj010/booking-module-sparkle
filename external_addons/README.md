# External Addons

This folder is mounted into the Odoo container as `/mnt/external-addons`.

The Sparkle booking flow depends on these Odoo addons being present here:

- `appointment`
- `appointment_crm`
- `website_appointment_crm`
- `gantt_view`

These modules are intentionally ignored by Git because they come from a separate
Odoo Enterprise/custom addons source. Keep only this README committed.

For this local project, copy or sync the required addon folders into this
directory before starting Docker.

