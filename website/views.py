from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from .models import School, Tag
from flask import request, flash
from . import db
from .static.schoolDiggerApi_user import get_school_districts
import json


views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        # name = request.form.get('name')
        # address = request.form.get('address')
        # city = request.form.get('city')
        # state = request.form.get('state')
        # zip_code = request.form.get('zip_code')
        # phone_number = request.form.get('phone_number')
        # email = request.form.get('email')
        # website = request.form.get('website')


        # new_school = School(name=name, address=address, city=city, state=state, zip_code=zip_code, phone_number=phone_number, email=email, website=website)
        

        # for tag_name in request.form.getlist('tags'):
        #     new_tag = Tag.query.filter_by(name=tag_name).first()
        #     new_school.tags.append(new_tag)

        # print(new_school.tags)
        # db.session.add(new_school)
        # db.session.commit()

        # flash("School Added!", category='success')
        school_districts = get_school_districts("IL")
        # print(school_districts)

        for district in school_districts:
            nces_id = district["districtID"]
            name = district["districtName"]
            street = district["street"]
            city = district["city"]
            state = district["state"]
            zip_code = district["zip"]
            phone_number = district["phone"]
            website = district["url"]
            lowGrade = district["lowGrade"]
            highGrade = district["highGrade"]
            numberTotalSchools = district["numberTotalSchools"]

            new_school = School(nces_id=nces_id, name=name, street=street, city=city, state=state, zip_code=zip_code, phone_number=phone_number, website=website, lowGrade=lowGrade, highGrade=highGrade, numberTotalSchools=numberTotalSchools)
            db.session.add(new_school)
            db.session.commit()

    return render_template("home.html", schools=School.query.all())

@views.route('/search')
def search():
    query = request.args.get("query")
    if(query != ""):
        results = School.query.filter(
            School.name.ilike(f"%{query}%") | 
            School.address.ilike(f"%{query}%") | 
            School.city.ilike(f"%{query}%") | 
            School.state.ilike(f"%{query}%") | 
            School.zip_code.ilike(f"%{query}%") |
            School.phone_number.ilike(f"%{query}%") |
            School.email.ilike(f"%{query}%") |
            School.website.ilike(f"%{query}%")
        ).all()
    else:
        results = School.query.all()
    print(results)
    return render_template('search_results.html', results=results)