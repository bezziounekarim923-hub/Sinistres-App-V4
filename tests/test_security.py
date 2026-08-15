import os
import sys
import json
import hmac
import shutil
import tempfile
import unittest
import hashlib
import datetime
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

    def test_delete_all_users_removes_every_account(self):
        db.create_user("admin1", "pw-admin", "Administrateur")
        db.create_user("gest", "pw-gest", "Gestionnaire")
        db.create_user("lecteur", "pw-lect", "Consultation")
        self.assertEqual(db.user_count(), 3)

        removed = db.delete_all_users()

        self.assertEqual(removed, 3)
        self.assertEqual(db.user_count(), 0)
        self.assertIsNone(db.authenticate("admin1", "pw-admin"))
        self.assertIsNone(db.authenticate("gest", "pw-gest"))
        self.assertIsNone(db.authenticate("lecteur", "pw-lect"))

    def test_delete_all_users_returns_zero_when_none(self):
        self.assertEqual(db.user_count(), 0)
        self.assertEqual(db.delete_all_users(), 0)


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


# --------------------------------------------------------------- S2 : signature de licence
class LicenseSigningTests(_IsolatedDir):
    def _set_master(self, password="master-pw"):
        licensing.set_master_password(password)

    def test_new_token_signed_with_master_key_verifies(self):
        self._set_master()
        token = licensing.generate_license_token(duration_days=10, label="poste-A")
        parsed = licensing._decode_token(token)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["label"], "poste-A")
        ok, msg = licensing.apply_license_token(token)
        self.assertTrue(ok, msg)
        status = licensing.check_license()
        self.assertTrue(status["valid"])

    def test_token_from_app_secret_alone_still_validates(self):
        """Compatibilité ascendante : un jeton signé avec le seul APP_SECRET
        (format d'avant S2) doit encore être accepté."""
        self._set_master()  # un master est défini => clé maître prioritaire
        import base64 as _b64
        expiry = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
        payload = f"{expiry}|legacy"
        legacy_sig = hmac.new(licensing.APP_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        raw = f"{payload}|{legacy_sig}"
        encoded = _b64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")
        token = "-".join(encoded[i:i + 5] for i in range(0, len(encoded), 5))
        parsed = licensing._decode_token(token)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["label"], "legacy")

    def test_token_rejected_when_signature_tampered(self):
        self._set_master()
        token = licensing.generate_license_token(duration_days=10, label="x")
        # Corrompt la signature : remplace le dernier groupe.
        parts = token.split("-")
        parts[-1] = "AAAAA" if parts[-1] != "AAAAA" else "BBBBB"
        tampered = "-".join(parts)
        self.assertIsNone(licensing._decode_token(tampered))

    def test_master_key_differs_from_app_secret_only(self):
        """La clé de signature doit différer selon le mot de passe maître :
        un jeton forgé avec APP_SECRET seul ne correspond pas à la clé maître."""
        self._set_master("secret-A")
        key_a = licensing._signing_key()
        self._set_master("secret-B")
        key_b = licensing._signing_key()
        self.assertNotEqual(key_a, key_b)
        self.assertNotEqual(key_a, licensing.APP_SECRET.encode("utf-8"))


# --------------------------------------------------------------- S3 : liste blanche get_distinct
class GetDistinctWhitelistTests(_IsolatedDir):
    def test_allowed_column_returns_values(self):
        db.bulk_insert([{"annee": 2024, "chauffeur": "Alice", "date_sinistre": "2024-01-01",
                         "source_sheet": "2024"},
                        {"annee": 2024, "chauffeur": "Bob", "date_sinistre": "2024-02-01",
                         "source_sheet": "2024"}])
        values = db.get_distinct("chauffeur")
        self.assertEqual(sorted(values), ["Alice", "Bob"])

    def test_disallowed_column_raises(self):
        with self.assertRaises(ValueError):
            db.get_distinct("chauffeur; DROP TABLE sinistres; --")

    def test_nonexistent_column_raises(self):
        with self.assertRaises(ValueError):
            db.get_distinct("does_not_exist")


if __name__ == "__main__":
    unittest.main()
