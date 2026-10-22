"""Database-backed data helpers for the Penguins dashboard."""

import pymysql

from .db import get_db_connection


def get_penguins_player_impact_rows():
    connection = get_db_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                """SELECT player_id, player_name, position, games_played,
                          ice_time_minutes, on_ice_xg_share_pct,
                          on_ice_shot_attempt_share_pct,
                          individual_expected_goals, individual_actual_goals
                   FROM penguins_player_impact_2025_26
                   ORDER BY player_id
                   LIMIT 10"""
            )
            return list(cursor.fetchall())
    finally:
        connection.close()
