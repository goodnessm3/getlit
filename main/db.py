import sqlite3
from flask import current_app, g


def get_db():

    if "db" not in g:
        g.db = sqlite3.connect("lit_db.sqlite3")
        schema = '''CREATE TABLE IF NOT EXISTS "papers" (
                    "doi"	TEXT,
                    "first_author"	TEXT,
                    "authors"	TEXT,
                    "title"	TEXT,
                    "journal"	TEXT,
                    "year"	INTEGER,
                    "added"	DATETIME DEFAULT CURRENT_TIMESTAMP,
                    "file_path"	TEXT,
                    "tags"	TEXT,
                    "user"	INTEGER,
                    PRIMARY KEY("doi")
                );'''
        cur = g.db.cursor()
        cur.execute(schema)

    return g.db


def dump_contents_for_page():

    db = get_db()
    cur = db.cursor()
    cur.execute('''SELECT title, first_author, journal, year, tags, file_path FROM papers''')
    return cur.fetchall()


def close_db(e=None):

    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):

    app.teardown_appcontext(close_db)