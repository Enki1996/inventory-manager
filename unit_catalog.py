"""Approved warehouse inventory units by branch; stored as these Arabic values."""
UNITS_BY_BRANCH = {
    'medication': ('حب', 'كبسول', 'بطل', 'امبول', 'فيال', 'انبوب', 'تحاميل', 'قطرات'),
    'medical_supplies': ('قطعة', 'كيس', 'بطل', 'باكة', 'رولة', 'باكيت', 'درزن'),
    'surgical_instruments': ('قطعة',),
}

def valid_unit(branch: str, unit: str) -> bool:
    return unit in UNITS_BY_BRANCH.get(branch, ())
