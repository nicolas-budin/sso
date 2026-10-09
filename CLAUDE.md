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
  - **Toute la configuration du realm est dans `keycloak/realm-demo.json`**, importé au démarrage (`--import-realm`). C'est la source de vérité : toute modification de config Keycloak doit y être reportée.
  - L'import est ignoré si le realm existe déjà : pour réimporter, `docker compose down -v && docker compose up -d`.
  - Les groupes LDAP sont synchronisés dans Keycloak ; les **realm roles** (ex. `admin`) sont assignés aux groupes dans Keycloak. Le groupe `informatique` est pré-créé dans le JSON avec le rôle `admin` ; le mapper LDAP le réutilise par son nom.
  - Clients : `test-cli` (public, direct access grants, tests curl) et `python-app` (confidentiel, standard flow).
  - Mapper "Group Membership" → claim `groups` (sans chemin complet) sur chaque client.
- **app.py** : Flask + Authlib, flux authorization code. Routes : `/`, `/login`, `/callback`, `/protected`, `/admin` (exige le rôle `admin`), `/logout` (déconnexion SSO via `end_session_endpoint`).

## Démarrage

```bash
docker compose up -d            # importe le realm demo automatiquement
# créer alice/bob et les groupes informatique/rh dans lldap (http://localhost:17170)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # le secret de labo de python-app est déjà renseigné
python app.py
```

Variables d'environnement : `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` (obligatoire, `python-app-secret-labo` en labo), `FLASK_SECRET_KEY`.

Les utilisateurs LDAP sont importés dans Keycloak à leur première connexion ; pas besoin de lancer une synchronisation manuelle.

## Utilisateurs de test

- `alice` ∈ groupe `informatique` → rôle `admin`
- `bob` ∈ groupe `rh` → aucun rôle particulier

## Conventions

- Commentaires, messages et documentation en français.
- Ne jamais committer de secrets : `.env` est dans `.gitignore`.
- Les jetons sont vérifiés par Authlib à la réception ; ne pas réutiliser `jwt_claims()` (décodage sans vérification) pour des jetons venant du navigateur.
- Les mots de passe du `docker-compose.yml` sont des valeurs de labo, à changer avant toute autre utilisation.

## Pistes d'évolution

- Automatiser aussi la création des utilisateurs et groupes lldap (API GraphQL de lldap).
- Ajouter une seconde appli pour démontrer le SSO entre deux applications.
- Protéger une API par bearer token (validation du JWT via JWKS).
- Variante Spring Boot (Spring Security en client OIDC).
