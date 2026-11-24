"""Official warehouse register names, organized by branch.

Edit this one mapping when the hospital officially adds/renames a register.
Values are stored as the exact Arabic register titles for accounting traceability.
"""

BOOKS_BY_BRANCH = {
    'medical_supplies': (
        'سجل النبيذة - قسم الصيدلة',
        'سجل النبيذة - مشتريات',
        'سجل الضمادات - قسم الصيدلة',
        'سجل الضمادات - مشتريات',
        'سجل الجراحية - قسم الصيدلة',
        'سجل الجراحية - مشتريات',
        'سجل الجناح الخاص - مشتريات',
    ),
    'medication': (
        'مختبرية جناح عام - قسم الصيدلة',
        'مختبرية جناح خاص - مشتريات',
        'سجل المشتريات عامة - مشتريات',
        'سجل الامبولات - قسم الصيدلة',
        'سجل الحبوب - قسم الصيدلة',
        'سجل الحياتية - قسم الصيدلة',
        'سجل المغذيات - قسم الصيدلة',
        'سجل المساحيق و المحاليل و المراهم - قسم الصيدلة',
        'سجل المخدرات - قسم الصيدلة',
        'سجل المؤثرات العقلية - قسم الصيدلة',
        'سجل الشرابات - قسم الصيدلة',
    ),
    'surgical_instruments': (
        'سجل الفاتورة',
        'سجل العامة',
    ),
}

assert len({value for books in BOOKS_BY_BRANCH.values() for value in books}) == sum(map(len, BOOKS_BY_BRANCH.values()))


def valid_book(branch: str, title: str) -> bool:
    return title in BOOKS_BY_BRANCH.get(branch, ())
