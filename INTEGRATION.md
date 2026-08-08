# Guide d'intégration — Améliorations (B1–B6, S1–S4)

Ce document explique comment intégrer dans ton projet les modifications de la
branche `arena/019fe1e5-sinistres-app-v4` (PR #1).

## 0. Résumé des changements

- **B1** — `montant_achats` : le champ lu dans l'Excel était perdu à l'import. → corrigé.
- **B2** — `update_sinistre` met maintenant à jour `updated_at`.
- **B3** — `run_tests.py` réécrit (multi-plateforme, lance tous les tests).
- **B4** — Rotation des sauvegardes SQLite (n'envahit plus le disque).
- **B5** — En `.exe` dans *Program Files*, bascule vers `%APPDATA%\SinistresApp` (+ migration des données).
- **B6** — Connexions SQLite sécurisées (context manager, fini les « database is locked »).
- **S1** — Mots de passe hachés en PBKDF2 (comptes + mot de passe maître).
- **S2** — Signature de licence dérivée du mot de passe maître (anti-falsification du .exe).
- **S3** — `get_distinct` protégé contre l'injection SQL (liste blanche).
- **S4** — Erreurs loggées au lieu d'être avalées (fichier `sinistres_app.log`).

**Tout est rétro-compatible** : bases, licences et comptes existants restent lisibles.

---

## 1. AVANT de commencer — sauvegardes (5 minutes)

Par précaution, copie ces fichiers dans un dossier sûr avant la mise à jour :

1. Ton fichier **`sinistres.db`** (à côté de l'application).
2. Ton **fichier Excel source** (`SUIVI_DES_SINISTRE...xlsx`).
3. Le dossier **`backups/`** (s'il existe).
4. Les fichiers `license.json` et `license_master.json` (s'ils existent).

> Ce n'est qu'une précaution — les modifications sont conçues pour ne rien
> casser. Mais on n'est jamais trop prudent avec ses données.

---

## 2. Intégration — choisis UNE des deux options

### ✅ Option A — Fusionner via GitHub (le plus simple, recommandé)

Sur ton PC, dans le dossier de ton projet :

```bash
# 1. Vérifie que tu es à jour
git checkout main
git pull origin main

# 2. Ouvre la PR dans ton navigateur et clique sur "Merge pull request" :
#    https://github.com/bezziounekarim923-hub/Sinistres-App-V4/pull/1

# 3. Récupère la fusion sur ton PC
git checkout main
git pull origin main
```

C'est tout — `main` contient maintenant toutes les améliorations.

### 🧪 Option B — Tester d'abord sur ton PC (prudent)

Vérifier que tout fonctionne avant de toucher à `main` :

```bash
# 1. Récupère la branche d'améliorations
git fetch origin
git checkout arena/019fe1e5-sinistres-app-v4

# 2. Installe les dépendances (rien de nouveau cette fois : openpyxl, matplotlib)
pip install -r requirements.txt

# 3. Lance les tests
python run_tests.py
#   -> doit afficher "Ran 40 tests ... OK"

# 4. Lance l'application pour vérifier visuellement
#    (double-clique sur 2_lancer_app.bat, ou)
python main.py

# 5. Si tout est bon, reviens sur main et fusionne
git checkout main
git pull origin main
git merge arena/019fe1e5-sinistres-app-v4
git push origin main
```

---

## 3. Activer la CI GitHub Actions (tests automatiques)

Le fichier `.github/workflows/ci.yml` n'a **pas pu être poussé** avec la PR :
le jeton utilisé manquait de la permission `workflows`. Pour l'activer :

**Option 1 — Sur GitHub directement :**
1. Va sur https://github.com/bezziounekarim923-hub/Sinistres-App-V4
2. Crée le fichier `.github/workflows/ci.yml` (bouton *Add file → Create new file*)
3. Colle le contenu fourni à la fin de ce document
4. Commit directement sur `main`

**Option 2 — Depuis ton PC (tu as les droits complets) :**
```bash
git checkout main
# crée le dossier et le fichier (voir contenu ci-dessous)
git add .github/workflows/ci.yml
git commit -m "CI: workflow GitHub Actions"
git push origin main
```

Une fois en place, les tests tourneront automatiquement à chaque push/PR.

---

## 4. APRÈS l'intégration — vérifications rapides

⚠️ **Nouvelle dépendance** : la génération de la fiche de sinistre utilise
**reportlab**. Relancez **`1_installer.bat` une fois** après la mise à jour pour
l'installer (si vous lancez l'app via Python). Pour le `.exe`, reportlab est
inclus automatiquement par `3_creer_exe.bat`.

Lance l'application et vérifie ces points :

- [ ] **Connexion** : ton compte habituel fonctionne toujours (le mot de passe est re-haché en silence à la 1re connexion).
- [ ] **Données** : tes sinistres sont tous là (onglet Sinistres).
- [ ] **Fichier Excel** : la synchronisation fonctionne (ajoute un sinistre test, vérifie qu'il apparaît dans l'Excel).
- [ ] **Licence** : elle est toujours active (Administration → Licence).
- [ ] **Sauvegardes** : le dossier `backups/` ne contient plus que ~50 fichiers (rotation B4).
- [ ] **Tests** : `python run_tests.py` → « Ran 40 tests ... OK ».

---

## 5. Cas particulier — .exe installé dans « Program Files » (B5)

Si tu génères un `.exe` (via `3_creer_exe.bat`) et que tu l'installes dans
**Program Files** (non inscriptible), l'application va maintenant stocker ses
données dans :

- **Windows** : `%APPDATA%\SinistresApp\`
  (ex. `C:\Users\TonNom\AppData\Roaming\SinistresApp\`)

Au 1er lancement après mise à jour, les fichiers existants (`sinistres.db`,
`license.json`, `license_master.json`, `status_colors.json`) **sont migrés
automatiquement** depuis l'ancien dossier vers le nouveau.

> Si tu rencontres un souci, retrouve tes données dans `%APPDATA%\SinistresApp\`.
> Pour continuer à utiliser l'ancien emplacement, installe le `.exe` dans un
> dossier inscriptible (Bureau, Documents) — le comportement est alors inchangé.

---

## 6. Si quelque chose ne va pas

1. **Restaure ta sauvegarde** de `sinistres.db` (étape 1).
2. Consulte le fichier de log : `sinistres_app.log` (à côté de l'application,
   ou dans `%APPDATA%\SinistresApp\` en .exe) — il contient les avertissements
   qui étaient auparavant masqués (S4).
3. Ouvre un message sur la PR #1 décrivant le problème.

---

## Annexe — Contenu de `.github/workflows/ci.yml`

```yaml
name: Tests

on:
  push:
    branches: [main, "arena/**"]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Configurer Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Installer tkinter (tests d'UI éventuels)
        run: sudo apt-get update && sudo apt-get install -y python3-tk

      - name: Installer les dépendances
        run: pip install -r requirements.txt

      - name: Lancer les tests
        run: python -m unittest discover -s tests -p "test_*.py" -v
```
