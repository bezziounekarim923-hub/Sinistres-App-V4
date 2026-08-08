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
        "main.py",
    ])

    print("\n✅ Exécutable généré dans :")
    print(os.path.join(OUTPUT_DIR, "sinistres_app.exe"))
