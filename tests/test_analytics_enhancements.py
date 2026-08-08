import os
import sys
import unittest
import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import analytics as an


class AnalyticsEnhancementsTests(unittest.TestCase):
    def test_kpis_includes_period_counts(self):
        today = datetime.date.today().isoformat()
        week_ago = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
        month_ago = (datetime.date.today() - datetime.timedelta(days=20)).isoformat()
        year_ago = (datetime.date.today() - datetime.timedelta(days=400)).isoformat()
        records = [
            {"annee": 2026, "date_sinistre": today, "statut_reglement": "REGLER", "montant_pv_expert": 1000, "montant_reglement_avant_rp": 900},
            {"annee": 2026, "date_sinistre": week_ago, "statut_reglement": "INSTANCE", "montant_pv_expert": 2000, "montant_reglement_avant_rp": 1500},
            {"annee": 2026, "date_sinistre": month_ago, "statut_reglement": "INSTANCE", "montant_pv_expert": 3000, "montant_reglement_avant_rp": 2500},
            {"annee": 2025, "date_sinistre": year_ago, "statut_reglement": "NEANT", "montant_pv_expert": 4000, "montant_reglement_avant_rp": 3500},
        ]

        kpis = an.kpis(records)
        self.assertEqual(kpis["total"], 4)
        self.assertEqual(kpis["sinistres_jour"], 1)
        self.assertEqual(kpis["sinistres_semaine"], 2)
        self.assertEqual(kpis["sinistres_mois"], 3)
        self.assertEqual(kpis["sinistres_annee"], 4)
        self.assertEqual(kpis["dossiers_attente"], 3)
        self.assertEqual(kpis["dossiers_sans_expertise"], 4)
        self.assertEqual(kpis["dossiers_sans_pv"], 4)

    def test_alertes_assign_priority_and_reason(self):
        today = datetime.date.today().isoformat()
        records = [{
            "chauffeur": "Alice",
            "date_sinistre": today,
            "date_expertise": None,
            "date_reception_pv": None,
            "statut_reglement": "INSTANCE",
            "numero_dossier": "D1",
        }]

        alerts = an.alertes(records)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["priority"], "haute")
        self.assertIn("expertise", alerts[0]["reason"].lower())


if __name__ == "__main__":
    unittest.main()
