# V4.20 — FEFO recommended star and expandable movement documents

- Restores a prominent ★ marker on the *earliest usable expiry date* within the outgoing shipment expiry dropdown. Keeps the exact stored lot ID for the issued stock; equal-expiry lots remain disambiguated by the existing secondary batch selector. FEFO validation and shortage alerts remain unchanged.
- Adds an accessible expansion button (with a line count) beside each movement in the recent activity, movements register, and pending-paperwork list. Default view shows one line plus count, and expanding shows **all receipt/issue lines** with numbered positions, item, batch, manufacturing date, expiry, quantity, unit price, plus movement document metadata.
- This update is display-only: no database schema migration or existing-stock reset. V9 remains in use.
- After deploying to the existing GitHub/Railway service, verify `/api/health` reports `release: 4.20.0`, and check the new controls on your live data.
