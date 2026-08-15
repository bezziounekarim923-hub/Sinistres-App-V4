# -*- coding: utf-8 -*-
"""
Tests du système de licences .lic (signature Ed25519), de la session
Administrateur / Gestionnaire, et de la révocation.

Couverture (cahier des charges §15) :
  - création / connexion d'un Administrateur ;
  - création d'un Gestionnaire ;
  - génération d'une licence ;
  - licence valable, expirée, modifiée, mauvaise signature, autre utilisateur,
    révoquée ;
  - mot de passe incorrect ;
  - Gestionnaire sans accès à l'administration ;
  - impossibilité de modifier localement la date d'expiration ;
  - renouvellement d'une licence.
"""
import os
import json
import shutil
import tempfile
import unittest
import datetime
from unittest.mock import patch

import database as db
import licensing


class LicenseSystemTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="licsys_")
        self._patch = patch.object(db, "get_app_dir", lambda: self.tmp)
        self._patch.start()
        db.init_db()
        licensing.ensure_signing_keys()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------- utilitaires
    def _make_license(self, licensee="gestionnaire01", days=365, start_date=None):
        path = os.path.join(self.tmp, "test.lic")
        doc = licensing.generate_license_file(path, licensee=licensee, duration_days=days, start_date=start_date)
        db.insert_license(doc)
        return path, doc

    def _read_license(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    # ------------------------------------------------------------- comptes
    def test_create_and_login_admin(self):
        db.create_user("owner", "admin-secret", "Administrateur")
        user = db.authenticate("owner", "admin-secret")
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "Administrateur")

    def test_wrong_password_fails(self):
        db.create_user("owner", "admin-secret", "Administrateur")
        self.assertIsNone(db.authenticate("owner", "mauvais"))
        self.assertIsNone(db.authenticate("inconnu", "admin-secret"))

    def test_create_gestionnaire(self):
        db.create_user("gest1", "motdepasse", "Gestionnaire", full_name="Karim B.")
        users = db.fetch_users()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]["role"], "Gestionnaire")
        self.assertEqual(users[0]["full_name"], "Karim B.")
        self.assertEqual(db.authenticate("gest1", "motdepasse")["role"], "Gestionnaire")

    def test_disabled_account_cannot_login(self):
        db.create_user("gest1", "motdepasse", "Gestionnaire")
        db.set_user_disabled("gest1", True)
        self.assertIsNone(db.authenticate("gest1", "motdepasse"))
        db.set_user_disabled("gest1", False)
        self.assertIsNotNone(db.authenticate("gest1", "motdepasse"))

    def test_gestionnaire_has_no_admin_role(self):
        db.create_user("owner", "admin-secret", "Administrateur")
        db.create_user("gest1", "motdepasse", "Gestionnaire")
        gest = db.authenticate("gest1", "motdepasse")
        self.assertEqual(gest["role"], "Gestionnaire")
        # Le rôle Gestionnaire ne permet pas l'administration.
        self.assertNotEqual(gest["role"], "Administrateur")
        # Seul un Administrateur peut être utilisé pour la session d'admin.
        def is_admin_authorized(user):
            return user and user["role"] == "Administrateur"
        self.assertFalse(is_admin_authorized(gest))
        self.assertTrue(is_admin_authorized(db.authenticate("owner", "admin-secret")))

    # ------------------------------------------------------------- licences
    def test_generate_license_and_valid_check(self):
        path, doc = self._make_license()
        self.assertTrue(os.path.exists(path))
        self.assertTrue(doc["license_id"].startswith("LIC-"))
        self.assertEqual(doc["licensee"], "gestionnaire01")

        result = licensing.load_license_file(path)
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["license_id"], doc["license_id"])

        # Registre côté Admin
        lic = db.get_license_by_id(doc["license_id"])
        self.assertIsNotNone(lic)
        self.assertEqual(lic["licensee"], "gestionnaire01")

    def test_activation_binds_account(self):
        path, doc = self._make_license(licensee="karim")
        res = licensing.activate_license_file(path, "karim")
        self.assertTrue(res["ok"])
        self.assertTrue(licensing.check_license()["valid"])
        self.assertEqual(licensing.check_license()["label"], "karim")

    def test_license_for_other_user_rejected(self):
        path, _ = self._make_license(licensee="karim")
        res = licensing.activate_license_file(path, "autre_utilisateur")
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "wrong_account")

    def test_license_expired(self):
        path, _ = self._make_license(licensee="karim", days=1, start_date=datetime.date(2020, 1, 1))
        result = licensing.load_license_file(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "expired")

    def test_license_tampered_expiry_is_rejected(self):
        # Un Gestionnaire ne peut pas modifier localement la date d'expiration :
        # la signature ne correspond plus.
        path, _ = self._make_license(licensee="karim")
        data = self._read_license(path)
        data["expiry_date"] = "2099-01-01"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        result = licensing.load_license_file(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "tampered")

    def test_license_bad_signature_rejected(self):
        path, _ = self._make_license(licensee="karim")
        data = self._read_license(path)
        data["signature"] = "A" * len(data["signature"])
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        result = licensing.load_license_file(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "tampered")

    def test_license_not_a_sinistres_license(self):
        path = os.path.join(self.tmp, "fake.lic")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"hello": "world"}, fh)
        result = licensing.load_license_file(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "not_license")

    def test_license_revoked(self):
        path, doc = self._make_license(licensee="karim")
        db.revoke_license(doc["license_id"])
        licensing.build_revocation_list(db.revoked_license_ids())
        result = licensing.load_license_file(path)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "revoked")
        # check_license rejette aussi la révocation après activation
        licensing.apply_license_document(doc)
        self.assertEqual(licensing.check_license()["reason"], "revoked")

    def test_license_renewal(self):
        path1, doc1 = self._make_license(licensee="karim")
        path2, doc2 = self._make_license(licensee="karim")
        self.assertNotEqual(doc1["license_id"], doc2["license_id"])
        self.assertTrue(licensing.load_license_file(path1)["ok"])
        self.assertTrue(licensing.load_license_file(path2)["ok"])
        self.assertEqual(db.licenses_count(), 2)

    def test_private_key_required_to_sign(self):
        # Sans clé privée, impossible de signer une nouvelle licence.
        priv_path = os.path.join(self.tmp, licensing.PRIVATE_KEY_FILE)
        pub_path = os.path.join(self.tmp, licensing.PUBLIC_KEY_FILE)
        os.remove(priv_path)
        self.assertFalse(licensing.has_private_key())
        with self.assertRaises(RuntimeError):
            licensing.generate_license_file(os.path.join(self.tmp, "x.lic"), licensee="x")
        os.remove(pub_path)

    def test_check_license_valid_after_apply(self):
        path, doc = self._make_license(licensee="karim")
        licensing.apply_license_document(doc)
        status = licensing.check_license()
        self.assertTrue(status["valid"])
        self.assertEqual(status["license_id"], doc["license_id"])
        self.assertEqual(status["label"], "karim")
        self.assertGreaterEqual(status["days_left"], 364)

    def test_registry_and_count(self):
        self.assertEqual(db.licenses_count(), 0)
        self._make_license(licensee="a")
        self._make_license(licensee="b")
        self.assertEqual(db.licenses_count(), 2)
        ids = [l["license_id"] for l in db.fetch_licenses()]
        self.assertEqual(len(ids), 2)


if __name__ == "__main__":
    unittest.main()
