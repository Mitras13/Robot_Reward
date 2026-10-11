"""
elan-padash-zaribvosoli-5040-18mehr-resend/builder.py

Fixed recipient list (messenger names) - see requirements.py.
"""

RECIPIENTS = [
    "ثمره حقگو RW",
    "فاطمه موسوی RW",
    "نرگس مهتری علیائی RW",
    "حانیه اللهیاری سوره RW",
    "رومینا آبشاری VP",
    "مریم راجزی همدانی RW",
    "فاطمه اسکندری RW",
    "دنیا صادقی حسن وند RW",
]


def build(raw_paths, slot_jdt):
    return {"slot_jdt": slot_jdt, "recipients": RECIPIENTS}
