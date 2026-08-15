# Logiciel SINISTRES APP (v4.0.0) — Édition Autonome Windows

Logiciel professionnel de gestion, suivi documentaire et analyse des sinistres de véhicules.

---

## 💎 1. DISTRIBUTION UTILISATEUR FINAL (Logiciel Windows Autonome)

L'utilisateur final n'a **pas besoin d'installer Python, pip ou la moindre dépendance**.  
Il reçoit un unique fichier d'installation officiel :
* **`Sinistres-App-Setup.exe`**

### Expérience utilisateur sous Windows :
1. Double-cliquez sur `Sinistres-App-Setup.exe`.
2. Suivez l'assistant d'installation (en français, semblable à VLC ou 7-Zip).
3. Un raccourci est automatiquement créé sur le Bureau et dans le Menu Démarrer.
4. Lancez **Sinistres App** : l'application fonctionne immédiatement.

### Sécurité et préservation des données :
* **Fichiers du programme** : Installés dans `C:\Program Files\Sinistres App\` (protégés en écriture).
* **Données utilisateur** : Toutes vos bases de données (`sinistres.db`), pièces jointes (`Documents_Sinistres/`), modèles Word d'entreprise (`FICHE_DE_SINISTRE_MODELE.docx`) et sauvegardes (`backups/`) sont systématiquement stockées dans votre répertoire personnel inscriptible :
  ```
  %APPDATA%\SinistresApp\
  ```
* **Mises à jour sans perte** : L'installation d'une nouvelle version (`4.1`, `4.2`, etc.) ou la désinstallation via *Paramètres Windows > Applications* n'efface jamais vos données personnelles dans `%APPDATA%\SinistresApp\`.

### 🔑 Activation Client (Licence 1 an + Compte utilisateur) — Réservé à l'Éditeur :
Pour distribuer le logiciel à un client ou collègue sans qu'il puisse devenir Administrateur :
1. Sur votre poste Administrateur : allez dans **Administration > Gestion des utilisateurs**.
2. Cliquez sur **« 🎁 Exporter accès client (.sini) »** : choisissez le nom d'utilisateur, le rôle (`Gestionnaire` ou `Consultation`), un mot de passe et la durée de la licence (`365` pour 1 an).
3. Envoyez à votre client : `Sinistres-App-Setup.exe` **+** le fichier `Acces_NomClient_365j.sini`.
4. Au premier lancement sur son PC, le client choisit **« 🔑 Activation Utilisateur (.sini) »** et sélectionne ce fichier : sa licence de 1 an est activée, son compte `Gestionnaire` est créé, et l'accès Administrateur est protégé et réservé à l'éditeur !

### Nouveautés : Relevé de Sinistralité Chauffeur / Flotte & Sauvegarde Miroir

- **👤 Fiche Chauffeur & Relevé de Sinistralité (Word .docx)** : Depuis le menu contextuel (clic droit sur un sinistre), ouvrez le profil d'un chauffeur ou d'un véhicule pour voir ses statistiques (AVEC/SANS tiers, nombre d'accidents) et générez d'un clic un document officiel d'entreprise **« Relevé Individuel de Sinistralité Chauffeur (.docx) »**.
- **☁️ Sauvegarde miroir externe (Clé USB / Cloud / Réseau)** : Dans **Paramètres > Général**, définissez un dossier de sauvegarde miroir externe. Chaque sauvegarde automatique de votre base sera instantanément dupliquée sur votre clé USB ou OneDrive pour vous prémunir contre toute panne matérielle !

---

## 🛠 2. COMPILATION ET BUILD REPRODUCTIBLE (Pour les développeurs)

Un pipeline complet, automatisé et reproductible est intégré pour générer l'installateur Windows.

### Exécuter le build complet en 1 clic (Windows) :
Double-cliquez sur **`build_release.bat`** (ou lancez `python build_release.py all` dans votre terminal).  
Le pipeline exécute 4 étapes vérifiées :
1. **`clean`** : Nettoyage des dossiers temporaires (`build/`, `dist/`, `release/`).
2. **`compile`** : Vérification de la syntaxe et exécution de **l'intégralité des 68 tests unitaires** du projet (`run_tests.py`).
3. **`package`** : Création de l'application autonome via **PyInstaller** en mode `--onedir` (`dist/windows/Sinistres App/`) avec tous les hooks (`sqlite3`, `docx`, `win32com`, `tkinter`, `openpyxl`).
4. **`installer`** : Compilation du script **Inno Setup** (`installer/Sinistres-App.iss`) pour produire le livrable final :
   ```
   release\Sinistres-App-Setup.exe
   ```

---

## 🧩 Contenu du code source (Développement)

| Fichier / Dossier | Rôle |
|---|---|
| `main.py` | L'application (interface graphique et logique principale) |
| `database.py` | Base de données SQLite et gestion sécurisée des chemins `%APPDATA%` |
| `fiche_sinistre_word.py` | Scanner intelligent et générateur de fiches Word (`.doc` & `.docx`) |
| `pieces_jointes.py` | Gestionnaire de pièces jointes (dossier documentaire du sinistre) |
| `importer.py` / `analytics.py` | Import Excel et analyses KPI / alertes |
| `build_release.py` / `.bat` | Pipeline de build reproductible |
| `installer/Sinistres-App.iss` | Script officiel pour Inno Setup 6 (`Sinistres-App-Setup.exe`) |

---

## 🚀 Installation manuelle en mode Python (Optionnel, pour développement)

### Étape 1 — Installer Python
Si Python n'est pas déjà installé sur le PC :
1. Allez sur https://www.python.org/downloads/
2. Téléchargez et installez la dernière version
3. **Important** : cochez la case *"Add Python to PATH"* pendant l'installation

### Étape 2 — Installer les composants de l'application
Double-cliquez sur **`1_installer.bat`**. Une fenêtre noire s'ouvre et installe
tout automatiquement (openpyxl, matplotlib, pyinstaller). Cela prend 1-2 minutes.

---

## ▶️ Utiliser l'application

Deux façons de la lancer :

**Option A — Rapide (recommandé pour commencer) :**
Double-cliquez sur **`2_lancer_app.bat`**. L'application s'ouvre directement.

**Option B — Créer un vrai fichier .exe (comme un logiciel normal) :**
1. Double-cliquez sur **`3_creer_exe.bat`**
2. Patientez 1 à 3 minutes
3. Le fichier `dist\SuiviSinistres.exe` est créé
4. Copiez ce fichier où vous voulez (Bureau, etc.) — vous pouvez ensuite
   supprimer tous les autres fichiers .py, seul le .exe est nécessaire pour
   fonctionner (il contient tout à l'intérieur)
5. Créez un raccourci sur le Bureau si vous le souhaitez (clic droit sur le
   fichier → *Créer un raccourci*, puis déplacez le raccourci sur le Bureau)

⚠️ La première fois que vous lancerez le `.exe`, Windows Defender peut
afficher un avertissement ("Windows a protégé votre ordinateur") car le
fichier n'est pas signé numériquement — c'est normal pour une application
faite maison. Cliquez sur *Informations complémentaires* puis
*Exécuter quand même*.

---

## 🔐 Connexion et rôles (première fois)

Au tout premier lancement, l'application vous demande de créer un compte
**Administrateur** (nom d'utilisateur + mot de passe). Ensuite, à chaque
lancement, une fenêtre de connexion s'affiche.

Trois rôles existent (menu **Administration → 👤 Gestion des utilisateurs**
pour en créer d'autres) :

| Rôle | Peut faire |
|---|---|
| **Administrateur** | Tout : ajout/modification/suppression, vider le fichier Excel, gérer les utilisateurs, voir le journal, les paramètres |
| **Gestionnaire** | Consulter, ajouter, modifier, déplacer vers la Corbeille — mais ne peut pas supprimer définitivement ni vider Excel |
| **Consultation** | Consultation, recherche, export et impression uniquement — aucune modification |

Depuis l'écran de connexion, un bouton **"➕ Créer un compte"** permet à
n'importe qui de créer son propre compte (Gestionnaire ou Consultation),
indépendant des autres — chacun a ses identifiants et ses droits propres.
Pour des raisons de sécurité, l'auto-inscription ne permet pas de créer un
compte Administrateur ; seul un Administrateur existant peut promouvoir un
compte via **Gestion des utilisateurs**.

---

## 🔑 Licence (réservé à l'éditeur — vous)

L'application nécessite une licence valide pour fonctionner, renouvelable
chaque année :

- **Premier lancement** : après connexion, si aucune licence n'est
  enregistrée, une fenêtre bloquante s'affiche. Cliquez sur
  **"🔑 Je suis l'éditeur — Générer une licence"**, définissez votre
  **mot de passe maître** (à conserver précieusement, il n'est jamais
  affiché ni récupérable), puis générez une licence d'1 an (365 jours
  par défaut, modifiable).
- Cette licence est **propre à ce poste**. Pour un autre poste, générez une
  licence sur ce poste-là également (le mot de passe maître doit y être
  redéfini une seule fois, indépendamment).
- **Renouvellement** : le menu **Administration → 🔑 Licence (réservé
  éditeur)** permet à tout moment de consulter l'état de la licence
  (date d'expiration, jours restants) et d'en générer une nouvelle —
  mais cet écran demande systématiquement le mot de passe maître. **Aucun
  compte Administrateur/Gestionnaire/Consultation de l'application ne peut
  y accéder sans le connaître : vous seul(e) contrôlez la licence.**
- 30 jours avant expiration, un avertissement s'affiche automatiquement à
  la connexion.
- Si la licence expire, l'application se rebloque au prochain lancement
  jusqu'à saisie d'un nouveau code (ou nouvelle génération avec le mot de
  passe maître).

⚠️ Si vous perdez le mot de passe maître, vous ne pourrez plus générer de
nouvelle licence sur ce poste : notez-le en lieu sûr.

---

## 🔎 Recherche universelle et auto-complétion

- La barre **"🔎 Recherche universelle"** (onglet Sinistres) cherche en même
  temps dans : N° dossier, chauffeur, immatriculation, camion, code CAM,
  compagnie, expert, agence, type de véhicule, lieu, banque.
- Dans le formulaire d'ajout/modification, les champs comme chauffeur, lieu,
  immatriculation, banque, compagnie, agence, expert, camion proposent
  automatiquement les valeurs déjà utilisées (tapez une lettre pour voir les
  suggestions).
- Si vous saisissez une valeur totalement nouvelle, l'application vous
  demande confirmation avant de l'ajouter à la base de suggestions.
- **Champs liés** : si vous renseignez le camion ou l'immatriculation, les
  champs correspondants (immatriculation/code CAM/type de véhicule, ou
  inversement) se complètent automatiquement s'ils sont vides.

ℹ️ Les champs **Compagnie / Agence / Expert / Camion / Assuré** ne se
remplissent que si votre fichier Excel contient réellement des colonnes
correspondantes. S'ils n'existent pas dans votre fichier, laissez-les
simplement vides.

---

## ✅ Vérifications automatiques avant enregistrement

Avant chaque sauvegarde, l'application vérifie :
- que le format des dates est valide (AAAA-MM-JJ) ;
- que la date de règlement n'est pas antérieure à la date du sinistre ;
- qu'un dossier "REGLER" a bien une date de règlement ;
- qu'un même N° de dossier n'est pas utilisé deux fois.

Dans ces cas, un message vous demande si vous voulez tout de même
enregistrer (aucun blocage strict, juste une alerte).

---

## 📄 Génération de la fiche de sinistre officielle

L'application génère automatiquement la **fiche de sinistre officielle** (PDF A4)
à partir des données d'un sinistre :

1. Dans l'onglet **Sinistres**, sélectionnez **une ligne**.
2. Cliquez sur **« 📄 Générer la fiche »**.
3. Un écran de **prévisualisation modifiable** s'ouvre, pré-rempli avec les
   informations du sinistre (date, lieu, matricule, chauffeur, PV, autorité,
   tiers, dégâts, circonstances…).
4. **Vérifiez / corrigez** les champs si besoin.
5. Choisissez l'action :
   - **« 💾 Enregistrer PDF »** : enregistre un PDF professionnel (vous choisissez
     l'emplacement ; par défaut un dossier `Fiches/` à côté de l'application).
   - **« 🖨 Imprimer »** : génère le PDF puis ouvre la boîte d'impression Windows.
   - **« 📥 Enregistrer dans le sinistre »** (Administrateur / Gestionnaire) :
     reporte les corrections dans le sinistre en base.

⚠️ **Important** : corriger un champ dans la fiche **ne modifie pas** le sinistre
en base. La fiche est un document indépendant. Pour reporter les changements
dans le sinistre, il faut cliquer explicitement « Enregistrer dans le sinistre ».

Le **numéro de fiche** est généré dynamiquement à partir du numéro et de l'année
réels du sinistre (ex. `n° 9/2026`), jamais la valeur d'exemple `0/2026`.

Les informations **absentes** de la base restent vides sur la fiche (ligne à
compléter manuellement) — l'application n'invente jamais de valeur.

### Champs spécifiques à la fiche ajoutés au formulaire

Pour que la fiche soit remplie au maximum, trois champs ont été ajoutés au
formulaire d'ajout/modification (et à la base) :

- **Autorité du PV** (ex. Gendarmerie nationale, Police…)
- **Adresse de l'autorité**
- **Copies des documents récupérées** (OUI / NON)

Si votre fichier Excel contient déjà des colonnes correspondantes, elles sont
importées automatiquement.

### Dépendance supplémentaire

La génération PDF utilise **reportlab**, **pypdf** et **python-docx**. Si vous aviez déjà installé
l'application, **relancez `1_installer.bat` une fois** pour les ajouter.

### Deux formats de modèle : Word (.docx, recommandé et ultra-simple) et PDF

L'application permet de générer la fiche de sinistre de plusieurs façons :

1. **Mode Word (.docx) avec balises (Recommandé - Zéro calibrage !)** :
   - C'est la méthode la plus simple. Word gère automatiquement les tableaux, retours à la ligne et marges.
   - Vous pouvez insérer des balises comme `{{numero_fiche}}`, `{{date_sinistre}}`, `{{chauffeur}}`, `{{degats_cause}}`, `{{circonstance_accident}}` partout dans votre document Word (`.docx`).
   - Cliquez sur **« 📝 Enregistrer Word (.docx) »** : l'application remplace instantanément vos balises par les vraies valeurs du sinistre.
   - **Vous n'avez pas de modèle ?** Cliquez sur **« 📥 Créer modèle Word (.docx) »** dans la fenêtre de fiche : l'application vous génère un document officiel prêt à être personnalisé dans Microsoft Word (ajout de logo, polices, etc.).

2. **Mode superposition PDF (fidèle au modèle PDF original)** :
   - Si vous préférez utiliser votre fichier PDF d'origine, vous pouvez l'importer via **« 📎 Charger modèle PDF »**.
   - **Outil de Calibrage interactif** : Si votre conversion Word → PDF a décalé les écritures, cliquez sur **« 📐 Calibrer modèle »** dans l'application pour ajuster globalement (gauche/droite, haut/bas) ou par champ, tester immédiatement avec un PDF d'essai et enregistrer.

3. **Mode dessiné (secours)** :
   - Si aucun modèle n'est importé, l'application redessine une fiche A4 propre (en-tête organisme, champs, signatures).

### Nouveautés : Pièces Jointes & Export Word par Lots

- **📎 Gestion documentaire par sinistre (Pièces jointes)** : Depuis le tableau des sinistres (clic droit ou bouton en haut), vous pouvez joindre, ouvrir et gérer tous les documents réels d'un dossier (photos de dégâts, scan du PV de gendarmerie, permis, devis...) classés automatiquement dans `Documents_Sinistres/`.
- **📦 Export Word par lots (Publipostage)** : Sélectionnez un ou plusieurs sinistres dans la liste et cliquez sur **« 📦 Export Word (Lot) »** pour générer d'un coup l'ensemble des fiches Word (.docx) remplies dans le dossier de votre choix.

---

## 🕑 Journal des opérations et tableau de bord Administration

Le menu **Administration** propose :
- **📊 Tableau de bord Administration** : nombre de dossiers, nombre
  d'utilisateurs, état et date de la dernière synchronisation, dernière
  sauvegarde, nombre de modifications enregistrées, espace disque utilisé.
- **🕑 Journal des opérations** : historique de toutes les actions
  (ajout, modification, suppression, restauration...) avec utilisateur,
  date/heure et dossier concerné.
- **⚙ Paramètres** : chemin du fichier Excel, thème clair/sombre,
  fréquence de synchronisation, couleurs des statuts.

---

## 📥 Première utilisation — Importer vos données

1. Ouvrez l'application
2. Allez dans l'onglet **"Import / Export"**
3. Cliquez sur **"Choisir un fichier Excel..."**
4. Sélectionnez votre fichier `SUIVI_DES_SINISTRE...xlsx`
5. L'application lit automatiquement toutes les feuilles (2017 à 2026) et
   importe chaque sinistre dans sa base de données interne

⚠️ **À partir de cet import, ce fichier Excel devient la référence.** Toute
création, modification ou suppression faite depuis l'application est
**immédiatement écrite dans ce fichier Excel** (une sauvegarde horodatée est
créée automatiquement avant chaque écriture, dans un dossier `backups/` à
côté de votre fichier).

---

## 🔄 Synchronisation avec Excel

- **Depuis l'application vers Excel** : chaque ajout, modification ou
  suppression est répercuté automatiquement dans le fichier Excel source.
- **Depuis Excel vers l'application** : si vous modifiez directement le
  fichier Excel (à la main, avec des formules, etc.), l'application détecte
  le changement (vérification automatique toutes les 20 secondes et à
  chaque fois que vous revenez sur la fenêtre) et vous propose de recharger
  les données. Vous pouvez aussi cliquer à tout moment sur
  **"🔄 Recharger depuis Excel"** en haut de l'application.
- **Couleurs** : les couleurs utilisées dans votre Excel pour chaque statut
  (Réglé, Instance, Néant, etc.) sont détectées automatiquement à l'import
  et reproduites à l'identique dans l'application et lors des écritures.

---

## 🗑️ Suppression et Corbeille

- Vous pouvez sélectionner un ou plusieurs dossiers dans l'onglet
  **"Sinistres"** (Ctrl+clic ou Maj+clic pour une sélection multiple) puis
  cliquer sur **"🗑 Supprimer la sélection"**. Une confirmation s'affiche
  avec le(s) numéro(s) de dossier concerné(s).
- Les dossiers supprimés ne sont **pas perdus** : ils vont dans l'onglet
  **"🗑 Corbeille"**, d'où vous pouvez les **restaurer** ou les **supprimer
  définitivement** (ce qui efface aussi la ligne correspondante dans le
  fichier Excel, après sauvegarde automatique).
- Le menu **"Administration"** en haut de la fenêtre propose de **vider
  entièrement le fichier Excel** (avec double confirmation et sauvegarde
  automatique), en conservant les feuilles, en-têtes, formules et mise en
  forme.

---

## 🖥️ Les onglets de l'application

- **📊 Tableau de bord** : indicateurs clés (total, montants, délai moyen,
  réglés/non réglés) + graphique par année + évolution mensuelle
- **📋 Sinistres** : liste complète avec filtres (année, statut, recherche),
  ajout/modification/suppression manuelle, export Excel de la vue filtrée
- **🧑‍✈️ Chauffeurs** : classement des chauffeurs par nombre de sinistres,
  ratio fautif/non fautif, montant total engagé, délai moyen
- **💰 Coûts & Délais** : montants totaux et moyens par année, évolution du
  délai moyen de règlement
- **⚠️ Alertes** : tous les dossiers non réglés, triés du plus ancien au
  plus récent (surlignés en orange après 30 jours, en rouge après 60 jours)
- **🗑 Corbeille** : dossiers supprimés, restaurables ou effaçables définitivement
- **📥 Import / Export** : import de nouveaux fichiers Excel, export complet
  de la base vers Excel

---

## 💡 Suggestions d'analyses supplémentaires (déjà incluses)

En plus de ce que fait votre fichier Excel actuel, l'application ajoute :
- Le **classement des chauffeurs à risque** (nombre de sinistres, taux de
  responsabilité) pour cibler des actions de prévention/formation
- Le **suivi des délais de règlement dans le temps**, pour repérer si les
  dossiers sont traités plus vite ou plus lentement d'année en année
- Des **alertes automatiques** sur les dossiers oubliés ou en retard
- Une vision **consolidée sur 10 ans** (2017-2026) au lieu de feuilles
  séparées, avec recherche instantanée tous champs confondus
- Les **lieux d'accident et types d'accident les plus fréquents**
  (visibles via l'export, exploitables pour cibler les zones/risques)

Idées pour la suite si utile : évolution du coût moyen par type de véhicule,
comparaison par banque/assureur, export PDF mensuel automatique. Dites-moi
si vous voulez que j'ajoute l'une de ces analyses.

---

## ❓ Problèmes fréquents

- **Mot de passe oublié / impossible de se connecter** → double-cliquez sur
  `4_recuperer_compte.bat`. Cet outil fonctionne sans avoir besoin de se
  connecter : il liste les comptes existants et vous permet de définir un
  nouveau mot de passe pour l'un d'eux directement.
- **Supprimer tous les comptes pour repartir de zéro** → double-cliquez sur
  `4_recuperer_compte.bat` puis choisissez l'option **« 2) Supprimer TOUS les
  comptes »** (confirmation requise). Les sinistres, pièces jointes et
  sauvegardes ne sont **pas** supprimés ; au prochain lancement, l'application
  vous demandera de créer un nouveau compte Administrateur.


- **"Python n'est pas reconnu..."** → Réinstallez Python en cochant bien
  *"Add Python to PATH"*.
- **La fenêtre se ferme immédiatement** → Lancez plutôt `2_lancer_app.bat`
  qui affiche les erreurs éventuelles.
- **Je veux repartir de zéro** → Supprimez le fichier `sinistres.db` à côté
  de l'application, puis relancez l'import.
