# -*- coding: utf-8 -*-
"""
Script de compilation PyInstaller pour créer les exécutables Windows autonomes :
  1. « Sinistres App »  → application Gestionnaire (main.py) ;
  2. « Console Admin »  → session d'administration (admin_console.py), réservée
                          au propriétaire (détient la clé privée de signature).

Produit par défaut des applications Windows (sans console) au format --onedir,
idéales pour être empaquetées par Inno Setup dans un installateur officiel.

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
ADMIN_NAME = "Console Admin"


def run(cmd):
    print("->", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def _common_args():
    """Arguments communs aux deux exécutables (données + imports cachés)."""
    sep = ";" if os.name == "nt" else ":"
    add_data = []

    for fname in ("fiche_template_fields.json", "status_colors.json"):
        fpath = os.path.join(ROOT, fname)
        if os.path.exists(fpath):
            add_data.extend(["--add-data", fpath + sep + "."])

    for mname in ("FICHE_DE_SINISTRE_MODELE.pdf", "FICHE_DE_SINISTRE_MODELE.docx"):
        mpath = os.path.join(ROOT, mname)
        if os.path.exists(mpath):
            add_data.extend(["--add-data", mpath + sep + "."])
            print(f"Modèle officiel embarqué : {mname}")

    hidden_imports = [
        "--hidden-import", "openpyxl",
        "--hidden-import", "reportlab",
        "--hidden-import", "pypdf",
        "--hidden-import", "docx",
        "--hidden-import", "sqlite3",
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.hazmat.primitives.asymmetric.ed25519",
        "--hidden-import", "cryptography.hazmat.primitives.serialization",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
    ]
    if os.name == "nt":
        hidden_imports.extend(["--hidden-import", "win32com.client", "--hidden-import", "pythoncom"])

    return add_data + hidden_imports


def _build_one(script, name, mode):
    run([
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", mode, "--windowed",
        "--name", name,
        "--distpath", OUTPUT_DIR,
        *_common_args(),
        script,
    ])


def build(mode="--onedir"):
    if not os.path.exists(os.path.join(ROOT, "requirements.txt")):
        raise SystemExit("requirements.txt introuvable")

    if shutil.which("pyinstaller") is None:
        print("PyInstaller n'est pas installé. Installation en cours...")
        run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    _build_one("main.py", APP_NAME, mode)
    _build_one("admin_console.py", ADMIN_NAME, mode)

    suffix = ".exe" if (mode == "--onefile" or os.name == "nt") else ""
    if mode == "--onefile":
        for name in (APP_NAME, ADMIN_NAME):
            out_file = os.path.join(OUTPUT_DIR, f"{name}.exe")
            print(f"\n✅ Exécutable portable généré : {out_file}")
    else:
        for name in (APP_NAME, ADMIN_NAME):
            out_dir = os.path.join(OUTPUT_DIR, name)
            print(f"\n✅ Répertoire compilé généré : {out_dir}")
            print(f"   Exécutable : {os.path.join(out_dir, f'{name}.exe')}")

    print("\nℹ️  Distribution :")
    print(f"   - « {APP_NAME} »  → remise aux Gestionnaires (avec leur licence .lic).")
    print(f"   - « {ADMIN_NAME} » → réservée au propriétaire (clé privée de signature).")


if __name__ == "__main__":
    selected_mode = "--onefile" if "--onefile" in sys.argv else "--onedir"
    build(mode=selected_mode)
