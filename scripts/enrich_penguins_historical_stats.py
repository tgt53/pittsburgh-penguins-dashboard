"""Add NHL standard regular-season skater stats to the Penguins season CSV.

MoneyPuck supplies the existing expected-goals data. This script retrieves the
corresponding Pittsburgh player/team rows from the NHL public Stats API and
joins them by season and player name.
"""

from __future__ import annotations

import csv
import io
import json
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "penguins_on_off_xgoals_2008_09_to_2025_26.csv"
YEARS = range(2008, 2026)
API = "https://api.nhle.com/stats/rest/en/skater/summary"
MONEYPUCK = "https://moneypuck.com/moneypuck/playerData/seasonSummary"
STAT_COLUMNS = {
    "Goals": "goals",
    "Assists": "assists",
    "Points": "points",
    "+/-": "plusMinus",
    "Penalty minutes": "penaltyMinutes",
    "Power-play goals": "ppGoals",
    "Power-play points": "ppPoints",
    "Short-handed goals": "shGoals",
    "TOI/GP (min)": "timeOnIcePerGame",
    "Game-winning goals": "gameWinningGoals",
    "Overtime goals": "otGoals",
    "Shots": "shots",
    "Shooting %": "shootingPct",
    "Faceoff win %": "faceoffWinPct",
}


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(c for c in value if not unicodedata.combining(c)).casefold().strip()


def fetch_season(year: int) -> list[dict]:
    season_id = f"{year}{year + 1}"
    entries = []
    total = None
    for start in range(0, 5000, 100):
        params = urllib.parse.urlencode({
            "isAggregate": "false",
            "isGame": "false",
            "cayenneExp": f"seasonId={season_id} and gameTypeId=2 and teamAbbrev='PIT'",
            "limit": "100",
            "start": str(start),
            "sort": "playerId",
        })
        request = urllib.request.Request(
            f"{API}?{params}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nhl.com/"},
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.load(response)
        if total is None:
            total = payload.get("total", 0)
        batch = payload.get("data", [])
        entries.extend(batch)
        if start + len(batch) >= total or not batch:
            break
        time.sleep(0.1)
    if total is None or total > len(entries):
        raise RuntimeError(f"NHL API response was truncated for {season_id}.")
    return entries


def fetch_moneypuck_ids(year: int) -> dict[tuple[str, str], str]:
    url = f"{MONEYPUCK}/{year}/regular/skaters.csv"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read().decode("utf-8-sig")
    season = f"{year}-{year + 1}"
    result = {}
    for row in csv.DictReader(io.StringIO(content)):
        if row.get("team") == "PIT" and row.get("situation") == "all":
            result[(season, normalized_name(row["name"]))] = row["playerId"]
    return result


def main() -> None:
    with DATA.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        original_fields = list(reader.fieldnames or [])
        rows = list(reader)

    for column in STAT_COLUMNS:
        if column not in original_fields:
            original_fields.append(column)

    by_id: dict[tuple[str, str], dict] = {}
    player_ids: dict[tuple[str, str], str] = {}
    for year in YEARS:
        player_ids.update(fetch_moneypuck_ids(year))
        for stats in fetch_season(year):
            key = (f"{year}-{year + 1}", str(stats["playerId"]))
            if key in by_id:
                raise RuntimeError(f"Duplicate NHL PIT stat row: {key}")
            by_id[key] = stats
        time.sleep(0.15)

    missing = []
    for row in rows:
        key = (row["Season"], normalized_name(row["Player"]))
        player_id = player_ids.get(key)
        stats = by_id.get((row["Season"], str(player_id))) if player_id else None
        if stats is None:
            missing.append(key)
            continue
        for column, source_key in STAT_COLUMNS.items():
            value = stats.get(source_key)
            if value is None:
                row[column] = ""
            elif source_key == "timeOnIcePerGame":
                row[column] = f"{float(value) / 60:.2f}"
            elif source_key in {"shootingPct", "faceoffWinPct"}:
                row[column] = f"{float(value) * 100:.2f}"
            elif source_key == "plusMinus":
                row[column] = str(int(value))
            else:
                row[column] = str(int(value))

    if missing:
        preview = ", ".join(f"{season} {name}" for season, name in missing[:12])
        raise RuntimeError(f"No matching NHL PIT stats for {len(missing)} rows: {preview}")

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=original_fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    DATA.write_text(output.getvalue(), encoding="utf-8", newline="")
    print(f"Updated {len(rows)} rows across {len(YEARS)} seasons in {DATA}")
    print(f"Added {len(STAT_COLUMNS)} NHL regular-season stats; unmatched rows: 0")


if __name__ == "__main__":
    main()
