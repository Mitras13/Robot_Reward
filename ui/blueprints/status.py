"""Live status page - GET "/" (the dashboard) and GET "/api/state"."""

from flask import Blueprint, current_app, jsonify, render_template

from ui.services.dashboard_state import build_state_payload

bp = Blueprint("status", __name__)


@bp.route("/")
def index():
    return render_template("status.html", active="/")


@bp.route("/api/state")
def api_state():
    state = current_app.config["APP_STATE"]
    lock = current_app.config["APP_LOCK"]
    return jsonify(build_state_payload(state, lock))
