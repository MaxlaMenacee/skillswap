# SkillSwap — Plateforme de troc de compétences entre étudiants

> Échangez vos compétences. Gratuitement. Entre étudiants.  
> Propose ce que tu sais faire. Apprends ce que tu veux. Sans argent, sans intermédiaire.

**URL du site déployé :** [À compléter après déploiement]

## Équipe

| Membre | Rôle |
|--------|------|
| Rouvrais Clément | Conception BDD, documentation, GitHub |
| [Membre 2] | [Rôle] |
| [Membre 3] | [Rôle] |

## Stack technique

| Élément | Choix | Justification Green IT |
|---------|-------|----------------------|
| Front-end | HTML5 / CSS3 / Vanilla JS | Zéro framework, zéro dépendance externe, pages < 200 Ko |
| Back-end | Flask (Python) | Léger, minimal, faible empreinte serveur |
| Base de données | SQLite | Zéro serveur dédié, fichier unique, sobre |
| Hébergement | Render / Alwaysdata | Gratuit, sobre, sans cloud surdimensionné |
| Outils projet | GitHub, Notion | Collaboration navigateur, pas d'outil superflu |

### Principes Green IT appliqués

- **Pages < 200 Ko** : polices système, zéro image superflue, CSS minimal (~4 Ko)
- **Zéro tracker** : aucun cookie non nécessaire, pas de Google Analytics
- **Zéro dépendance JS** : vanilla JavaScript uniquement, pas de framework
- **2 dépendances Python** : Flask + flask-bcrypt (le strict minimum)
- **Mode sombre natif** : via `prefers-color-scheme`, réduit la conso sur OLED
- **Lazy loading** : attribut `loading="lazy"` sur les images
- **Requêtes optimisées** : SELECT ciblés, index SQL, pagination systématique
- **Hébergement sobre** : pas de cloud surdimensionné

## Installation locale

```bash
# 1. Cloner le dépôt
git clone https://github.com/[votre-username]/skillswap.git
cd skillswap

# 2. Créer un environnement virtuel
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Installer les dépendances
pip install -r backend/requirements.txt

# 4. Configurer l'environnement
cp .env.example .env
# Modifier SECRET_KEY dans .env

# 5. Lancer l'application
python backend/app.py
```

Le site sera accessible sur `http://localhost:5000`.

**Compte admin par défaut :**  
Email : `admin@skillswap.fr` / Mot de passe : `Admin123!`

## Structure du dépôt

```
skillswap/
├── backend/
│   ├── app.py                 # Application Flask (routes, logique, auth)
│   └── requirements.txt       # Dépendances Python (2 paquets)
├── frontend/
│   ├── templates/             # Templates Jinja2 (HTML)
│   │   ├── base.html          # Layout de base
│   │   ├── index.html         # Page d'accueil
│   │   ├── login.html         # Connexion
│   │   ├── inscription.html   # Inscription
│   │   ├── dashboard.html     # Tableau de bord utilisateur
│   │   ├── parcourir.html     # Parcourir les profils
│   │   ├── voir_profil.html   # Profil public
│   │   ├── modifier_profil.html
│   │   ├── gerer_competences.html
│   │   ├── nouvelle_session.html
│   │   ├── modifier_session.html
│   │   ├── admin_utilisateurs.html
│   │   ├── admin_modifier_utilisateur.html
│   │   ├── admin_sessions.html
│   │   └── erreur.html
│   └── static/
│       └── style.css          # CSS unique (~4 Ko)
├── database/
│   └── init.sql               # Script d'initialisation BDD
├── docs/                      # Rapport, diagrammes, captures
├── .env.example
├── .gitignore
└── README.md
```

## Conventions de commit

```
feat: ajout d'une fonctionnalité
fix: correction de bug
docs: documentation
style: mise en forme (pas de changement fonctionnel)
refactor: refactorisation du code
test: ajout de tests
chore: maintenance (dépendances, config)
```

## Lien vers le rapport

[docs/rapport.pdf](docs/rapport.pdf)
