# Warehouse branches and book/register categories — V4.2

## Fixed branch vs. flexible book category

Every *new* inventory item belongs to exactly one branch:

| Internal value | English | Arabic |
|---|---|---|
| `medication` | Medication | الأدوية |
| `medical_supplies` | Medical Supplies | المستلزمات الطبية |
| `surgical_instruments` | Surgical Instruments | الأدوات الجراحية |

The **Book / Register Category** field is **separate** from the branch. It is plain text stored in the existing `items.category` field; examples include `سجل الحياتية`, `سجل المواد الجراحية`, or another register name the warehouse uses. Users can type any valid register title. Existing register names appear as suggestions, and the inventory table can search/filter by book or branch. This deliberately does not create a complex hierarchy or force specific register names.

Item names, generic names, manufacturers, catalog manufacture/expiry reference dates, alternate names, quantities and batch-specific expiry are preserved from V4.1.

## Staff access

- **Administrator:** may work in all three branches, assign employee branches, and manage backups. Initial `enki` account remains the administrator.
- **Manager:** one assigned branch, can create/edit items and perform authorized stock movements and corrections **only within that branch**.
- **Operator:** one assigned branch; cannot edit catalog items, but can receive, issue or return stock **only within that branch**.
- **Viewer:** one assigned branch as staff metadata, read-only access.

Account creation requires a valid branch for all non-admin roles. When the employee is allowed to create/edit an item, their branch is shown in a disabled selector (submitted through a hidden value). The backend **independently** enforces the branch on every item creation, edit, receipt, issue, return, and adjustment; editing the browser's data cannot bypass permissions.

Changing an employee's role or assigned branch revokes their active sessions immediately. All attempts to mix stock from multiple branches in one shipment are rejected atomically — nothing is subtracted/added if any line is unauthorized.

The shared **Departments** list is not branch inventory; it remains a hospital-wide set of shipment destinations. Read access to catalogs and reports remains hospital-wide in this test version. Branch restrictions specifically govern editing/movement rights.

## Upgrading V4.1 without losing stock

V4.2 adds `items.branch` and `users.branch` columns and increments the backup schema to 3. Existing records are **not deleted**, moved, or assigned to a guessed branch. On an old database:

- Existing items are labelled **Unassigned** until the administrator edits them and selects one of the three branches. Their stock, batches, requisition references and movement history are retained.
- Existing non-admin accounts are also **Unassigned**. They can still log in and read data but cannot modify stock until an administrator assigns them a branch.
- The admin account `enki` keeps full cross-branch control.
- An admin may assign an unclassified historical item to a branch, but may **not** reassign an already classified item to another branch after stock movements have occurred (protects historical branch attribution).

Before deploying, download a V4.1 database backup and keep it off the server. Update your **existing GitHub repository code**; retain the same Railway persistent `/data` volume. V4.2 can restore V3/V4, V4.1, and V4.2 portable backups; older schemas are migrated on restore.

## Example

- **Scientific item:** Ceftriaxone 1 g
- **Warehouse branch:** Medication / الأدوية
- **Book / Register Category:** سجل الحياتية
- **Supplier / manufacturer, batch and expiry:** recorded in the existing fields; each received batch retains its own accurate expiry date.

## Testing and security

Run `python test_flow.py`, `python test_item_details.py`, `python test_branches.py`, and `python test_upgrade_from_v41.py` with dependencies installed. They use disposable databases and do not alter live stock.

This is still a small-team test application, **not** a production-approved hospital inventory system. Public Railway deployment requires a unique strong admin password, persistent storage, HTTPS, and cautious handling of backups. Application exports contain password hashes and are **not encrypted**. Use dummy records until a full security and data-protection review is completed.
