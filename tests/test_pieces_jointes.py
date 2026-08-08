# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
import database as db
import pieces_jointes as pj


class TestPiecesJointes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.record = {
            "numero": "100",
            "annee": 2026,
            "numero_dossier": "DOS/2026/01",
            "chauffeur": "Jean DUPONT"
        }

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_get_dossier_folder_name(self):
        name = pj.get_dossier_folder_name(self.record)
        self.assertIn("DOS_2026_01", name)
        self.assertIn("Jean_DUPONT", name)

    def test_add_and_list_attachments(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            dummy_file = os.path.join(self.tmp, "test_photo.jpg")
            with open(dummy_file, "w") as f:
                f.write("image data")

            dest = pj.add_attachment(self.record, dummy_file)
            self.assertIsNotNone(dest)
            self.assertTrue(os.path.exists(dest))

            items = pj.list_attachments(self.record)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["name"], "test_photo.jpg")
            self.assertEqual(items[0]["ext"], ".jpg")
            self.assertEqual(pj.count_attachments(self.record), 1)

    def test_duplicate_names_handled(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            f1 = os.path.join(self.tmp, "photo.jpg")
            with open(f1, "w") as f:
                f.write("v1")
            pj.add_attachment(self.record, f1)

            # Ajout du même nom depuis un sous-dossier
            sub = os.path.join(self.tmp, "sub")
            os.makedirs(sub, exist_ok=True)
            f2 = os.path.join(sub, "photo.jpg")
            with open(f2, "w") as f:
                f.write("v2")
            pj.add_attachment(self.record, f2)

            items = pj.list_attachments(self.record)
            self.assertEqual(len(items), 2)
            names = [i["name"] for i in items]
            self.assertIn("photo.jpg", names)
            self.assertIn("photo_1.jpg", names)

    def test_delete_attachment(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            dummy = os.path.join(self.tmp, "doc.pdf")
            with open(dummy, "w") as f:
                f.write("pdf")
            pj.add_attachment(self.record, dummy)
            self.assertEqual(pj.count_attachments(self.record), 1)

            res = pj.delete_attachment(self.record, "doc.pdf")
            self.assertTrue(res)
            self.assertEqual(pj.count_attachments(self.record), 0)


if __name__ == "__main__":
    unittest.main()
