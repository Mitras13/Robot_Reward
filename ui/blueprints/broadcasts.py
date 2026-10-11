"""
Display-only page for bulk-message ("پیام انبوه") history - shows, per
reward, every one-off broadcast sent to that reward's whole recipient list
(see ui/services/broadcast_store.py for why this doesn't trigger a send
itself yet). Kept separate from settings.py's per-slot rewards table since
this is a different kind of thing (a manual, whole-list announcement, not
a scheduled per-slot report).
"""

from flask import Blueprint, jsonify, render_template

from ui.services import broadcast_store

bp = Blueprint("broadcasts", __name__)

# فعلاً فقط همین دو پاداش - همونایی که کاربر صریحاً خواسته بود جدا نمایش
# داده بشن (۲۰۲۶-۰۹-۲۰). لیست ثابت عمدیه، نه پویا از رو rewards.csv - چون
# این صفحه مخصوص پیام انبوهِ این دو پاداشه، نه یه فیچر عمومی برای هر پاداشی.
TRACKED_REWARDS = [
    {"id": "padash-karshenasan-5040", "label": "شرکت 5040 (طرح ویژه پاداش رتبه‌بندی کارشناسان)"},
    {"id": "padash-tamdid-karshenasan-hamkadeh", "label": "شرکت همکده (طرح ویژه تمدید کارشناسان)"},
    # user 2026-10-07: show the Glorsion launch announcement here too
    {"id": "elan-padash-gloroshen-5040-15mehr", "label": "شرکت 5040 (اعلام پاداش ویژه ضد لک گلورشن)"},
    # user 2026-10-10: show the collection-ratio contest announcement here too
    {"id": "elan-padash-zaribvosoli-5040-18mehr", "label": "شرکت 5040 (اعلام رقابت افزایش ضریب وصولی کارشناسان)"},
]


@bp.route("/broadcasts")
def broadcasts_page():
    sections = [
        {"id": r["id"], "label": r["label"], "history": broadcast_store.list_broadcasts(r["id"])}
        for r in TRACKED_REWARDS
    ]
    return render_template("broadcasts.html", active="/broadcasts", sections=sections)


@bp.route("/api/broadcasts")
def api_broadcasts_get():
    return jsonify({
        r["id"]: broadcast_store.list_broadcasts(r["id"])
        for r in TRACKED_REWARDS
    })
