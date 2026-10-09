"""
Mini application web Flask sans authentification (hello world), pour comparaison avec app.py.

Lancement :
    pip install -r requirements.txt
    python app_no_keycloak.py
Puis ouvrir http://localhost:5001
"""
from flask import Flask, render_template_string

app = Flask(__name__)


PAGE = """
<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Appli Python sans Keycloak</title>
<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px}</style></head><body>
<h1>Appli Python sans Keycloak</h1>
<p>{{ message }}</p>
<p><a href="{{ url_for('index') }}">Accueil</a> · <a href="{{ url_for('admin') }}">Zone admin</a></p>
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, message="Hello world !")


@app.route("/admin")
def admin():
    # Aucune protection ici : n'importe qui y accède (comparer avec /admin dans app.py)
    return render_template_string(PAGE, message="Bienvenue dans la zone admin.")


if __name__ == "__main__":
    # Port 5001 pour pouvoir tourner en même temps que app.py (port 5000)
    app.run(host="localhost", port=5001, debug=True)
