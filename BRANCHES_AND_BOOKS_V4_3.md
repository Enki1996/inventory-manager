# Official warehouse branch books — V4.3

## Medical Supplies — المستلزمات الطبية (7)

1. سجل النبيذة - قسم الصيدلة
2. سجل النبيذة - مشتريات
3. سجل الضمادات - قسم الصيدلة
4. سجل الضمادات - مشتريات
5. سجل الجراحية - قسم الصيدلة
6. سجل الجراحية - مشتريات
7. سجل الجناح الخاص - مشتريات

## Medication — الأدوية (10)

1. مختبرية جناح عام - قسم الصيدلة
2. مختبرية جناح خاص - مشتريات
3. سجل المشتريات عامة - مشتريات
4. سجل الامبولات - قسم الصيدلة
5. سجل الحبوب - قسم الصيدلة
6. سجل الحياتية - قسم الصيدلة
7. سجل المساحيق و المحاليل و المراهم - قسم الصيدلة
8. سجل المخدرات - قسم الصيدلة
9. سجل المؤثرات العقلية - قسم الصيدلة
10. سجل الشرابات - قسم الصيدلة

## Surgical Instruments — الأدوات الجراحية (2)

1. سجل الفاتورة
2. سجل العامة

Names match the supplied hospital register wording exactly. Confirm any official spelling changes before deploying a renamed book—previously stored names are not automatically rewritten.

## Application rules

- **Each item has one branch and one book** selected from that branch's official list.
- A staff account is assigned to one branch. The item's branch selector is disabled for that employee. Administrators can choose any branch, but cannot use a book from a different branch.
- Add and Edit Item use a regular dropdown, not a free-text entry or datalist.
- Changing the item branch clears an incompatible book selection.
- The warehouse inventory screen filters by Branch and Book, with the book filter showing the branch's official choices and retaining discoverability of legacy unapproved names.
- Backend `POST /api/items` and `PATCH /api/items/{id}` enforce the branch/book combination, protecting against developer-tools or direct API bypasses.
- Books classify **items**; the branch-level employee permission model continues to apply to receiving, distribution, returns and corrections. Books are not yet separate permission scopes.
- For V4.2 data with arbitrary register text, old names remain stored to preserve accounting history. Editing an item with such a name requires choosing one of the official choices. Existing balances, batches and movement history remain unchanged.
- The official catalog is in `book_catalog.py` and is exposed to authenticated clients by `GET /api/books`. To change the approved register list later, update the catalog and redeploy through GitHub/Railway; no database reset is needed.
