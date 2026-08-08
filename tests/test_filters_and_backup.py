import os
import sqlite3
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database as db
import analytics as an


def setup_function():
    db.init_db()
    conn = db.get_connection()
    conn.execute("DELETE FROM sinistres")
    conn.commit()
    conn.close()


def test_fetch_all_filters_and_search():
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO sinistres (annee, chauffeur, statut_reglement, date_sinistre, immatriculation, lieu_accident, numero_dossier, montant_pv_expert, montant_reglement_avant_rp, delai_reg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2024, "Alice", "REGLER", "2024-04-12", "1234AA", "Paris", "N°89", 1200.0, 1000.0, 15),
    )
    conn.execute(
        "INSERT INTO sinistres (annee, chauffeur, statut_reglement, date_sinistre, immatriculation, lieu_accident, numero_dossier, montant_pv_expert, montant_reglement_avant_rp, delai_reg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2025, "Bob", "EN COURS", "2025-05-10", "9999ZZ", "Lyon", "N°120", 3000.0, 2000.0, 40),
    )
    conn.commit()
    conn.close()

    filters = {"annee": 2024, "statut": "REGLER", "search": "Alice"}
    rows = db.fetch_all(filters)
    assert len(rows) == 1
    assert rows[0]["chauffeur"] == "Alice"

    filters = {"search": "N°120"}
    rows = db.fetch_all(filters)
    assert len(rows) == 1
    assert rows[0]["numero_dossier"] == "N°120"


def test_backup_path_creation():
    backup_dir = os.path.join(os.path.dirname(__file__), "..", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    assert os.path.isdir(backup_dir)


def test_analytics_kpis_and_alerts():
    conn = db.get_connection()
    conn.execute(
        "INSERT INTO sinistres (annee, chauffeur, statut_reglement, date_sinistre, immatriculation, lieu_accident, numero_dossier, montant_pv_expert, montant_reglement_avant_rp, delai_reg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2024, "Alice", "REGLER", "2024-04-12", "1234AA", "Paris", "N°89", 1200.0, 1000.0, 15),
    )
    conn.execute(
        "INSERT INTO sinistres (annee, chauffeur, statut_reglement, date_sinistre, immatriculation, lieu_accident, numero_dossier, montant_pv_expert, montant_reglement_avant_rp, delai_reg) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2025, "Bob", "EN COURS", "2025-05-10", "9999ZZ", "Lyon", "N°120", 3000.0, 2000.0, 40),
    )
    conn.commit()
    conn.close()

    rows = db.fetch_all()
    kpis = an.kpis(rows)
    assert kpis["total"] == 2
    assert kpis["regles"] == 1
    assert kpis["non_regles"] == 1

    alerts = an.alertes(rows)
    assert len(alerts) == 1
    assert alerts[0]["chauffeur"] == "Bob"
