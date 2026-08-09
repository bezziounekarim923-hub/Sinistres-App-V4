# -*- coding: utf-8 -*-
"""
Script de build reproductible pour créer l'application Windows officielle
et son installateur (Sinistres-App-Setup.exe).

Utilisation en ligne de commande :
    python build_release.py [clean|compile|package|installer|all]

Exemples :
    python build_release.py         -> Exécute tout le pipeline (all)
    python build_release.py clean   -> Nettoie les dossiers temporaires
    python build_release.py package -> Génère le dossier compilé dist/windows/Sinistres App
"""
import os
import sys
import shutil
import subprocess
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(ROOT, "dist", "windows", "Sinistres App")
RELEASE_DIR = os.path.join(ROOT, "release")
INSTALLER_ISS = os.path.join(ROOT, "installer", "Sinistres-App.iss")


def log(msg, symbol="ℹ️"):
    print(f"\n{symbol}  {msg}")


def step_clean():
    log("Nettoyage du projet (dossiers temporaires et de build)...", "🧹")
    dirs_to_clean = ["build", "dist", "release", ".pytest_cache", ".mypy_cache"]
    for d in dirs_to_clean:
        path = os.path.join(ROOT, d)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
            print(f"   - Supprimé : {d}/")
    # Nettoyage des pycache et fichiers .pyc
    for root, dirs, files in os.walk(ROOT):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)
        for f in files:
            if f.endswith(".pyc") or f.startswith(".write_test_"):
                try:
                    os.remove(os.path.join(root, f))
                except OSError:
                    pass
    log("Nettoyage terminé.", "✅")


def step_compile():
    log("Vérification de la syntaxe et exécution des tests unitaires...", "🧪")
    import py_compile
    py_files = glob.glob(os.path.join(ROOT, "*.py"))
    for py_file in py_files:
        py_compile.compile(py_file, doraise=True)
    print("   - Syntaxe Python vérifiée sur tous les modules.")

    log("Exécution de la suite de tests unitaires (run_tests.py)...", "⚙️")
    res = subprocess.run([sys.executable, "run_tests.py"], cwd=ROOT)
    if res.returncode != 0:
        raise SystemExit("❌ ÉCHEC DES TESTS UNITAIRES. Arrêt du build pour éviter une distribution défectueuse.")
    log("Suite de tests validée à 100%.", "✅")


def step_package():
    log("Compilation de l'exécutable autonome Windows avec PyInstaller (--onedir)...", "📦")
    subprocess.check_call([sys.executable, "build_exe.py"], cwd=ROOT)
    exe_name = "Sinistres App.exe" if os.name == "nt" else "Sinistres App"
    exe_path = os.path.join(DIST_DIR, exe_name)
    if not os.path.exists(exe_path):
        raise SystemExit(f"❌ Exécutable introuvable après compilation : {exe_path}")
    log(f"Exécutable autonome créé dans : {DIST_DIR}", "✅")


def step_installer():
    log("Création de l'installateur officiel Windows (Sinistres-App-Setup.exe)...", "💿")
    os.makedirs(RELEASE_DIR, exist_ok=True)

    # Recherche du compilateur Inno Setup (ISCC) sous Windows ou dans le PATH
    iscc_candidates = [
        "iscc", "ISCC", "ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    ]
    iscc_exe = None
    for cand in iscc_candidates:
        if shutil.which(cand) or os.path.exists(cand):
            iscc_exe = cand
            break

    if iscc_exe:
        log(f"Inno Setup détecté ({iscc_exe}), compilation du script ISS...", "⚙️")
        subprocess.check_call([iscc_exe, INSTALLER_ISS], cwd=ROOT)
        setup_exe = os.path.join(RELEASE_DIR, "Sinistres-App-Setup.exe")
        if os.path.exists(setup_exe):
            size_mb = round(os.path.getsize(setup_exe) / (1024 * 1024), 2)
            log(f"INSTALLATEUR CRÉÉ AVEC SUCCÈS : {setup_exe} ({size_mb} Mo)", "🎉")
        else:
            print("❌ Erreur : fichier setup non généré.")
    else:
        log("Inno Setup 6 non détecté sur cette machine de build.", "⚠️")
        print("   Pour finaliser l'installateur Windows sur votre PC :")
        print("   1. Installez Inno Setup 6 : https://jrsoftware.org/isdl.php")
        print(f"   2. Ouvrez le script {INSTALLER_ISS} dans Inno Setup et cliquez sur Compile")
        print("      OU lancez simplement : build_release.bat")
        readme = os.path.join(RELEASE_DIR, "LISEZ_MOI_INSTALLATEUR.txt")
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write(
                "=== CRÉATION DU FICHIER Sinistres-App-Setup.exe ===\n\n"
                "Le dossier d'exécutable autonome est généré et prêt dans : dist/windows/Sinistres App/\n\n"
                "Pour créer le fichier d'installation unique Sinistres-App-Setup.exe :\n"
                "1. Téléchargez et installez Inno Setup 6 : https://jrsoftware.org/isdl.php\n"
                "2. Double-cliquez sur le script : installer\\Sinistres-App.iss\n"
                "3. Cliquez sur Compile (ou exécutez build_release.bat)\n\n"
                "Le fichier Sinistres-App-Setup.exe apparaîtra automatiquement dans ce dossier release/.\n"
            )
        log(f"Instructions enregistrées dans {readme}", "ℹ️")


def build_all():
    log("DÉMARRAGE DU BUILD REPRODUCTIBLE — SINISTRES APP V4", "🚀")
    step_clean()
    step_compile()
    step_package()
    step_installer()
    log("BUILD TERMINÉ. Le livrable final est prêt pour la distribution Windows.", "🏁")


if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "all"
    if action == "clean":
        step_clean()
    elif action == "compile":
        step_compile()
    elif action == "package":
        step_package()
    elif action == "installer":
        step_installer()
    elif action == "all":
        build_all()
    else:
        print(f"Action inconnue : {action}. Options : clean | compile | package | installer | all")
