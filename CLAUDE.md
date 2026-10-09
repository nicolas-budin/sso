# Labo SSO : Keycloak + LDAP + appli Python

Projet d'apprentissage pour tester un SSO OpenID Connect avec Keycloak, qui lit les utilisateurs et les groupes dans un annuaire LDAP. Usage local uniquement.

## Architecture

```
Navigateur ──> app Flask (localhost:5000) ──OIDC──> Keycloak (localhost:8080) ──LDAP──> lldap (localhost:3890)
```

- **lldap** : annuaire LDAP léger, source des utilisateurs et des groupes. UI web sur http://localhost:17170.
  - Base DN : `dc=demo,dc=local`
  - Utilisateurs : `ou=people,dc=demo,dc=local` (RDN `uid`, objectClass `person`)
  - Groupes : `ou=groups,dc=demo,dc=local` (objectClass `groupOfUniqueNames`, membres via `member`)
  - Compte de bind : `uid=admin,ou=people,dc=demo,dc=local`
- **Keycloak** (26.x, mode `start-dev`) : realm `demo`, User Federation LDAP en READ_ONLY + `group-ldap-mapper`.
  - Les groupes LDAP sont synchronisés dans Keycloak ; les **realm roles** (ex. `admin`) sont assignés aux groupes dans Keycloak.
  - Clients : `test-cli` (public, direct access grants, tests curl) et `python-app` (confidentiel, standard flow).
  - Mapper "Group Membership" → claim `groups` (sans chemin complet) sur chaque client.
- **app.py** : Flask + Authlib, flux authorization code. Routes : `/`, `/login`, `/callback`, `/protected`, `/admin` (exige le rôle `admin`), `/logout` (déconnexion SSO via `end_session_endpoint`).

## Démarrage

```bash
docker compose up -d
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # puis renseigner KEYCLOAK_CLIENT_SECRET
python app.py
```

Variables d'environnement : `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` (obligatoire), `FLASK_SECRET_KEY`.

## Utilisateurs de test

- `alice` ∈ groupe `informatique` → rôle `admin`
- `bob` ∈ groupe `rh` → aucun rôle particulier

## Conventions

- Commentaires, messages et documentation en français.
- Ne jamais committer de secrets : `.env` est dans `.gitignore`.
- Les jetons sont vérifiés par Authlib à la réception ; ne pas réutiliser `jwt_claims()` (décodage sans vérification) pour des jetons venant du navigateur.
- Les mots de passe du `docker-compose.yml` sont des valeurs de labo, à changer avant toute autre utilisation.

## Pistes d'évolution

- Exporter la config du realm (`kc.sh export`) et l'importer au démarrage (`--import-realm`) pour éviter la configuration manuelle.
- Ajouter une seconde appli pour démontrer le SSO entre deux applications.
- Protéger une API par bearer token (validation du JWT via JWKS).
- Variante Spring Boot (Spring Security en client OIDC).
