from flask import Blueprint, render_template, request, flash, url_for, redirect
from .models import db,School
from sqlalchemy.orm import selectinload
from .static.schoolDiggerApi_user import get_school_districts
from .static.searchThroughQuery import search_dip_for_district

views = Blueprint('views', __name__)

#---------------------- state codes for school digger api ----------------------------
STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"]

#------------------------------ helper methods ---------------------------------------------
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
    #--------------------------cache existing by nces for O(1) lookups----------------------

    existing = {s.nces_id: s for s in School.query.all()}
    added, updated = 0, 0
    #---------- check how we are adding to the database when it needs to be updated ---------

    for state in STATES:
        for d in get_school_districts(state):
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

#---------------------- setup page to download any schools which need to be added -------------

@views.route('/', methods=['GET', 'POST'])
def home():
    initialized = db.session.query(School.id).limit(1).scalar() is not None
    if request.method == 'POST':
        if initialized:
            flash("District already added.","info")
            return redirect(url_for('views.update_districts'))
        added = populate_all_states()
        flash(f" Added {added} districts from all states", "success")
        return redirect(url_for('views.home'))

    schools = School.query.order_by(School.name.asc()).all() if initialized else []
    return render_template("home.html", schools=schools, initialized=initialized)


@views.route('/districts/update', methods=['GET', 'POST'])
def update_districts():
    # -------------------------------- update district --------------------
    # -------------------------- gather documents and analyze -------------
    # --------------------------------------- --------------------------
    return render_template("update.html")


@views.route('/district/<int:district_id>')
def district_detail(district_id):
    """Display detailed information for a specific school district"""
    school = School.query.get_or_404(district_id)
    return render_template("district_detail.html", school=school)

from sqlalchemy import or_

@views.route('/search')
def search():
    q = (request.args.get("query") or "").strip()

    if q:
        like = f"%{q}%"
        results = (
            School.query.filter(or_(
                School.name.ilike(like),
                School.street.ilike(like),
                School.city.ilike(like),
                School.state.ilike(like),
                School.zip_code.ilike(like),
                School.phone_number.ilike(like),
                School.email.ilike(like),
                School.website.ilike(like),
            ))
            .order_by(School.name.asc())
            .all()
        )
    else:
        results = School.query.order_by(School.name.asc()).all()

    return render_template('search_results.html', results=results, query=q)


