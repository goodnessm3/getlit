from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for, jsonify, send_file, current_app
from io import BytesIO
from main.downloader import get_paper, write_info_to_db, check_services, extract_captcha_img, answer_captcha, save_captcha_image, get_cached
from main.db import get_db, dump_contents_for_page
import os
import json

bp = Blueprint('lookup_page', __name__, url_prefix='')


@bp.route('/getlit', methods=('GET', 'POST'))
def begin():

    if request.method == "GET":
        if session.get("doi"):

            ###### todo, don't repeat
            data, name, myinfo, resp, service = get_paper(session["doi"], cookie=session.get("innercookie"))
            session["doi"] = None
            return send_file(BytesIO(data), download_name=name)
            #######
        else:
            table = dump_contents_for_page()
            floc = current_app.config["SAVE_DIRECTORY"]  # to make download links
            return render_template('page1/page1.html', table=table, file_loc=floc)  # normal viewing

    elif request.method == "POST":

        db = get_db()
        cur = db.cursor()

        doi = request.form["doi"]
        cached = get_cached(cur, doi)

        if cached:
            name = os.path.split(cached)[-1]
            print(f"Serving previously saved pdf from: {cached}")
            return send_file(cached, download_name=name)  # early return

        # if not cached, it's a new file, we gotta get the info to prepare to save it
        data, name, myinfo, resp, service = get_paper(doi, cookie=session.get("innercookie"))

        if data:
            if data[:4] == b"%PDF":
                destination = os.path.join(current_app.config["SAVE_DIRECTORY"], name)
                with open(destination, "wb") as f:
                    f.write(data)

                # now that the file was successfully found, record it in the database, so we can provide it
                # directly next time rather than going to the source each time
                write_info_to_db(cur, doi, myinfo, name)
                db.commit()

                print(f"Cached a new file at: {destination}")
                return send_file(BytesIO(data), download_name=name)

            elif data[:6] == b"<html>":  # we were expecting a pdf but got html, must be the captcha page
                im, hidden = extract_captcha_img(data)
                session["hidden"] = hidden
                captcha_img = service + im
                print("captcha url is ",  captcha_img)
                dst = save_captcha_image(captcha_img)  # returns the filename where it was saved in the static directory
                session["captcha_filename"] = dst
                session["innercookie"] = resp.headers['Set-Cookie']
                session["captcha_link"] = captcha_img
                session["respurl"] = resp.url
                session["doi"] = doi  # preserve this so we can load the doc after solving the captcha
                print("redirecting to captcha page")
                return redirect(url_for("lookup_page.captcha"))

        else:
            flash("Connection to all services failed.")
            return render_template('page1/page1.html')


@bp.route('/services', methods=("GET",))
def services():

    return check_services()


@bp.route('/captcha', methods=("GET", "POST"))
def captcha():

    if request.method == "GET":
        return render_template('captcha/captcha.html', captcha_link=session["captcha_link"], captcha_filename=session["captcha_filename"])
    elif request.method == "POST":
        print(request.form)
        answer_captcha(session["respurl"], request.form.get("answer"), session["innercookie"], session["hidden"])
        return redirect(url_for('lookup_page.begin'))
