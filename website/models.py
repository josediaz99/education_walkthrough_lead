from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

document_tag = db.Table(
    'document_tag',
    db.Column('document_id', db.Integer, db.ForeignKey('document.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String(10000))
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))
    first_name = db.Column(db.String(150))
    notes = db.relationship('Note')
    schools = db.relationship('School')


class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    address = db.Column(db.String(150))
    city = db.Column(db.String(150))
    state = db.Column(db.String(150))
    zip_code = db.Column(db.String(10))
    phone_number = db.Column(db.String(20))
    email = db.Column(db.String(150), unique=True)
    website = db.Column(db.String(150))
    documents = db.relationship('Document')
    tags = db.relationship('Tag', secondary=document_tag, backref='schools')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    url = db.Column(db.String(150))
    upload_date = db.Column(db.DateTime(timezone=True), default=func.now())
    school_id = db.Column(db.Integer, db.ForeignKey('school.id'))

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    description = db.Column(db.String(150))