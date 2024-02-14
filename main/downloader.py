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


def write_info_to_db(conn, doi, dc):

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
                  )

    conn.execute('''INSERT INTO papers (doi, 
    first_author, 
    authors, 
    title, 
    journal, 
    year) VALUES (?, ?, ?, ?, ?, ?)''', insert_tup)


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


def get_dl_link(url_root, doi):

    """get a pdf download link from the service at url_root for a document specified by doi"""

    try:
        resp = requests.get(url_root + "/" + doi)
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


def get_paper(doi):
    """Look up the citation info for a paper specified by doi, using CrossRef. Download the paper
    from an external service, and make an entry in a local db storing the paper info."""

    myjson = works.doi(doi)  # the raw json from crossref
    myinfo = get_info(myjson)  # find certain details like author, year
    fname = determine_filename(myjson)  # decide what to call the file when we save it, using json, not the parsed info

    inmemory = None  # default values only overwritten if one service is successful in the loop

    for x in SERVICES:
        try:
            dl_link = get_dl_link(x, doi)  # this also queries the service and may fail, exception is propagated
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

    return inmemory, fname, myinfo


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
