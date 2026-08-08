import os
import sys
import unittest
import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import analytics as an


# "Aujourd'hui" est figé sur une date sûre (mi-mois, loin de toute frontière de
# période) pour que les comptages par jour/semaine/mois/année soient déterministes
# et indépendants du jour réel où la suite de tests est exécutée.
_REFERENCE_TODAY = datetime.date(2026, 8, 15)
_REAL_DATE = datetime.date


class _FakeDate(_REAL_DATE):
    @classmethod
    def today(cls):
        return _REAL_DATE(2026, 8, 15)


class AnalyticsEnhancementsTests(unittest.TestCase):
    def test_kpis_includes_period_counts(self):
        records = [
            {"annee": 2026, "date_sinistre": "2026-08-15", "statut_reglement": "REGLER", "montant_pv_expert": 1000, "montant_reglement_avant_rp": 900},
            {"annee": 2026, "date_sinistre": "2026-08-12", "statut_reglement": "INSTANCE", "montant_pv_expert": 2000, "montant_reglement_avant_rp": 1500},
            {"annee": 2026, "date_sinistre": "2026-08-01", "statut_reglement": "INSTANCE", "montant_pv_expert": 3000, "montant_reglement_avant_rp": 2500},
            {"annee": 2025, "date_sinistre": "2025-06-04", "statut_reglement": "NEANT", "montant_pv_expert": 4000, "montant_reglement_avant_rp": 3500},
        ]

        with patch.object(an.datetime, "date", _FakeDate):
            kpis = an.kpis(records)

        self.assertEqual(kpis["total"], 4)
        self.assertEqual(kpis["sinistres_jour"], 1)      # 2026-08-15 uniquement
        self.assertEqual(kpis["sinistres_semaine"], 2)   # 08-15 + 08-12 (<= 6 jours)
        self.assertEqual(kpis["sinistres_mois"], 3)      # 08-15 + 08-12 + 08-01
        self.assertEqual(kpis["sinistres_annee"], 3)     # 3 en 2026 (2025 exclu)
        self.assertEqual(kpis["dossiers_attente"], 3)    # INSTANCE, INSTANCE, NEANT
        self.assertEqual(kpis["dossiers_sans_expertise"], 4)
        self.assertEqual(kpis["dossiers_sans_pv"], 4)

    def test_alertes_assign_priority_and_reason(self):
        records = [{
            "chauffeur": "Alice",
            "date_sinistre": _REFERENCE_TODAY.isoformat(),
            "date_expertise": None,
            "date_reception_pv": None,
            "statut_reglement": "INSTANCE",
            "numero_dossier": "D1",
        }]

        with patch.object(an.datetime, "date", _FakeDate):
            alerts = an.alertes(records)

        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["priority"], "haute")
        self.assertIn("expertise", alerts[0]["reason"].lower())


if __name__ == "__main__":
    unittest.main()
