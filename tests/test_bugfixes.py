import os
import sys
import shutil
import tempfile
import unittest
import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import database as db


class _IsolatedDb(unittest.TestCase):
    """Base de données SQLite isolée dans un dossier temporaire (via monkeypatch
    de get_app_dir) : aucune écriture sur la vraie sinistres.db."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sinistres_test_")
        self._patch = patch.object(db, "get_app_dir", lambda: self.tmp)
        self._patch.start()
        db.init_db()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


# ----------------------------------------------------------------- B1 : montant_achats
class MontantAchatsTests(_IsolatedDb):
    """B1 — Le champ montant_achats (lu dans l'Excel) doit être persisté en base,
    alors qu'il était silencieusement jeté avant l'ajout à COLUMNS / au schéma."""

    def test_column_exists_in_schema(self):
        conn = db.get_connection()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(sinistres)")]
        conn.close()
        self.assertIn("montant_achats", cols)

    def test_persisted_through_bulk_insert(self):
        db.bulk_insert([{
            "annee": 2024, "chauffeur": "Ach", "date_sinistre": "2024-05-01",
            "source_sheet": "2024", "montant_achats": 1234.56,
        }])
        rows = db.fetch_all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["montant_achats"], 1234.56)

    def test_persisted_through_update(self):
        db.bulk_insert([{
            "annee": 2024, "chauffeur": "Ach2", "date_sinistre": "2024-05-02",
            "source_sheet": "2024",
        }])
        rid = db.fetch_all()[0]["id"]
        db.update_sinistre(rid, {"montant_achats": 99.5})
        row = db.fetch_all({"include_deleted": True})[0]
        self.assertEqual(row["montant_achats"], 99.5)


# ----------------------------------------------------------------- B2 : updated_at
class UpdatedAtTests(_IsolatedDb):
    """B2 — update_sinistre doit actualiser updated_at (avant, il ne le faisait jamais)."""

    def test_update_sets_updated_at(self):
        db.bulk_insert([{
            "annee": 2024, "chauffeur": "Upd", "date_sinistre": "2024-05-01",
            "source_sheet": "2024", "statut_reglement": "INSTANCE",
        }])
        row = db.fetch_all()[0]
        rid = row["id"]
        self.assertIsNone(row.get("updated_at"))  # bulk_insert ne le renseigne pas

        db.update_sinistre(rid, {"statut_reglement": "REGLER", "date_reglement": "2024-06-01"})
        after = db.fetch_all({"include_deleted": True})[0]
        self.assertEqual(after["statut_reglement"], "REGLER")
        self.assertIsNotNone(after["updated_at"])
        # timestamp ISO valide
        datetime.datetime.fromisoformat(after["updated_at"])


# ----------------------------------------------------------------- B4 : rotation sauvegardes
class BackupRotationTests(unittest.TestCase):
    """B4 — backup_db crée une copie à chaque opération ; sans rotation le dossier
    backups/ grossit à l'infini. On vérifie que _prune_backups limite le nombre."""

    def test_prune_keeps_most_recent(self):
        tmp = tempfile.mkdtemp(prefix="sinistres_bk_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        keep = db.MAX_BACKUPS
        for i in range(keep + 5):
            with open(os.path.join(tmp, f"sinistres_backup_{i:04d}.db"), "w") as fh:
                fh.write("x")
            os.utime(os.path.join(tmp, f"sinistres_backup_{i:04d}.db"), (i, i))  # mtime croissante
        db._prune_backups(tmp)
        remaining = sorted(f for f in os.listdir(tmp) if f.startswith("sinistres_backup_"))
        self.assertEqual(len(remaining), keep)
        # les 5 plus anciens (i = 0..4) ont été supprimés
        for i in range(5):
            self.assertNotIn(f"sinistres_backup_{i:04d}.db", remaining)

    def test_backup_db_runs_rotation(self):
        tmp = tempfile.mkdtemp(prefix="sinistres_bk2_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with patch.object(db, "get_app_dir", lambda: tmp):
            with open(os.path.join(tmp, db.DB_NAME), "w") as fh:
                fh.write("dummy")
            bk = os.path.join(tmp, "backups")
            os.makedirs(bk, exist_ok=True)
            for i in range(db.MAX_BACKUPS + 3):
                with open(os.path.join(bk, f"sinistres_backup_old_{i:04d}.db"), "w") as fh:
                    fh.write("old")
            bp = db.backup_db()
        self.assertIsNotNone(bp)
        self.assertTrue(os.path.exists(bp))
        remaining = [f for f in os.listdir(bk) if f.startswith("sinistres_backup_")]
        self.assertLessEqual(len(remaining), db.MAX_BACKUPS)


# ----------------------------------------------------------------- B5 : dossier inscriptible
class AppDirResolutionTests(unittest.TestCase):
    """B5 — En .exe dans Program Files, get_app_dir() doit basculer vers un dossier
    utilisateur inscriptible et y migrer les fichiers existants."""

    def test_dev_keeps_legacy_even_if_not_writable(self):
        tmp = tempfile.mkdtemp(prefix="sinistres_dir_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        with patch.object(db, "_is_writable", lambda p: False):
            self.assertEqual(db._resolve_app_dir(tmp, is_frozen=False), tmp)

    def test_frozen_writable_keeps_legacy(self):
        tmp = tempfile.mkdtemp(prefix="sinistres_dir_")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.assertEqual(db._resolve_app_dir(tmp, is_frozen=True), tmp)  # tmp est inscriptible

    def test_frozen_unwritable_falls_back_and_migrates(self):
        legacy = tempfile.mkdtemp(prefix="sinistres_legacy_")
        target = tempfile.mkdtemp(prefix="sinistres_target_")
        self.addCleanup(shutil.rmtree, legacy, ignore_errors=True)
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        with open(os.path.join(legacy, db.DB_NAME), "w") as fh:
            fh.write("SENTINEL_DB")
        with open(os.path.join(legacy, "license.json"), "w") as fh:
            fh.write("SENTINEL_LIC")
        with patch.object(db, "_is_writable", lambda p: False), \
             patch.object(db, "_user_data_dir", lambda: target):
            result = db._resolve_app_dir(legacy, is_frozen=True)
        self.assertEqual(result, target)
        with open(os.path.join(target, db.DB_NAME)) as fh:
            self.assertEqual(fh.read(), "SENTINEL_DB")
        with open(os.path.join(target, "license.json")) as fh:
            self.assertEqual(fh.read(), "SENTINEL_LIC")

    def test_migration_does_not_overwrite_existing(self):
        legacy = tempfile.mkdtemp(prefix="sinistres_legacy2_")
        target = tempfile.mkdtemp(prefix="sinistres_target2_")
        self.addCleanup(shutil.rmtree, legacy, ignore_errors=True)
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        with open(os.path.join(legacy, db.DB_NAME), "w") as fh:
            fh.write("OLD")
        with open(os.path.join(target, db.DB_NAME), "w") as fh:
            fh.write("EXISTING")
        db._migrate_app_files(legacy, target)
        with open(os.path.join(target, db.DB_NAME)) as fh:
            self.assertEqual(fh.read(), "EXISTING")  # non écrasé


if __name__ == "__main__":
    unittest.main()
