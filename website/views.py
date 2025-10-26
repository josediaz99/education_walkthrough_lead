import asyncio
from flask import Blueprint, render_template, request, flash, url_for, redirect
from .models import db,School,Document,Tag
from sqlalchemy.orm import selectinload
from .static.schoolDiggerApi_user import get_school_districts
from .static.searchThroughQuery import search_dip_for_district
from .static.rag import analyze_doc
from sqlalchemy import or_

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
    updates database with anyt new or updated infromation from school digger api
    """
    existing = {s.nces_id: s for s in School.query.all()}
    added, updated = 0, 0
   
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

async def search_and_store_docs(school):
    """search for district improvement plans and stores documents to database"""
    try:
        results = await search_dip_for_district(school.name, state=school.state)
        added = 0
        
        for result in results:
            # Check if document already exists
            existing = Document.query.filter_by(
                school_id=school.id,
                url=result.get("url")
            ).first()
            
            if not existing:
                doc = Document(
                    title=result.get("verified_title") or result.get("title", "Untitled"),
                    url=result.get("url"),
                    school_id=school.id,
                    score=result.get("score", 0),
                    reasons=result.get("why", "")
                )
                db.session.add(doc)
                added += 1
        
        db.session.commit()
        return added
    except Exception as e:
        print(f"Error searching for documents for {school.name}: {str(e)}")
        return None

def get_tags(school,doc):
    """
    this function should be used to take the top document and performs analysis to return tags to be inserter into the database
    this function will be inside fo a loop which will have school and the top document available
    """
    responses = analyze_doc(doc.url)

    tags = []

    for response in responses.values():
        new_tag = Tag.query.filter_by(name=response["name"]).first()
        tags.append(new_tag)

    return tags

def store_tag(school, tags):
    """
    this function should be used to take the tags which were found by the rag system to be stored in the database
    this function will also be in a loop which will have the school and tags available
    """
    school.tags = tags

#---------------------- home page for displayed information -------------

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
    tags = Tag.query.all()
    
    return render_template("home.html", schools=schools, initialized=initialized, states=STATES, tags=tags)

@views.route('/districts/update', methods=['GET', 'POST'])
def update_districts():
    if request.method == 'POST':
        action = request.form.get('action')
         # -------------------------------- update district ---------------------------------------
        if action == 'update_schools':
            try:
                added, updated = update_all_states()
                flash(f"Successfully updated districts: {added} added, {updated} updated", "success")
            except Exception as e:
                flash(f"Error updating districts: {str(e)}", "error")
                
            return redirect(url_for('views.update_districts'))
        # ------------------------- gather documents and analyze ----------------------------------
        elif action == 'analyze_all':
            try:
                all_schools = School.query.all()
                if not all_schools:
                    flash('No Districts were found, Please update district first',  'warning')
                    return redirect(url_for('views.update_districts'))
                flash(f"Starting analysis of {len(all_schools)} districts, this may take a while", 'info')
                # --------------------- perform webscraping + store documents -------------------------------
                total_docs_added = 0
                docs_analyzed = 0
                for school in all_schools:
                    """we are performing analysis after filling documents to reduce chance of getting caught as a bot"""
                    try:
                        #-------- get documents for each school---------------------------------
                        docs_added = asyncio.run(search_and_store_docs(school))
                        total_docs_added += docs_added
                        #--------- getting top document for the school--------------------------
                        top_doc = Document.query.filter_by(school_id = school.id).order_by(Document.score.desc()).first()
                        #--------- perform rag analysis on top document ------------------------> this portion will handle using the rag system in our update page
                        if top_doc:
                            tags = get_tags(school,top_doc)
                            store_tag(school,tags)
                            docs_analyzed += 1

                    except Exception as e:
                        print(f"Error analyzing {school.name}: {str(e)}")
                        continue
                    flash(f" Analysis complete: {total_docs_added} documents found, {docs_analyzed} schools analyzed", "success")
            except Exception as e:
                flash(f"Error updating districts: {str(e)}", "error")
            return redirect(url_for('views.update_districts'))
        # --------------- gather documents and analyze in case of missing --------------------------
        elif action == 'analyze_missing':
            try:
                school_with_no_docs = db.session.query(School).outerjoin(Document,School.id == Document.school_id).filter(Document.id == None).all()
                if not school_with_no_docs:#when there is no schools without documents
                    flash("All districts have been anylized", 'info')
                    return redirect(url_for('views.update_districts'))
                flash(f"anylyzing {len(school_with_no_docs)} districts with missing documents",'info')
                total_docs_added = 0
                docs_analyzed = 0
                for school in school_with_no_docs:
                    try:
                        #-------- get documents for each school---------------------------------
                        docs_added = asyncio.run(search_and_store_docs(school))
                        total_docs_added += docs_added
                        #--------- getting top document for the school--------------------------
                        top_doc = Document.query.filter_by(school_id = school.id).order_by(Document.score.desc()).first()
                        #--------- perform rag analysis on top document ------------------------> this portion will handle using the rag system in our update page
                        if top_doc:
                            tags = get_tags(school,top_doc)
                            store_tag(school,tags)
                            docs_analyzed += 1
                    except Exception as e:
                        print(f"Error analyzing {school.name}: {str(e)}")
                        continue
                flash(f"Missing analysis complete: {total_docs_added} documents found, {docs_analyzed} schools were analyzed", "success")

            except Exception as e:
                flash(f"Error dusing missing analysis: {str(e)}","error")
            return redirect(url_for('views.update_districts'))
    return render_template("update.html")

@views.route('/district/<int:district_id>')
def district_detail(district_id):
    """Display detailed information for a specific school district"""
    #------------------- getting school district --------------------------
    school = School.query.get_or_404(district_id)
    #------------------- manualy input improvement plan -------------------
    if request.method == 'POST':
        action = request.form.get('action')
        #--------------- analyze manualy input plan -----------------------
        if action == 'analyze_url':
            url = request.url.get('custom_url','').strip()
            
            if not url:
                flash('Please provide URL','warning')
                return redirect(url_for('views.district_details',district_id=district_id))
            
            try:
                tags = get_tags()
                store_tag(school,tags)
                flash('URL analysis complete', "success")
            except Exception as e:
                flash(f"Error analyzing URL: {str(e)}", "error")
    all_tags = Tag.query.all()
    return render_template("district_detail.html", school=school)

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


