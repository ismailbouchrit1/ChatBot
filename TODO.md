# Guide clair: local + Vercel (Neon)

Ce document explique comment tester en local et deployer sur Vercel + Neon,
sans erreurs.

IMPORTANT:
- L'application utilise TOUJOURS la valeur de `DATABASE_URL` au moment ou elle demarre.
- Si `DATABASE_URL=sqlite:///chatbot.db`, elle utilise SQLite.
- Si `DATABASE_URL=postgresql://...`, elle utilise PostgreSQL.

---

## A) Local (SQLite) - test rapide

1) Ouvrir PowerShell dans le dossier PFE_ChatBot

2) Creer un environnement virtuel

```bash
python -m venv .venv
.venv\Scripts\activate
```

3) Installer les dependances

```bash
pip install -r requirements.txt
```

4) Verifier `.env` (au minimum)

- `GEMINI_API_KEY`
- `SECRET_KEY`
- `ENCRYPTION_KEY`
- `CSRF_SECRET`
- `APP_BASE_URL=http://127.0.0.1:5000`

5) (Recommande) Repartir sur une base propre

- Supprimer `chatbot.db` si vous aviez deja teste avant.

6) Initialiser les migrations

- Si le dossier `migrations/` n'existe pas, lancez les migrations une seule fois.
- Si vous ne voulez pas utiliser le terminal, dites-le et je le ferai pour vous.

7) Lancer le serveur

```bash
python app.py
```

8) Ouvrir dans le navigateur

- http://127.0.0.1:5000

Comptes demo:
- admin@school.ma / admin123
- prof@school.ma / prof123
- eleve1@school.ma / eleve123

---

## B) Vercel + Neon (PostgreSQL)

1) Creer la base Neon

- https://neon.tech
- Creer un projet
- Copier la connection string (format `postgresql://...` avec `sslmode=require`)

2) Mettre a jour le fichier `.env` local

- Ouvrir `.env`
- Remplacer `DATABASE_URL=sqlite:///chatbot.db` par la valeur Neon

3) Appliquer les migrations (obligatoire pour Neon)

- Si vous ne voulez pas utiliser le terminal, dites-le et je le ferai pour vous.

4) Mettre le projet sur GitHub (obligatoire pour Vercel)

- Creer un repository GitHub
- Ajouter votre projet et pousser les fichiers
- Verifier [ .gitignore ](.gitignore) pour etre sur que les fichiers sensibles ne sont pas envoyes
  - Ne jamais envoyer [.env](.env)
  - Ne jamais envoyer .venv/, instance/, __pycache__/

5) Deployer sur Vercel

- https://vercel.com -> New Project -> Importer le repo GitHub
- Ajouter les variables d'environnement:

  - `GEMINI_API_KEY`
  - `DATABASE_URL`
  - `SECRET_KEY`
  - `ENCRYPTION_KEY`
  - `CSRF_SECRET`
  - `APP_BASE_URL` (temporairement `https://placeholder.vercel.app`)
  - `LOG_LEVEL=WARNING`
  - `FLASK_ENV=production`
  - `ALLOWED_ORIGINS=https://votre-app.vercel.app`

6) Deploy

7) Recuperer l'URL Vercel (ex: `https://votre-app.vercel.app`)

8) Mettre a jour:

- `APP_BASE_URL=https://votre-app.vercel.app`
- `ALLOWED_ORIGINS=https://votre-app.vercel.app`

Puis redeployer.

Note: SQLite ne fonctionne pas sur Vercel. PostgreSQL est obligatoire.

---

## C) (Optionnel) Email d'alertes

Remplir dans `.env` ou Vercel:

- `SMTP_SERVER`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `ALERT_RECIPIENT_DEFAULT`
- `ALERT_RECIPIENT_CRITIQUE`
- `ALERT_RECIPIENT_ELEVEE`
- `ALERT_RECIPIENT_MODEREE`

Pour Gmail, utilisez un mot de passe d'application.
