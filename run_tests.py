#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lance tous les tests unitaires du projet (découverte automatique).

Multi-plateforme : utilise l'interpréteur Python courant (``sys.executable``) au
lieu d'un chemin Windows codé en dur, et exécute TOUS les modules du dossier
``tests/`` (et non un seul).

Utilisation :  python run_tests.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    cmd = [
        sys.executable, "-m", "unittest",
        "discover", "-s", "tests", "-p", "test_*.py", "-v",
    ]
    result = subprocess.run(cmd, cwd=HERE)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
