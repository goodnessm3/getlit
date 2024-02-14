from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for, jsonify, send_file, current_app
from io import BytesIO
from main.downloader import get_paper, write_info_to_db, check_services
from main.db import get_db
import os

bp = Blueprint('lookup_page', __name__, url_prefix='')


@bp.route('/getlit', methods=('GET', 'POST'))
def begin():

    if request.method == "GET":

        return render_template('page1/page1.html')

    elif request.method == "POST":

        doi = request.form["doi"]
        data, name, myinfo = get_paper(doi)

        db = get_db()
        cur = db.cursor()
        write_info_to_db(cur, doi, myinfo)
        db.commit()

        if data:
            destination = os.path.join(current_app.config["SAVE_DIRECTORY"], name)
            with open(destination, "wb") as f:
                f.write(data)
            return send_file(BytesIO(data), download_name=name)

        else:
            flash("Connection to all services failed.")
            return render_template('page1/page1.html')


@bp.route('/services', methods=("GET",))
def services():

    return check_services()
