# Chatbot Socio-Emotionnel

Un chatbot d'accompagnement socio-emotionnel pour les eleves marocains du cycle collegial et qualifiant. Propulse par Google Gemini AI (gratuit).

## Fonctionnalites

- **Chat IA** : Conversations empathiques avec detection automatique de langue (FR/AR)
- **Mirroring dialecte + sentiment** : Reponses dans la langue/dialecte de l'eleve + suggestions adaptees
- **Systeme d'alerte double** : Detection par IA + analyse de mots-cles pour les situations critiques
- **3 Roles** : Eleve, Enseignant, Administrateur
- **Tableau de bord eleve** : Evolution emotionnelle, statistiques
- **Tableau de bord enseignant** : Alertes, bien-etre de la classe, indicateurs par eleve
- **Panneau admin** : Gestion des utilisateurs, classes, rapports, export CSV
- **Nuage de mots** : Themes frequents (eleve et classe)
- **Export PDF** : Rapports d'alertes (admin)
- **Export eleve** : Telechargement de l'historique
- **Securite** : JWT, bcrypt, chiffrement AES-256, rate limiting
- **Gratuit** : Aucune API payante requise

---

## Pre-requis

- **Python 3.10+** installe sur votre machine
- **pip** (gestionnaire de paquets Python)
- **Un navigateur web** moderne (Chrome, Firefox, Edge)

---

## Installation pas a pas

### Etape 1 : Cloner ou telecharger le projet

```bash
cd C:\Users\votre_nom\Desktop
git clone <url_du_repo> PFE_ChatBot
cd PFE_ChatBot
```

Ou si vous avez deja le dossier, ouvrez un terminal dans `PFE_ChatBot`.

### Etape 2 : Creer un environnement virtuel (recommande)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### Etape 3 : Installer les dependances

```bash
pip install -r requirements.txt
```

### Etape 4 : Obtenir une cle API Gemini (GRATUIT)

1. Allez sur [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. Connectez-vous avec votre compte Google
3. Cliquez sur **"Create API Key"**
4. Copiez la cle generee

> **Note** : L'API Gemini est gratuite avec des limites generales (15 requetes/minute, 1M tokens/jour). C'est largement suffisant pour un usage scolaire.

### Etape 5 : Configurer les variables d'environnement

```bash
# Copier le fichier template
copy .env.example .env    # Windows
# cp .env.example .env    # Mac/Linux
```

Ouvrez le fichier `.env` et modifiez les valeurs :

```env
# OBLIGATOIRE : votre cle API Gemini
GEMINI_API_KEY=votre_cle_api_ici

# Securite : changez ces valeurs !
SECRET_KEY=une_chaine_aleatoire_longue_de_64_caracteres_minimum
ENCRYPTION_KEY=une_autre_chaine_aleatoire_de_32_caracteres

# Les autres valeurs peuvent rester par defaut pour le developpement
```

> **Important** : Le fichier `.env` contient des secrets. Ne le partagez jamais et ne le mettez pas sur Git.

### Etape 6 : Lancer l'application

```bash
python app.py
```

Vous devriez voir :

```
INFO: Seeding database with demo data...
INFO: Demo data seeded successfully!
INFO:   Admin: admin@school.ma / admin123
INFO:   Teacher: prof@school.ma / prof123
INFO:   Student: eleve1@school.ma / eleve123
 * Running on http://127.0.0.1:5000
```

### Etape 7 : Ouvrir dans le navigateur

Allez sur : **http://127.0.0.1:5000**

---

## Comptes de demonstration

| Role | Email | Mot de passe |
|------|-------|-------------|
| Administrateur | admin@school.ma | admin123 |
| Enseignant | prof@school.ma | prof123 |
| Enseignant | prof2@school.ma | prof123 |
| Eleve | eleve1@school.ma | eleve123 |
| Eleve | eleve2@school.ma | eleve123 |
| Eleve | eleve3@school.ma | eleve123 |

---

## Structure du projet

```
PFE_ChatBot/
├── app.py                  # Application Flask principale
├── config.py               # Configuration
├── models.py               # Modeles de base de donnees
├── auth.py                 # Authentification JWT + bcrypt
├── chat_service.py         # Integration API Gemini
├── alerts.py               # Systeme d'alerte double
├── encryption.py           # Chiffrement AES-256
├── requirements.txt        # Dependances Python
├── .env.example            # Template des variables d'environnement
├── .gitignore
├── prompts/
│   └── system_prompt_v3.txt  # Prompt systeme versionne
├── static/
│   ├── css/style.css       # Styles CSS
│   └── js/                 # Scripts JavaScript
│       ├── app.js          # Utilitaires partages
│       ├── chat.js         # Interface de chat
│       ├── dashboard.js    # Tableau de bord eleve
│       ├── teacher.js      # Tableau de bord enseignant
│       └── admin.js        # Panneau d'administration
└── templates/              # Templates HTML Jinja2
    ├── base.html
    ├── login.html
    ├── chat.html
    ├── dashboard_eleve.html
    ├── dashboard_enseignant.html
    └── admin.html
```

## Technologies utilisees (toutes gratuites)

| Composant | Technologie |
|-----------|-------------|
| Backend | Python Flask |
| IA | Google Gemini API (gratuit) |
| Base de donnees | SQLite (via SQLAlchemy) |
| Authentification | JWT + bcrypt |
| Chiffrement | AES-256 (Fernet) |
| Frontend | HTML5 / CSS3 / JavaScript |
| Graphiques | Chart.js |
| Icones | Lucide Icons |
| Police | Inter (Google Fonts) |

## Configuration email (optionnel)

Pour activer les notifications email d'alertes, configurez dans `.env` :

```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_application
```

Pour Gmail, utilisez un [mot de passe d'application](https://myaccount.google.com/apppasswords).

---

## Deploiement sur Vercel

1. Creer une base PostgreSQL geree (ex: Neon, Supabase, Railway) et recuperer `DATABASE_URL`.
2. Creer un projet Vercel et ajouter les variables d'environnement :

```
GEMINI_API_KEY=...
DATABASE_URL=...
SECRET_KEY=...
ENCRYPTION_KEY=...
APP_BASE_URL=https://votre-app.vercel.app
```

3. Deployer le depot (Vercel detecte `vercel.json`).

> **Note** : SQLite n'est pas persistant sur Vercel. Utilisez PostgreSQL en production.

---

## Migrations (Alembic / Flask-Migrate)

Initialiser les migrations :

```bash
flask db init
flask db migrate -m "init"
flask db upgrade
```

---

## Tests

```bash
pytest
```

---

## Docker (local)

```bash
docker-compose up --build
```

---

## Licence

Projet academique - PFE (Projet de Fin d'Etudes)
