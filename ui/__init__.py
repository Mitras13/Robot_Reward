"""
ui - the Flask admin panel.

Replaces the earlier stdlib http.server dashboard (1405/06/23-26) now that
the panel needs more than one page and needs to actually WRITE config
(config/rewards.csv, config/sender_version.txt), not just display it -
user decision 1405/06/27 (real, standard, scalable app shape: blueprints +
templates/ + static/, not one embedded HTML string per page).

create_app() is called once, from main.py, which then calls
app.run() itself (blocking - same role the old webserver.run() played).
state/lock are main.py's shared status dict + its lock; stored on
app.config so any route can read them without a global import cycle.
"""

from flask import Flask

from ui.blueprints.broadcasts import bp as broadcasts_bp
from ui.blueprints.settings import bp as settings_bp
from ui.blueprints.status import bp as status_bp

NAV_ITEMS = [("/", "وضعیت زنده"), ("/settings", "تنظیمات"), ("/broadcasts", "پیام انبوه")]


def create_app(state, lock):
    app = Flask(__name__)
    app.config["APP_STATE"] = state
    app.config["APP_LOCK"] = lock
    app.jinja_env.globals["nav_items"] = NAV_ITEMS

    app.register_blueprint(status_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(broadcasts_bp)

    return app
