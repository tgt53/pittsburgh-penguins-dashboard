# Pittsburgh Penguins Dashboard Project

## MoneyPuck player impact walkthrough

Start with [`notebooks/moneypuck_penguins_impact.ipynb`](notebooks/moneypuck_penguins_impact.ipynb). The notebook explains each step in plain English and includes the raw data preview, cleaned player table, data checks, chart, and short summary. It uses MoneyPuck's 2025–26 regular season Pittsburgh skater CSV.

### Open and run it

1. Open this project folder in VS Code and install the **Jupyter** extension if VS Code offers it.
2. If Python reports missing packages, open VS Code's Terminal and run `python -m pip install -r requirements.txt` once.
3. Open the notebook above. Choose a Python 3 kernel if asked.
4. Choose **Run All** near the top. You can also run one step at a time with **Shift+Enter**; each step's explanation comes first.

The original MoneyPuck CSV is saved at `data/moneypuck_pit_2025_26_skaters_raw.csv`, so the notebook can run without internet. The cleaned table and chart are also included at [`data/penguins_player_impact_2025_26.csv`](data/penguins_player_impact_2025_26.csv) and [`data/penguins_impact_chart_2025_26.png`](data/penguins_impact_chart_2025_26.png).

MoneyPuck's [download page](https://www.moneypuck.com/data.htm) says its listed data is free for non-commercial use and asks for clear credit whenever its data is shown. Keep the attribution in the notebook when sharing its outputs.
