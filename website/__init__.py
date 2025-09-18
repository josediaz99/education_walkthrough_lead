from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path

db = SQLAlchemy()
DB_NAME = "database.db"

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'chat is ts tuff or naw'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    db.init_app(app)

    from .views import views

    app.register_blueprint(views, url_prefix='/')

    create_database(app)

    return app

def create_database(app):
    if not path.exists('website/' + DB_NAME):
        with app.app_context():
            db.create_all()
            
            from .models import Tag
            pd_tag = Tag(name="Professional Development")
            ib_tag = Tag(name="IB")
            ap_tag = Tag(name="AP")
            avid_tag = Tag(name="AVID")

            db.session.add_all([pd_tag, ib_tag, ap_tag, avid_tag])

            db.session.commit()

        print('Created Database!')