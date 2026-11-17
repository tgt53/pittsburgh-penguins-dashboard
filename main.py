import csv
import json
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, redirect, render_template, send_file, url_for

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
HISTORICAL_DATA = Path(__file__).parent / "data" / "penguins_on_off_xgoals_2008_09_to_2025_26.csv"
MONEYPUCK_ALL_XG_DATA = Path(__file__).parent / "data" / "moneypuck_all_players_on_off_xgoals_2007_08_to_2026_27.csv"
NHL_API_ROOT = "https://api-web.nhle.com/v1"


def fetch_nhl_json(path):
    request = Request(
        f"{NHL_API_ROOT}/{path}",
        headers={"User-Agent": "Mozilla/5.0 PenguinsDashboard/1.0", "Accept": "application/json"},
    )
    with urlopen(request, timeout=12) as response:
        return json.load(response)


@app.route("/")
def home():
    today = date.today()
    season_start = today.year if today.month >= 7 else today.year - 1
    season_id = f"{season_start}{season_start + 1}"
    return render_template("home.html", season_id=season_id, season_label=f"{season_start}\u2013{str(season_start + 1)[-2:]}")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/on-off")
def historical_on_off():
    return render_historical_on_off()


@app.route("/players/<int:player_id>")
def player_profile(player_id):
    return render_template("player.html", player_id=player_id)


@app.route("/api/roster/<season_id>")
def roster_api(season_id):
    if len(season_id) != 8 or not season_id.isdigit():
        return jsonify(error="Invalid NHL season."), 400
    return proxy_nhl_json(f"roster/PIT/{season_id}")


@app.route("/api/player/<int:player_id>")
def player_api(player_id):
    return proxy_nhl_json(f"player/{player_id}/landing")


@app.route("/api/moneypuck/on-off/<int:player_id>")
def moneypuck_on_off_api(player_id):
    if not MONEYPUCK_ALL_XG_DATA.exists():
        return jsonify(error="MoneyPuck player-season data has not been built yet."), 503
    with MONEYPUCK_ALL_XG_DATA.open(encoding="utf-8", newline="") as source:
        rows = [row for row in csv.DictReader(source) if row["Player ID"] == str(player_id)]
    return jsonify(rows)


def proxy_nhl_json(path):
    try:
        return jsonify(fetch_nhl_json(path))
    except HTTPError as error:
        return jsonify(error=f"The NHL API returned HTTP {error.code}."), 502
    except (URLError, TimeoutError, OSError):
        return jsonify(error="Could not reach the NHL API. Check the server's internet connection."), 502


def render_historical_on_off():
    with HISTORICAL_DATA.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    return render_template("on_off.html", rows=rows)


@app.route("/on-off/download")
def download_historical_on_off():
    return send_file(HISTORICAL_DATA, as_attachment=True, download_name=HISTORICAL_DATA.name, mimetype="text/csv")
