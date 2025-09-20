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
            new_tags = []
            if(db.session.query(Tag.id).filter_by(name="Professional Development").first() is None):
                pd_tag = Tag(name="Professional Development")
                new_tags.append(pd_tag)
            
            if(db.session.query(Tag.id).filter_by(name="IB").first() is None):
                ib_tag = Tag(name="IB")
                new_tags.append(ib_tag)
            
            if(db.session.query(Tag.id).filter_by(name="AP").first() is None):
                ap_tag = Tag(name="AP")
                new_tags.append(ap_tag)

            if(db.session.query(Tag.id).filter_by(name="AVID").first() is None):
                avid_tag = Tag(name="AVID")
                new_tags.append(avid_tag)

            db.session.add_all(new_tags)

            db.session.commit()

        print('Created Database!')