from flask import Flask
import os
from subprocess import Popen


def create_app(test_config=None):

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='rutbaga',
        PERMANENT_SESSION_LIFETIME=157000000,
        SAVE_DIRECTORY=r"C:\Users\crg\Desktop"
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    from . import start
    app.register_blueprint(start.bp)

    return app


app = create_app()
