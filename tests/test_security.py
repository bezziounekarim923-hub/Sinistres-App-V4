import os
import sys
import json
import shutil
import tempfile
import unittest
import hashlib
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import database as db
import licensing


class _IsolatedDir(unittest.TestCase):
    """Dossier d'application isolé (base + fichiers de licence en temp)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sinistres_sec_")
        self._patch = patch.object(db, "get_app_dir", lambda: self.tmp)
        self._patch.start()
        db.init_db()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


# --------------------------------------------------------------- S1 : comptes utilisateurs
class UserPasswordTests(_IsolatedDir):
    def test_create_user_stores_pbkdf2_and_authenticates(self):
        db.create_user("alice", "S3cret!", "Gestionnaire")
        with db.db_connection() as conn:
            row = conn.execute("SELECT password_hash, salt FROM users WHERE username='alice'").fetchone()
        self.assertTrue(row["password_hash"].startswith("pbkdf2_sha256$"))
        self.assertIsNone(row["salt"])

        user = db.authenticate("alice", "S3cret!")
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "alice")

    def test_wrong_password_fails(self):
        db.create_user("bob", "good-pw", "Consultation")
        self.assertIsNone(db.authenticate("bob", "bad-pw"))
        self.assertIsNone(db.authenticate("bob", ""))

    def test_unknown_user_fails(self):
        self.assertIsNone(db.authenticate("ghost", "whatever"))

    def test_legacy_sha256_user_upgrades_on_login(self):
        # Simule un compte créé avec l'ancien hachage SHA-256 monopasse.
        salt = "abc123"
        digest = hashlib.sha256((salt + "oldpw").encode("utf-8")).hexdigest()
        with db.db_connection() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
                ("legacy", digest, salt, "Administrateur", "2024-01-01T00:00:00"),
            )
            conn.commit()
        # L'ancien mot de passe doit encore fonctionner (compatibilité).
        user = db.authenticate("legacy", "oldpw")
        self.assertIsNotNone(user)
        # ... et le hachage doit avoir été mis à niveau en PBKDF2 (sel effacé).
        with db.db_connection() as conn:
            row = conn.execute("SELECT password_hash, salt FROM users WHERE username='legacy'").fetchone()
        self.assertTrue(row["password_hash"].startswith("pbkdf2_sha256$"))
        self.assertIsNone(row["salt"])
        # La re-connexion doit fonctionner avec le nouveau hachage.
        self.assertIsNotNone(db.authenticate("legacy", "oldpw"))

    def test_update_user_password_uses_pbkdf2(self):
        db.create_user("carol", "initial", "Consultation")
        uid = db.fetch_users()[0]["id"]
        db.update_user_password(uid, "nouveau")
        self.assertIsNone(db.authenticate("carol", "initial"))
        self.assertIsNotNone(db.authenticate("carol", "nouveau"))
        with db.db_connection() as conn:
            row = conn.execute("SELECT salt FROM users WHERE username='carol'").fetchone()
        self.assertIsNone(row["salt"])

    def test_verify_password_constant_time_boolean(self):
        h = db._hash_password_pbkdf2("pw")
        self.assertTrue(db.verify_password("pw", h))
        self.assertFalse(db.verify_password("Pw", h))
        self.assertFalse(db.verify_password("pw", "not-a-real-hash"))


# --------------------------------------------------------------- S1 : mot de passe maître
class MasterPasswordTests(_IsolatedDir):
    def test_set_and_check(self):
        self.assertFalse(licensing.master_password_is_set())
        licensing.set_master_password("master-secret")
        self.assertTrue(licensing.master_password_is_set())
        self.assertTrue(licensing.check_master_password("master-secret"))
        self.assertFalse(licensing.check_master_password("wrong"))

    def test_stored_format_is_pbkdf2(self):
        licensing.set_master_password("abc")
        with open(licensing.get_master_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data.get("algo"), "pbkdf2_sha256")
        self.assertTrue(data["hash"].startswith("pbkdf2_sha256$"))
        self.assertNotIn("salt", data)  # sel embarqué dans le hash, pas séparé

    def test_legacy_master_upgrades_on_check(self):
        # Simule l'ancien format {"salt", "hash"} SHA-256.
        salt = "deadbeef"
        digest = hashlib.sha256((salt + "oldmaster").encode("utf-8")).hexdigest()
        with open(licensing.get_master_path(), "w", encoding="utf-8") as fh:
            json.dump({"salt": salt, "hash": digest}, fh)
        self.assertTrue(licensing.check_master_password("oldmaster"))
        # Vérifie la mise à niveau vers PBKDF2.
        with open(licensing.get_master_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data.get("algo"), "pbkdf2_sha256")
        self.assertTrue(data["hash"].startswith("pbkdf2_sha256$"))
        self.assertTrue(licensing.check_master_password("oldmaster"))


if __name__ == "__main__":
    unittest.main()
