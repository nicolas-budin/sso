# Labo SSO : Keycloak + LDAP + Python

Projet d'apprentissage pour comprendre l'authentification centralisée : un annuaire LDAP (lldap) contient les utilisateurs et les groupes, Keycloak s'appuie dessus pour faire du SSO OpenID Connect, et de petites applications Flask montrent trois façons de gérer (ou non) le login.

> Usage local uniquement. Les mots de passe et secrets du dépôt sont des valeurs de labo.

```
Navigateur ──> app.py (:5000) ──OIDC──> Keycloak (:8080) ──LDAP──> lldap (:3890)
Navigateur ──> app_ldap.py (:5002) ─────────────LDAP─────────────> lldap (:3890)
Navigateur ──> app_no_keycloak.py (:5001)        (aucune authentification)
```

## Contenu

| Fichier | Rôle |
|---|---|
| `docker-compose.yml` | Lance **lldap** (annuaire LDAP + UI web) et **Keycloak** 26 en mode `start-dev`. |
| `keycloak/realm-demo.json` | Configuration complète du realm `demo`, importée au premier démarrage : fédération LDAP en lecture seule, synchronisation des groupes, rôle `admin` donné au groupe `informatique`, clients `test-cli` et `python-app`. |
| `app.py` | Appli Flask + Authlib qui délègue le login à Keycloak (flux *authorization code*). Lit les groupes dans l'ID token et les rôles dans l'access token ; `/admin` exige le rôle `admin`. Déconnexion SSO. |
| `app_ldap.py` | Même idée **sans Keycloak** : formulaire de login, vérification du mot de passe par un *bind* LDAP, lecture des groupes dans l'annuaire ; `/admin` exige le groupe `informatique`. |
| `app_no_keycloak.py` | Hello world Flask sans authentification, comme point de comparaison. |
| `Labo-SSO-Keycloak-LDAP.md` | Le cours : notions LDAP et Keycloak, groupes et rôles, et le labo pas à pas. **À lire pour comprendre le pourquoi.** |
| `.env.example` | Modèle des variables d'environnement, à copier en `.env`. |

## Démarrage

Prérequis : Docker et Python 3.10+.

```bash
docker compose up -d                  # lldap + Keycloak, le realm "demo" est importé automatiquement
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Puis, dans l'UI de lldap (http://localhost:17170, `admin` / `ChangeMe-ldap-2026`), créer les utilisateurs de test :

| Utilisateur | Groupe | Effet |
|---|---|---|
| `alice` | `informatique` | rôle Keycloak `admin`, accès à `/admin` |
| `bob` | `rh` | aucun droit particulier |

Lancer ensuite une ou plusieurs applis (elles peuvent tourner en même temps) :

```bash
python app.py              # http://localhost:5000  (SSO via Keycloak)
python app_ldap.py         # http://localhost:5002  (LDAP direct)
python app_no_keycloak.py  # http://localhost:5001  (sans authentification)
```

## Accès utiles

| Service | URL | Identifiants |
|---|---|---|
| lldap (UI web) | http://localhost:17170 | `admin` / `ChangeMe-ldap-2026` |
| Keycloak (console d'admin) | http://localhost:8080 | `admin` / `admin` |
| Compte utilisateur Keycloak | http://localhost:8080/realms/demo/account | utilisateurs LDAP |

## Ce qu'on peut observer

- **Le SSO** : connecté dans `app.py`, ouvrir la console de compte Keycloak ne redemande pas le mot de passe.
- **Le contenu des jetons** : la page `/protected` de `app.py` affiche l'access token décodé (`groups`, `realm_access.roles`, `exp`…).
- **Rôles contre groupes** : `alice` accède à `/admin` dans les deux applis, mais `app.py` teste un *rôle* Keycloak alors que `app_ldap.py` teste un *groupe* LDAP.
- **Qui voit le mot de passe** : avec `app.py`, seul Keycloak le reçoit ; avec `app_ldap.py`, l'application le manipule elle-même.

Pour tester sans navigateur :

```bash
curl -s http://localhost:8080/realms/demo/protocol/openid-connect/token \
  -d client_id=test-cli -d grant_type=password -d scope=openid \
  -d username=alice -d password='MOT_DE_PASSE_ALICE'
```

## Modifier la configuration Keycloak

`keycloak/realm-demo.json` est la source de vérité. Une modification faite dans la console d'admin est perdue au prochain `docker compose down -v` si elle n'est pas reportée dans ce fichier. L'import est ignoré quand le realm existe déjà ; pour réimporter :

```bash
docker compose down -v && docker compose up -d
```

Attention : `-v` efface aussi les volumes de lldap, donc les utilisateurs et groupes de l'annuaire.

## Variables d'environnement

| Variable | Utilisée par | Défaut |
|---|---|---|
| `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID` | `app.py` | `http://localhost:8080`, `demo`, `python-app` |
| `KEYCLOAK_CLIENT_SECRET` | `app.py` | obligatoire (`python-app-secret-labo` en labo) |
| `LDAP_URL`, `LDAP_BASE_DN`, `LDAP_BIND_DN` | `app_ldap.py` | `ldap://localhost:3890`, `dc=demo,dc=local`, compte `admin` |
| `LDAP_BIND_PASSWORD` | `app_ldap.py` | obligatoire |
| `LDAP_ADMIN_GROUP` | `app_ldap.py` | `informatique` |
| `FLASK_SECRET_KEY` | `app.py`, `app_ldap.py` | aléatoire à chaque lancement ; mettre une vraie valeur, par exemple `python -c "import secrets; print(secrets.token_hex(32))"` |
