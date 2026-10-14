"""Load the saved 2025-26 MoneyPuck Penguins data into TiDB's `test` schema.

The database URL is read from the ignored local .env file (TIDB_URL). It must
point to the non-system `test` schema. The import validates both CSV files,
then upserts rows so rerunning it does not create duplicates. It also imports
the rate-based composite impact table when its analysis CSV is present.
"""

from __future__ import annotations

import csv
import json
import os
import ssl
from pathlib import Path
from urllib.parse import unquote, urlparse

import certifi
import pymysql


PROJECT_DIR = Path(__file__).resolve().parents[1]
LATEST_RAW_CSV = PROJECT_DIR / "data" / "moneypuck_pit_2025_26_skaters_latest.csv"
RAW_CSV = LATEST_RAW_CSV if LATEST_RAW_CSV.exists() else PROJECT_DIR / "data" / "moneypuck_pit_2025_26_skaters_raw.csv"
CLEAN_CSV = PROJECT_DIR / "data" / "penguins_player_impact_2025_26.csv"
COMPOUND_CSV = PROJECT_DIR / "data" / "penguins_xgoal_compound_2025_26.csv"
EXPECTED_DATABASE = "test"


def read_local_env() -> None:
    """Read simple KEY=VALUE lines without printing any secret values."""
    env_path = PROJECT_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Expected input file is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def to_int(value: str) -> int:
    return int(float(value))


def main() -> None:
    read_local_env()
    connection_url = os.environ.get("TIDB_URL")
    if not connection_url:
        raise SystemExit("Add TIDB_URL to your local .env file before running this loader.")

    parsed = urlparse(connection_url)
    database = parsed.path.strip("/")
    if parsed.scheme != "mysql" or not parsed.hostname or not parsed.username or not parsed.password:
        raise SystemExit("TIDB_URL must be a complete mysql:// connection URL.")
    if database != EXPECTED_DATABASE:
        raise SystemExit(
            f"This loader only writes to the non-system `{EXPECTED_DATABASE}` schema; "
            "do not point it at `sys`."
        )

    raw_rows = read_csv(RAW_CSV)
    clean_rows = read_csv(CLEAN_CSV)
    compound_rows = read_csv(COMPOUND_CSV) if COMPOUND_CSV.exists() else []
    if not raw_rows or not clean_rows:
        raise SystemExit("One of the MoneyPuck CSV files is empty.")

    raw_keys = [
        (to_int(row["playerId"]), to_int(row["season"]), row["situation"])
        for row in raw_rows
    ]
    if len(raw_keys) != len(set(raw_keys)):
        raise SystemExit("Raw CSV contains duplicate player/season/situation rows.")
    if any(row["team"] != "PIT" for row in raw_rows):
        raise SystemExit("Raw CSV includes a team other than PIT.")

    all_situation_ids = {
        row["name"].strip(): to_int(row["playerId"])
        for row in raw_rows
        if row["situation"] == "all"
    }
    clean_names = [row["Player"].strip() for row in clean_rows]
    if len(clean_names) != len(set(clean_names)):
        raise SystemExit("Clean CSV contains duplicate player names.")
    if any(name not in all_situation_ids for name in clean_names):
        raise SystemExit("A clean-table player could not be matched to the raw data.")
    for row in clean_rows:
        if to_int(row["Games"]) < 10:
            raise SystemExit("Clean CSV includes a player below the 10-game minimum.")
        if not 0 <= float(row["On-ice xG share (%)"]) <= 100:
            raise SystemExit("Clean CSV contains an invalid expected-goal share.")
        if not 0 <= float(row["On-ice shot attempt share (%)"]) <= 100:
            raise SystemExit("Clean CSV contains an invalid shot-attempt share.")
    compound_names = [row["Player"].strip() for row in compound_rows]
    if len(compound_names) != len(set(compound_names)):
        raise SystemExit("Compound CSV contains duplicate player names.")
    for row in compound_rows:
        if row["Player"].strip() not in all_situation_ids:
            raise SystemExit("A compound-table player could not be matched to the raw data.")
        if to_int(row["Games"]) < 10 or float(row["Minutes"]) < 300:
            raise SystemExit("Compound CSV includes a player below its sample-size cutoff.")
        if abs(float(row["xG difference"]) - (float(row["xGF"]) - float(row["xGA"]))) > 0.02:
            raise SystemExit("Compound CSV contains an inconsistent xGoals difference.")

    tls_context = ssl.create_default_context(cafile=certifi.where())
    connection = pymysql.connect(
        host=parsed.hostname,
        port=parsed.port or 3306,
        user=unquote(parsed.username),
        password=unquote(parsed.password),
        database=database,
        ssl=tls_context,
        connect_timeout=20,
        read_timeout=60,
        write_timeout=60,
        autocommit=False,
        charset="utf8mb4",
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS moneypuck_pit_skaters_raw_2025_26 (
                    player_id BIGINT NOT NULL,
                    season SMALLINT NOT NULL,
                    player_name VARCHAR(120) NOT NULL,
                    team CHAR(3) NOT NULL,
                    position VARCHAR(12),
                    situation VARCHAR(20) NOT NULL,
                    games_played SMALLINT,
                    ice_time_seconds DOUBLE,
                    raw_record JSON NOT NULL,
                    PRIMARY KEY (player_id, season, situation)
                )"""
            )
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS penguins_player_impact_2025_26 (
                    player_id BIGINT NOT NULL PRIMARY KEY,
                    player_name VARCHAR(120) NOT NULL,
                    position VARCHAR(12),
                    games_played SMALLINT NOT NULL,
                    ice_time_minutes DECIMAL(10, 1) NOT NULL,
                    on_ice_xg_share_pct DECIMAL(5, 1) NOT NULL,
                    on_ice_shot_attempt_share_pct DECIMAL(5, 1) NOT NULL,
                    individual_expected_goals DECIMAL(10, 1) NOT NULL,
                    individual_actual_goals INT NOT NULL
                )"""
            )
            if compound_rows:
                cursor.execute(
                    """CREATE TABLE IF NOT EXISTS penguins_xgoal_compound_2025_26 (
                        player_id BIGINT NOT NULL PRIMARY KEY,
                        rank_number SMALLINT NOT NULL,
                        player_name VARCHAR(120) NOT NULL,
                        position VARCHAR(12),
                        games_played SMALLINT NOT NULL,
                        ice_time_minutes DECIMAL(10, 2) NOT NULL,
                        on_ice_xg_for DECIMAL(10, 2) NOT NULL,
                        on_ice_xg_against DECIMAL(10, 2) NOT NULL,
                        on_ice_xg_difference DECIMAL(10, 2) NOT NULL,
                        xg_for_per_60 DECIMAL(10, 2) NOT NULL,
                        xg_against_per_60 DECIMAL(10, 2) NOT NULL,
                        xg_difference_per_60 DECIMAL(10, 2) NOT NULL,
                        combined_impact_score DECIMAL(10, 2) NOT NULL
                    )"""
                )

            raw_sql = """INSERT INTO moneypuck_pit_skaters_raw_2025_26
                (player_id, season, player_name, team, position, situation,
                 games_played, ice_time_seconds, raw_record)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE player_name=VALUES(player_name),
                    team=VALUES(team), position=VALUES(position),
                    games_played=VALUES(games_played),
                    ice_time_seconds=VALUES(ice_time_seconds), raw_record=VALUES(raw_record)"""
            cursor.executemany(
                raw_sql,
                [
                    (
                        to_int(row["playerId"]),
                        to_int(row["season"]),
                        row["name"].strip(),
                        row["team"],
                        row["position"] or None,
                        row["situation"],
                        to_int(row["games_played"]) if row["games_played"] else None,
                        float(row["icetime"]) if row["icetime"] else None,
                        json.dumps(row, ensure_ascii=False, allow_nan=False),
                    )
                    for row in raw_rows
                ],
            )
            if compound_rows:
                compound_sql = """INSERT INTO penguins_xgoal_compound_2025_26
                    (player_id, rank_number, player_name, position, games_played,
                     ice_time_minutes, on_ice_xg_for, on_ice_xg_against,
                     on_ice_xg_difference, xg_for_per_60, xg_against_per_60,
                     xg_difference_per_60, combined_impact_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE rank_number=VALUES(rank_number),
                        player_name=VALUES(player_name), position=VALUES(position),
                        games_played=VALUES(games_played),
                        ice_time_minutes=VALUES(ice_time_minutes),
                        on_ice_xg_for=VALUES(on_ice_xg_for),
                        on_ice_xg_against=VALUES(on_ice_xg_against),
                        on_ice_xg_difference=VALUES(on_ice_xg_difference),
                        xg_for_per_60=VALUES(xg_for_per_60),
                        xg_against_per_60=VALUES(xg_against_per_60),
                        xg_difference_per_60=VALUES(xg_difference_per_60),
                        combined_impact_score=VALUES(combined_impact_score)"""
                cursor.executemany(
                    compound_sql,
                    [
                        (
                            all_situation_ids[row["Player"].strip()],
                            to_int(row["Rank"]),
                            row["Player"].strip(),
                            row["Position"] or None,
                            to_int(row["Games"]),
                            float(row["Minutes"]),
                            float(row["xGF"]),
                            float(row["xGA"]),
                            float(row["xG difference"]),
                            float(row["xGF per 60"]),
                            float(row["xGA per 60"]),
                            float(row["xG difference per 60"]),
                            float(row["Combined impact score"]),
                        )
                        for row in compound_rows
                    ],
                )

            clean_sql = """INSERT INTO penguins_player_impact_2025_26
                (player_id, player_name, position, games_played, ice_time_minutes,
                 on_ice_xg_share_pct, on_ice_shot_attempt_share_pct,
                 individual_expected_goals, individual_actual_goals)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE player_name=VALUES(player_name),
                    position=VALUES(position), games_played=VALUES(games_played),
                    ice_time_minutes=VALUES(ice_time_minutes),
                    on_ice_xg_share_pct=VALUES(on_ice_xg_share_pct),
                    on_ice_shot_attempt_share_pct=VALUES(on_ice_shot_attempt_share_pct),
                    individual_expected_goals=VALUES(individual_expected_goals),
                    individual_actual_goals=VALUES(individual_actual_goals)"""
            cursor.executemany(
                clean_sql,
                [
                    (
                        all_situation_ids[row["Player"].strip()],
                        row["Player"].strip(),
                        row["Pos"] or None,
                        to_int(row["Games"]),
                        float(row["Ice time (min)"]),
                        float(row["On-ice xG share (%)"]),
                        float(row["On-ice shot attempt share (%)"]),
                        float(row["Expected goals"]),
                        to_int(row["Actual goals"]),
                    )
                    for row in clean_rows
                ],
            )
        connection.commit()

        with connection.cursor() as cursor:
            for table in (
                "moneypuck_pit_skaters_raw_2025_26",
                "penguins_player_impact_2025_26",
            ):
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                print(f"{table}: {cursor.fetchone()[0]} rows")
            if compound_rows:
                cursor.execute("SELECT COUNT(*) FROM penguins_xgoal_compound_2025_26")
                print(f"penguins_xgoal_compound_2025_26: {cursor.fetchone()[0]} rows")
        print(f"Loaded {len(raw_rows)} raw situation rows, {len(clean_rows)} cleaned player rows, and {len(compound_rows)} compound impact rows into `{database}`.")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
