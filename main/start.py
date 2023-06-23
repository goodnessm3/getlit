from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for, jsonify, send_file
from io import BytesIO
from main.downloader import get_paper, write_info_to_db
from main.db import get_db

bp = Blueprint('lookup_page', __name__, url_prefix='')


@bp.route('/getlit', methods=('GET', 'POST'))
def begin():

    if request.method == "GET":

        return render_template('page1/page1.html')

    elif request.method == "POST":
        if session.get("tok", None) == "louder":

            print(request.form)
            doi = request.form["doi"]
            data, name, myinfo = get_paper(doi)

            db = get_db()
            cur = db.cursor()
            write_info_to_db(cur, doi, myinfo)
            db.commit()

            return send_file(data, download_name=name)
        else:
            return render_template('page1/page1.html')


@bp.route('/ajax', methods=('GET',))
def ajax_example():

    if not "tok" in session:
        session["tok"] = "louder"

    return render_template('ajax/ajax.html')
