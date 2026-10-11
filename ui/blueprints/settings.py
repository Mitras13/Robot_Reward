"""
Settings page - GET "/settings" (the page shell), GET "/api/rewards"
(current rows + sender version, for the page to render), POST
"/api/rewards" and POST "/api/sender_version" (writes, after the page's
own confirm modal). See ui/services/config_store.py for validation and
atomic-write details - this module stays a thin HTTP layer.
"""

from flask import Blueprint, jsonify, render_template, request

from ui.services import config_store
from ui.services.config_store import ConfigValidationError

bp = Blueprint("settings", __name__)


@bp.route("/settings")
def settings_page():
    return render_template("settings.html", active="/settings")


@bp.route("/api/rewards", methods=["GET"])
def api_rewards_get():
    return jsonify({
        "rows": config_store.list_rewards_with_meta(),
        "sender_version": config_store.current_sender_version(),
    })


@bp.route("/api/rewards", methods=["POST"])
def api_rewards_post():
    body = request.get_json(silent=True) or {}
    rows = body.get("rows")
    if not isinstance(rows, list):
        return jsonify({"error": "بدنه‌ی درخواست نامعتبر است (rows لازم است)"}), 400
    try:
        config_store.save_rewards(rows)
    except ConfigValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})


@bp.route("/api/sender_version", methods=["POST"])
def api_sender_version_post():
    body = request.get_json(silent=True) or {}
    try:
        config_store.save_sender_version(body.get("version"))
    except ConfigValidationError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})
