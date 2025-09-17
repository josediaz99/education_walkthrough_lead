from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from .models import Note
from flask import request, flash
from . import db
import json


views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        # note = request.form.get('note')
        # if len(note) < 1:
        #     flash("Note is too short!", category='error')
        # else:
        #     new_note = Note(data=note, user_id=current_user.id)
        #     db.session.add(new_note)
        #     db.session.commit()
        #     flash("Note Added!", category='success')
        name = request.form.get('name')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip_code')
        phone_number = request.form.get('phone_number')
        email = request.form.get('email')
        website = request.form.get('website')
        print(request.form.getlist('tags'))


        new_school = School(name=name, address=address, city=city, state=state, zip_code=zip_code, phone_number=phone_number, email=email, website=website, user_id=current_user.id)
        

        for tag in request.form.getlist('tags'):
            new_school.append(tag)

        db.session.add(new_school)
        db.session.commit()

        flash("School Added!", category='success')
    return render_template("home.html", user=current_user)


@views.route('/delete-note', methods=['POST'])
def delete_note():
    note = json.loads(request.data)
    noteId = note['noteId']
    note = Note.query.get(noteId)
    if note:
        if note.user_id == current_user.id:
            db.session.delete(note)
            db.session.commit()
    return jsonify({})
