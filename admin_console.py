# -*- coding: utf-8 -*-
"""
CONSOLE D'ADMINISTRATION — Sinistres App
========================================
Session Administrateur SÉPARÉE de l'application Gestionnaire (main.py).

Réservée au propriétaire de l'application : permet de
  1. créer / modifier / désactiver des comptes Gestionnaire ;
  2. générer, consulter, révoquer et renouveler les licences (.lic).

Lancer avec : python admin_console.py   (ou 5_console_admin.bat sous Windows)

La clé PRIVÉE de signature des licences est générée ici (une seule fois) et ne
sort jamais de ce poste : elle est exclue des copies destinées aux Gestionnaires.
"""
import os
import sys
import datetime

import app_logging
app_logging.setup_logging()

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import database as db
import licensing

COLOR_BG = "#f4f6f9"
COLOR_PRIMARY = "#1f3a5f"
COLOR_ACCENT = "#2f6fed"
COLOR_OK = "#1e8e5a"
COLOR_WARN = "#c0392b"
COLOR_CARD = "#ffffff"


# ------------------------------------------------------------------- connexion
class AdminFirstSetupDialog(tk.Toplevel):
    """Premier lancement de la console : création du compte Administrateur
    (propriétaire). Génère aussi la paire de clés de signature des licences."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Création du compte Administrateur")
        self.geometry("400x320")
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", parent.destroy)

        tk.Label(self, text="👑 Bienvenue", font=("Segoe UI", 13, "bold")).pack(pady=(16, 4))
        tk.Label(self, text="Aucun compte Administrateur n'existe encore.\nCréez le compte du propriétaire de l'application.",
                 justify="center", fg="#555").pack(pady=(0, 12))

        form = tk.Frame(self)
        form.pack(fill="x", padx=28)
        tk.Label(form, text="Nom d'utilisateur :").grid(row=0, column=0, sticky="w", pady=5)
        self.entry_user = ttk.Entry(form, width=24)
        self.entry_user.grid(row=0, column=1, pady=5)
        tk.Label(form, text="Mot de passe :").grid(row=1, column=0, sticky="w", pady=5)
        self.entry_pass = ttk.Entry(form, width=24, show="•")
        self.entry_pass.grid(row=1, column=1, pady=5)
        tk.Label(form, text="Confirmer :").grid(row=2, column=0, sticky="w", pady=5)
        self.entry_pass2 = ttk.Entry(form, width=24, show="•")
        self.entry_pass2.grid(row=2, column=1, pady=5)
        self.entry_user.focus_set()

        ttk.Button(self, text="✅ Créer le compte Administrateur", command=self._create).pack(pady=16)

    def _create(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get()
        password2 = self.entry_pass2.get()
        if not username or not password:
            messagebox.showwarning("Champs requis", "Nom d'utilisateur et mot de passe requis.")
            return
        if len(password) < 4:
            messagebox.showwarning("Mot de passe trop court", "Au moins 4 caractères.")
            return
        if password != password2:
            messagebox.showwarning("Erreur", "Les deux mots de passe ne correspondent pas.")
            return
        db.create_user(username, password, "Administrateur")
        licensing.ensure_signing_keys()
        db.log_action(username, "CREATION_COMPTE_ADMINISTRATEUR", dossier_label=username,
                      nouvelle_valeur={"username": username, "role": "Administrateur"})
        messagebox.showinfo("Compte créé", f"Le compte Administrateur « {username} » a été créé.\nVous pouvez maintenant vous connecter.")
        self.destroy()


class AdminLoginDialog(tk.Toplevel):
    """Connexion à la session Administrateur (rôle Administrateur uniquement)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Console d'administration — Connexion")
        self.geometry("380x260")
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", parent.destroy)

        tk.Label(self, text="👑 Session Administrateur", font=("Segoe UI", 13, "bold")).pack(pady=(20, 4))
        tk.Label(self, text="Réservée au propriétaire de l'application.", fg="#555").pack(pady=(0, 12))

        form = tk.Frame(self)
        form.pack(fill="x", padx=28)
        tk.Label(form, text="Nom d'utilisateur :").grid(row=0, column=0, sticky="w", pady=6)
        self.entry_user = ttk.Entry(form, width=22)
        self.entry_user.grid(row=0, column=1, pady=6)
        tk.Label(form, text="Mot de passe :").grid(row=1, column=0, sticky="w", pady=6)
        self.entry_pass = ttk.Entry(form, width=22, show="•")
        self.entry_pass.grid(row=1, column=1, pady=6)
        self.entry_pass.bind("<Return>", lambda e: self._login())

        btn = tk.Frame(self)
        btn.pack(pady=16)
        ttk.Button(btn, text="🔐 Connexion", command=self._login).pack(side="left", padx=6)
        ttk.Button(btn, text="Quitter", command=parent.destroy).pack(side="left", padx=6)
        self.entry_user.focus_set()

    def _login(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get()
        user = db.authenticate(username, password)
        if not user or user["role"] != "Administrateur":
            messagebox.showerror("Accès refusé",
                                 "Identifiants incorrects, ou ce compte n'a pas le rôle Administrateur.\n\n"
                                 "La session d'administration est réservée au propriétaire.")
            self.entry_pass.delete(0, "end")
            return
        self.parent.current_user = user["username"]
        self.destroy()


# ------------------------------------------------------------------- console
class AdminConsole(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Console d'administration — Sinistres App")
        self.geometry("1020x620")
        self.minsize(880, 520)
        self.configure(bg=COLOR_BG)

        db.init_db()
        self.current_user = None

        self.withdraw()
        # Premier lancement : création du compte Administrateur (et des clés).
        if db.user_count() == 0 or not any(u["role"] == "Administrateur" for u in db.fetch_users()):
            dlg = AdminFirstSetupDialog(self)
            self.wait_window(dlg)
        while not self.current_user:
            dlg = AdminLoginDialog(self)
            self.wait_window(dlg)
            if not self.current_user:
                return  # fermé sans connexion
        self.deiconify()

        self._setup_style()
        self._build_ui()
        self._refresh_all()

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(16, 10), font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("TButton", padding=6, font=("Segoe UI", 9))

    def _build_ui(self):
        header = tk.Frame(self, bg=COLOR_PRIMARY, height=56)
        header.pack(side="top", fill="x")
        tk.Label(header, text="👑 CONSOLE D'ADMINISTRATION", bg=COLOR_PRIMARY, fg="white",
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=20, pady=10)
        tk.Label(header, text=f"Connecté : {self.current_user} (Administrateur)",
                 bg=COLOR_PRIMARY, fg="#cfe0ff", font=("Segoe UI", 9)).pack(side="right", padx=20)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_comptes = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_licences = tk.Frame(self.notebook, bg=COLOR_BG)
        self.notebook.add(self.tab_comptes, text="👥 Comptes Gestionnaire")
        self.notebook.add(self.tab_licences, text="🎟️ Licences")

        self._build_comptes_tab()
        self._build_licences_tab()

    # ------------------------------------------------------------- comptes
    def _build_comptes_tab(self):
        top = tk.Frame(self.tab_comptes, bg=COLOR_BG)
        top.pack(fill="x", padx=12, pady=10)
        ttk.Button(top, text="➕ Créer un compte Gestionnaire", command=self._create_gestionnaire).pack(side="left", padx=4)
        ttk.Button(top, text="🔒 Réinitialiser le mot de passe", command=self._reset_password).pack(side="left", padx=4)
        ttk.Button(top, text="🚫 Désactiver / ✅ Activer", command=self._toggle_disabled).pack(side="left", padx=4)
        ttk.Button(top, text="🗑 Supprimer", command=self._delete_user).pack(side="left", padx=4)
        ttk.Button(top, text="🎟️ Générer une licence...", command=self._generate_license_for_selected).pack(side="right", padx=4)

        cols = ["username", "role", "full_name", "created_at", "disabled"]
        headers = ["Utilisateur", "Rôle", "Nom complet", "Créé le", "État"]
        frame = tk.Frame(self.tab_comptes)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree_comptes = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c, h in zip(cols, headers):
            self.tree_comptes.heading(c, text=h)
            self.tree_comptes.column(c, width=150, anchor="w")
        self.tree_comptes.column("disabled", width=90, anchor="center")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree_comptes.yview)
        self.tree_comptes.configure(yscrollcommand=vsb.set)
        self.tree_comptes.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _refresh_comptes(self):
        self.tree_comptes.delete(*self.tree_comptes.get_children())
        for u in db.fetch_users():
            etat = "❌ Désactivé" if u.get("disabled") else "✅ Actif"
            self.tree_comptes.insert("", "end", values=[
                u["username"], u["role"], u.get("full_name") or "", u.get("created_at") or "", etat
            ])

    def _get_selected_username(self):
        sel = self.tree_comptes.selection()
        if not sel:
            messagebox.showinfo("Sélection", "Veuillez sélectionner un compte dans la liste.")
            return None
        return self.tree_comptes.item(sel[0])["values"][0]

    def _create_gestionnaire(self):
        dlg = tk.Toplevel(self)
        dlg.title("Créer un compte Gestionnaire")
        dlg.geometry("400x320")
        dlg.grab_set()
        dlg.resizable(False, False)

        form = tk.Frame(dlg)
        form.pack(padx=24, pady=16)
        tk.Label(form, text="Nom d'utilisateur :").grid(row=0, column=0, sticky="w", pady=5)
        e_user = ttk.Entry(form, width=24)
        e_user.grid(row=0, column=1, pady=5)
        tk.Label(form, text="Nom complet (optionnel) :").grid(row=1, column=0, sticky="w", pady=5)
        e_name = ttk.Entry(form, width=24)
        e_name.grid(row=1, column=1, pady=5)
        tk.Label(form, text="Mot de passe initial :").grid(row=2, column=0, sticky="w", pady=5)
        e_pass = ttk.Entry(form, width=24, show="•")
        e_pass.grid(row=2, column=1, pady=5)
        tk.Label(form, text="Confirmer :").grid(row=3, column=0, sticky="w", pady=5)
        e_pass2 = ttk.Entry(form, width=24, show="•")
        e_pass2.grid(row=3, column=1, pady=5)

        def create():
            username = e_user.get().strip()
            password = e_pass.get()
            password2 = e_pass2.get()
            full_name = e_name.get().strip() or None
            if not username or not password:
                messagebox.showwarning("Champs requis", "Nom d'utilisateur et mot de passe requis.", parent=dlg)
                return
            if len(password) < 4:
                messagebox.showwarning("Mot de passe trop court", "Au moins 4 caractères.", parent=dlg)
                return
            if password != password2:
                messagebox.showwarning("Erreur", "Les deux mots de passe ne correspondent pas.", parent=dlg)
                return
            if db.fetch_user_by_username(username):
                messagebox.showerror("Erreur", f"Le compte « {username} » existe déjà.", parent=dlg)
                return
            db.create_user(username, password, "Gestionnaire", full_name=full_name)
            db.log_action(self.current_user, "CREATION_COMPTE_GESTIONNAIRE", dossier_label=username,
                          nouvelle_valeur={"username": username, "role": "Gestionnaire", "full_name": full_name})
            self._refresh_comptes()
            messagebox.showinfo("Compte créé",
                                f"Le compte Gestionnaire « {username} » a été créé.\n\n"
                                "Vous pouvez maintenant lui générer une licence (.lic) dans l'onglet « Licences ».",
                                parent=dlg)
            dlg.destroy()

        ttk.Button(dlg, text="✅ Créer", command=create).pack(pady=10)

    def _reset_password(self):
        username = self._get_selected_username()
        if not username:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Réinitialiser le mot de passe")
        dlg.geometry("360x200")
        dlg.grab_set()
        tk.Label(dlg, text=f"Nouveau mot de passe pour « {username} » :", wraplength=300).pack(padx=20, pady=(16, 6))
        e_pass = ttk.Entry(dlg, width=28, show="•")
        e_pass.pack(pady=6)
        e_pass.focus_set()

        def do():
            new_pass = e_pass.get()
            if len(new_pass) < 4:
                messagebox.showwarning("Trop court", "Au moins 4 caractères.", parent=dlg)
                return
            user = db.fetch_user_by_username(username)
            db.update_user_password(user["id"], new_pass)
            db.log_action(self.current_user, "REINIT_MOT_DE_PASSE", dossier_label=username)
            messagebox.showinfo("Terminé", "Mot de passe réinitialisé.", parent=dlg)
            dlg.destroy()

        e_pass.bind("<Return>", lambda e: do())
        ttk.Button(dlg, text="Valider", command=do).pack(pady=10)

    def _toggle_disabled(self):
        username = self._get_selected_username()
        if not username:
            return
        if username == self.current_user:
            messagebox.showwarning("Action impossible", "Vous ne pouvez pas désactiver votre propre compte Administrateur.")
            return
        user = db.fetch_user_by_username(username)
        if user["role"] == "Administrateur":
            messagebox.showwarning("Action impossible", "Impossible de désactiver un compte Administrateur.")
            return
        currently = bool(user.get("disabled"))
        action = "activer" if currently else "désactiver"
        if not messagebox.askyesno("Confirmer", f"Voulez-vous {action} le compte « {username} » ?"):
            return
        db.set_user_disabled(username, not currently)
        db.log_action(self.current_user, "REACTIVATION_COMPTE" if currently else "DESACTIVATION_COMPTE", dossier_label=username)
        self._refresh_comptes()

    def _delete_user(self):
        username = self._get_selected_username()
        if not username:
            return
        if username == self.current_user:
            messagebox.showwarning("Action impossible", "Vous ne pouvez pas supprimer votre propre compte Administrateur.")
            return
        user = db.fetch_user_by_username(username)
        if user["role"] == "Administrateur":
            messagebox.showwarning("Action impossible", "Impossible de supprimer un compte Administrateur.")
            return
        if not messagebox.askyesno("Confirmer", f"Supprimer le compte « {username} » ?"):
            return
        db.delete_user(user["id"])
        db.log_action(self.current_user, "SUPPRESSION_UTILISATEUR", dossier_label=username)
        self._refresh_comptes()

    def _generate_license_for_selected(self):
        username = self._get_selected_username()
        if not username:
            return
        user = db.fetch_user_by_username(username)
        if user["role"] not in ("Gestionnaire", "Consultation"):
            messagebox.showwarning("Action impossible", "Les licences sont réservées aux comptes Gestionnaire / Consultation.")
            return
        self._generate_license(licensee=username)

    # ------------------------------------------------------------- licences
    def _build_licences_tab(self):
        top = tk.Frame(self.tab_licences, bg=COLOR_BG)
        top.pack(fill="x", padx=12, pady=10)
        ttk.Button(top, text="🎟️ Générer une licence", command=lambda: self._generate_license()).pack(side="left", padx=4)
        ttk.Button(top, text="⛔ Révoquer", command=self._revoke).pack(side="left", padx=4)
        ttk.Button(top, text="✅ Réactiver", command=self._unrevoke).pack(side="left", padx=4)
        ttk.Button(top, text="🔄 Régénérer (renouveler)", command=self._renew).pack(side="left", padx=4)
        ttk.Button(top, text="📄 Exporter la liste de révocation", command=self._export_revocations).pack(side="right", padx=4)

        cols = ["license_id", "licensee", "created_at", "start_date", "expiry_date", "jours", "statut"]
        headers = ["Licence", "Gestionnaire", "Créée le", "Début", "Expiration", "Jours rest.", "Statut"]
        frame = tk.Frame(self.tab_licences)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree_licences = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c, h in zip(cols, headers):
            self.tree_licences.heading(c, text=h)
            self.tree_licences.column(c, width=130, anchor="w")
        self.tree_licences.column("statut", width=110, anchor="center")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree_licences.yview)
        self.tree_licences.configure(yscrollcommand=vsb.set)
        self.tree_licences.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree_licences.tag_configure("revoked", background="#fdecea")
        self.tree_licences.tag_configure("expired", background="#fff8e1")
        self.tree_licences.tag_configure("active", background="#e8f5e9")

    def _license_status(self, lic):
        if lic.get("revoked"):
            return "⛔ Révoquée", "revoked"
        try:
            days = (datetime.date.fromisoformat(lic["expiry_date"]) - datetime.date.today()).days
        except (KeyError, TypeError, ValueError):
            days = None
        if days is None:
            return "⚠ Inconnue", "expired"
        if days < 0:
            return "⌛ Expirée", "expired"
        return f"✅ Active", "active"

    def _refresh_licences(self):
        self.tree_licences.delete(*self.tree_licences.get_children())
        for lic in db.fetch_licenses():
            statut, tag = self._license_status(lic)
            try:
                jours = (datetime.date.fromisoformat(lic["expiry_date"]) - datetime.date.today()).days
            except Exception:
                jours = ""
            self.tree_licences.insert("", "end", values=[
                lic["license_id"], lic["licensee"], lic.get("created_at") or "",
                lic.get("start_date") or "", lic.get("expiry_date") or "",
                jours if jours != "" else "", statut,
            ], tags=(tag,))

    def _get_selected_license(self):
        sel = self.tree_licences.selection()
        if not sel:
            messagebox.showinfo("Sélection", "Veuillez sélectionner une licence dans la liste.")
            return None
        license_id = self.tree_licences.item(sel[0])["values"][0]
        return db.get_license_by_id(license_id)

    def _generate_license(self, licensee=None):
        users = [u for u in db.fetch_users() if u["role"] in ("Gestionnaire", "Consultation")]
        if not users:
            messagebox.showwarning("Aucun compte", "Créez d'abord un compte Gestionnaire dans l'onglet « Comptes ».")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Générer une licence (.lic)")
        dlg.geometry("440x300")
        dlg.grab_set()
        dlg.resizable(False, False)

        form = tk.Frame(dlg)
        form.pack(padx=24, pady=16)
        tk.Label(form, text="Compte Gestionnaire :").grid(row=0, column=0, sticky="w", pady=6)
        names = [u["username"] for u in users]
        cb_user = ttk.Combobox(form, values=names, state="readonly", width=24)
        if licensee and licensee in names:
            cb_user.set(licensee)
        cb_user.grid(row=0, column=1, pady=6)
        tk.Label(form, text="Durée de validité (jours) :").grid(row=1, column=0, sticky="w", pady=6)
        e_days = ttk.Entry(form, width=12)
        e_days.insert(0, str(licensing.DEFAULT_DURATION_DAYS))
        e_days.grid(row=1, column=1, sticky="w", pady=6)
        tk.Label(form, text="(365 jours = 1 an)").grid(row=2, column=1, sticky="w", fg="#888")

        def generate():
            licensee_sel = cb_user.get().strip()
            if not licensee_sel:
                messagebox.showwarning("Champ requis", "Sélectionnez un compte Gestionnaire.", parent=dlg)
                return
            try:
                days = int(e_days.get().strip())
                if days <= 0:
                    raise ValueError()
            except ValueError:
                messagebox.showwarning("Durée invalide", "Durée en jours (ex : 365).", parent=dlg)
                return

            default_dir = os.path.join(db.get_app_dir(), "Licences")
            os.makedirs(default_dir, exist_ok=True)
            filename = f"licence_{licensee_sel}_{days}j.lic"
            path = filedialog.asksaveasfilename(
                parent=dlg, title="Enregistrer le fichier de licence (.lic)",
                defaultextension=".lic", initialdir=default_dir, initialfile=filename,
                filetypes=[("Licence Sinistres App", "*.lic"), ("Tous les fichiers", "*.*")])
            if not path:
                return
            try:
                licensing.ensure_signing_keys()
                doc = licensing.generate_license_file(path, licensee=licensee_sel, duration_days=days)
                db.insert_license(doc)
                db.log_action(self.current_user, "GENERATION_LICENCE", dossier_label=licensee_sel,
                              nouvelle_valeur={"license_id": doc["license_id"],
                                               "expiry": doc["expiry_date"], "duree_jours": days})
                self._refresh_licences()
                messagebox.showinfo("Licence générée 🎉",
                                    f"Licence créée : {doc['license_id']}\n"
                                    f"Compte lié : {licensee_sel}\n"
                                    f"Expire le : {doc['expiry_date']}\n\n"
                                    f"Fichier : {path}\n\n"
                                    "Transmettez ce fichier .lic au gestionnaire avec l'application.",
                                    parent=dlg)
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de générer la licence :\n{e}", parent=dlg)

        ttk.Button(dlg, text="📦 Générer le fichier .lic", command=generate).pack(pady=14)

    def _revoke(self):
        lic = self._get_selected_license()
        if not lic:
            return
        if lic.get("revoked"):
            messagebox.showinfo("Déjà révoquée", "Cette licence est déjà révoquée.")
            return
        if not messagebox.askyesno("Révoquer", f"Révoquer la licence {lic['license_id']} ({lic['licensee']}) ?\n\n"
                                              "Elle ne pourra plus être utilisée sur un poste ayant reçu la liste de révocation."):
            return
        db.revoke_license(lic["license_id"])
        licensing.build_revocation_list(db.revoked_license_ids())
        db.log_action(self.current_user, "REVOCATION_LICENCE", dossier_label=lic["license_id"])
        self._refresh_licences()

    def _unrevoke(self):
        lic = self._get_selected_license()
        if not lic:
            return
        if not lic.get("revoked"):
            messagebox.showinfo("Active", "Cette licence n'est pas révoquée.")
            return
        db.unrevoke_license(lic["license_id"])
        licensing.build_revocation_list(db.revoked_license_ids())
        db.log_action(self.current_user, "REACTIVATION_LICENCE", dossier_label=lic["license_id"])
        self._refresh_licences()

    def _renew(self):
        lic = self._get_selected_license()
        if not lic:
            return
        if not messagebox.askyesno("Renouveler",
                                   f"Générer une NOUVELLE licence pour « {lic['licensee']} » ?\n\n"
                                   "Un nouveau numéro de licence sera créé ; l'ancienne reste dans le registre."):
            return
        self._generate_license(licensee=lic["licensee"])

    def _export_revocations(self):
        ids = db.revoked_license_ids()
        if not ids:
            messagebox.showinfo("Aucune révocation", "Aucune licence n'est révoquée pour le moment.")
            return
        default_path = os.path.join(db.get_app_dir(), licensing.REVOCATION_FILE)
        licensing.build_revocation_list(ids)
        path = filedialog.asksaveasfilename(
            parent=self, title="Enregistrer la liste de révocation",
            defaultextension=".json", initialdir=db.get_app_dir(),
            initialfile=licensing.REVOCATION_FILE,
            filetypes=[("Fichier JSON", "*.json")])
        if not path:
            return
        try:
            import shutil
            shutil.copy2(default_path, path)
            messagebox.showinfo("Liste exportée",
                                f"Liste de révocation enregistrée :\n{path}\n\n"
                                "Transmettez ce fichier aux postes Gestionnaire (à placer dans le dossier de l'application, "
                                f"sous le nom « {licensing.REVOCATION_FILE} »).")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'exporter :\n{e}")

    def _refresh_all(self):
        self._refresh_comptes()
        self._refresh_licences()


if __name__ == "__main__":
    app = AdminConsole()
    if app.current_user:
        app.mainloop()
