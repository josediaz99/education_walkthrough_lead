from . import db
from sqlalchemy.sql import func

document_tag = db.Table(
    'document_tag',
    db.Column('document_id', db.Integer, db.ForeignKey('document.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

school_tag = db.Table(
    'school_tag',
    db.Column('school_id', db.Integer, db.ForeignKey('school.id'), primary_key = True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key = True)
)

class School(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nces_id = db.Column(db.String(10), unique=True)
    name = db.Column(db.String(150))
    street = db.Column(db.String(50))
    county = db.Column(db.String(150))
    city = db.Column(db.String(150))
    state = db.Column(db.String(150))
    zip_code = db.Column(db.String(10))
    phone_number = db.Column(db.String(20))
    email = db.Column(db.String(150), unique=True)
    website = db.Column(db.String(150))
    numberTotalSchools = db.Column(db.Integer)
    street = db.Column(db.String(150))
    lowGrade = db.Column(db.String(10))
    highGrade = db.Column(db.String(10))
    documents = db.relationship('Document')
    tags = db.relationship('Tag', secondary=school_tag, backref='schools')
    #lat = db.column(db.loat)
    #long = db.column(db.float)

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