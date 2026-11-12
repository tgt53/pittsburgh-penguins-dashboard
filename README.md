# Pittsburgh Penguins Dashboard

This site focuses on Pittsburgh Penguins regular-season on/off expected goals from 2008–09 through 2025–26. The home page includes a season trend chart, a searchable player-season table, and a CSV download.

## What the numbers mean

Each row in the table represents one Penguins skater in one season. xGF is expected goals for; xGA is expected goals against. On-ice totals cover the time that player was on the ice. Off-ice totals cover the team's events while that player was on the bench. The on-ice and off-ice differentials equal xGF minus xGA; positive values mean xGF was higher. Per-60 rates divide the total by the relevant minutes and multiply by 60, which helps compare players and seasons with different playing time. Differential per 60 is the xGF minus xGA rate over 60 minutes.

The chart includes players who appeared in at least 10 games and weights each player's rate by their on-ice or off-ice minutes. It is a descriptive comparison, not evidence that a player caused a change.

## Refresh the historical data

Run this from the project folder when you want to rebuild the dataset:

```powershell
python scripts/build_penguins_historical_on_off.py
```

The script downloads MoneyPuck's public regular-season skater CSV for each season year 2008 through 2025. It keeps Pittsburgh rows marked `situation=all`, selects on-ice and off-ice expected goals and time, and writes one row per player per season to `data/penguins_on_off_xgoals_2008_09_to_2025_26.csv`. The current file has 556 rows across 18 seasons.

## Refresh the standard player stats

After rebuilding the MoneyPuck file, run:

```powershell
python scripts/enrich_penguins_historical_stats.py
```

This adds goals, assists, points, plus/minus, penalty minutes, power-play goals and points, short-handed goals, time on ice per game, game-winning goals, overtime goals, shots, shooting percentage, and faceoff win percentage. The script uses MoneyPuck player IDs to join Pittsburgh-only NHL Stats API regular-season totals to each season row. Time on ice is shown in minutes per game; shooting and faceoff percentages are shown as percentages. Faceoff percentage is blank when the NHL source has no faceoff attempts. The public NHL endpoint is `https://api.nhle.com/stats/rest/en/skater/summary`.

MoneyPuck's dataset is credited on the dashboard; the conventional season stats come from the [NHL Stats API](https://api.nhle.com/stats/rest/en/skater/summary).

MoneyPuck asks that its data be clearly credited whenever shown. The site links to [MoneyPuck's data page](https://moneypuck.com/data.htm).

## Run the site

Install dependencies with `python -m pip install -r requirements.txt`, then run `python main.py` from the project folder and open the local address shown in the terminal.
