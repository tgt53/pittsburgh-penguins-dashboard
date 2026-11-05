"""Download and prepare MoneyPuck regular-season Penguins skater on/off xGoals.

Run from the project folder with: python scripts/build_penguins_historical_on_off.py
The downloaded MoneyPuck files are listed public season-summary CSVs. Output is
one row per Penguin per season, retaining MoneyPuck's on-ice/off-ice xG totals
and adding per-60 rates for fairer comparisons across ice time.
"""

from __future__ import annotations

import csv
import io
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "penguins_on_off_xgoals_2008_09_to_2025_26.csv"
YEARS = range(2008, 2026)  # MoneyPuck season field is the ending year.
FIELDS = [
    "Season", "Player", "Position", "Games", "On-ice minutes",
    "Off-ice minutes", "xGF on total", "xGA on total",
    "On-ice xG differential", "xGF off total", "xGA off total",
    "Off-ice xG differential", "xGF on per 60",
    "xGA on per 60", "On-ice xG differential per 60",
    "xGF off per 60", "xGA off per 60",
    "Off-ice xG differential per 60",
]


def download_rows(year: int) -> list[dict[str, str]]:
    url = f"https://moneypuck.com/moneypuck/playerData/seasonSummary/{year}/regular/skaters.csv"
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
        rows = download_rows(year)
        penguins = [r for r in rows if r.get("team") == "PIT" and r.get("situation") == "all"]
        if not penguins:
            raise RuntimeError(f"No Pittsburgh all-situations rows found for {year}.")
        for row in penguins:
            on_minutes = number(row, "icetime") / 60
            off_minutes = number(row, "timeOnBench") / 60
            record: dict[str, object] = {
                "Season": f"{year}-{year + 1}",
                "Player": row["name"],
                "Position": row.get("position", ""),
                "Games": int(float(row["games_played"])),
                "On-ice minutes": round(on_minutes, 2),
                "Off-ice minutes": round(off_minutes, 2),
                "xGF on total": round(number(row, "OnIce_F_xGoals"), 2),
                "xGA on total": round(number(row, "OnIce_A_xGoals"), 2),
                "On-ice xG differential": round(number(row, "OnIce_F_xGoals") - number(row, "OnIce_A_xGoals"), 2),
                "xGF off total": round(number(row, "OffIce_F_xGoals"), 2),
                "xGA off total": round(number(row, "OffIce_A_xGoals"), 2),
                "Off-ice xG differential": round(number(row, "OffIce_F_xGoals") - number(row, "OffIce_A_xGoals"), 2),
                "xGF on per 60": round(number(row, "OnIce_F_xGoals") * 60 / on_minutes, 3) if on_minutes else 0,
                "xGA on per 60": round(number(row, "OnIce_A_xGoals") * 60 / on_minutes, 3) if on_minutes else 0,
                "On-ice xG differential per 60": round((number(row, "OnIce_F_xGoals") - number(row, "OnIce_A_xGoals")) * 60 / on_minutes, 3) if on_minutes else 0,
                "xGF off per 60": round(number(row, "OffIce_F_xGoals") * 60 / off_minutes, 3) if off_minutes else 0,
                "xGA off per 60": round(number(row, "OffIce_A_xGoals") * 60 / off_minutes, 3) if off_minutes else 0,
                "Off-ice xG differential per 60": round((number(row, "OffIce_F_xGoals") - number(row, "OffIce_A_xGoals")) * 60 / off_minutes, 3) if off_minutes else 0,
            }
            output_rows.append(record)

    OUTPUT.parent.mkdir(exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"Saved {len(output_rows)} player-season rows to {OUTPUT}")
    print(f"Seasons: {len({row['Season'] for row in output_rows})}; players: {len({row['Player'] for row in output_rows})}")


if __name__ == "__main__":
    main()
