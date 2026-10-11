"""
padash-5040-mehr-report/requirements.py

Dedicated, SEPARATE reward whose only job is delivering the end-of-campaign
management-report image for padash-karshenasan-5040 on a schedule the main
campaign reward can't do by itself (data frozen at campaign end, but sent
hours later, after a human confirms it first) - per the user's explicit
request 2026-09-22:
  - 00:00 on 1 مهر (right after the campaign's last day, 31 شهریور, ends):
    freeze/compute the report using padash-karshenasan-5040's own
    requirements.py/builder.py (imported directly, not duplicated) anchored
    to the exact campaign-end slot (1405/06/31 23:59) - so late data entry
    after midnight never changes "بازه‌ی پاداش" numbers.
  - 08:30 on 1 مهر: send the frozen image to میترا سرخوش ONLY, for review.

Sending to گروه «گزارشات پاداش» is intentionally NOT automated here - this
project has no mechanism to detect a human's chat confirmation. That send
happens manually (by the user asking) once میترا سرخوش approves.

No downloads needed directly - build() drives the sibling reward's own
pipeline internally.
"""


def get_requirements(slot_jdt):
    return []
