from flask import Flask, render_template
from app.main import get_penguins_player_impact_rows

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")


@app.route("/")
def home():
    players = get_penguins_player_impact_rows()
    return render_template("index.html", players=players)
