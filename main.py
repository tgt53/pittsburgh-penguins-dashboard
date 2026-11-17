import csv
import io
import json
import threading
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, redirect, render_template, send_file, url_for

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
HISTORICAL_DATA = Path(__file__).parent / "data" / "penguins_on_off_xgoals_2008_09_to_2025_26.csv"
MONEYPUCK_ALL_XG_DATA = Path(__file__).parent / "data" / "moneypuck_all_players_on_off_xgoals_2007_08_to_2026_27.csv"
NHL_API_ROOT = "https://api-web.nhle.com/v1"
NHL_STATS_ROOT = "https://api.nhle.com/stats/rest/en"
MONEYPUCK_REFRESH_SECONDS = 6 * 60 * 60
_moneypuck_refresh_lock = threading.Lock()
_moneypuck_refresh_started = 0.0


def refresh_current_moneypuck_season() -> None:
    """Replace active-season rows with the latest public MoneyPuck snapshot."""
    season_start = date.today().year if date.today().month >= 7 else date.today().year - 1
    url = f"https://moneypuck.com/moneypuck/playerData/seasonSummary/{season_start}/regular/skaters.csv"
    request = Request(url, headers={"User-Agent": "PenguinsDashboard/1.0"})
    with urlopen(request, timeout=30) as response:
        source_rows = csv.DictReader(io.StringIO(response.read().decode("utf-8-sig")))
        rows = []
        for row in source_rows:
            if row.get("situation") != "all" or row.get("team", "").upper() in {"", "ALL", "TOT", "2TM", "NHL"}:
                continue
            on_minutes = float(row.get("icetime") or 0) / 60
            off_minutes = float(row.get("timeOnBench") or 0) / 60
            on_xgf, on_xga = float(row.get("OnIce_F_xGoals") or 0), float(row.get("OnIce_A_xGoals") or 0)
            off_xgf, off_xga = float(row.get("OffIce_F_xGoals") or 0), float(row.get("OffIce_A_xGoals") or 0)
            rows.append({
                "Player ID": row.get("playerId", ""), "Season": f"{season_start}-{season_start + 1}",
                "Team": {"L.A": "LAK", "N.J": "NJD", "S.J": "SJS", "T.B": "TBL"}.get(row["team"].upper(), row["team"].upper()),
                "Player": row.get("name", ""), "Position": row.get("position", ""),
                "Games": int(float(row.get("games_played") or 0)),
                "On-ice minutes": round(on_minutes, 2), "Off-ice minutes": round(off_minutes, 2),
                "xGF on total": round(on_xgf, 2), "xGA on total": round(on_xga, 2),
                "On-ice xG differential": round(on_xgf - on_xga, 2),
                "xGF off total": round(off_xgf, 2), "xGA off total": round(off_xga, 2),
                "Off-ice xG differential": round(off_xgf - off_xga, 2),
                "xGF on per 60": round(on_xgf * 60 / on_minutes, 3) if on_minutes else 0,
                "xGA on per 60": round(on_xga * 60 / on_minutes, 3) if on_minutes else 0,
                "On-ice xG differential per 60": round((on_xgf - on_xga) * 60 / on_minutes, 3) if on_minutes else 0,
                "xGF off per 60": round(off_xgf * 60 / off_minutes, 3) if off_minutes else 0,
                "xGA off per 60": round(off_xga * 60 / off_minutes, 3) if off_minutes else 0,
                "Off-ice xG differential per 60": round((off_xgf - off_xga) * 60 / off_minutes, 3) if off_minutes else 0,
            })
    if not rows:
        raise RuntimeError(f"MoneyPuck returned no active-season skater rows for {season_start}.")

    with _moneypuck_refresh_lock:
        with MONEYPUCK_ALL_XG_DATA.open(encoding="utf-8", newline="") as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames
            existing = [row for row in reader if row.get("Season") != f"{season_start}-{season_start + 1}"]
        temporary = MONEYPUCK_ALL_XG_DATA.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields)
            writer.writeheader()
            writer.writerows(existing)
            writer.writerows(rows)
        temporary.replace(MONEYPUCK_ALL_XG_DATA)


def _refresh_current_season_in_background() -> None:
    global _moneypuck_refresh_started
    now = time.monotonic()
    if now - _moneypuck_refresh_started < MONEYPUCK_REFRESH_SECONDS:
        return
    if not _moneypuck_refresh_lock.acquire(blocking=False):
        return
    _moneypuck_refresh_started = now
    _moneypuck_refresh_lock.release()

    def refresh() -> None:
        try:
            refresh_current_moneypuck_season()
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as error:
            app.logger.warning("MoneyPuck current-season refresh failed: %s", error)

    threading.Thread(target=refresh, daemon=True).start()


def fetch_nhl_json(path):
    request = Request(
        f"{NHL_API_ROOT}/{path}",
        headers={"User-Agent": "Mozilla/5.0 PenguinsDashboard/1.0", "Accept": "application/json", "Referer": "https://www.nhl.com/"},
    )
    with urlopen(request, timeout=12) as response:
        return json.load(response)


def fetch_nhl_stats(path, season_id):
    query = f"{NHL_STATS_ROOT}/{path}?isAggregate=false&isGame=false&limit=100&cayenneExp=seasonId={season_id}%20and%20teamAbbrevs=%22PIT%22"
    request = Request(query, headers={"User-Agent": "Mozilla/5.0 PenguinsDashboard/1.0", "Accept": "application/json", "Referer": "https://www.nhl.com/"})
    with urlopen(request, timeout=12) as response:
        return json.load(response).get("data", [])


def roster_from_moneypuck(season_id):
    season = f"{season_id[:4]}-{int(season_id[4:])}"
    groups = {"forwards": [], "defensemen": [], "goalies": []}
    local_numbers = {8482993: 85, 8482470: 7}
    if not MONEYPUCK_ALL_XG_DATA.exists():
        return groups
    with MONEYPUCK_ALL_XG_DATA.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            if row.get("Season") != season or row.get("Team") != "PIT" or int(row.get("Games") or 0) < 1:
                continue
            player_id = row.get("Player ID", "")
            first, _, last = row.get("Player", "").partition(" ")
            player = {
                "id": int(player_id), "firstName": {"default": first}, "lastName": {"default": last},
                "positionCode": row.get("Position", "F"),
                "sweaterNumber": local_numbers.get(int(player_id)),
                "headshot": f"https://assets.nhle.com/mugs/nhl/{season_id}/PIT/{player_id}.png",
            }
            group = "defensemen" if row.get("Position") == "D" else "forwards"
            groups[group].append(player)
    if season_id == "20262027":
        # Local goalie fallback for the current season; NHL roster data remains the live source.
        groups["goalies"] = [
            {"id": 8481668, "firstName": {"default": "Arturs"}, "lastName": {"default": "Silovs"}, "positionCode": "G",
             "sweaterNumber": 37, "headshot": "https://assets.nhle.com/mugs/nhl/20262027/PIT/8481668.png"},
            {"id": 8483703, "firstName": {"default": "Sergei"}, "lastName": {"default": "Murashov"}, "positionCode": "G",
             "sweaterNumber": 1, "headshot": "https://assets.nhle.com/mugs/nhl/20262027/PIT/8483703.png"},
        ]
    return groups


def local_player_profile(player_id):
    rows = []
    local_numbers = {8482993: 85, 8482470: 7}
    if MONEYPUCK_ALL_XG_DATA.exists():
        with MONEYPUCK_ALL_XG_DATA.open(encoding="utf-8", newline="") as source:
            rows = [row for row in csv.DictReader(source) if row.get("Player ID") == str(player_id)]
    if rows:
        name = rows[0].get("Player", "")
        position = rows[0].get("Position", "")
        sweater_number = local_numbers.get(player_id)
        historic_stats = {}
        if HISTORICAL_DATA.exists():
            with HISTORICAL_DATA.open(encoding="utf-8-sig", newline="") as source:
                for historic in csv.DictReader(source):
                    if historic.get("Player") == name:
                        historic_stats[historic.get("Season", "")] = historic
        seasons = []
        for row in rows:
            season = row["Season"]
            season_total = {
                "season": int(season.replace("-", "")), "gameTypeId": 2, "leagueAbbrev": "NHL",
                "teamAbbrev": row.get("Team", ""), "gamesPlayed": int(float(row.get("Games") or 0)),
            }
            historic = historic_stats.get(season) if row.get("Team") == "PIT" else None
            if historic:
                stat_columns = {
                    "Goals": "goals", "Assists": "assists", "Points": "points", "+/-": "plusMinus",
                    "Penalty minutes": "pim", "Power-play goals": "powerPlayGoals",
                    "Power-play points": "powerPlayPoints", "Short-handed goals": "shorthandedGoals",
                    "Game-winning goals": "gameWinningGoals", "Overtime goals": "overtimeGoals", "Shots": "shots",
                }
                for column, field in stat_columns.items():
                    value = historic.get(column)
                    if value not in (None, ""):
                        season_total[field] = int(float(value))
                for column, field in (("Shooting %", "shootingPctg"), ("Faceoff win %", "faceoffWinningPctg")):
                    value = historic.get(column)
                    if value not in (None, ""):
                        season_total[field] = float(value) / 100
                toi = historic.get("TOI/GP (min)")
                if toi not in (None, ""):
                    total_seconds = round(float(toi) * 60)
                    season_total["avgToi"] = f"{total_seconds // 60}:{total_seconds % 60:02d}"
            seasons.append(season_total)
    else:
        current_goalies = {
            8481668: ("Arturs", "Silovs", 37),
            8483703: ("Sergei", "Murashov", 1),
        }
        goalie = current_goalies.get(player_id)
        if goalie:
            name = f"{goalie[0]} {goalie[1]}"
            position = "G"
            sweater_number = goalie[2]
            seasons = []
        elif rows:
            sweater_number = local_numbers.get(player_id)
        else:
            return None
    first, _, last = name.partition(" ")
    return {
        "id": player_id, "firstName": {"default": first}, "lastName": {"default": last},
        "position": position, "sweaterNumber": sweater_number, "fullTeamName": "Pittsburgh Penguins",
        "headshot": f"https://assets.nhle.com/mugs/nhl/20262027/PIT/{player_id}.png",
        "seasonTotals": seasons,
    }


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
    try:
        roster = fetch_nhl_json(f"roster/PIT/{season_id}")
    except HTTPError as error:
        app.logger.warning("NHL roster API returned HTTP %s; using local current-season data.", error.code)
        return jsonify(roster_from_moneypuck(season_id))
    except (URLError, TimeoutError, OSError, ValueError) as error:
        app.logger.warning("NHL roster API unavailable; using local current-season data: %s", error)
        return jsonify(roster_from_moneypuck(season_id))

    # Season stats add call-ups and departed players, but the active roster still works without them.
    try:
        roster_groups = {"forwards": "forwards", "defensemen": "defensemen", "goalies": "goalies"}
        known = {}
        for group in roster_groups:
            for player in roster.get(group, []):
                known[str(player.get("id", player.get("playerId", "")))] = player

        stats_by_group = [
            ("skaters", fetch_nhl_stats("skater/summary", season_id)),
            ("goalies", fetch_nhl_stats("goalie/summary", season_id)),
        ]
        for group, stats_rows in stats_by_group:
            for row in stats_rows:
                if int(row.get("gamesPlayed") or 0) < 1:
                    continue
                player_id = str(row.get("playerId", ""))
                position = row.get("positionCode", "")
                target_group = "goalies" if group == "goalies" else ("defensemen" if position == "D" else "forwards")
                if player_id in known:
                    player = known[player_id]
                else:
                    full_name = row.get("skaterFullName") or row.get("goalieFullName") or ""
                    first, _, last = full_name.partition(" ")
                    try:
                        details = fetch_nhl_json(f"player/{player_id}/landing")
                    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
                        details = {}
                    player = {
                        "id": row.get("playerId"),
                        "firstName": details.get("firstName", {"default": first}),
                        "lastName": details.get("lastName", {"default": last}),
                        "positionCode": details.get("position") or position or ("G" if group == "goalies" else "F"),
                        "sweaterNumber": details.get("sweaterNumber"),
                        "headshot": details.get("headshot") or f"https://assets.nhle.com/mugs/nhl/{season_id}/PIT/{player_id}.png",
                    }
                    known[player_id] = player
                if player not in roster.setdefault(target_group, []):
                    roster[target_group].append(player)
    except HTTPError as error:
        app.logger.warning("NHL season stats refresh failed with HTTP %s; showing active roster only.", error.code)
    except (URLError, TimeoutError, OSError, ValueError, KeyError) as error:
        app.logger.warning("NHL season stats refresh failed; showing active roster only: %s", error)
    return jsonify(roster)


@app.route("/api/player/<int:player_id>")
def player_api(player_id):
    try:
        return jsonify(fetch_nhl_json(f"player/{player_id}/landing"))
    except HTTPError as error:
        local = local_player_profile(player_id)
        if local:
            return jsonify(local)
        return jsonify(error=f"The NHL API returned HTTP {error.code} and no local profile is available."), 502
    except (URLError, TimeoutError, OSError, ValueError):
        local = local_player_profile(player_id)
        if local:
            return jsonify(local)
        return jsonify(error="Could not reach the NHL API and no local profile is available."), 502


@app.route("/api/moneypuck/on-off/<int:player_id>")
def moneypuck_on_off_api(player_id):
    _refresh_current_season_in_background()
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
