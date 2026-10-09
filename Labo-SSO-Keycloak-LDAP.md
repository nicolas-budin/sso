# Labo SSO : Keycloak + LDAP

9 octobre 2026 · Nicolas

Ce document reprend une conversation d'apprentissage sur l'authentification centralisée. Il explique LDAP et Keycloak, puis décrit pas à pas un labo local où une application Python se connecte en SSO via Keycloak, qui lit les utilisateurs et les groupes dans un annuaire LDAP (lldap).

En une phrase : **l'annuaire LDAP dit qui existe et dans quels groupes, Keycloak traduit ça en jetons et en rôles, et l'application ne fait que lire le jeton.**

```
┌────────────────┐  HTTP  ┌───────────────────┐  OIDC  ┌──────────────────┐  LDAP  ┌──────────────────┐
│ Navigateur     │ ─────> │ Application Flask │ ─────> │ Keycloak         │ ─────> │ Annuaire lldap   │
│ alice, bob     │        │ localhost:5000    │        │ localhost:8080   │        │ localhost:3890   │
│ l'utilisateur  │        │ lit le jeton      │        │ groupes → rôles  │        │ utilisateurs     │
│ se connecte    │        │ vérifie les rôles │        │ émet les jetons  │        │ et groupes       │
└────────────────┘        └───────────────────┘        └──────────────────┘        └──────────────────┘
```

L'application ne parle jamais à l'annuaire : elle délègue le login à Keycloak, qui seul interroge lldap.

## LDAP

LDAP (*Lightweight Directory Access Protocol*) est un **protocole standard pour interroger et modifier un annuaire**, une base de données optimisée pour décrire les utilisateurs, groupes, machines et ressources d'une organisation.

### À quoi ça sert

- **Authentification centralisée** : les applications vérifient login et mot de passe auprès du même annuaire et récupèrent les groupes de l'utilisateur, donc ses droits.
- **Carnet d'adresses d'entreprise** : e-mail, téléphone, service.

### Ce que contient un annuaire

LDAP ne connaît pas vraiment les notions d'« utilisateur » ou de « groupe » : c'est un arbre d'entrées génériques, dont le type est donné par leurs *objectClass*. Utilisateurs et groupes sont simplement les entrées les plus courantes.

| Type d'entrée | objectClass courants | Attributs typiques |
| --- | --- | --- |
| Utilisateur | `person`, `inetOrgPerson`, `posixAccount` | `uid`, `cn`, `mail`, `userPassword` |
| Groupe | `groupOfNames`, `groupOfUniqueNames`, `posixGroup` | `cn`, `member` (liste des DN des membres) |
| Conteneur | `organizationalUnit` | `ou` |

On peut aussi y ranger des machines, imprimantes, comptes de service, règles sudo, etc. Active Directory y stocke en plus les ordinateurs du domaine et les GPO.

### DN, OU et les autres préfixes

Le **DN** (*Distinguished Name*) est l'identifiant unique et complet d'une entrée, comme le chemin complet d'un fichier. Il se lit de droite à gauche, de la racine vers l'entrée :

```
uid=alice,ou=people,dc=demo,dc=local
```

C'est l'équivalent de `/local/demo/people/alice`.

| Préfixe | Signification | Rôle |
| --- | --- | --- |
| `dc` | *Domain Component* | Morceaux du nom de domaine, qui forment la racine (`dc=demo,dc=local` pour demo.local) |
| `ou` | *Organizational Unit* | Conteneur, l'équivalent d'un dossier (par service, par site…) |
| `cn` | *Common Name* | Nom d'une entrée, souvent un groupe ou le nom complet d'une personne dans AD |
| `uid` | *User ID* | Identifiant de connexion d'un utilisateur |

Le premier élément d'un DN (`uid=alice`) s'appelle le **RDN** (*Relative Distinguished Name*) : le nom de l'entrée dans son conteneur, comme un nom de fichier dans son dossier.

### Zoom sur dc (Domain Component)

`dc` forme la **racine** de l'arbre LDAP à partir d'un nom de domaine DNS : chaque morceau du domaine séparé par un point devient un `dc`.

| Nom de domaine | Racine LDAP (base DN) |
| --- | --- |
| `demo.local` | `dc=demo,dc=local` |
| `entreprise.ch` | `dc=entreprise,dc=ch` |
| `ad.entreprise.ch` | `dc=ad,dc=entreprise,dc=ch` |

On le lit de droite à gauche : `dc=local` est le niveau le plus haut, `dc=demo` est en dessous, et tout le reste de l'annuaire (`ou=people`, `ou=groups`…) vient sous cette racine.

- **Une convention, pas une obligation** : les anciens annuaires utilisaient `o=Entreprise,c=CH` (organisation, pays). La forme en `dc` s'est imposée parce qu'elle réutilise le domaine DNS, déjà unique. Active Directory l'utilise systématiquement.
- **Choisi une seule fois**, à l'installation de l'annuaire. Dans le labo, c'est `LLDAP_LDAP_BASE_DN: dc=demo,dc=local` dans le `docker-compose.yml`.
- **Présent partout comme suffixe** : le Bind DN, le Users DN et le Groups DN saisis dans Keycloak se terminent tous par `,dc=demo,dc=local`.

### Opérations et ports

- **Opérations** : *bind* (s'authentifier), *search* (avec un filtre comme `(&(objectClass=user)(ou=IT))`), *add*, *modify*, *delete*.
- **Ports** : 389 en clair ou avec StartTLS, 636 pour LDAPS (chiffré TLS).

### LDAP et Active Directory

**Active Directory** est le service d'annuaire de Microsoft ; **LDAP est l'un des protocoles qu'on utilise pour lui parler**. D'autres annuaires parlent LDAP : OpenLDAP, 389 Directory Server, FreeIPA, lldap…

## Keycloak

Keycloak est un **serveur d'identité et de gestion des accès** (IAM) open source, porté par Red Hat. LDAP est un *protocole* pour interroger un annuaire ; Keycloak est un *produit* qui gère l'authentification à la place des applications.

### Le principe

L'application ne vérifie plus les mots de passe. Elle **redirige l'utilisateur vers Keycloak**, qui affiche la page de login et vérifie l'identité. Keycloak renvoie ensuite l'utilisateur avec un **jeton signé** (« c'est Jean Dupont, il a les rôles X et Y »), que l'application se contente de valider.

### Ce que ça apporte

- **SSO (Single Sign-On)** : une seule connexion pour toutes les applications branchées.
- **Protocoles standards** : OpenID Connect et OAuth 2.0 (jetons JWT), SAML 2.0 pour les applications plus anciennes.
- **Fédération d'utilisateurs** : lecture des comptes dans un annuaire AD/LDAP existant, sans les copier, ou connexion à d'autres fournisseurs d'identité (Entra ID, Google, SwissID…).
- **Sécurité centralisée** : MFA/OTP, politiques de mots de passe, gestion des sessions, déconnexion globale.
- **Rôles et droits**, par application ou globaux.

### Concepts de base

| Concept | Description |
| --- | --- |
| Realm | Espace isolé avec ses propres utilisateurs, rôles et configuration (ex. un realm employés, un realm assurés) |
| Client | Application déclarée qui délègue son authentification à Keycloak |
| Users / Groups | Utilisateurs et groupes, locaux ou fédérés depuis un annuaire |
| Roles | Droits attribués aux utilisateurs ou aux groupes, qui se retrouvent dans le jeton |

### LDAP et Keycloak ensemble

L'annuaire LDAP/AD reste la **source des identités** : qui existe, quel mot de passe, quels groupes. Keycloak est la **porte d'entrée** moderne : il s'appuie sur l'annuaire mais expose aux applications des protocoles web (OIDC) au lieu de les obliger à parler LDAP.

Dans une architecture Spring Boot sur OpenShift, c'est un couple courant : Spring Security en client OIDC, Keycloak devant, l'AD derrière. Red Hat distribue une version supportée (*Red Hat build of Keycloak*) installée via un opérateur OpenShift.

## Groupes et rôles

Keycloak gère les trois notions : utilisateurs, groupes **et** rôles. L'annuaire LDAP, lui, ne connaît que les utilisateurs et les groupes. La différence est une question de sens :

- **Un groupe** décrit *qui tu es* dans l'organisation : « informatique », « rh », « équipe migration ».
- **Un rôle** décrit *ce que tu as le droit de faire* dans une application : `admin`, `lecteur`, `valider-dossier`.

Keycloak distingue les **realm roles**, globaux à tout le realm, et les **client roles**, propres à une application (ex. `gestion-rentes:validateur`).

### Comment ça s'articule

On attribue des rôles à un groupe, et tous ses membres en héritent :

```
LDAP : alice ∈ groupe "informatique"
        ↓ (synchronisé par le group-ldap-mapper)
Keycloak : groupe "informatique" → rôles "app-x:admin", "app-y:lecteur"
        ↓
Jeton d'alice : roles = [admin, lecteur]
```

L'annuaire reste la source de vérité pour l'appartenance aux groupes. Keycloak fait la **traduction groupe → droits applicatifs**, et l'application ne vérifie que des rôles.

### Pourquoi des rôles plutôt que des groupes dans les applis

Utiliser directement les groupes couple l'application à l'organigramme : si le service « informatique » est renommé ou scindé, il faut modifier le code. Avec des rôles, on change seulement le mapping dans Keycloak.

Il existe aussi un `role-ldap-mapper` qui transforme des groupes LDAP directement en rôles, mais l'approche groupes + rôles assignés aux groupes est généralement plus souple.

## Choisir un serveur LDAP pour un petit projet

Pour un petit projet ou un labo, **lldap** est le meilleur point de départ. Les autres options se justifient par un besoin précis.

| Option | Pour qui | Points forts | Limites |
| --- | --- | --- | --- |
| **lldap** | Petit projet, homelab, labo SSO | Léger (Rust), un conteneur Docker, interface web simple, s'intègre avec Keycloak, Authelia, Nextcloud, Gitea | Schéma fixe (utilisateurs + groupes), pas de réplication |
| OpenLDAP | Apprendre LDAP en profondeur, besoins avancés | Référence historique, complet, robuste | Configuration pénible (cn=config, LDIF, schémas) |
| Samba AD | Parc avec postes Windows | Alternative libre à Active Directory (domaine, GPO) | Plus lourd |
| FreeIPA | Parc Linux | Annuaire + Kerberos + DNS + certificats | Surdimensionné pour un petit projet |
| Kanidm | Un seul composant au lieu de deux | Serveur d'identité moderne (Rust), LDAP en lecture + OIDC natif | Moins répandu |
| Keycloak seul | Toutes les applis parlent OIDC | Base d'utilisateurs interne, pas d'annuaire à gérer | Inutile si des applis ne savent faire que du LDAP |

Un annuaire LDAP devient utile quand certaines applications ne parlent que LDAP, ou quand on veut un annuaire indépendant du serveur d'authentification.

## Le labo pas à pas

Le labo tourne en local avec Docker Compose : **lldap** comme annuaire et **Keycloak** (26.x, mode `start-dev`) branché dessus.

| Service | URL | Identifiants (labo uniquement) |
| --- | --- | --- |
| lldap, interface web | http://localhost:17170 | `admin` / `ChangeMe-ldap-2026` |
| lldap, LDAP | `ldap://localhost:3890` (`ldap://lldap:3890` depuis Keycloak) | même compte |
| Keycloak, console | http://localhost:8080 | `admin` / `admin` |

Lancement : `docker compose up -d`.

### 1. Remplir l'annuaire

Dans lldap, créer deux utilisateurs avec e-mail et mot de passe, puis deux groupes :

- `alice` dans le groupe `informatique`
- `bob` dans le groupe `rh`

### 2. Créer le realm

Dans Keycloak, menu des realms en haut à gauche → *Create realm* → `demo`. Toujours travailler dans ce realm, jamais dans `master`.

### 3. Brancher le LDAP

*User federation* → *Add LDAP providers* :

| Champ | Valeur | Signification |
| --- | --- | --- |
| Vendor | Other | Type d'annuaire. Choisir *Active Directory*, *Red Hat Directory Server*… pré-remplit les autres champs ; lldap n'est pas listé, donc tout se remplit à la main |
| Connection URL | `ldap://lldap:3890` (bouton *Test connection*) | Adresse du serveur. `ldap://` = en clair, `ldaps://` = chiffré. `lldap` est le nom du conteneur dans le réseau Docker, d'où l'absence de `localhost` |
| Bind DN | `uid=admin,ou=people,dc=demo,dc=local` | Compte avec lequel Keycloak s'authentifie auprès de l'annuaire (le *bind*) avant de chercher. En entreprise : un compte de service dédié en lecture seule, jamais un admin |
| Bind credentials | `ChangeMe-ldap-2026` (bouton *Test authentication*) | Mot de passe de ce compte |
| Edit mode | `READ_ONLY` | Keycloak ne modifie jamais l'annuaire : pas de changement de mot de passe ou d'e-mail depuis Keycloak. Autres modes : *WRITABLE* (Keycloak écrit dans le LDAP), *UNSYNCED* (modifications gardées dans Keycloak seulement) |
| Users DN | `ou=people,dc=demo,dc=local` | « Dossier » de l'arbre où se trouvent les utilisateurs ; Keycloak ne cherche que là |
| Username LDAP attribute | `uid` | Attribut qui devient le login dans Keycloak (dans AD : `sAMAccountName`) |
| RDN LDAP attribute | `uid` | Attribut qui nomme l'entrée dans son DN, le `uid=alice` de `uid=alice,ou=people,…` (dans AD : souvent `cn`) |
| UUID LDAP attribute | `uid` | Identifiant stable qui permet de reconnaître l'utilisateur même s'il est renommé. Idéalement technique : `entryUUID` (OpenLDAP), `objectGUID` (AD) ; `uid` suffit pour un labo |
| User object classes | `person` | Filtre sur le type d'entrée : seules les entrées avec cet objectClass sont des utilisateurs |
| Search scope | One Level | Profondeur de recherche. *One Level* = uniquement sous `ou=people` ; *Subtree* descend dans les sous-dossiers (utile dans un AD organisé en OU par service ou par site) |
| Pagination | Off | Résultats demandés par pages. Indispensable avec un gros AD (limite de 1000 résultats par requête), mais lldap ne le gère pas |

Enregistrer, puis *Action → Sync all users* : alice et bob apparaissent dans *Users*.

### 4. Mapper les groupes

Onglet *Mappers* du provider LDAP → *Add mapper* → type `group-ldap-mapper` :

| Champ | Valeur |
| --- | --- |
| LDAP Groups DN | `ou=groups,dc=demo,dc=local` |
| Group name LDAP attribute | `cn` |
| Group object classes | `groupOfUniqueNames` |
| Membership LDAP attribute | `member` |
| Membership attribute type | DN |
| Membership user LDAP attribute | `uid` |
| Mode | `READ_ONLY` |
| User groups retrieve strategy | `LOAD_GROUPS_BY_MEMBER_ATTRIBUTE` |

Enregistrer, puis *Sync LDAP groups to Keycloak* : les groupes apparaissent dans *Groups*.

### 5. Premier test SSO

Ouvrir http://localhost:8080/realms/demo/account en navigation privée et se connecter avec alice et son mot de passe LDAP. Si ça marche, Keycloak authentifie bien contre l'annuaire.

### 6. Ajouter un rôle aux groupes

Créer un realm role `admin`, puis *Groups → informatique → Role mapping* → l'assigner. Alice hérite du rôle, bob non.

### 7. Vérifier le jeton en ligne de commande

1. *Clients → Create client* → `test-cli`, *Client authentication* désactivé, *Direct access grants* coché.
2. Onglet *Client scopes* → `test-cli-dedicated` → *Configure a new mapper* → *Group Membership*, claim `groups`, *Full group path* décoché.
3. Demander un jeton et le décoder :

```bash
curl -s http://localhost:8080/realms/demo/protocol/openid-connect/token \
  -d client_id=test-cli -d grant_type=password -d scope=openid \
  -d username=alice -d password='MOT_DE_PASSE_ALICE' \
| jq '.access_token | split(".")[1] | gsub("-";"+") | gsub("_";"/") | @base64d | fromjson'
```

Le jeton décodé contient `"groups": ["informatique"]` et, après l'étape 6, `admin` dans `realm_access.roles`. Le *password grant* ne sert qu'aux tests ; une vraie application utilise le flux *authorization code*.

## Connecter une application Python

L'application `app.py` utilise **Flask + Authlib** en flux *authorization code* OpenID Connect. Authlib découvre les endpoints de Keycloak via `/.well-known/openid-configuration`, échange le code contre les jetons et vérifie la signature de l'ID token.

### 1. Déclarer le client dans Keycloak

Realm `demo` → *Clients* → *Create client* :

| Champ | Valeur |
| --- | --- |
| Client ID | `python-app` |
| Client authentication | On (client confidentiel, c'est un serveur web) |
| Standard flow | Coché (flux authorization code) |
| Valid redirect URIs | `http://localhost:5000/callback` |
| Valid post logout redirect URIs | `http://localhost:5000/` |
| Web origins | `http://localhost:5000` |

Copier ensuite le **Client secret** dans l'onglet *Credentials*.

### 2. Mettre les groupes dans le jeton

*Client scopes* → `python-app-dedicated` → *Configure a new mapper* → *Group Membership* : claim `groups`, *Full group path* décoché, *Add to userinfo* coché.

### 3. Lancer l'application

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # flask, authlib, requests, python-dotenv
cp .env.example .env              # y mettre KEYCLOAK_CLIENT_SECRET
python app.py
```

Puis ouvrir http://localhost:5000 et cliquer sur *Se connecter*.

### Ce qu'on peut tester

| Route | Comportement |
| --- | --- |
| `/` | Accueil : utilisateur, groupes et rôles une fois connecté |
| `/login` | Redirection vers la page de login Keycloak |
| `/callback` | Retour de Keycloak, échange du code contre les jetons |
| `/protected` | Contenu complet de l'access token (connexion requise) |
| `/admin` | Réservé au realm role `admin` : alice passe, bob reçoit une erreur 403 |
| `/logout` | Déconnexion de l'appli **et** de la session SSO Keycloak (`end_session_endpoint`) |

**Test du SSO** : après s'être connecté sur l'appli, ouvrir http://localhost:8080/realms/demo/account. On y est déjà connecté sans ressaisir de mot de passe, car c'est la même session Keycloak.

Pour FastAPI, le principe est identique avec `authlib.integrations.starlette_client`.

## Projet Claude Code

Le labo est empaqueté dans `sso-lab.zip`, prêt à devenir un projet Claude Code : décompresser, `git init`, puis lancer `claude` dans le dossier.

| Fichier | Rôle |
| --- | --- |
| `docker-compose.yml` | lldap + Keycloak |
| `app.py` | Application Flask + Authlib, lit le fichier `.env` |
| `requirements.txt` | flask, authlib, requests, python-dotenv |
| `.env.example` | Modèle des variables : `KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`, `FLASK_SECRET_KEY` |
| `.gitignore` | Exclut `.env`, `.venv/`, `__pycache__/` : les secrets ne partent jamais dans git |
| `CLAUDE.md` | Contexte lu automatiquement par Claude Code : architecture, DN LDAP, clients Keycloak, utilisateurs de test, conventions |

**Conventions notées dans `CLAUDE.md`** : documentation et commentaires en français, jamais de secrets committés, ne pas réutiliser `jwt_claims()` (décodage sans vérification) pour des jetons venant du navigateur, mots de passe du compose à changer hors du labo.

### Astuce macOS : voir les fichiers cachés

`.env.example` et `.gitignore` commencent par un point, donc le Finder les cache. **⌘ Cmd + ⇧ Shift + .** les affiche ou les masque. Pour les montrer en permanence :

```bash
defaults write com.apple.finder AppleShowAllFiles -bool true
killall Finder
```

Dans le Terminal, `ls -la` les affiche aussi.

### Pistes d'évolution

- [ ] Exporter la configuration du realm (`kc.sh export`) et l'importer au démarrage (`--import-realm`), pour ne plus rien cliquer après un `docker compose down -v`
- [ ] Ajouter une seconde application pour démontrer le SSO entre deux applis
- [ ] Protéger une API par bearer token, avec validation du JWT via JWKS
- [ ] Variante Spring Boot avec Spring Security en client OIDC
