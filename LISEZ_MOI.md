# Application SUIVI DES SINISTRES

Application de bureau pour gérer et analyser vos sinistres de véhicules
(remplace et améliore votre fichier Excel).

## 🧩 Contenu du dossier

| Fichier | Rôle |
|---|---|
| `main.py` | L'application (interface graphique) |
| `database.py` | Gestion de la base de données |
| `importer.py` | Import des fichiers Excel |
| `analytics.py` | Calculs statistiques |
| `requirements.txt` | Liste des composants nécessaires |
| `1_installer.bat` | À lancer UNE SEULE FOIS pour installer |
| `2_lancer_app.bat` | Pour lancer l'application (sans créer de .exe) |
| `3_creer_exe.bat` | Pour créer un fichier `.exe` autonome |

---

## 🚀 Installation (à faire une seule fois)

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


- **"Python n'est pas reconnu..."** → Réinstallez Python en cochant bien
  *"Add Python to PATH"*.
- **La fenêtre se ferme immédiatement** → Lancez plutôt `2_lancer_app.bat`
  qui affiche les erreurs éventuelles.
- **Je veux repartir de zéro** → Supprimez le fichier `sinistres.db` à côté
  de l'application, puis relancez l'import.
