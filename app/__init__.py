from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="../static")
    app.config.from_object("config.Config")
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "main.login"

    # register blueprints or import routes
    from .routes import main as main_bp
    app.register_blueprint(main_bp)

    return app
