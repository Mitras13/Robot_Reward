"""
elan-padash-zaribvosoli-5040-18mehr-resend/requirements.py

One-off resend of the elan-padash-zaribvosoli-5040-18mehr announcement (user
2026-10-10) to the 8 کارشناسان its 10:46 batch failed for: 6 whose panel
name differs from their messenger name (messenger names checked by hand by
the user) + 2 the sender's cache wrongly held as deactivated. A separate
folder because the running app already imported the original reward's
modules and would not pick up edits to them without a restart.
No download - the recipient list is fixed in builder.py.
"""


def get_requirements(slot_jdt):
    return []
