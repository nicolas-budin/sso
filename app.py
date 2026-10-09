"""
Mini application web Flask protégée par Keycloak (OpenID Connect, authorization code flow).

Lancement :
    pip install -r requirements.txt
    cp .env.example .env   # puis y mettre KEYCLOAK_CLIENT_SECRET (onglet "Credentials" du client)
    python app.py
Puis ouvrir http://localhost:5000
"""
import base64
import json
import os
from functools import wraps
from urllib.parse import urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, session, url_for

load_dotenv()  # charge le fichier .env s'il existe

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
REALM = os.getenv("KEYCLOAK_REALM", "demo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "python-app")
CLIENT_SECRET = os.environ["KEYCLOAK_CLIENT_SECRET"]
ISSUER = f"{KEYCLOAK_URL}/realms/{REALM}"

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32))

oauth = OAuth(app)
oauth.register(
    name="keycloak",
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    # Authlib découvre automatiquement les endpoints (authorize, token, logout, clés JWKS...)
    server_metadata_url=f"{ISSUER}/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile email"},
)


def jwt_claims(token: str) -> dict:
    """Décode le contenu d'un JWT sans vérifier la signature.
    Acceptable ici uniquement parce que le jeton vient d'être reçu directement
    du endpoint token de Keycloak (échange serveur à serveur)."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


PAGE = """
<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Appli Python + Keycloak</title>
<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px}
pre{background:#f4f4f4;padding:12px;overflow:auto}a.btn{display:inline-block;padding:8px 14px;
background:#2b6cb0;color:#fff;border-radius:6px;text-decoration:none}</style></head><body>
<h1>Appli Python + Keycloak</h1>
{% if user %}
  <p>Connecté en tant que <b>{{ user.preferred_username }}</b> ({{ user.email }})</p>
  <p>Groupes : {{ user.groups | join(", ") or "aucun" }}</p>
  <p>Rôles (realm) : {{ user.roles | join(", ") or "aucun" }}</p>
  <p><a href="{{ url_for('protected') }}">Page protégée</a> · <a href="{{ url_for('logout') }}">Se déconnecter</a></p>
{% else %}
  <p>Vous n'êtes pas connecté.</p>
  <a class="btn" href="{{ url_for('login') }}">Se connecter avec Keycloak</a>
{% endif %}
{% if extra %}<h2>{{ extra.title }}</h2><pre>{{ extra.body }}</pre>{% endif %}
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, user=session.get("user"), extra=None)


@app.route("/login")
def login():
    # Redirige le navigateur vers la page de login de Keycloak
    return oauth.keycloak.authorize_redirect(url_for("callback", _external=True))


@app.route("/callback")
def callback():
    # Keycloak renvoie un "code" ; Authlib l'échange contre les jetons
    # et vérifie la signature de l'ID token
    token = oauth.keycloak.authorize_access_token()
    userinfo = token["userinfo"]
    access = jwt_claims(token["access_token"])

    session["user"] = {
        "preferred_username": userinfo.get("preferred_username"),
        "email": userinfo.get("email"),
        "groups": userinfo.get("groups", []),  # nécessite le mapper "Group Membership"
        "roles": access.get("realm_access", {}).get("roles", []),
        "claims": access,
    }
    session["id_token"] = token["id_token"]
    return redirect(url_for("index"))


@app.route("/protected")
@login_required
def protected():
    user = session["user"]
    extra = {
        "title": "Contenu de l'access token",
        "body": json.dumps(user["claims"], indent=2, ensure_ascii=False),
    }
    return render_template_string(PAGE, user=user, extra=extra)


@app.route("/admin")
@login_required
def admin():
    # Exemple d'autorisation basée sur un rôle Keycloak
    if "admin" not in session["user"]["roles"]:
        return "Accès refusé : rôle 'admin' requis.", 403
    return "Bienvenue dans la zone admin."


@app.route("/logout")
def logout():
    # Déconnexion locale + déconnexion de la session SSO Keycloak
    id_token = session.pop("id_token", None)
    session.clear()
    end_session = oauth.keycloak.load_server_metadata()["end_session_endpoint"]
    params = {"post_logout_redirect_uri": url_for("index", _external=True), "client_id": CLIENT_ID}
    if id_token:
        params["id_token_hint"] = id_token
    return redirect(f"{end_session}?{urlencode(params)}")


if __name__ == "__main__":
    app.run(host="localhost", port=5000, debug=True)
