# -*- coding: utf-8 -*-
"""
Script de compilation PyInstaller pour créer l'exécutable Windows autonome
« Sinistres App ».

Cet exécutable UNIQUE est le point d'entrée de l'application : au lancement,
il affiche l'écran de CHOIX DE SESSION :
    - 👑 Session Administrateur  (console d'administration, propriétaire) ;
    - 🧑‍💼 Session Gestionnaire   (application de gestion des sinistres).

Produit par défaut une application Windows (sans console) au format --onedir,
idéale pour être empaquetée par Inno Setup dans un installateur officiel.

Supporte également le mode portable --onefile :
    python build_exe.py --onefile
"""
import os
import subprocess
import sys
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT, "dist", "windows")
APP_NAME = "Sinistres App"


def run(cmd):
    print("->", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def build(mode="--onedir"):
    if not os.path.exists(os.path.join(ROOT, "requirements.txt")):
        raise SystemExit("requirements.txt introuvable")

    if shutil.which("pyinstaller") is None:
        print("PyInstaller n'est pas installé. Installation en cours...")
        run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    sep = ";" if os.name == "nt" else ":"
    add_data = []

    # Embarquement des fichiers de configuration et modèles par défaut
    for fname in ("fiche_template_fields.json", "status_colors.json"):
        fpath = os.path.join(ROOT, fname)
        if os.path.exists(fpath):
            add_data.extend(["--add-data", fpath + sep + "."])

    # Modèles officiels de fiches
    for mname in ("FICHE_DE_SINISTRE_MODELE.pdf", "FICHE_DE_SINISTRE_MODELE.docx"):
        mpath = os.path.join(ROOT, mname)
        if os.path.exists(mpath):
            add_data.extend(["--add-data", mpath + sep + "."])
            print(f"Modèle officiel embarqué : {mname}")

    # Hidden imports pour s'assurer qu'aucun module n'est manquant sur un PC Windows vierge
    hidden_imports = [
        "--hidden-import", "openpyxl",
        "--hidden-import", "reportlab",
        "--hidden-import", "pypdf",
        "--hidden-import", "docx",
        "--hidden-import", "sqlite3",
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.hazmat.primitives.asymmetric.ed25519",
        "--hidden-import", "cryptography.hazmat.primitives.serialization",
        "--hidden-import", "admin_console",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
    ]
    if os.name == "nt":
        hidden_imports.extend(["--hidden-import", "win32com.client", "--hidden-import", "pythoncom"])

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        mode,
        "--windowed",
        "--name",
        APP_NAME,
        "--distpath",
        OUTPUT_DIR,
        # cryptography (Ed25519) doit être empaqueté intégralement, sinon la
        # génération de licence échoue dans l'exécutable compilé.
        "--collect-all", "cryptography",
        *add_data,
        *hidden_imports,
        "main.py",
    ])

    if mode == "--onefile":
        out_file = os.path.join(OUTPUT_DIR, f"{APP_NAME}.exe")
        print(f"\n✅ Éxécutable portable généré : {out_file}")
    else:
        out_dir = os.path.join(OUTPUT_DIR, APP_NAME)
        print(f"\n✅ Répertoire compilé généré : {out_dir}")
        print(f"   Exécutable : {os.path.join(out_dir, f'{APP_NAME}.exe')}")

    print("\nℹ️  Au lancement de « Sinistres App » : choix de session")
    print("    (👑 Administrateur / 🧑‍💼 Gestionnaire).")


if __name__ == "__main__":
    selected_mode = "--onefile" if "--onefile" in sys.argv else "--onedir"
    build(mode=selected_mode)
