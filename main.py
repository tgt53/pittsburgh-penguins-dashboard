import csv
from pathlib import Path

from flask import Flask, redirect, render_template, send_file, url_for

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
HISTORICAL_DATA = Path(__file__).parent / "data" / "penguins_on_off_xgoals_2008_09_to_2025_26.csv"


@app.route("/")
def home():
    return render_historical_on_off()


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/on-off")
def historical_on_off():
    return redirect(url_for("home"))


def render_historical_on_off():
    with HISTORICAL_DATA.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    return render_template("on_off.html", rows=rows)


@app.route("/on-off/download")
def download_historical_on_off():
    return send_file(HISTORICAL_DATA, as_attachment=True, download_name=HISTORICAL_DATA.name, mimetype="text/csv")
