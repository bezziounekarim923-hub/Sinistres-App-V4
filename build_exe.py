import os
import subprocess
import sys
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT, "dist", "windows")


def run(cmd):
    print("->", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


if __name__ == "__main__":
    if not os.path.exists(os.path.join(ROOT, "requirements.txt")):
        raise SystemExit("requirements.txt introuvable")

    if shutil.which("pyinstaller") is None:
        print("PyInstaller n'est pas installé. Installation en cours...")
        run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

    # Données à embarquer : spec de coordonnées de la fiche, et modèle PDF
    # officiel s'il est présent (pour le mode superposition). En --onefile, les
    # --add-data sont extraits dans le dossier temporaire __file__ au lancement.
    sep = ";" if os.name == "nt" else ":"
    add_data = ["--add-data", os.path.join(ROOT, "fiche_template_fields.json") + sep + "."]
    model_pdf = os.path.join(ROOT, "FICHE_DE_SINISTRE_MODELE.pdf")
    if os.path.exists(model_pdf):
        add_data += ["--add-data", model_pdf + sep + "."]
        print("Modèle de fiche embarqué : FICHE_DE_SINISTRE_MODELE.pdf")
    model_docx = os.path.join(ROOT, "FICHE_DE_SINISTRE_MODELE.docx")
    if os.path.exists(model_docx):
        add_data += ["--add-data", model_docx + sep + "."]
        print("Modèle de fiche Word embarqué : FICHE_DE_SINISTRE_MODELE.docx")

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "sinistres_app",
        "--distpath",
        OUTPUT_DIR,
        *add_data,
        "main.py",
    ])

    print("\n✅ Exécutable généré dans :")
    print(os.path.join(OUTPUT_DIR, "sinistres_app.exe"))
