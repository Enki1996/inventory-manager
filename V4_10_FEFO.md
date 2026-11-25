# V4.10 — FEFO stock issue recommendations

FEFO means **First Expiring, First Out** (الأقرب انتهاءً يُصرف أولاً), regardless of arrival date.

- Stock remains in distinct lots: each item can have many batch numbers, expiry dates and receipt prices. Outgoing price snapshots do not change receipt prices.
- Outgoing lot choices are sorted by earliest usable expiry, and the earliest lot is preselected when a product is chosen.
- A yellow notice calls attention to the earliest lot when it expires within 60 days; expired lots remain excluded from outgoing issue.
- Choosing a later-expiring lot with any usable earlier stock left raises an inline FEFO warning. A shortcut selects the recommended earlier batch.
- Submitting a non-FEFO issue requires a text explanation, which is preserved in movement notes and the audit record. This check is performed by the server inside the stock-update transaction and considers all rows in one outgoing document together.
- A later lot may be used without an override once the same outgoing document allocates all available quantity in earlier-expiring lots. Lots with the same expiry can be used in either order.
- Lots with no expiry are placed last; verify their dates manually. No other stock, item, user, or permission structures are replaced. Database schema remains V7.

### Railway deployment

Update the code in the existing private GitHub repository and redeploy the same service. Keep the existing `/data` persistent volume attached and export a backup before any update. Verify `/api/health` reports `release: 4.10.0` and `version: 7`.

### Verification

Run `python test_v410_fefo.py`; it covers multiple lots, receipts, non-FEFO rejection, documented override, and correct allocation across multiple shipment lines.
