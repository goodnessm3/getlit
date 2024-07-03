#!/usr/bin/env bash
gunicorn main:app -b 0.0.0.0:9111 --access-logfile guni.log --reload --reload-extra-file main/static --reload-extra-file main/templates