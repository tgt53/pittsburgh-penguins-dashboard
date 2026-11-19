"""Build team-by-team on/off expected-goals rows for every skater season.

MoneyPuck publishes separate regular-season and playoff skater summary CSVs.
This script keeps every team's all-situations row for player profiles.
"""

from __future__ import annotations

import csv
import io
from urllib.error import HTTPError
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "moneypuck_all_players_on_off_xgoals_2007_08_to_2026_27.csv"
YEARS = range(2007, 2027)  # MoneyPuck season field is the starting year.
TEAM_ALIASES = {"L.A": "LAK", "N.J": "NJD", "S.J": "SJS", "T.B": "TBL"}
FIELDS = [
    "Player ID", "Season", "Game Type", "Team", "Player", "Position", "Games",
    "On-ice minutes", "Off-ice minutes", "xGF on total", "xGA on total",
    "On-ice xG differential", "xGF off total", "xGA off total",
    "Off-ice xG differential", "xGF on per 60", "xGA on per 60",
    "On-ice xG differential per 60", "xGF off per 60", "xGA off per 60",
    "Off-ice xG differential per 60",
]


def download_rows(year: int, game_type: str) -> list[dict[str, str]]:
    url = f"https://moneypuck.com/moneypuck/playerData/seasonSummary/{year}/{game_type}/skaters.csv"
    request = urllib.request.Request(url, headers={"User-Agent": "PenguinsDashboard/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        content = response.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(content)))


def number(row: dict[str, str], key: str) -> float:
    value = row.get(key, "")
    return float(value) if value else 0.0


def main() -> None:
    output_rows: list[dict[str, object]] = []
    for year in YEARS:
        for game_type, game_type_id in (("regular", 2), ("playoffs", 3)):
            try:
                rows = download_rows(year, game_type)
            except HTTPError as error:
                if game_type == "playoffs" and error.code == 404:
                    print(f"No playoff file for {year}-{year + 1}; skipped")
                    continue
                raise
            season_rows = [
                row for row in rows
                if row.get("situation") == "all"
                and row.get("team", "").upper() not in {"", "ALL", "TOT", "2TM", "NHL"}
            ]
            if not season_rows:
                raise RuntimeError(f"No {game_type} all-situations skater rows found for {year}.")
            for row in season_rows:
                on_minutes = number(row, "icetime") / 60
                off_minutes = number(row, "timeOnBench") / 60
                on_xgf = number(row, "OnIce_F_xGoals")
                on_xga = number(row, "OnIce_A_xGoals")
                off_xgf = number(row, "OffIce_F_xGoals")
                off_xga = number(row, "OffIce_A_xGoals")
                output_rows.append({
                    "Player ID": row.get("playerId", ""),
                    "Season": f"{year}-{year + 1}",
                    "Game Type": game_type_id,
                    "Team": TEAM_ALIASES.get(row["team"].upper(), row["team"].upper()),
                    "Player": row["name"],
                    "Position": row.get("position", ""),
                    "Games": int(float(row.get("games_played") or 0)),
                    "On-ice minutes": round(on_minutes, 2),
                    "Off-ice minutes": round(off_minutes, 2),
                    "xGF on total": round(on_xgf, 2),
                    "xGA on total": round(on_xga, 2),
                    "On-ice xG differential": round(on_xgf - on_xga, 2),
                    "xGF off total": round(off_xgf, 2),
                    "xGA off total": round(off_xga, 2),
                    "Off-ice xG differential": round(off_xgf - off_xga, 2),
                    "xGF on per 60": round(on_xgf * 60 / on_minutes, 3) if on_minutes else 0,
                    "xGA on per 60": round(on_xga * 60 / on_minutes, 3) if on_minutes else 0,
                    "On-ice xG differential per 60": round((on_xgf - on_xga) * 60 / on_minutes, 3) if on_minutes else 0,
                    "xGF off per 60": round(off_xgf * 60 / off_minutes, 3) if off_minutes else 0,
                    "xGA off per 60": round(off_xga * 60 / off_minutes, 3) if off_minutes else 0,
                    "Off-ice xG differential per 60": round((off_xgf - off_xga) * 60 / off_minutes, 3) if off_minutes else 0,
                })
            print(f"Loaded {year}-{year + 1} {game_type}: {len(season_rows)} player-team rows")

    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Saved {len(output_rows)} player-team-season rows to {OUTPUT}")


if __name__ == "__main__":
    main()
