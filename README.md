# Pittsburgh Penguins Dashboard Project

## MoneyPuck player impact walkthrough

Start with [`notebooks/moneypuck_penguins_impact.ipynb`](notebooks/moneypuck_penguins_impact.ipynb). The notebook explains each step in plain English and includes the raw data preview, cleaned player table, data checks, chart, and short summary. It uses MoneyPuck's 2025-26 regular season Pittsburgh skater CSV.

### Open and run it

1. Open this project folder in VS Code and install the **Jupyter** extension if VS Code offers it.
2. If Python reports missing packages, open VS Code's Terminal and run `python -m pip install -r requirements.txt` once.
3. Open the notebook above. Choose a Python 3 kernel if asked.
4. Choose **Run All** near the top. You can also run one step at a time with **Shift+Enter**; each step's explanation comes first.

The original MoneyPuck CSV is saved at `data/moneypuck_pit_2025_26_skaters_raw.csv`, so the notebook can run without internet. The cleaned table and chart are also included at [`data/penguins_player_impact_2025_26.csv`](data/penguins_player_impact_2025_26.csv) and [`data/penguins_impact_chart_2025_26.png`](data/penguins_impact_chart_2025_26.png).

For a deeper comparison of on-ice expected goals, see [`notebooks/moneypuck_penguins_xgoal_compound.ipynb`](notebooks/moneypuck_penguins_xgoal_compound.ipynb). It shows expected goals for, against, the difference, rates per 60 minutes, and an equally weighted combined score. The table and chart are saved as [`data/penguins_xgoal_compound_2025_26.csv`](data/penguins_xgoal_compound_2025_26.csv) and [`data/penguins_xgoal_compound_2025_26.png`](data/penguins_xgoal_compound_2025_26.png).

For on-ice versus off-ice expected goals, see [`notebooks/moneypuck_penguins_on_off_xgoals.ipynb`](notebooks/moneypuck_penguins_on_off_xgoals.ipynb). It compares each qualifying player's xGF and xGA rates per 60 using MoneyPuck's recorded on-ice and bench time. The table and chart are saved as [`data/penguins_on_off_xgoals_2025_26.csv`](data/penguins_on_off_xgoals_2025_26.csv) and [`data/penguins_on_off_xgoals_2025_26.png`](data/penguins_on_off_xgoals_2025_26.png).

MoneyPuck's [download page](https://www.moneypuck.com/data.htm) says its listed data is free for non-commercial use and asks for clear credit whenever its data is shown. Keep the attribution in the notebook when sharing its outputs.

## Load the MoneyPuck tables into TiDB

The database loader writes to the non-system `test` schema. It creates four tables: `moneypuck_pit_skaters_raw_2025_26` (all raw rows preserved as JSON), `penguins_player_impact_2025_26` (the cleaned player table), `penguins_xgoal_compound_2025_26` (players meeting the comparison cutoffs), and `penguins_on_off_xgoals_2025_26` (the on-ice versus off-ice xGoals rates). The loader checks the source files and uses upserts, so rerunning it updates matching rows instead of duplicating them.

Keep the connection URL in the ignored `.env` file as `TIDB_URL=mysql://USER:PASSWORD@HOST:4000/test`. Use the `test` database path; the loader refuses to write into TiDB's built-in `sys` schema. Install project dependencies with `python -m pip install -r requirements.txt`, then run `python scripts/load_moneypuck_to_tidb.py` from the project folder. Never commit `.env`.
