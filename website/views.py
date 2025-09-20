from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from .models import School, Tag
from flask import request, flash, abort
from . import db
from .static.schoolDiggerApi_user import get_school_districts
import json


views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        print("LOADING SCHOOLS")
        school_districts = get_school_districts("IL")

        for district in school_districts:
            if(db.session.query(School.id).filter_by(nces_id=district["districtID"]).first() is None):
                nces_id = district["districtID"]
                name = district["districtName"]
                street = district["street"]
                city = district["city"]
                state = district["state"]
                zip_code = district["zip"]
                phone_number = district["phone"]
                website = district["url"]
                # lowGrade = district["lowGrade"]
                # highGrade = district["highGrade"]
                numberTotalSchools = district["numberTotalSchools"]

                new_school = School(nces_id=nces_id, name=name, street=street, city=city, state=state, zip_code=zip_code, phone_number=phone_number, website=website, numberTotalSchools=numberTotalSchools)
                db.session.add(new_school)
                db.session.commit()

    return render_template("home.html", schools=School.query.all())

@views.route('/district/<int:district_id>')
def district_detail(district_id):
    """Display detailed information for a specific school district"""
    school = School.query.get_or_404(district_id)
    return render_template("district_detail.html", school=school)

@views.route('/search')
def search():
    query = request.args.get("query")
    if(query != ""):
        results = School.query.filter(
            School.name.ilike(f"%{query}%") | 
            School.street.ilike(f"%{query}%") | 
            School.city.ilike(f"%{query}%") | 
            School.state.ilike(f"%{query}%") | 
            School.zip_code.ilike(f"%{query}%") |
            School.phone_number.ilike(f"%{query}%") |
            School.email.ilike(f"%{query}%") |
            School.website.ilike(f"%{query}%")
        ).all()
    else:
        results = School.query.all()
    
    return render_template('search_results.html', results=results)

@views.route('/filter', methods=['POST'])
def filter():
    city = request.form.get('city')
    state = request.form.get('state')
    zip_code = request.form.get('zip_code')

    tag_names = request.form.getlist('tags')
    tags = db.session.query(Tag).filter(Tag.name.in_(tag_names)).all()

    query = db.session.query(School)

    if(city):
        query = query.filter(School.city == city)
    if(state):
        query = query.filter(School.state == state)
    if(zip_code):
        query = query.filter(School.zip_code == zip_code)
    if(tags):
        query = query.filter(School.tags.any(Tag.id.in_([tag.id for tag in tags])))

    results = query.all()

    return render_template('search_results.html', results=results)