# -*- coding: utf-8 -*-
import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import database as db
import licensing
import client_access as ca


class TestClientAccess(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, db.DB_NAME)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_export_and_import_client_access(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            db.init_db()
            sini_file = os.path.join(self.tmp, "client_alger.sini")
            
            # 1. L'éditeur exporte un accès client de 365 jours
            res_path = ca.export_client_access_file(
                sini_file,
                client_username="transport_dz",
                client_password="secretpassword",
                client_role="Gestionnaire",
                duration_days=365,
                admin_password="masteradminpassword"
            )
            self.assertTrue(os.path.exists(res_path))
            
            # 2. Le client importe sur un PC vierge
            ok, user, expiry = ca.import_client_access_file(sini_file)
            self.assertTrue(ok)
            self.assertEqual(user, "transport_dz")
            self.assertIn("202", expiry)
            
            # 3. Vérification en base : l'utilisateur transport_dz est Gestionnaire
            auth_client = db.authenticate("transport_dz", "secretpassword")
            self.assertIsNotNone(auth_client)
            self.assertEqual(auth_client["role"], "Gestionnaire")
            
            # 4. Vérification du compte Admin de réserve
            auth_admin = db.authenticate("admin", "masteradminpassword")
            self.assertIsNotNone(auth_admin)
            self.assertEqual(auth_admin["role"], "Administrateur")
            
            # 5. Vérification de la licence active
            lic_status = licensing.check_license()
            self.assertTrue(lic_status["valid"])
            self.assertGreaterEqual(lic_status["days_left"], 364)

    def test_invalid_signature_raises(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            db.init_db()
            sini_file = os.path.join(self.tmp, "corrupt.sini")
            ca.export_client_access_file(sini_file, "user1", "pass1", "Gestionnaire", 365)
            
            # Falsification du contenu sans connaître APP_SECRET
            with open(sini_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            data["payload"]["client_user"]["role"] = "Administrateur"
            with open(sini_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
                
            with self.assertRaises(ValueError):
                ca.import_client_access_file(sini_file)

    def test_export_and_import_license_file(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            db.init_db()
            lic_file = os.path.join(self.tmp, "licence_manager.sini")

            # 1. L'éditeur génère une licence seule (sans identifiants)
            res_path = ca.export_license_file(lic_file, label="Karim", duration_days=365)
            self.assertTrue(os.path.exists(res_path))

            # 2. Le fichier ne contient AUCUN compte (format v2)
            with open(lic_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(data["payload"]["kind"], "license")
            self.assertNotIn("client_user", data["payload"])
            self.assertNotIn("admin_user", data["payload"])
            self.assertEqual(ca.detect_client_file_kind(lic_file), "license")

            # 3. Le gestionnaire active sa licence depuis le fichier
            ok, expiry, label = ca.import_license_file(lic_file)
            self.assertTrue(ok)
            self.assertIn("202", expiry)
            self.assertEqual(label, "Karim")
            self.assertTrue(licensing.check_license()["valid"])
            self.assertGreaterEqual(licensing.check_license()["days_left"], 364)

            # 4. Aucun compte n'a été créé automatiquement
            self.assertEqual(db.user_count(), 0)

    def test_license_file_invalid_signature_raises(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            db.init_db()
            lic_file = os.path.join(self.tmp, "fake_licence.sini")
            ca.export_license_file(lic_file, label="X", duration_days=30)

            # Falsification du contenu sans connaître APP_SECRET
            with open(lic_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            data["payload"]["license"]["duration_days"] = 9999
            with open(lic_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh)

            with self.assertRaises(ValueError):
                ca.import_license_file(lic_file)

    def test_import_license_file_rejects_full_format(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            db.init_db()
            sini_file = os.path.join(self.tmp, "ancien_complet.sini")
            ca.export_client_access_file(sini_file, "ancien", "pass123", "Gestionnaire", 365)
            self.assertEqual(ca.detect_client_file_kind(sini_file), "full")
            with self.assertRaises(ValueError):
                ca.import_license_file(sini_file)


if __name__ == "__main__":
    unittest.main()
