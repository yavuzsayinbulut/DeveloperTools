"""ui-effects — generic CSS/JS animation pack for any web project.

Use the Flask integration via ``ui_effects.flask_blueprint`` or copy/link the
static directory into another framework.
"""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"

__all__ = ["PACKAGE_DIR", "STATIC_DIR", "create_blueprint"]


def create_blueprint(name: str = "ui_effects", url_prefix: str = "/ui-effects"):
    """Build a Flask blueprint that serves the bundled css/js under url_prefix."""
    from flask import Blueprint  # imported lazily to avoid hard dependency

    return Blueprint(
        name,
        __name__,
        static_folder=str(STATIC_DIR),
        static_url_path=url_prefix,
    )
