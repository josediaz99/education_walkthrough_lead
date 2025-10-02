from flask import Blueprint, render_template, request, flash, url_for, redirect
from .models import db,School
from sqlalchemy import selectinload
from .static.schoolDiggerApi_user import get_school_districts

views = Blueprint('views', __name__)

#---------------------- state codes for school digger api ----------------------------
STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"
] 
#---------------------- helper methods ---------------------------------------------
def get_district_data(d):
    """gets district data from what is available by the school digger api and returns a dictionary of district info"""
    return dict(
        nces_id=d.get("districtID"),
        name=d.get("districtName"),
        street=d.get("street"),
        city=d.get("city"),
        state=d.get("state"),
        zip_code=d.get("zip"),
        phone_number=d.get("phone"),
        website=d.get("url"),
        lowGrade=d.get("lowGrade"),
        highGrade=d.get("highGrade"),
        numberTotalSchools=d.get("numberTotalSchools"),
    )

def populate_all_states():
    """populates the school db when first initialized with district data and returns the number of added data"""
    existing = {n for (n,) in db.session.query(School.nces_id).all() if n}
    added = 0
    for st in STATES:
        for d in get_school_districts(st):
            nces = d.get("districtID")
            if not nces or nces in existing:
                continue
            db.session.add(School(**get_district_data(d)))
            existing.add(nces)
            added += 1
    db.session.commit()
    return added

def update_all_states():
    """
    Upsert pass for all 50 states.
    Returns (added, updated) counts.
    """
    # cache existing by nces for O(1) lookups
    existing = {s.nces_id: s for s in School.query.all()}
    added, updated = 0, 0

    for state in STATES:
        for d in get_school_districts(st):
            nces = d.get("districtID")
            if not nces:
                continue
            if nces in existing:
                s = existing[nces]
                fields = get_district_data(d)
                changed = False
                for k, v in fields.items():
                    if getattr(s, k) != v:
                        setattr(s, k, v)
                        changed = True
                if changed:
                    updated += 1
            else:
                s = School(**get_district_data(d))
                db.session.add(s)
                existing[nces] = s
                added += 1

    db.session.commit()
    return added, updated
#---------------------- setup page to download any schools which need to be added
@views.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        #build a set of nces ids which have already been seen
        existing = {n for (n,) in db.session.query(School.nces_id).all() if n}
        added = 0

        #going through each state and entering them as a school to the database
        for state in STATES:
            districts = get_school_districts(state=state)
            for district in districts:
                nces_id = district.get("districtID")
                if not nces_id or nces_id in existing:
                    continue

                school = School(
                nces_id = nces_id,
                name = district["districtName"],
                street = district["street"],
                city = district["city"],
                state = district["state"],
                zip_code = district["zip"],
                phone_number = district["phone"],
                website = district["url"],
                email = None,
                lowGrade = district["lowGrade"],
                highGrade = district["highGrade"],
                numberTotalSchools = district["numberTotalSchools"]
                )
            db.session.add(school)
            existing.add(nces_id)
            added =+ 1
    db.session.commit()
    #let th
    flash(f"Populated/updated districtfrom all 50 states. added {added} districts", "success")
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
    print(results)
    return render_template('search_results.html', results=results)