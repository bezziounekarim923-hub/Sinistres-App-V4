import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import database as db
import analytics as an


class FiltersAndAnalyticsTests(unittest.TestCase):
    """Tests de filtrage/recherche et de KPI/alertes, sur une base isolée (temporaire)
    pour ne jamais toucher à la vraie sinistres.db de l'utilisateur."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sinistres_test_")
        self._patch = patch.object(db, "get_app_dir", lambda: self.tmp)
        self._patch.start()
        db.init_db()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _insert_two(self):
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

    def test_fetch_all_filters_and_search(self):
        self._insert_two()

        rows = db.fetch_all({"annee": 2024, "statut": "REGLER", "search": "Alice"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["chauffeur"], "Alice")

        rows = db.fetch_all({"search": "N°120"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["numero_dossier"], "N°120")

    def test_analytics_kpis_and_alerts(self):
        self._insert_two()

        rows = db.fetch_all()
        kpis = an.kpis(rows)
        self.assertEqual(kpis["total"], 2)
        self.assertEqual(kpis["regles"], 1)
        self.assertEqual(kpis["non_regles"], 1)

        alerts = an.alertes(rows)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["chauffeur"], "Bob")


if __name__ == "__main__":
    unittest.main()
