# V4.18 Changes

- Account menu redesigned with matching profile and logout actions, removed Return Home.
- Password change moved to My Account; audit tab admin-only.
- Administrators can view employee-entered profile information, with no password hashes exposed.
- Notification button opens summary dialog for expired/expiring lots, no-stock items and missing emergency paperwork.
- Outgoing stock selection is expiry-first. The exact batch ID remains the transaction reference and is shown after selection; when multiple lots share a date an additional explicit selector appears. Quantity warnings appear before submission and server-side stock validation remains.
- Schema remains V9; no database reset or restore is required.
- Restore unchanged; apply by replacing code in the existing GitHub repository and redeploying the same Railway service with its current `/data` volume.
