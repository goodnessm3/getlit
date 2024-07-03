from crossref.restful import Works
import sqlite3
import os
import requests
from bs4 import BeautifulSoup
from unicodedata import normalize
import datetime
import urllib.parse
import re
from io import BytesIO

works = Works()


def get_authors(js):
    out = []
    for x in js["author"]:
        name = f'{x["given"]} {x["family"]}'
        out.append(name)
    return out  # this is destined to be a string written into sql so it wouldn't understand a list anyway


def get_first_author(js):
    out = None  # default if no first author is listed
    for x in js["author"]:
        if x["sequence"] == "first":
            out = f'{x["given"]} {x["family"]}'
    return out


def get_year(js):

    """"published-print or published-online for year, might be a recent non-printed paper"""

    try:
        data = js["published-print"]
    except KeyError:
        data = js["published-online"]
    return data["date-parts"][0][0]  # it's a list that contains a list of year, month


def get_info(js):

    """Return all required info as a dict by pulling it from the json and processing it as necessary"""

    norm = lambda x: normalize("NFKD", x)
    # normalise unicode text to cope with special/weird characters

    authors = get_authors(js)
    first_author = get_first_author(js)
    year = get_year(js)
    title = js["title"][0]
    journal = js["container-title"][0]
    return {"authors": ", ".join([norm(x) for x in authors]),
            "first_author": norm(first_author),
            "year": year,
            "title": norm(title),
            "journal": norm(journal)}

def get_cached(conn, doi):

    """If we already downloaded this paper before, return the location where it's saved to serve to the user
    directly. Return None if it's a new doi that we need to download."""

    conn.execute("SELECT file_path FROM papers WHERE doi = ?", (doi,))
    res = conn.fetchone()  # doi will always be unique
    if res:
        return res[0]  # unpacking a tuple of length 1 to the value it contains
    else:
        return  # not found, return None


def write_info_to_db(conn, doi, dc, save_dest):

    conn.execute("SELECT * FROM papers WHERE doi = ?", (doi,))
    res = conn.fetchall()
    if res:
        return  # don't try to re-add a paper, the unique constraint will fail

    insert_tup = (doi,
                  dc["first_author"],
                  dc["authors"],
                  dc["title"],
                  dc["journal"],
                  dc["year"],
                  save_dest,
                  )

    conn.execute('''INSERT INTO papers (doi, 
    first_author, 
    authors, 
    title, 
    journal, 
    year,
    file_path) VALUES (?, ?, ?, ?, ?, ?, ?)''', insert_tup)


def determine_filename(info):

    """look at the JSON from crossref to determine a sensible name for the pdf based on author"""
    # TODO: cope with multiple papers from the same author in the same month

    out = None
    first_time = True

    for x in info["author"]:
        if first_time:
            out = x["family"]
            first_time = False
            # assume that the first in the list is the first author
        if x["sequence"] == "first":
            # unless another is specifically labelled as first author, then use this instead
            out = x["family"]
            break

    year = get_year(info)

    return normalize("NFKD", out).replace(" ", "") + str(year) + ".pdf"


def get_dl_link(url_root, doi, cookie):

    """get a pdf download link from the service at url_root for a document specified by doi"""

    try:
        if cookie:
            resp = requests.get(url_root + "/" + doi)
        else:
            resp = requests.get(url_root + "/" + doi, headers={"cookie": cookie})
    except Exception as e:
        raise e  # sometimes services go down
    soup = BeautifulSoup(resp.content, "html.parser")
    for x in soup.find_all("button"):  # download link used to be a href=, changed to a button
        y = x.get("onclick")
        if y and "download" in y:
            to_ret = y[15:-1]  # don't want the start which is location.href='

            if "https://" not in to_ret:
                return "https://" + to_ret.lstrip("/")  # sometimes the link is missing this, unpredictably
            else:
                return to_ret


def get_paper(doi, cookie):

    """Look up the citation info for a paper specified by doi, using CrossRef. Download the paper
    from an external service, and make an entry in a local db storing the paper info."""

    myjson = works.doi(doi)  # the raw json from crossref
    myinfo = get_info(myjson)  # find certain details like author, year
    fname = determine_filename(myjson)  # decide what to call the file when we save it, using json, not the parsed info

    inmemory = None  # default values only overwritten if one service is successful in the loop
    resp = None
    x = None

    for x in SERVICES: # TODO: pass origin and referrer
        try:
            dl_link = get_dl_link(x, doi, cookie)  # this also queries the service and may fail, exception is propagated
            if not dl_link:
                print(f"Download link not found on page for {x}")
                continue
            print("Found download link: ", dl_link)
            resp = requests.get(dl_link)
            inmemory = resp.content  # don't save locally just send to user
            print(f"connection to {x} succeeded!")
            break  # the first service that worked

        except requests.exceptions.ConnectionError:
            print(f"connection to {x} failed")

    return inmemory, fname, myinfo, resp, x  # return the whole response as well in case we need it


def extract_captcha_img(html):

    """We are being presented with a captcha page, extract and return the URL"""

    soup = BeautifulSoup(html, "html.parser")
    im = soup.find_all("img")[0]["src"]  # assuming the layout of the page never changes it only has this one image
    hidden = None

    for x in soup.find_all("input"):
        q = x.get("type")
        if q == "hidden":
            hidden = (x.get("value"))

    return im, hidden


def save_captcha_image(url):

    data = requests.get(url)
    parts = url.split("/")
    dest = parts[-1]
    with open(os.path.join("main", "static", dest), "wb") as f:
        f.write(data.content)
    print(f"saved captcha image {dest}")
    return dest


def answer_captcha(url, answer, cookie, hidden):

    print("in hte answer func, the url naswer and cookie are", url, answer, cookie)
    headers = {"cookie": cookie}
    resp = requests.post(url, data={"answer": answer, "id": hidden}, headers=headers)
    # this primes the server so that the next time we make our original get request, it will go through
    #print("here is data after posting captcha")
    #print(resp.headers)
    #print(resp.content)


def load_services():

    out = []
    with open("main/services.txt", "r") as f:
        for line in f.readlines():
            out.append(line.rstrip("\n"))
    return out


def check_services():

    out = ""
    for x in SERVICES:
        try:
            requests.get(x)
            out += "1"
        except requests.exceptions.ConnectionError:
            out += "0"

    return out


SERVICES = load_services()
