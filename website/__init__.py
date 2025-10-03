from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_migrate import init as mig_init, migrate as mig_migrate, upgrade as mig_upgrade
from sqlalchemy import text
import os

db = SQLAlchemy()
migrate = Migrate()
DB_NAME = "database.db"

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'set_to_own_secret_key' # change to personal secret key
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app,db)

    from .views import views
    app.register_blueprint(views, url_prefix='/')


    return app

def bootstrap_db(app):
    """Initialize migrations, create/update schema, and seed default data."""

    with app.app_context():
        # 1) Ensure migrations/ exists; if not, create initial migration
        if not os.path.isdir("migrations"):
            mig_init(directory="migrations")
            mig_migrate(message="initial", directory="migrations")

        # 2) Always upgrade to head (creates tables on first run)
        mig_upgrade(revision="head", directory="migrations")

        # 3) Seed tags idempotently
        from .models import Tag, db as _db
        names = ["Professional Development", "IB", "AP", "AVID"]
        existing = {t.name for t in Tag.query.filter(Tag.name.in_(names)).all()}
        for n in names:
            if n not in existing:
                _db.session.add(Tag(name=n))
        _db.session.commit()
