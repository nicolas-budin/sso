"""
Mini application web Flask qui authentifie directement contre l'annuaire LDAP (lldap), sans Keycloak.
Pour comparaison avec app.py : ici l'application reçoit le mot de passe et parle LDAP elle-même.

Principe du login :
    1. bind avec le compte de service (LDAP_BIND_DN) et recherche de l'utilisateur par son uid ;
    2. bind avec le DN trouvé et le mot de passe saisi : s'il réussit, le mot de passe est bon ;
    3. recherche des groupes dont l'utilisateur est membre (attribut member).

Lancement :
    pip install -r requirements.txt
    cp .env.example .env   # puis vérifier LDAP_BIND_PASSWORD
    python app_ldap.py
Puis ouvrir http://localhost:5002
"""
import os
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, redirect, render_template_string, request, session, url_for
from ldap3 import Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

load_dotenv()  # charge le fichier .env s'il existe

LDAP_URL = os.getenv("LDAP_URL", "ldap://localhost:3890")
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=demo,dc=local")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", f"uid=admin,ou=people,{LDAP_BASE_DN}")
LDAP_BIND_PASSWORD = os.environ["LDAP_BIND_PASSWORD"]
USERS_DN = f"ou=people,{LDAP_BASE_DN}"
GROUPS_DN = f"ou=groups,{LDAP_BASE_DN}"
# Pas de rôles en LDAP : on donne l'accès admin directement à un groupe
ADMIN_GROUP = os.getenv("LDAP_ADMIN_GROUP", "informatique")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32))

server = Server(LDAP_URL)


def ldap_authenticate(username: str, password: str) -> dict | None:
    """Vérifie login et mot de passe dans l'annuaire. Renvoie l'utilisateur et ses groupes, ou None."""
    # Un mot de passe vide ferait un bind anonyme qui "réussit" : à refuser explicitement
    if not username or not password:
        return None
    try:
        with Connection(server, LDAP_BIND_DN, LDAP_BIND_PASSWORD, auto_bind=True) as service:
            # escape_filter_chars empêche l'injection LDAP via le nom saisi (ex. "*")
            service.search(USERS_DN, f"(&(objectClass=person)(uid={escape_filter_chars(username)}))",
                           attributes=["uid", "mail", "cn"])
            if len(service.entries) != 1:
                return None
            entry = service.entries[0]
            user_dn = entry.entry_dn

            # Le bind avec le DN de l'utilisateur est la vérification du mot de passe
            user_conn = Connection(server, user_dn, password)
            if not user_conn.bind():
                return None
            user_conn.unbind()

            service.search(GROUPS_DN, f"(member={escape_filter_chars(user_dn)})", attributes=["cn"])
            groups = sorted(str(g.cn) for g in service.entries)
    except LDAPException:
        app.logger.exception("Erreur LDAP")
        return None

    return {
        "username": str(entry.uid),
        "email": str(entry.mail) if entry.mail else "",
        "dn": user_dn,
        "groups": groups,
    }


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


PAGE = """
<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Appli Python + LDAP</title>
<style>body{font-family:system-ui,sans-serif;max-width:720px;margin:40px auto;padding:0 16px}
label{display:block;margin:8px 0}.err{color:#c53030}button{padding:8px 14px;
background:#2b6cb0;color:#fff;border:0;border-radius:6px}</style></head><body>
<h1>Appli Python + LDAP</h1>
{% if user %}
  <p>Connecté en tant que <b>{{ user.username }}</b>{% if user.email %} ({{ user.email }}){% endif %}</p>
  <p>DN : <code>{{ user.dn }}</code></p>
  <p>Groupes : {{ user.groups | join(", ") or "aucun" }}</p>
  <p><a href="{{ url_for('admin') }}">Zone admin</a> · <a href="{{ url_for('logout') }}">Se déconnecter</a></p>
{% else %}
  <form method="post" action="{{ url_for('login') }}">
    <label>Utilisateur <input name="username" autofocus></label>
    <label>Mot de passe <input name="password" type="password"></label>
    <button type="submit">Se connecter</button>
  </form>
  {% if error %}<p class="err">{{ error }}</p>{% endif %}
{% endif %}
{% if message %}<p>{{ message }}</p>{% endif %}
</body></html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, user=session.get("user"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template_string(PAGE, user=None)
    user = ldap_authenticate(request.form.get("username", ""), request.form.get("password", ""))
    if user is None:
        return render_template_string(PAGE, user=None, error="Identifiants invalides."), 401
    session.clear()
    session["user"] = user
    return redirect(url_for("index"))


@app.route("/admin")
@login_required
def admin():
    # Autorisation basée sur un groupe LDAP (dans app.py, c'est un rôle Keycloak)
    user = session["user"]
    if ADMIN_GROUP not in user["groups"]:
        return f"Accès refusé : groupe '{ADMIN_GROUP}' requis.", 403
    return render_template_string(PAGE, user=user, message="Bienvenue dans la zone admin.")


@app.route("/logout")
def logout():
    # Pas de SSO ici : la déconnexion est purement locale
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    # Port 5002 pour pouvoir tourner en même temps que app.py (5000) et app_no_keycloak.py (5001)
    app.run(host="localhost", port=5002, debug=True)
