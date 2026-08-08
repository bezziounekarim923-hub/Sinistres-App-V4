# -*- coding: utf-8 -*-
"""
SUIVI DES SINISTRES - Application de bureau
=============================================
Application de gestion et d'analyse des sinistres de véhicules.
Lancer avec : python main.py
"""
import os
import sys
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import datetime
import re

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import database as db
import importer
import analytics as an
import licensing

APP_TITLE = "Suivi des Sinistres — Tableau de bord"
COLOR_BG = "#f4f6f9"
COLOR_PRIMARY = "#1f3a5f"
COLOR_ACCENT = "#2f6fed"
COLOR_OK = "#1e8e5a"
COLOR_WARN = "#c0392b"
COLOR_CARD = "#ffffff"

FIELDS_FORM = [
    # Champs principaux du fichier Sinistres
    ("numero", "N°"),
    ("code_cam", "N° CODE DE CAM"),
    ("type_vehicule", "Type de véhicule"),
    ("date_sinistre", "Date du sinistre (JJ-MM-AAAA)"),
    ("date_declaration", "Date de la déclaration (JJ-MM-AAAA)"),
    ("lieu_accident", "Lieu d'accident"),
    ("immatriculation", "N° d'immatriculation"),
    ("chauffeur", "Nom & prénom du chauffeur"),
    ("type_accident", "Type d'accident"),
    ("degats_cause", "Dégâts causés"),
    ("avec_sans_tiers", "Avec ou sans tiers"),
    ("fautif", "Fautif ou pas fautif"),
    ("visa_reparation", "Visa de réparation"),
    ("expertise", "Expertise"),
    ("date_expertise", "Date d'expertise (JJ-MM-AAAA)"),
    ("pv_recu", "PV reçu"),
    ("date_reception_pv", "Date de réception du PV (JJ-MM-AAAA)"),
    ("delai_pv_jours", "Délai des PV par jour"),
    ("confirmation_pv", "Confirmation des PV"),
    ("date_confirmation_pv", "Date de confirmation des PV (JJ-MM-AAAA)"),
    ("numero_dossier", "N° Dossier"),
    ("montant_pv_expert", "Montant à rembourser selon PV expert"),
    ("montant_reglement_avant_rp", "Montant règlement avant R/P"),
    ("ecart", "Écart"),
    ("banque", "Banque"),
    ("numero_cheque", "N° de chèque"),
    ("date_reglement", "Date de règlement (JJ-MM-AAAA)"),
    ("jours_immobilisation", "Nbr jours d'immobilisation"),
    ("heures_maindoeuvre", "Nombre d'heures main-d'œuvre"),
    ("montant_peinture", "Montant peinture"),
    ("montant_fournitures", "Montant fournitures"),
    ("vetuste", "Vétusté"),
    ("franchise", "Franchise"),
    ("statut_reglement", "Règlement"),
    # Champs complémentaires déjà gérés par l'application
    ("annee", "Année"),
    ("circonstance_accident", "Circonstance d'accident"),
    ("compagnie", "Compagnie"),
    ("agence", "Agence"),
    ("expert", "Expert"),
    ("assure", "Assuré"),
    ("camion", "Camion"),
    ("delai_reg", "Délai de règlement (jours)"),
    ("observation", "Observation"),
]

# Champs liés : en sélectionnant/tapant une valeur connue dans l'un, les autres se
# complètent automatiquement s'ils sont vides (cahier des charges §10).
LINKED_FIELD_GROUPS = [
    ("camion", ["immatriculation", "code_cam", "type_vehicule"]),
    ("immatriculation", ["camion", "code_cam", "type_vehicule"]),
]

# Champs qui alimentent l'auto-complétion "valeur déjà connue" (§9)
AUTOCOMPLETE_FIELDS = [
    "chauffeur", "lieu_accident", "immatriculation", "banque", "type_accident",
    "type_vehicule", "compagnie", "agence", "expert", "camion", "assure",
    "code_cam", "numero_dossier",
]

# Champs de recherche universelle (§7) : la barre de recherche cherche dans tous ces champs
UNIVERSAL_SEARCH_FIELDS = [
    "numero_dossier", "chauffeur", "immatriculation", "camion", "code_cam",
    "compagnie", "expert", "agence", "type_vehicule", "lieu_accident", "banque",
]

# Champs à liste de choix fixe (menu déroulant strict, avec possibilité de taper une
# valeur libre si besoin). Complété dynamiquement avec les valeurs déjà présentes en base.
FIELD_CHOICES = {
    "statut_reglement": ["REGLER", "INSTANCE", "NEANT"],
    "fautif": ["FAUTIF", "NON FAUTIF"],
    "expertise": ["OUI", "NON"],
    "pv_recu": ["OUI", "NON"],
    "confirmation_pv": ["OUI", "NON"],
    "avec_sans_tiers": ["AVEC TIERS", "SANS TIERS"],
}

# Droits d'accès par rôle (§21)
ROLE_PERMISSIONS = {
    "Administrateur": {"create", "edit", "delete", "purge", "admin", "users", "settings", "export"},
    "Gestionnaire": {"create", "edit", "delete", "export"},
    "Consultation": {"export"},
}

# Couleurs de secours si aucune couleur réelle n'a été détectée dans le fichier Excel
DEFAULT_STATUS_TAG_COLORS = {
    "REGLER": "#e8f5e9",
    "INSTANCE": "#fff8e1",
    "EN COURS": "#fff8e1",
    "NEANT": "#f3f4f6",
}

DATE_FIELDS = (
    "date_sinistre", "date_declaration", "date_expertise", "date_reception_pv",
    "date_confirmation_pv", "date_reglement"
)
DATE_INPUT_FORMATS = ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y")


def parse_date_input(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in DATE_INPUT_FORMATS:
            try:
                return datetime.datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.date.fromisoformat(text)
        except ValueError:
            return None
    return None


def format_date_for_display(value):
    if value in (None, ""):
        return ""
    parsed = parse_date_input(value)
    if parsed is None:
        return str(value).strip()
    return parsed.strftime("%d-%m-%Y")


def format_date_for_storage(value):
    if value in (None, ""):
        return None
    parsed = parse_date_input(value)
    if parsed is None:
        return value.strip() if isinstance(value, str) else value
    return parsed.isoformat()


class App(tk.Tk):
    def __init__(self, skip_login_as=None):
        """skip_login_as: (username, role) — réservé aux tests automatisés pour
        contourner la boîte de dialogue de connexion interactive."""
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1280x800")
        self.configure(bg=COLOR_BG)
        self.minsize(1024, 650)

        db.init_db()

        self.current_user = None
        self.current_role = None
        self.withdraw()
        if skip_login_as:
            self.current_user, self.current_role = skip_login_as
        else:
            self._run_authentication()
            self._run_license_check()
        self.deiconify()

        self.filters = {"annee": None, "chauffeur": None, "statut": None, "search": None, "date_from": None, "date_to": None, "month": None, "day": None, "dossiers": []}
        self._pending_source_warning = None
        self.source_workbook_path = self._load_source_workbook_path()
        self.source_mtime = self._get_source_mtime()
        self.auto_sync_enabled = True

        self._setup_style()
        self._build_menu()
        self._build_layout()
        self._apply_permissions()
        self.refresh_all()
        self._update_sync_status_label()
        if self._pending_source_warning:
            self._log(self._pending_source_warning)

        self.bind("<FocusIn>", self._on_focus_in)
        self.after(20000, self._poll_external_changes)

    # ------------------------------------------------------------- authentification
    def _run_authentication(self):
        """Force la création d'un premier compte Administrateur si aucun utilisateur
        n'existe, puis affiche la fenêtre de connexion (§21)."""
        if db.user_count() == 0:
            FirstAdminSetupDialog(self)
        while not self.current_user:
            dlg = LoginDialog(self)
            self.wait_window(dlg)
            if not self.current_user:
                if not messagebox.askretrycancel("Connexion", "Identifiants incorrects ou connexion annulée. Réessayer ?"):
                    self.destroy()
                    sys.exit(0)

    def has_permission(self, permission):
        return permission in ROLE_PERMISSIONS.get(self.current_role, set())

    # ------------------------------------------------------------- licence
    def _run_license_check(self):
        status = licensing.check_license()
        if not status["valid"]:
            dlg = LicenseRequiredDialog(self, status)
            self.wait_window(dlg)
            status = licensing.check_license()
            if not status["valid"]:
                messagebox.showerror("Licence requise", "L'application ne peut pas démarrer sans licence valide.")
                self.destroy()
                sys.exit(0)
        if status["days_left"] is not None and status["days_left"] <= 30:
            messagebox.showwarning(
                "Licence bientôt expirée",
                f"Votre licence expire dans {status['days_left']} jour(s) (le {status['expiry']}).\n"
                "Pensez à contacter l'éditeur pour la renouveler.")

    def _show_license_management(self):
        LicenseManagementDialog(self)

    def _apply_permissions(self):
        """Active/désactive les actions selon le rôle de l'utilisateur connecté (§21)."""
        role = self.current_role
        state_create = "normal" if self.has_permission("create") else "disabled"
        state_delete = "normal" if self.has_permission("delete") else "disabled"
        state_purge = "normal" if self.has_permission("purge") else "disabled"

        for attr, perm_state in (
            ("btn_add", state_create), ("btn_edit", state_create),
            ("btn_delete_selected", state_delete),
        ):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.config(state=perm_state)

        for attr, perm_state in (
            ("btn_restore", state_create),  # restaurer = équivalent d'une modification, pas d'une suppression
            ("btn_purge", state_purge), ("btn_empty_corbeille", state_purge),
        ):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.config(state=perm_state)

        if hasattr(self, "menubar"):
            admin_ok = self.has_permission("admin")
            try:
                self.menubar.entryconfig("Administration", state="normal" if admin_ok else "disabled")
            except tk.TclError:
                pass

        self.lbl_user_info.config(text=f"👤 {self.current_user} ({role})")

    def _get_source_mtime(self):
        if self.source_workbook_path and os.path.exists(self.source_workbook_path):
            try:
                return os.path.getmtime(self.source_workbook_path)
            except OSError:
                return None
        return None

    # ---------------------------------------------------------------- menu
    def _build_menu(self):
        menubar = tk.Menu(self)
        self.menubar = menubar
        admin_menu = tk.Menu(menubar, tearoff=0)
        admin_menu.add_command(label="🗑 Vider le fichier Excel...", command=self._admin_clear_excel)
        admin_menu.add_separator()
        admin_menu.add_command(label="🔄 Recharger depuis Excel", command=self._reload_from_source)
        admin_menu.add_command(label="🔁 Forcer une synchronisation complète", command=lambda: self._write_through_sync(force=True, notify=True))
        admin_menu.add_separator()
        admin_menu.add_command(label="📊 Tableau de bord Administration", command=self._show_admin_dashboard)
        admin_menu.add_command(label="🕑 Journal des opérations", command=self._show_journal)
        admin_menu.add_command(label="👤 Gestion des utilisateurs", command=self._show_user_management)
        admin_menu.add_separator()
        admin_menu.add_command(label="⚙ Paramètres", command=self._show_settings)
        admin_menu.add_separator()
        admin_menu.add_command(label="🔑 Licence (réservé éditeur)", command=self._show_license_management)
        admin_menu.add_command(label="📦 Préparer une copie pour un nouveau poste...", command=self._prepare_client_copy)
        menubar.add_cascade(label="Administration", menu=admin_menu)
        self.config(menu=menubar)

    # ---------------------------------------------------------------- style
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
        style.configure("Accent.TButton", background=COLOR_ACCENT, foreground="white")

    # --------------------------------------------------------------- layout
    def _build_layout(self):
        header = tk.Frame(self, bg=COLOR_PRIMARY, height=56)
        header.pack(side="top", fill="x")
        tk.Label(header, text="🚚  SUIVI DES SINISTRES", bg=COLOR_PRIMARY, fg="white",
                  font=("Segoe UI", 15, "bold")).pack(side="left", padx=20, pady=10)
        self.lbl_user_info = tk.Label(header, text="", bg=COLOR_PRIMARY, fg="#cfe0ff",
                                       font=("Segoe UI", 9))
        self.lbl_user_info.pack(side="left", padx=6)
        self.lbl_count = tk.Label(header, text="", bg=COLOR_PRIMARY, fg="#cfe0ff",
                                   font=("Segoe UI", 10))
        self.lbl_count.pack(side="right", padx=20)

        self.lbl_sync_status = tk.Label(header, text="", bg=COLOR_PRIMARY, fg="#ffd166",
                                         font=("Segoe UI", 9, "bold"))
        self.lbl_sync_status.pack(side="right", padx=10)

        self.lbl_notification = tk.Label(header, text="", bg=COLOR_PRIMARY, fg="#8bf29b",
                                          font=("Segoe UI", 9, "bold"))
        self.lbl_notification.pack(side="right", padx=10)

        reload_btn = tk.Button(header, text="🔄 Recharger depuis Excel",
                                command=self._reload_from_source, bg="white", fg=COLOR_PRIMARY,
                                font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4,
                                cursor="hand2")
        reload_btn.pack(side="right", padx=6)

        print_btn = tk.Button(header, text="🖨 Imprimer / Exporter les graphiques (PDF)",
                               command=self._print_all_charts, bg="white", fg=COLOR_PRIMARY,
                               font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4,
                               cursor="hand2")
        print_btn.pack(side="right", padx=6)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_dashboard = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_sinistres = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_a_traiter = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_chauffeurs = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_couts = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_alertes = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_corbeille = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_import = tk.Frame(self.notebook, bg=COLOR_BG)

        self.notebook.add(self.tab_dashboard, text="📊 Tableau de bord")
        self.notebook.add(self.tab_sinistres, text="📋 Sinistres")
        self.notebook.add(self.tab_a_traiter, text="🚨 À traiter")
        self.notebook.add(self.tab_chauffeurs, text="🧑‍✈️ Chauffeurs")
        self.notebook.add(self.tab_couts, text="💰 Coûts & Délais")
        self.notebook.add(self.tab_alertes, text="⚠️ Alertes")
        self.notebook.add(self.tab_corbeille, text="🗑 Corbeille")
        self.notebook.add(self.tab_import, text="📥 Import / Export")

        self._build_dashboard_tab()
        self._build_sinistres_tab()
        self._build_a_traiter_tab()
        self._build_chauffeurs_tab()
        self._build_couts_tab()
        self._build_alertes_tab()
        self._build_corbeille_tab()
        self._build_import_tab()

        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.refresh_all())

    # ------------------------------------------------------------ data get
    def _load_source_workbook_path(self):
        path_file = os.path.join(db.get_app_dir(), "last_import_path.txt")
        if os.path.exists(path_file):
            with open(path_file, "r", encoding="utf-8") as fh:
                path = fh.read().strip() or None
                if path and not os.path.exists(path):
                    # Le fichier référencé n'existe plus à cet emplacement : on mémorise
                    # l'alerte pour l'afficher une fois l'interface (et le log) prête.
                    self._pending_source_warning = (
                        f"⚠ Fichier Excel source introuvable à l'emplacement mémorisé : {path}\n"
                        f"   → Réimportez-le depuis l'onglet « Import / Export » pour réactiver la synchronisation.")
                return path
        return None

    def _save_source_workbook_path(self, path):
        self.source_workbook_path = path
        path_file = os.path.join(db.get_app_dir(), "last_import_path.txt")
        with open(path_file, "w", encoding="utf-8") as fh:
            fh.write(path or "")

    def get_records(self):
        return db.fetch_all(self.filters)

    def _update_sync_status_label(self, error=False):
        if not hasattr(self, "lbl_sync_status"):
            return
        if not self.source_workbook_path:
            self.lbl_sync_status.config(text="⚠ Aucun fichier Excel lié", fg="#ffd166")
        elif not os.path.exists(self.source_workbook_path):
            self.lbl_sync_status.config(text="⚠ Fichier Excel introuvable", fg="#ff8a80")
        elif error:
            self.lbl_sync_status.config(text="❌ Échec de synchronisation", fg="#ff8a80")
        else:
            heure = datetime.datetime.now().strftime("%H:%M:%S")
            self.lbl_sync_status.config(text=f"✅ Synchronisé à {heure}", fg="#8bf29b")

    def refresh_all(self):
        records = self.get_records()
        all_records = db.fetch_all({"include_deleted": False})
        total_count = db.count_all()
        self.lbl_count.config(text=f"{len(records)} sinistre(s) affiché(s) — {total_count} au total")
        self._refresh_dashboard(records, all_records)
        self._refresh_sinistres_table(records, all_records)
        self._refresh_a_traiter(records)
        self._refresh_chauffeurs(records)
        self._refresh_couts(records)
        self._refresh_alertes(records)
        self._refresh_corbeille()

    # ------------------------------------------------------ synchronisation Excel
    def _write_through_sync(self, force=False, notify=False):
        """Écrit immédiatement les données actuelles de la base dans le fichier Excel
        source (création, modification, suppression). Point central appelé après
        chaque opération d'écriture, conformément au cahier des charges (§1)."""
        if not self.auto_sync_enabled and not force:
            return
        if not self.source_workbook_path:
            self._update_sync_status_label()
            messagebox.showwarning(
                "Synchronisation impossible",
                "Aucun fichier Excel source n'est enregistré.\n\n"
                "Allez dans l'onglet « Import / Export » et choisissez votre fichier Excel "
                "une première fois : toutes les modifications suivantes s'y écriront "
                "automatiquement.")
            return
        if not os.path.exists(self.source_workbook_path):
            self._update_sync_status_label()
            messagebox.showwarning(
                "Synchronisation impossible",
                f"Le fichier Excel source est introuvable à cet emplacement :\n{self.source_workbook_path}\n\n"
                "A-t-il été déplacé, renommé ou se trouve-t-il sur un lecteur/dossier réseau "
                "actuellement déconnecté ? Réimportez-le depuis l'onglet « Import / Export » "
                "si besoin.")
            return
        try:
            all_records = db.fetch_all({"include_deleted": False})
            backup_path, assignments, unmatched = importer.sync_records_to_workbook(self.source_workbook_path, all_records)
            for record_id, sheet_name, row_idx in assignments:
                if record_id:
                    db.set_excel_location(record_id, sheet_name, row_idx)
            self.source_mtime = self._get_source_mtime()
            self._update_sync_status_label()
            if hasattr(self, "txt_log"):
                self._log(f"🔄 Synchronisé vers Excel ({len(all_records)} sinistre(s)) — sauvegarde : {backup_path}")
            if unmatched:
                labels = ", ".join(self._record_label(r) for r in unmatched[:10])
                messagebox.showwarning(
                    "Synchronisation partielle",
                    f"{len(unmatched)} sinistre(s) n'ont pas pu être placés dans une feuille "
                    f"Excel (aucune feuille ne correspond à leur année) : {labels}"
                    + (" …" if len(unmatched) > 10 else "") +
                    "\n\nVérifiez le champ « Année » de ces sinistres."
                )
                if hasattr(self, "txt_log"):
                    self._log(f"⚠ {len(unmatched)} sinistre(s) non synchronisé(s) (année sans feuille correspondante)")
            elif notify:
                messagebox.showinfo("Synchronisation", "Le fichier Excel source a été mis à jour avec succès.")
        except Exception as e:
            self._update_sync_status_label(error=True)
            if hasattr(self, "txt_log"):
                self._log(f"❌ Échec de la synchronisation automatique : {e}")
            messagebox.showwarning("Synchronisation", f"Impossible de synchroniser vers Excel :\n{e}")

    def _reload_from_source(self):
        if not self.source_workbook_path or not os.path.exists(self.source_workbook_path):
            messagebox.showwarning("Recharger", "Aucun fichier Excel source n'a encore été importé.")
            return
        try:
            summary = importer.import_workbook(self.source_workbook_path, progress_callback=self._log if hasattr(self, "txt_log") else None)
            self.source_mtime = self._get_source_mtime()
            self.refresh_all()
            self._update_sync_status_label()
            total = sum(summary.values())
            messagebox.showinfo("Rechargement", f"Données rechargées depuis Excel ({total} nouvel(les) entrée(s) détectée(s)).")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de recharger le fichier Excel :\n{e}")

    def _on_focus_in(self, event=None):
        self._poll_external_changes()

    def _poll_external_changes(self):
        if self.source_workbook_path and os.path.exists(self.source_workbook_path):
            try:
                current_mtime = os.path.getmtime(self.source_workbook_path)
            except OSError:
                current_mtime = None
            if current_mtime and self.source_mtime and current_mtime > self.source_mtime + 1:
                if messagebox.askyesno(
                        "Fichier Excel modifié",
                        "Le fichier Excel source a été modifié en dehors de l'application "
                        "(directement dans Excel).\n\nVoulez-vous recharger les données maintenant ?"):
                    self._reload_from_source()
                else:
                    self.source_mtime = current_mtime
        self.after(20000, self._poll_external_changes)

    # ------------------------------------------------------------ administration
    # ------------------------------------------------------------ copie pour un nouveau poste
    # Fichiers propres à CE poste : ne jamais les inclure dans une copie destinée
    # à quelqu'un d'autre (données personnelles, licence active de ce poste...).
    CLIENT_COPY_EXCLUDE_FILES = {
        "license.json",           # licence active de CE poste : ne pas offrir gratuitement
        "sinistres.db",           # base de données locale (données de ce poste)
        "last_import_path.txt",   # chemin du fichier Excel de ce poste
        "status_colors.json",
        "settings.json",
    }
    CLIENT_COPY_EXCLUDE_DIRS = {
        "backups", "__pycache__", ".pytest_cache", ".git", "dist", "build", ".vscode", "testdata",
    }

    def _prepare_client_copy(self):
        if not self.has_permission("admin"):
            messagebox.showwarning("Accès refusé", "Seul un Administrateur peut préparer une copie de l'application.")
            return

        has_master = licensing.master_password_is_set()
        warning = ""
        if not has_master:
            warning = ("\n\n⚠️ ATTENTION : aucun mot de passe maître n'est défini sur ce poste. "
                       "La copie n'inclura donc pas de fichier license_master.json, et la personne "
                       "qui la recevra pourra définir SON PROPRE mot de passe maître et générer "
                       "elle-même des licences illimitées, gratuitement !\n\n"
                       "Définissez d'abord votre mot de passe maître (menu Administration → "
                       "🔑 Licence) avant de préparer une copie à distribuer.")

        if not messagebox.askyesno(
                "Préparer une copie pour un nouveau poste",
                "Cette opération va créer une copie propre de l'application, prête à être "
                "mise sur une clé USB et donnée à quelqu'un d'autre.\n\n"
                "✅ Sera inclus : le programme, et votre mot de passe maître (protégé, "
                "toujours haché) pour que vous restiez le seul à pouvoir générer des licences.\n"
                "❌ Ne sera PAS inclus : votre licence active, votre base de données, "
                "le chemin de votre fichier Excel." + warning + "\n\nContinuer ?"):
            return

        dest_parent = filedialog.askdirectory(title="Choisir où créer la copie (ex : clé USB)")
        if not dest_parent:
            return

        import shutil as _shutil
        source_dir = db.get_app_dir()
        folder_name = f"SuiviSinistres_{datetime.date.today().isoformat()}"
        dest_dir = os.path.join(dest_parent, folder_name)
        try:
            if os.path.exists(dest_dir):
                messagebox.showerror("Erreur", f"Le dossier existe déjà :\n{dest_dir}\nSupprimez-le ou choisissez un autre emplacement.")
                return
            os.makedirs(dest_dir)
            copied = []
            for name in os.listdir(source_dir):
                src_path = os.path.join(source_dir, name)
                if name in self.CLIENT_COPY_EXCLUDE_FILES:
                    continue
                if os.path.isdir(src_path) and name in self.CLIENT_COPY_EXCLUDE_DIRS:
                    continue
                dst_path = os.path.join(dest_dir, name)
                if os.path.isdir(src_path):
                    _shutil.copytree(src_path, dst_path, ignore=_shutil.ignore_patterns("__pycache__", "*.pyc"))
                else:
                    _shutil.copy2(src_path, dst_path)
                copied.append(name)

            master_included = os.path.exists(os.path.join(dest_dir, "license_master.json"))
            summary = (f"Copie créée avec succès :\n{dest_dir}\n\n"
                       f"{'✅' if master_included else '⚠️'} Mot de passe maître "
                       f"{'inclus (protection active)' if master_included else 'NON inclus — protection absente !'}\n"
                       "❌ Pas de licence active, pas de base de données : la personne devra "
                       "importer son propre fichier Excel et vous demander un code de licence.\n\n"
                       "Vous pouvez maintenant copier ce dossier sur la clé USB.")
            db.log_action(self.current_user, "PREPARATION_COPIE_CLIENT", dossier_label=folder_name)
            messagebox.showinfo("Copie prête", summary)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de préparer la copie :\n{e}")

    def _admin_clear_excel(self):
        if not self.has_permission("admin"):
            messagebox.showwarning("Accès refusé", "Seul un Administrateur peut effectuer cette opération.")
            return
        if not self.source_workbook_path or not os.path.exists(self.source_workbook_path):
            messagebox.showwarning("Administration", "Aucun fichier Excel source n'a encore été importé.")
            return
        if not messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer toutes les données du fichier Excel ?"):
            return
        if not messagebox.askyesno(
                "Confirmation finale",
                "Cette opération est irréversible.\nUne sauvegarde sera créée automatiquement avant le vidage.\n\nContinuer ?"):
            return
        try:
            total_records = db.count_all()
            backup_path, total_cleared = importer.clear_all_data_workbook(self.source_workbook_path, progress_callback=self._log if hasattr(self, "txt_log") else None)
            db.truncate_all()
            db.log_action(self.current_user, "VIDER_EXCEL", dossier_label="(tous)",
                           ancienne_valeur={"nb_sinistres": total_records}, nouvelle_valeur={"nb_sinistres": 0})
            self.refresh_all()
            messagebox.showinfo(
                "Terminé",
                f"Toutes les données ont été supprimées.\n{total_cleared} cellule(s) effacée(s).\n\n"
                f"Sauvegarde créée avant l'opération :\n{backup_path}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de vider le fichier Excel :\n{e}")

    # ------------------------------------------------------------ tableau de bord admin / journal / utilisateurs / paramètres
    def _show_admin_dashboard(self):
        AdminDashboardDialog(self)

    def _show_journal(self):
        JournalDialog(self)

    def _show_user_management(self):
        if not self.has_permission("users"):
            messagebox.showwarning("Accès refusé", "Seul un Administrateur peut gérer les utilisateurs.")
            return
        UserManagementDialog(self)

    def _show_settings(self):
        if not self.has_permission("settings"):
            messagebox.showwarning("Accès refusé", "Seul un Administrateur peut modifier les paramètres.")
            return
        SettingsDialog(self)

    # ------------------------------------------------------------ impression
    def _print_all_charts(self):
        """Exporte le tableau filtré et les graphiques dans un PDF unique."""
        from matplotlib.backends.backend_pdf import PdfPages

        path = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("Fichier PDF", "*.pdf")],
            initialfile=f"rapport_sinistres_{datetime.date.today().isoformat()}.pdf")
        if not path:
            return

        records = self.get_records()
        try:
            with PdfPages(path) as pdf:
                pdf.savefig(self._build_table_pdf_figure(records), bbox_inches="tight")
                for fig in [self.fig_annee, self.fig_mois, self.fig_chauffeurs, self.fig_fautif, self.fig_montant, self.fig_delai]:
                    pdf.savefig(fig, bbox_inches="tight")
            messagebox.showinfo(
                "Export réussi",
                f"Le rapport PDF a été enregistré dans :\n{path}\n\n"
                "Ouvrez le fichier PDF puis faites Ctrl+P pour l'imprimer."
            )
            try:
                if sys.platform.startswith("win"):
                    os.startfile(path)
                elif sys.platform == "darwin":
                    os.system(f'open "{path}"')
                else:
                    os.system(f'xdg-open "{path}"')
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'exporter le rapport PDF :\n{e}")

    def _build_table_pdf_figure(self, records):
        fig = Figure(figsize=(11, 8), dpi=120)
        ax = fig.add_subplot(111)
        ax.axis("off")

        headers = ["ID", "Année", "Date", "Chauffeur", "Immatriculation", "N° dossier", "Statut", "Montant PV", "Montant Règlement"]
        rows = []
        for r in records[:40]:
            rows.append([
                r.get("id") or "",
                r.get("annee") or "",
                r.get("date_sinistre") or "",
                (r.get("chauffeur") or "")[:24],
                r.get("immatriculation") or "",
                r.get("numero_dossier") or "",
                r.get("statut_reglement") or "",
                f"{(r.get('montant_pv_expert') or 0):,.0f}".replace(",", " "),
                f"{(r.get('montant_reglement_avant_rp') or 0):,.0f}".replace(",", " "),
            ])

        table = ax.table(cellText=rows, colLabels=headers, cellLoc="left", loc="center", colWidths=[0.06, 0.06, 0.11, 0.22, 0.12, 0.12, 0.10, 0.11, 0.11])
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.2)
        ax.set_title(f"Vue filtrée - {len(records)} sinistre(s)", fontsize=10, pad=10)
        return fig

    # ============================================================ DASHBOARD
    def _build_dashboard_tab(self):
        top = tk.Frame(self.tab_dashboard, bg=COLOR_BG)
        top.pack(fill="x", padx=10, pady=10)
        self.kpi_cards = {}
        for key, label in [("total", "Total sinistres"),
                            ("montant_total_pv", "Total Montant PV Expert (DA)"),
                            ("montant_total_reglement", "Total Montant Règlement (DA)"),
                            ("regles", "Réglés"), ("non_regles", "Non réglés"),
                            ("delai_moyen", "Délai moyen (jours)"),
                            ("sinistres_semaine", "Sinistres cette semaine"),
                            ("dossiers_attente", "Dossiers en attente")]:
            card = tk.Frame(top, bg=COLOR_CARD, highlightbackground="#ddd", highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=5)
            tk.Label(card, text=label, bg=COLOR_CARD, fg="#666", font=("Segoe UI", 9)).pack(pady=(12, 2))
            val = tk.Label(card, text="—", bg=COLOR_CARD, fg=COLOR_PRIMARY, font=("Segoe UI", 14, "bold"))
            val.pack(pady=(0, 12))
            self.kpi_cards[key] = val

        ctrl = tk.Frame(self.tab_dashboard, bg=COLOR_BG)
        ctrl.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(ctrl, text="Vue de la courbe d'évolution :", bg=COLOR_BG, font=("Segoe UI", 9, "bold")).pack(side="left")
        self.cb_granularite = ttk.Combobox(ctrl, width=10, state="readonly",
                                            values=["Par jour", "Par mois", "Par année"])
        self.cb_granularite.set("Par mois")
        self.cb_granularite.pack(side="left", padx=(6, 14))
        self.cb_granularite.bind("<<ComboboxSelected>>", lambda e: self._on_granularite_change())

        tk.Label(ctrl, text="Année :", bg=COLOR_BG).pack(side="left")
        self.cb_trend_annee = ttk.Combobox(ctrl, width=8, state="readonly")
        self.cb_trend_annee.pack(side="left", padx=(4, 14))
        self.cb_trend_annee.bind("<<ComboboxSelected>>", lambda e: self._refresh_dashboard(self.get_records()))

        tk.Label(ctrl, text="Mois :", bg=COLOR_BG).pack(side="left")
        self.cb_trend_mois = ttk.Combobox(ctrl, width=11, state="readonly", values=[
            "Toutes", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"])
        self.cb_trend_mois.set("Toutes")
        self.cb_trend_mois.pack(side="left", padx=(4, 0))
        self.cb_trend_mois.bind("<<ComboboxSelected>>", lambda e: self._refresh_dashboard(self.get_records()))

        summary = tk.Frame(self.tab_dashboard, bg=COLOR_BG)
        summary.pack(fill="x", padx=10, pady=(0, 8))
        self.summary_frame = tk.LabelFrame(summary, text="Résumé du jour", bg=COLOR_BG, fg=COLOR_PRIMARY, font=("Segoe UI", 10, "bold"))
        self.summary_frame.pack(fill="x")
        self.summary_text = tk.Label(self.summary_frame, text="", bg=COLOR_BG, justify="left", font=("Segoe UI", 10))
        self.summary_text.pack(anchor="w", padx=10, pady=8)

        charts = tk.Frame(self.tab_dashboard, bg=COLOR_BG)
        charts.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        charts.columnconfigure(0, weight=1)
        charts.columnconfigure(1, weight=1)
        charts.rowconfigure(0, weight=1)

        self.fig_annee = Figure(figsize=(5, 3.4), dpi=90)
        self.ax_annee = self.fig_annee.add_subplot(111)
        self.canvas_annee = FigureCanvasTkAgg(self.fig_annee, master=charts)
        self.canvas_annee.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.fig_mois = Figure(figsize=(5, 3.4), dpi=90)
        self.ax_mois = self.fig_mois.add_subplot(111)
        self.canvas_mois = FigureCanvasTkAgg(self.fig_mois, master=charts)
        self.canvas_mois.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

    def _refresh_dashboard(self, records, all_records=None):
        if all_records is None:
            all_records = db.fetch_all({"include_deleted": False})
        k = an.kpis(records)
        self.kpi_cards["total"].config(text=str(k["total"]))
        self.kpi_cards["montant_total_pv"].config(text=f"{k['montant_total_pv']:,.0f}".replace(",", " "))
        self.kpi_cards["montant_total_reglement"].config(text=f"{k['montant_total_reglement']:,.0f}".replace(",", " "))
        self.kpi_cards["regles"].config(text=str(k["regles"]), fg=COLOR_OK)
        self.kpi_cards["non_regles"].config(text=str(k["non_regles"]), fg=COLOR_WARN)
        self.kpi_cards["delai_moyen"].config(text=str(k["delai_moyen"]))
        self.kpi_cards["sinistres_semaine"].config(text=str(k["sinistres_semaine"]))
        self.kpi_cards["dossiers_attente"].config(text=str(k["dossiers_attente"]))

        alerts = an.alertes(records)
        high_priority = [a for a in alerts if a.get("priority") == "haute"]
        self.summary_text.config(
            text=(
                f"Aujourd’hui : {k['sinistres_jour']} nouveau(x) sinistre(s) | "
                f"Cette semaine : {k['sinistres_semaine']} | "
                f"Dossiers en attente : {k['dossiers_attente']} | "
                f"Alertes prioritaires : {len(high_priority)}"
            )
        )

        # graphique par année (référence fixe)
        self.ax_annee.clear()
        data = an.par_annee(records)
        if data:
            years = list(data.keys())
            counts = [v["count"] for v in data.values()]
            bars = self.ax_annee.bar([str(y) for y in years], counts, color=COLOR_ACCENT)
            self.ax_annee.bar_label(bars, fontsize=8)
        self.ax_annee.set_title("Nombre de sinistres par année", fontsize=10)
        self.fig_annee.tight_layout()
        self.canvas_annee.draw()

        # graphique d'évolution : granularité choisie (jour / mois / année)
        annees_disponibles = sorted({r["annee"] for r in all_records if r.get("annee")}, reverse=True)
        self.cb_trend_annee["values"] = ["Toutes"] + [str(a) for a in annees_disponibles]
        if not self.cb_trend_annee.get():
            self.cb_trend_annee.set(str(annees_disponibles[0]) if annees_disponibles else "Toutes")

        granularite = self.cb_granularite.get() if hasattr(self, "cb_granularite") else "Par mois"
        annee_txt = self.cb_trend_annee.get() if hasattr(self, "cb_trend_annee") else "Toutes"
        annee_sel = int(annee_txt) if annee_txt and annee_txt != "Toutes" else None
        mois_labels_fr = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                          "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        mois_txt = self.cb_trend_mois.get() if hasattr(self, "cb_trend_mois") else "Toutes"
        mois_sel = mois_labels_fr.index(mois_txt) + 1 if mois_txt in mois_labels_fr else None

        self.ax_mois.clear()
        if granularite == "Par année":
            data_a = an.par_annee(records)
            years = list(data_a.keys())
            counts = [v["count"] for v in data_a.values()]
            self.ax_mois.bar([str(y) for y in years], counts, color=COLOR_ACCENT)
            self.ax_mois.set_title("Évolution par année", fontsize=10)
        elif granularite == "Par jour":
            annee_jour = annee_sel or (annees_disponibles[0] if annees_disponibles else None)
            mois_jour = mois_sel or datetime.date.today().month
            data_j = an.par_jour(records, annee=annee_jour, mois=mois_jour)
            jours = list(range(1, 32))
            vals = [data_j.get(j, 0) for j in jours]
            self.ax_mois.plot(jours, vals, marker="o", markersize=3, color=COLOR_PRIMARY)
            titre = f"Évolution par jour — {mois_labels_fr[mois_jour-1]} {annee_jour if annee_jour else ''}"
            self.ax_mois.set_title(titre, fontsize=10)
            self.ax_mois.set_xlabel("Jour du mois", fontsize=8)
        else:  # Par mois
            if mois_sel:
                # Un mois précis est choisi : comparer ce mois entre les années,
                # affiché en barres comme le graphique "par année".
                data_my = an.par_mois_toutes_annees(records, mois_sel)
                years = list(data_my.keys())
                vals = list(data_my.values())
                bars = self.ax_mois.bar([str(y) for y in years], vals, color=COLOR_ACCENT)
                self.ax_mois.bar_label(bars, fontsize=8)
                titre = f"Évolution de {mois_labels_fr[mois_sel-1]} par année"
            else:
                # Aucun mois précis : les 12 mois de l'année choisie (ou toutes années), en barres.
                data_m = an.par_mois(records, annee=annee_sel)
                mois_labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]
                vals = [data_m.get(m, 0) for m in range(1, 13)]
                bars = self.ax_mois.bar(mois_labels, vals, color=COLOR_ACCENT)
                self.ax_mois.bar_label(bars, fontsize=8)
                titre = f"Évolution mensuelle {annee_sel if annee_sel else '(toutes années)'}"
            self.ax_mois.set_title(titre, fontsize=10)
        self.ax_mois.tick_params(axis='x', labelsize=8)
        self.fig_mois.tight_layout()
        self.canvas_mois.draw()

    def _on_granularite_change(self):
        # Le sélecteur de mois est utile pour "Par jour" (choix du mois affiché)
        # et pour "Par mois" (comparer un mois précis entre les années).
        self._refresh_dashboard(self.get_records())

    # ============================================================ SINISTRES
    def _build_sinistres_tab(self):
        bar = tk.Frame(self.tab_sinistres, bg=COLOR_BG)
        bar.pack(fill="x", padx=10, pady=8)

        tk.Label(bar, text="Année :", bg=COLOR_BG).pack(side="left")
        self.cb_annee = ttk.Combobox(bar, width=8, state="readonly")
        self.cb_annee.pack(side="left", padx=(2, 12))
        self.cb_annee.bind("<<ComboboxSelected>>", self._apply_filters)

        tk.Label(bar, text="Mois :", bg=COLOR_BG).pack(side="left")
        self.cb_mois = ttk.Combobox(bar, width=12, state="readonly", values=["Tous", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"])
        self.cb_mois.set("Tous")
        self.cb_mois.pack(side="left", padx=(2, 12))
        self.cb_mois.bind("<<ComboboxSelected>>", self._apply_filters)

        tk.Label(bar, text="Statut :", bg=COLOR_BG).pack(side="left")
        self.cb_statut = ttk.Combobox(bar, width=14, state="readonly")
        self.cb_statut.pack(side="left", padx=(2, 12))
        self.cb_statut.bind("<<ComboboxSelected>>", self._apply_filters)

        tk.Label(bar, text="🔎 Recherche universelle :", bg=COLOR_BG).pack(side="left")
        self.entry_search = ttk.Entry(bar, width=28)
        self.entry_search.pack(side="left", padx=(2, 12))
        self.entry_search.bind("<Return>", self._apply_filters)

        ttk.Button(bar, text="🔍 Filtrer", command=self._apply_filters).pack(side="left", padx=4)
        ttk.Button(bar, text="♻ Réinitialiser", command=self._reset_filters).pack(side="left", padx=4)
        ttk.Button(bar, text="📅 Période", command=self._open_date_filters).pack(side="left", padx=4)
        ttk.Button(bar, text="🔎 Rechercher par N° Dossier", command=self._open_dossier_selector).pack(side="left", padx=4)
        self.lbl_dossier_filter = tk.Label(bar, text="", bg=COLOR_BG, fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold"))
        self.lbl_dossier_filter.pack(side="left", padx=(2, 4))
        ttk.Button(bar, text="📄 Export PDF", command=self._print_all_charts).pack(side="left", padx=4)
        self.btn_add = ttk.Button(bar, text="➕ Ajouter", command=self._add_record)
        self.btn_add.pack(side="right", padx=4)
        self.btn_edit = ttk.Button(bar, text="✏ Modifier", command=self._edit_record)
        self.btn_edit.pack(side="right", padx=4)
        self.btn_delete_selected = ttk.Button(bar, text="🗑 Supprimer la sélection", command=self._delete_selected)
        self.btn_delete_selected.pack(side="right", padx=4)
        ttk.Button(bar, text="⬇ Exporter (Excel)", command=self._export_view).pack(side="right", padx=4)

        # Tableau complet : toutes les colonnes métier demandées sont visibles.
        table_fields = FIELDS_FORM[:34]
        cols = ["id"] + [key for key, _ in table_fields]
        headers = ["ID"] + [label.replace(" (AAAA-MM-JJ)", "") for _, label in table_fields]
        widths = [0] + [115] * len(table_fields)
        # Largeurs plus confortables pour les champs textuels importants.
        wide = {"chauffeur": 190, "lieu_accident": 160, "degats_cause": 180,
                "type_accident": 150, "numero_dossier": 130,
                "montant_pv_expert": 170, "montant_reglement_avant_rp": 190}
        widths = [0] + [wide.get(key, 115) for key, _ in table_fields]

        frame = tk.Frame(self.tab_sinistres)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree_sinistres = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        for c, h, w in zip(cols, headers, widths):
            self.tree_sinistres.heading(c, text=h)
            self.tree_sinistres.column(c, width=w, anchor="w")
        self.tree_sinistres.column("id", width=0, stretch=False)  # ID caché
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree_sinistres.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree_sinistres.xview)
        self.tree_sinistres.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree_sinistres.pack(side="left", fill="both", expand=True)
        self.tree_sinistres.bind("<Double-1>", lambda e: self._edit_record())

    def _apply_filters(self, event=None):
        annee = self.cb_annee.get()
        statut = self.cb_statut.get()
        mois = self.cb_mois.get()
        self.filters["annee"] = int(annee) if annee and annee != "Toutes" else None
        self.filters["statut"] = statut if statut and statut != "Tous" else None
        self.filters["search"] = self.entry_search.get().strip() or None
        mois_map = {"Janvier": 1, "Février": 2, "Mars": 3, "Avril": 4, "Mai": 5, "Juin": 6,
                    "Juillet": 7, "Août": 8, "Septembre": 9, "Octobre": 10, "Novembre": 11, "Décembre": 12}
        self.filters["month"] = mois_map.get(mois) if mois and mois != "Tous" else None
        self.refresh_all()

    def _reset_filters(self):
        self.filters = {"annee": None, "chauffeur": None, "statut": None, "search": None, "date_from": None, "date_to": None, "month": None, "day": None, "dossiers": []}
        self.entry_search.delete(0, "end")
        self.cb_annee.set("Toutes")
        self.cb_mois.set("Tous")
        self.cb_statut.set("Tous")
        if hasattr(self, "lbl_dossier_filter"):
            self.lbl_dossier_filter.config(text="")
        self.refresh_all()

    def _open_date_filters(self):
        DateFilterDialog(self, self.filters, callback=self._set_date_filters)

    def _set_date_filters(self, date_from, date_to, month, day):
        self.filters["date_from"] = date_from
        self.filters["date_to"] = date_to
        self.filters["month"] = month
        self.filters["day"] = day
        self.refresh_all()

    def _open_dossier_selector(self):
        DossierSelectionDialog(self, self.filters.get("dossiers", []), callback=self._set_dossier_filters)

    def _set_dossier_filters(self, dossiers):
        self.filters["dossiers"] = dossiers
        if hasattr(self, "lbl_dossier_filter"):
            self.lbl_dossier_filter.config(
                text=f"({len(dossiers)} dossier(s) sélectionné(s))" if dossiers else "")
        self.refresh_all()

    def _refresh_sinistres_table(self, records, all_records=None):
        if all_records is None:
            all_records = db.fetch_all({"include_deleted": False})
        years = ["Toutes"] + [str(y) for y in sorted({r["annee"] for r in all_records if r.get("annee")}, reverse=True)]
        self.cb_annee["values"] = years
        if not self.cb_annee.get():
            self.cb_annee.set("Toutes")

        statuts = ["Tous"] + sorted({(r.get("statut_reglement") or "").strip() for r in all_records if r.get("statut_reglement")})
        self.cb_statut["values"] = statuts
        if not self.cb_statut.get():
            self.cb_statut.set("Tous")

        self.tree_sinistres.delete(*self.tree_sinistres.get_children())
        detected_colors = db.load_status_colors()
        for r in records:
            m_pv = r.get("montant_pv_expert")
            m_reg = r.get("montant_reglement_avant_rp")
            statut = (r.get("statut_reglement") or "").strip().upper()
            tag = self._status_tag(statut, detected_colors)
            values = [r["id"]]
            for key, _label in FIELDS_FORM[:34]:
                value = r.get(key)
                if key in {"montant_pv_expert", "montant_reglement_avant_rp", "ecart",
                           "montant_peinture", "montant_fournitures", "vetuste", "franchise"} and value not in (None, ""):
                    try:
                        value = f"{float(value):,.2f}".replace(",", " ")
                    except (TypeError, ValueError):
                        pass
                values.append("" if value is None else value)
            self.tree_sinistres.insert("", "end", values=values, tags=(tag,))

    def _status_tag(self, statut, detected_colors=None):
        """Retourne (et configure si besoin) le tag Treeview correspondant à un statut,
        en utilisant la couleur réellement détectée dans le fichier Excel source si
        disponible, sinon une couleur de secours cohérente avec la convention usuelle."""
        detected_colors = detected_colors if detected_colors is not None else db.load_status_colors()
        statut = (statut or "").strip().upper()
        tag_name = "status_" + re.sub(r"[^A-Za-z0-9]", "_", statut or "vide")
        color = detected_colors.get(statut)
        if not color:
            if statut == "REGLER":
                color = DEFAULT_STATUS_TAG_COLORS["REGLER"]
            elif statut in {"EN COURS", "ENCOURS", "EN-COURS", "NON REGLER", "NON REGLÉ", "INSTANCE"}:
                color = DEFAULT_STATUS_TAG_COLORS["INSTANCE"]
            elif statut in {"NEANT", "NÉANT", "AUCUN", ""}:
                color = DEFAULT_STATUS_TAG_COLORS["NEANT"]
            else:
                color = "#f1f3f5"
        self.tree_sinistres.tag_configure(tag_name, background=color)
        return tag_name

    def _get_selected_id(self):
        sel = self.tree_sinistres.selection()
        if not sel:
            messagebox.showinfo("Sélection", "Veuillez sélectionner une ligne.")
            return None
        return int(self.tree_sinistres.item(sel[0])["values"][0])

    def _get_selected_ids(self):
        sel = self.tree_sinistres.selection()
        return [int(self.tree_sinistres.item(iid)["values"][0]) for iid in sel]

    def _add_record(self):
        if not self.has_permission("create"):
            messagebox.showwarning("Accès refusé", "Votre rôle ne permet pas d'ajouter un sinistre.")
            return
        RecordForm(self, on_save=self._save_new_record, current_user=self.current_user)

    def _save_new_record(self, data):
        db.insert_sinistre(data)
        new_records = [r for r in db.fetch_all() if r.get("chauffeur") == data.get("chauffeur")
                       and r.get("date_sinistre") == data.get("date_sinistre")]
        rid = new_records[-1]["id"] if new_records else None
        db.log_action(self.current_user, "AJOUT", dossier_label=self._record_label(data),
                       sinistre_id=rid, nouvelle_valeur=data)
        self.refresh_all()
        self._write_through_sync()
        self._show_notification("✓ Dossier enregistré avec succès.")

    def _edit_record(self):
        if not self.has_permission("edit"):
            messagebox.showwarning("Accès refusé", "Votre rôle ne permet pas de modifier un sinistre.")
            return
        rid = self._get_selected_id()
        if rid is None:
            return
        conn = db.get_connection()
        row = conn.execute("SELECT * FROM sinistres WHERE id=?", (rid,)).fetchone()
        conn.close()
        if row:
            RecordForm(self, record=dict(row), on_save=lambda data: self._save_edit(rid, data), current_user=self.current_user)

    def _save_edit(self, rid, data):
        old_record = next((r for r in db.fetch_all({"include_deleted": True}) if r["id"] == rid), None)
        db.update_sinistre(rid, data)
        db.log_action(self.current_user, "MODIFICATION", dossier_label=self._record_label(data),
                       sinistre_id=rid, ancienne_valeur=old_record, nouvelle_valeur=data)
        self.refresh_all()
        self._write_through_sync()
        self._show_notification("✓ Dossier mis à jour avec succès.")

    def _record_label(self, record):
        """Libellé lisible d'un sinistre pour les messages de confirmation (N° Dossier ou N°)."""
        numero_dossier = (record.get("numero_dossier") or "").strip()
        numero = (record.get("numero") or "").strip() if record.get("numero") else ""
        if numero_dossier:
            return numero_dossier
        if numero:
            return f"N°{numero}"
        return f"#{record.get('id')}"

    def _delete_selected(self):
        if not self.has_permission("delete"):
            messagebox.showwarning("Accès refusé", "Votre rôle ne permet pas de supprimer un sinistre.")
            return
        ids = self._get_selected_ids()
        if not ids:
            messagebox.showinfo("Sélection", "Veuillez sélectionner au moins une ligne.")
            return
        all_records = {r["id"]: r for r in db.fetch_all()}
        if len(ids) == 1:
            record = all_records.get(ids[0], {})
            label = self._record_label(record)
            question = (f"Êtes-vous sûr de vouloir supprimer le dossier {label} ?\n\n"
                        "Le dossier sera déplacé vers la Corbeille (vous pourrez le restaurer).")
        else:
            question = (f"Êtes-vous sûr de vouloir supprimer les {len(ids)} dossiers sélectionnés ?\n\n"
                        "Ils seront déplacés vers la Corbeille (vous pourrez les restaurer).")
        if not messagebox.askyesno("Confirmer la suppression", question):
            return
        db.delete_many(ids)
        for rid in ids:
            record = all_records.get(rid, {})
            db.log_action(self.current_user, "SUPPRESSION", dossier_label=self._record_label(record),
                           sinistre_id=rid, ancienne_valeur=record)
        self.refresh_all()
        self._write_through_sync()
        self._show_notification(f"✓ {len(ids)} dossier(s) déplacé(s) vers la Corbeille.")

    def _show_notification(self, message, warning=False):
        """Notification non bloquante (§25) affichée quelques secondes dans l'en-tête."""
        if not hasattr(self, "lbl_notification"):
            return
        self.lbl_notification.config(text=message, fg="#ff8a80" if warning else "#8bf29b")
        if getattr(self, "_notif_after_id", None):
            try:
                self.after_cancel(self._notif_after_id)
            except Exception:
                pass
        self._notif_after_id = self.after(6000, lambda: self.lbl_notification.config(text=""))

    def _export_view(self):
        records = self.get_records()
        if not records:
            messagebox.showinfo("Export", "Aucune donnée à exporter.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                             filetypes=[("Fichier Excel", "*.xlsx")],
                                             initialfile="export_sinistres.xlsx")
        if not path:
            return
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sinistres"
        cols = list(records[0].keys())
        ws.append(cols)
        for r in records:
            ws.append([r.get(c) for c in cols])
        wb.save(path)
        messagebox.showinfo("Export", f"Export terminé :\n{path}")

    # ============================================================ CHAUFFEURS
    def _build_a_traiter_tab(self):
        top = tk.Frame(self.tab_a_traiter, bg=COLOR_BG)
        top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text="Dossiers à traiter rapidement :", bg=COLOR_BG,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self.lbl_a_traiter_count = tk.Label(top, text="", bg=COLOR_BG, fg=COLOR_WARN, font=("Segoe UI", 10, "bold"))
        self.lbl_a_traiter_count.pack(side="right")

        cols = ["id", "numero_dossier", "chauffeur", "date_sinistre", "jours_ecoules", "priority", "reason"]
        headers = ["ID", "N° Dossier", "Chauffeur", "Date sinistre", "Jours", "Priorité", "Motif"]
        frame = tk.Frame(self.tab_a_traiter)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree_a_traiter = ttk.Treeview(frame, columns=cols, show="headings")
        for c, h in zip(cols, headers):
            self.tree_a_traiter.heading(c, text=h)
            self.tree_a_traiter.column(c, width=140, anchor="w")
        self.tree_a_traiter.column("id", width=0, stretch=False)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree_a_traiter.yview)
        self.tree_a_traiter.configure(yscrollcommand=vsb.set)
        self.tree_a_traiter.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree_a_traiter.tag_configure("critique", background="#fdecea")
        self.tree_a_traiter.tag_configure("attention", background="#fff8e1")

    def _refresh_a_traiter(self, records=None):
        if records is None:
            records = db.fetch_all({"include_deleted": False})
        data = an.alertes(records)
        self.lbl_a_traiter_count.config(text=f"{len(data)} dossier(s) à traiter")
        self.tree_a_traiter.delete(*self.tree_a_traiter.get_children())
        for r in data:
            jours = r.get("jours_ecoules")
            tag = ""
            if r.get("priority") == "haute":
                tag = "critique"
            elif jours is not None and jours > 30:
                tag = "attention"
            self.tree_a_traiter.insert("", "end", values=[
                r.get("id") or "", r.get("numero_dossier") or "", r.get("chauffeur") or "",
                r.get("date_sinistre") or "", jours if jours is not None else "",
                r.get("priority") or "moyenne", r.get("reason") or "",
            ], tags=(tag,) if tag else ())

    def _build_chauffeurs_tab(self):
        top = tk.Frame(self.tab_chauffeurs, bg=COLOR_BG)
        top.pack(fill="both", expand=True, padx=10, pady=10)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.rowconfigure(1, weight=1)

        self.fig_chauffeurs = Figure(figsize=(5, 3.2), dpi=90)
        self.ax_chauffeurs = self.fig_chauffeurs.add_subplot(111)
        self.canvas_chauffeurs = FigureCanvasTkAgg(self.fig_chauffeurs, master=top)
        self.canvas_chauffeurs.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.fig_fautif = Figure(figsize=(5, 3.2), dpi=90)
        self.ax_fautif = self.fig_fautif.add_subplot(111)
        self.canvas_fautif = FigureCanvasTkAgg(self.fig_fautif, master=top)
        self.canvas_fautif.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        cols = ["chauffeur", "nb", "fautif", "non_fautif", "montant_pv", "montant_reglement", "delai_moyen"]
        headers = ["Chauffeur", "Nb sinistres", "Fautif", "Non fautif",
                   "Total PV Expert (DA)", "Total Règlement (DA)", "Délai moyen (j)"]
        frame = tk.Frame(top)
        frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self.tree_chauffeurs = ttk.Treeview(frame, columns=cols, show="headings")
        for c, h in zip(cols, headers):
            self.tree_chauffeurs.heading(c, text=h)
            self.tree_chauffeurs.column(c, width=150, anchor="w")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree_chauffeurs.yview)
        self.tree_chauffeurs.configure(yscrollcommand=vsb.set)
        self.tree_chauffeurs.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _refresh_chauffeurs(self, records):
        data = an.par_chauffeur(records)

        self.ax_chauffeurs.clear()
        top10 = data[:10]
        if top10:
            names = [d["chauffeur"][:18] for d in top10][::-1]
            counts = [d["nb"] for d in top10][::-1]
            self.ax_chauffeurs.barh(names, counts, color=COLOR_ACCENT)
        self.ax_chauffeurs.set_title("Top 10 chauffeurs (nb sinistres)", fontsize=10)
        self.ax_chauffeurs.tick_params(axis='y', labelsize=7)
        self.fig_chauffeurs.tight_layout()
        self.canvas_chauffeurs.draw()

        self.ax_fautif.clear()
        rep = an.repartition_fautif(records)
        if sum(rep.values()) > 0:
            self.ax_fautif.pie(rep.values(), labels=rep.keys(), autopct="%1.0f%%",
                                colors=[COLOR_WARN, COLOR_OK])
        self.ax_fautif.set_title("Répartition Fautif / Non fautif", fontsize=10)
        self.fig_fautif.tight_layout()
        self.canvas_fautif.draw()

        self.tree_chauffeurs.delete(*self.tree_chauffeurs.get_children())
        for d in data:
            self.tree_chauffeurs.insert("", "end", values=[
                d["chauffeur"], d["nb"], d["fautif"], d["non_fautif"],
                f"{d['montant_pv']:,.0f}".replace(",", " "),
                f"{d['montant_reglement']:,.0f}".replace(",", " "),
                d["delai_moyen"],
            ])

    # ============================================================ COUTS
    def _build_couts_tab(self):
        top = tk.Frame(self.tab_couts, bg=COLOR_BG)
        top.pack(fill="both", expand=True, padx=10, pady=10)
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.rowconfigure(0, weight=1)

        self.fig_montant = Figure(figsize=(5, 3.4), dpi=90)
        self.ax_montant = self.fig_montant.add_subplot(111)
        self.canvas_montant = FigureCanvasTkAgg(self.fig_montant, master=top)
        self.canvas_montant.get_tk_widget().grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.fig_delai = Figure(figsize=(5, 3.4), dpi=90)
        self.ax_delai = self.fig_delai.add_subplot(111)
        self.canvas_delai = FigureCanvasTkAgg(self.fig_delai, master=top)
        self.canvas_delai.get_tk_widget().grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        cols = ["annee", "montant_pv_total", "montant_reglement_total", "delai_moyen"]
        headers = ["Année", "Total PV Expert (DA)", "Total Règlement (DA)", "Délai moyen (j)"]
        frame = tk.Frame(top)
        frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self.tree_couts = ttk.Treeview(frame, columns=cols, show="headings", height=8)
        for c, h in zip(cols, headers):
            self.tree_couts.heading(c, text=h)
            self.tree_couts.column(c, width=180, anchor="w")
        self.tree_couts.pack(fill="both", expand=True)

    def _refresh_couts(self, records):
        data = an.couts_et_delais_par_annee(records)
        self.ax_montant.clear()
        if data:
            years = [str(y) for y in data.keys()]
            totaux_pv = [v["montant_pv_total"] for v in data.values()]
            totaux_reg = [v["montant_reglement_total"] for v in data.values()]
            x = range(len(years))
            width = 0.35
            self.ax_montant.bar([i - width / 2 for i in x], totaux_pv, width, label="PV Expert", color="#8e44ad")
            self.ax_montant.bar([i + width / 2 for i in x], totaux_reg, width, label="Règlement", color=COLOR_ACCENT)
            self.ax_montant.set_xticks(list(x))
            self.ax_montant.set_xticklabels(years)
            self.ax_montant.legend(fontsize=8)
        self.ax_montant.set_title("Montants totaux par année (DA)", fontsize=10)
        self.fig_montant.tight_layout()
        self.canvas_montant.draw()

        self.ax_delai.clear()
        if data:
            years = [str(y) for y in data.keys()]
            delais = [v["delai_moyen"] for v in data.values()]
            self.ax_delai.plot(years, delais, marker="o", color=COLOR_WARN)
        self.ax_delai.set_title("Délai moyen de règlement par année (jours)", fontsize=10)
        self.fig_delai.tight_layout()
        self.canvas_delai.draw()

        self.tree_couts.delete(*self.tree_couts.get_children())
        for a, v in data.items():
            self.tree_couts.insert("", "end", values=[
                a, f"{v['montant_pv_total']:,.0f}".replace(",", " "),
                f"{v['montant_reglement_total']:,.0f}".replace(",", " "), v["delai_moyen"],
            ])

    # ============================================================ ALERTES
    def _build_alertes_tab(self):
        top = tk.Frame(self.tab_alertes, bg=COLOR_BG)
        top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text="Dossiers non réglés, triés par ancienneté :", bg=COLOR_BG,
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        self.lbl_alertes_count = tk.Label(top, text="", bg=COLOR_BG, fg=COLOR_WARN, font=("Segoe UI", 10, "bold"))
        self.lbl_alertes_count.pack(side="right")

        cols = ["chauffeur", "date_sinistre", "jours_ecoules", "priority", "reason",
                "immatriculation", "lieu_accident", "statut_reglement", "numero_dossier"]
        headers = ["Chauffeur", "Date sinistre", "Jours écoulés", "Priorité", "Motif",
                   "Immatriculation", "Lieu", "Statut", "N° Dossier"]
        frame = tk.Frame(self.tab_alertes)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree_alertes = ttk.Treeview(frame, columns=cols, show="headings")
        for c, h in zip(cols, headers):
            self.tree_alertes.heading(c, text=h)
            self.tree_alertes.column(c, width=150, anchor="w")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree_alertes.yview)
        self.tree_alertes.configure(yscrollcommand=vsb.set)
        self.tree_alertes.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree_alertes.tag_configure("critique", background="#fdecea")
        self.tree_alertes.tag_configure("attention", background="#fff8e1")
        self.tree_alertes.tag_configure("regle", background="#e8f5e9")
        self.tree_alertes.tag_configure("autre", background="#f1f3f5")

    def _refresh_alertes(self, records=None):
        if records is None:
            records = db.fetch_all({"include_deleted": False})
        data = an.alertes(records)
        self.lbl_alertes_count.config(text=f"{len(data)} dossier(s) en attente de règlement")
        self.tree_alertes.delete(*self.tree_alertes.get_children())
        for r in data:
            jours = r.get("jours_ecoules")
            tag = ""
            if jours is not None:
                if jours > 60:
                    tag = "critique"
                elif jours > 30:
                    tag = "attention"
            else:
                tag = "autre"
            if (r.get("statut_reglement") or "").strip().upper() == "REGLER":
                tag = "regle"
            self.tree_alertes.insert("", "end", values=[
                r.get("chauffeur") or "", r.get("date_sinistre") or "", jours if jours is not None else "",
                r.get("priority") or "moyenne", r.get("reason") or "suivi en attente",
                r.get("immatriculation") or "", r.get("lieu_accident") or "",
                r.get("statut_reglement") or "(vide)", r.get("numero_dossier") or "",
            ], tags=(tag,) if tag else ())

    # ============================================================ CORBEILLE
    def _build_corbeille_tab(self):
        top = tk.Frame(self.tab_corbeille, bg=COLOR_BG)
        top.pack(fill="x", padx=10, pady=10)
        tk.Label(top, text="Dossiers supprimés (récupérables) :", bg=COLOR_BG,
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        self.lbl_corbeille_count = tk.Label(top, text="", bg=COLOR_BG, fg="#666", font=("Segoe UI", 10))
        self.lbl_corbeille_count.pack(side="left", padx=10)

        self.btn_restore = ttk.Button(top, text="♻ Restaurer la sélection", command=self._restore_selected)
        self.btn_restore.pack(side="right", padx=4)
        self.btn_purge = ttk.Button(top, text="🗑 Supprimer définitivement", command=self._purge_selected)
        self.btn_purge.pack(side="right", padx=4)
        self.btn_empty_corbeille = ttk.Button(top, text="🧹 Vider la corbeille", command=self._empty_corbeille)
        self.btn_empty_corbeille.pack(side="right", padx=4)

        cols = ["id", "numero", "numero_dossier", "annee", "chauffeur", "date_sinistre",
                "statut_reglement", "deleted_at"]
        headers = ["ID", "N°", "N° Dossier", "Année", "Chauffeur", "Date sinistre",
                   "Statut", "Supprimé le"]
        widths = [0, 60, 110, 60, 180, 100, 130, 150]

        frame = tk.Frame(self.tab_corbeille)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tree_corbeille = ttk.Treeview(frame, columns=cols, show="headings", selectmode="extended")
        for c, h, w in zip(cols, headers, widths):
            self.tree_corbeille.heading(c, text=h)
            self.tree_corbeille.column(c, width=w, anchor="w")
        self.tree_corbeille.column("id", width=0, stretch=False)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree_corbeille.yview)
        self.tree_corbeille.configure(yscrollcommand=vsb.set)
        self.tree_corbeille.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _refresh_corbeille(self):
        if not hasattr(self, "tree_corbeille"):
            return
        data = db.fetch_deleted()
        self.lbl_corbeille_count.config(text=f"{len(data)} dossier(s) dans la corbeille")
        self.tree_corbeille.delete(*self.tree_corbeille.get_children())
        for r in data:
            self.tree_corbeille.insert("", "end", values=[
                r["id"], r.get("numero") or "", r.get("numero_dossier") or "", r.get("annee") or "",
                r.get("chauffeur") or "", r.get("date_sinistre") or "",
                r.get("statut_reglement") or "", r.get("deleted_at") or "",
            ])

    def _get_selected_corbeille_ids(self):
        sel = self.tree_corbeille.selection()
        return [int(self.tree_corbeille.item(iid)["values"][0]) for iid in sel]

    def _restore_selected(self):
        ids = self._get_selected_corbeille_ids()
        if not ids:
            messagebox.showinfo("Sélection", "Veuillez sélectionner au moins un dossier à restaurer.")
            return
        all_records = {r["id"]: r for r in db.fetch_all({"include_deleted": True})}
        db.restore_many(ids)
        for rid in ids:
            record = all_records.get(rid, {})
            db.log_action(self.current_user, "RESTAURATION", dossier_label=self._record_label(record), sinistre_id=rid)
        self.refresh_all()
        self._write_through_sync()
        messagebox.showinfo("Corbeille", f"{len(ids)} dossier(s) restauré(s).")

    def _purge_selected(self):
        if not self.has_permission("purge"):
            messagebox.showwarning("Accès refusé", "Seul un Administrateur peut supprimer définitivement un dossier.")
            return
        ids = self._get_selected_corbeille_ids()
        if not ids:
            messagebox.showinfo("Sélection", "Veuillez sélectionner au moins un dossier à supprimer définitivement.")
            return
        if not messagebox.askyesno(
                "Suppression définitive",
                f"Supprimer définitivement {len(ids)} dossier(s) ?\n\n"
                "Cette opération est irréversible et effacera aussi la ligne correspondante "
                "dans le fichier Excel source (une sauvegarde sera créée avant)."):
            return
        all_records = {r["id"]: r for r in db.fetch_all({"include_deleted": True})}
        for rid in ids:
            record = all_records.get(rid)
            if record and self.source_workbook_path and record.get("excel_sheet") and record.get("excel_row"):
                try:
                    importer.clear_excel_row(self.source_workbook_path, record["excel_sheet"], record["excel_row"])
                except Exception as e:
                    if hasattr(self, "txt_log"):
                        self._log(f"❌ Erreur lors de l'effacement Excel du dossier {self._record_label(record)} : {e}")
            db.log_action(self.current_user, "PURGE_DEFINITIVE", dossier_label=self._record_label(record or {}),
                           sinistre_id=rid, ancienne_valeur=record)
        db.purge_many(ids)
        self.refresh_all()
        messagebox.showinfo("Corbeille", f"{len(ids)} dossier(s) supprimé(s) définitivement.")

    def _empty_corbeille(self):
        if not self.has_permission("purge"):
            messagebox.showwarning("Accès refusé", "Seul un Administrateur peut vider la Corbeille.")
            return
        data = db.fetch_deleted()
        if not data:
            messagebox.showinfo("Corbeille", "La corbeille est déjà vide.")
            return
        if not messagebox.askyesno(
                "Vider la corbeille",
                f"Supprimer définitivement les {len(data)} dossier(s) de la corbeille ?\n\n"
                "Cette opération est irréversible."):
            return
        if not messagebox.askyesno("Confirmation finale", "Êtes-vous vraiment sûr ? Cette action est irréversible."):
            return
        for record in data:
            if self.source_workbook_path and record.get("excel_sheet") and record.get("excel_row"):
                try:
                    importer.clear_excel_row(self.source_workbook_path, record["excel_sheet"], record["excel_row"])
                except Exception as e:
                    if hasattr(self, "txt_log"):
                        self._log(f"❌ Erreur lors de l'effacement Excel : {e}")
            db.log_action(self.current_user, "VIDER_CORBEILLE", dossier_label=self._record_label(record), ancienne_valeur=record)
        db.purge_many([r["id"] for r in data])
        self.refresh_all()
        messagebox.showinfo("Corbeille", "La corbeille a été vidée.")

    # ============================================================ IMPORT/EXPORT
    def _build_import_tab(self):
        frame = tk.Frame(self.tab_import, bg=COLOR_BG)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(frame, text="Importer un fichier Excel (.xlsx)", bg=COLOR_BG,
                  font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 6))
        tk.Label(frame, text="Une fois importé, ce fichier devient la source de référence : toute création, "
                             "modification ou suppression dans l'application est immédiatement écrite dans "
                             "ce fichier Excel, et toute modification faite directement dans Excel est "
                             "détectée automatiquement.",
                  bg=COLOR_BG, fg="#555", wraplength=700, justify="left").pack(anchor="w", pady=(0, 14))

        btn_row = tk.Frame(frame, bg=COLOR_BG)
        btn_row.pack(anchor="w", pady=(0, 12))
        ttk.Button(btn_row, text="📂 Choisir un fichier Excel...", command=self._choose_import_file).pack(side="left")
        ttk.Button(btn_row, text="⬇ Exporter toute la base (Excel)", command=self._export_all).pack(side="left", padx=10)
        ttk.Button(btn_row, text="🔄 Synchroniser vers Excel source", command=self._sync_to_source_excel).pack(side="left", padx=10)

        self.txt_log = tk.Text(frame, height=22, bg="#0f1117", fg="#9ff59f", font=("Consolas", 9))
        self.txt_log.pack(fill="both", expand=True, pady=(10, 0))
        self._log(f"Base de données : {db.get_db_path()}")
        self._log(f"Total actuel en base : {db.count_all()} sinistre(s)")

    def _log(self, msg):
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")
        self.update_idletasks()

    def _choose_import_file(self):
        path = filedialog.askopenfilename(filetypes=[("Fichier Excel", "*.xlsx *.xls")])
        if not path:
            return
        self._log(f"\n--- Import depuis : {path} ---")
        try:
            summary = importer.import_workbook(path, progress_callback=self._log)
            total_inserted = sum(summary.values())
            self._save_source_workbook_path(path)
            self.source_mtime = self._get_source_mtime()
            self._log(f"\n✅ Import terminé : {total_inserted} nouveau(x) sinistre(s) ajouté(s).")
            self._log(f"Total en base : {db.count_all()} sinistre(s)")
            self._log("ℹ Ce fichier est maintenant la source de référence (synchronisation automatique activée).")
            messagebox.showinfo("Import réussi", f"{total_inserted} nouveau(x) sinistre(s) importé(s).\n\n"
                                                   "Ce fichier est maintenant synchronisé automatiquement.")
        except Exception as e:
            self._log(f"❌ Erreur : {e}")
            messagebox.showerror("Erreur d'import", str(e))
        self.refresh_all()
        self._update_sync_status_label()

    def _export_all(self):
        records = db.fetch_all()
        if not records:
            messagebox.showinfo("Export", "La base est vide.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                             filetypes=[("Fichier Excel", "*.xlsx")],
                                             initialfile="export_complet_sinistres.xlsx")
        if not path:
            return
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sinistres"
        cols = list(records[0].keys())
        ws.append(cols)
        for r in records:
            ws.append([r.get(c) for c in cols])
        wb.save(path)
        self._log(f"Export complet effectué : {path}")
        messagebox.showinfo("Export", f"Export terminé :\n{path}")

    def _sync_to_source_excel(self):
        if not self.source_workbook_path:
            messagebox.showwarning("Synchronisation", "Aucun fichier Excel source n’a été importé pour le moment.")
            return
        try:
            records = db.fetch_all({"include_deleted": False})
            backup_path, assignments, unmatched = importer.sync_records_to_workbook(self.source_workbook_path, records, progress_callback=self._log)
            for record_id, sheet_name, row_idx in assignments:
                if record_id:
                    db.set_excel_location(record_id, sheet_name, row_idx)
            self.source_mtime = self._get_source_mtime()
            self._log(f"✅ Fichier Excel source mis à jour : {self.source_workbook_path}")
            self._log(f"🗂 Sauvegarde créée : {backup_path}")
            if unmatched:
                labels = ", ".join(self._record_label(r) for r in unmatched[:10])
                self._log(f"⚠ {len(unmatched)} sinistre(s) non synchronisé(s) (année manquante) : {labels}")
                messagebox.showwarning("Synchronisation partielle",
                                        f"{len(unmatched)} sinistre(s) n'ont pas pu être synchronisés "
                                        f"(champ Année manquant ou incohérent) : {labels}")
            else:
                messagebox.showinfo("Synchronisation réussie", "Les changements ont été écrits dans le fichier Excel source.")
        except Exception as e:
            self._log(f"❌ Erreur de synchronisation : {e}")
            messagebox.showerror("Erreur", f"Impossible de synchroniser le fichier Excel :\n{e}")


class DateFilterDialog(tk.Toplevel):
    def __init__(self, parent, current_filters, callback=None):
        super().__init__(parent)
        self.title("Filtres de période")
        self.geometry("360x220")
        self.callback = callback
        self.current_filters = current_filters

        tk.Label(self, text="Filtres avancés", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(12, 8))

        row1 = tk.Frame(self)
        row1.pack(fill="x", padx=16, pady=4)
        tk.Label(row1, text="Depuis :", width=12, anchor="w").pack(side="left")
        self.entry_from = ttk.Entry(row1)
        self.entry_from.pack(side="left", fill="x", expand=True)
        self.entry_from.insert(0, current_filters.get("date_from") or "")

        row2 = tk.Frame(self)
        row2.pack(fill="x", padx=16, pady=4)
        tk.Label(row2, text="Jusqu'au :", width=12, anchor="w").pack(side="left")
        self.entry_to = ttk.Entry(row2)
        self.entry_to.pack(side="left", fill="x", expand=True)
        self.entry_to.insert(0, current_filters.get("date_to") or "")

        row3 = tk.Frame(self)
        row3.pack(fill="x", padx=16, pady=4)
        tk.Label(row3, text="Mois (1-12) :", width=12, anchor="w").pack(side="left")
        self.entry_month = ttk.Entry(row3, width=8)
        self.entry_month.pack(side="left")
        self.entry_month.insert(0, current_filters.get("month") or "")
        tk.Label(row3, text="Jour (1-31) :", width=10, anchor="w").pack(side="left", padx=(8, 0))
        self.entry_day = ttk.Entry(row3, width=8)
        self.entry_day.pack(side="left")
        self.entry_day.insert(0, current_filters.get("day") or "")

        btn_row = tk.Frame(self)
        btn_row.pack(fill="x", padx=16, pady=(12, 0))
        ttk.Button(btn_row, text="Appliquer", command=self._apply).pack(side="left")
        ttk.Button(btn_row, text="Effacer", command=self._clear).pack(side="left", padx=8)
        ttk.Button(btn_row, text="Fermer", command=self.destroy).pack(side="left")

    def _apply(self):
        if self.callback:
            self.callback(self.entry_from.get().strip() or None, self.entry_to.get().strip() or None,
                          self.entry_month.get().strip() or None, self.entry_day.get().strip() or None)
        self.destroy()

    def _clear(self):
        self.entry_from.delete(0, "end")
        self.entry_to.delete(0, "end")
        self.entry_month.delete(0, "end")
        self.entry_day.delete(0, "end")


class DossierSelectionDialog(tk.Toplevel):
    def __init__(self, parent, current_dossiers, callback=None):
        super().__init__(parent)
        self.title("Recherche par N° Dossier")
        self.geometry("460x480")
        self.callback = callback
        self.selected = set(current_dossiers or [])

        tk.Label(self, text="Numéros de dossier", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
        tk.Label(self, text="Cochez un ou plusieurs dossiers puis cliquez sur Confirmer pour "
                             "n'afficher que ces dossiers dans la liste des sinistres.",
                  fg="#555", wraplength=420, justify="left").pack(anchor="w", padx=16)

        top = tk.Frame(self)
        top.pack(fill="x", padx=16, pady=(10, 4))
        tk.Label(top, text="Année :").pack(side="left")
        all_records = db.fetch_all()
        annees = sorted({r["annee"] for r in all_records if r.get("annee")}, reverse=True)
        self.cb_annee = ttk.Combobox(top, width=10, state="readonly",
                                      values=["Toutes"] + [str(a) for a in annees])
        self.cb_annee.set("Toutes")
        self.cb_annee.pack(side="left", padx=(4, 12))
        self.cb_annee.bind("<<ComboboxSelected>>", lambda e: self._rebuild_list())

        ttk.Button(top, text="☑ Tout cocher", command=self._check_all).pack(side="left", padx=4)
        ttk.Button(top, text="☐ Tout décocher", command=self._uncheck_all).pack(side="left", padx=4)

        self.lbl_selected_count = tk.Label(self, text="", fg=COLOR_ACCENT, font=("Segoe UI", 9, "bold"))
        self.lbl_selected_count.pack(anchor="w", padx=16, pady=(2, 4))

        self._all_records = all_records
        canvas = tk.Canvas(self, borderwidth=0)
        self.list_frame = tk.Frame(canvas)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True, padx=16, pady=6)
        self._canvas_window = canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.canvas = canvas

        self.checkvars = {}
        self._rebuild_list()

        btn_row = tk.Frame(self)
        btn_row.pack(fill="x", padx=16, pady=(0, 12))
        ttk.Button(btn_row, text="✅ Confirmer", command=self._apply).pack(side="left")
        ttk.Button(btn_row, text="Fermer", command=self.destroy).pack(side="left", padx=8)

    def _dossiers_for_current_year(self):
        annee_txt = self.cb_annee.get()
        records = self._all_records
        if annee_txt and annee_txt != "Toutes":
            records = [r for r in records if str(r.get("annee")) == annee_txt]
        return sorted({(r.get("numero_dossier") or "").strip() for r in records if (r.get("numero_dossier") or "").strip()})

    def _rebuild_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        self.checkvars = {}
        dossiers = self._dossiers_for_current_year()
        if not dossiers:
            tk.Label(self.list_frame, text="Aucun numéro de dossier disponible pour ce filtre.", fg="#777").pack(anchor="w", pady=6)
        else:
            for dossier in dossiers:
                var = tk.BooleanVar(value=dossier in self.selected)
                var.trace_add("write", lambda *a: self._update_count())
                ttk.Checkbutton(self.list_frame, text=dossier, variable=var).pack(anchor="w", pady=2)
                self.checkvars[dossier] = var
        self._update_count()

    def _update_count(self):
        total_checked = len(self.selected - set(self.checkvars.keys())) + sum(1 for v in self.checkvars.values() if v.get())
        self.lbl_selected_count.config(text=f"{total_checked} dossier(s) sélectionné(s) au total")

    def _check_all(self):
        for var in self.checkvars.values():
            var.set(True)

    def _uncheck_all(self):
        for var in self.checkvars.values():
            var.set(False)

    def _apply(self):
        # On fusionne la sélection de la vue courante avec celle déjà faite sur d'autres années
        for dossier, var in self.checkvars.items():
            if var.get():
                self.selected.add(dossier)
            else:
                self.selected.discard(dossier)
        if self.callback:
            self.callback(sorted(self.selected))
        self.destroy()


class RecordForm(tk.Toplevel):
    """Formulaire d'ajout / modification d'un sinistre."""

    def __init__(self, parent, record=None, on_save=None, current_user=None):
        super().__init__(parent)
        self.title("Modifier le sinistre" if record else "Ajouter un sinistre")
        self.geometry("900x780")
        self.minsize(760, 620)
        self.app = parent
        self.on_save = on_save
        self.record = record or {}
        self.is_edit = bool(record)
        self.entries = {}
        self.current_user = current_user
        self.suggestions = self._load_suggestions()
        self.linked_index = self._build_linked_index()

        canvas = tk.Canvas(self, borderwidth=0)
        frame = tk.Frame(canvas)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        for key, label in FIELDS_FORM:
            row = tk.Frame(frame)
            row.pack(fill="x", padx=10, pady=4)
            tk.Label(row, text=label, width=28, anchor="w").pack(side="left")
            value = self.record.get(key)
            if key in FIELD_CHOICES:
                choices = list(FIELD_CHOICES[key])
                extra = self.suggestions.get(key, [])
                for v in extra:
                    if v.upper() not in [c.upper() for c in choices]:
                        choices.append(v)
                entry = ttk.Combobox(row, width=28, values=choices, state="normal")
                entry.pack(side="left", fill="x", expand=True)
                if value is not None:
                    entry.set(str(value))
            else:
                entry = ttk.Entry(row, width=30)
                entry.pack(side="left", fill="x", expand=True)
                if value is not None:
                    display_value = format_date_for_display(value) if key in DATE_FIELDS else value
                    entry.insert(0, str(display_value))
                self._attach_autocomplete(entry, key)
            self.entries[key] = entry

        # Champs liés (§10) : camion <-> immatriculation/code CAM/type
        for source_key, target_keys in LINKED_FIELD_GROUPS:
            if source_key in self.entries:
                self.entries[source_key].bind(
                    "<FocusOut>", lambda e, sk=source_key, tk_=target_keys: self._apply_linked_fields(sk, tk_))

        # N° d'ordre automatique (pas besoin de le saisir) : pré-rempli au prochain
        # numéro disponible pour l'année choisie, et recalculé si l'année change.
        self._numero_auto = not self.is_edit
        if "numero" in self.entries and not self.is_edit:
            self._fill_next_numero()
            if "annee" in self.entries:
                self.entries["annee"].bind("<FocusOut>", self._on_annee_changed_for_numero, add="+")
            self.entries["numero"].bind("<KeyRelease>", self._on_numero_manually_edited, add="+")

        # Calculs automatiques : délai PV, écart, immobilisation et délai règlement.
        for key in ("date_expertise", "date_reception_pv", "date_sinistre", "date_reglement",
                    "montant_pv_expert", "montant_reglement_avant_rp"):
            if key in self.entries:
                self.entries[key].bind("<FocusOut>", self._recalculate, add="+")
        self._recalculate()

        btn_row = tk.Frame(frame)
        btn_row.pack(fill="x", padx=10, pady=16)
        ttk.Button(btn_row, text="💾 Enregistrer", command=self._save).pack(side="left")
        ttk.Button(btn_row, text="Annuler", command=self.destroy).pack(side="left", padx=10)

    def _set_entry_value(self, key, value):
        widget = self.entries.get(key)
        if widget is None:
            return
        widget.delete(0, tk.END)
        if value not in (None, ""):
            display_value = format_date_for_display(value) if key in DATE_FIELDS else value
            widget.insert(0, str(display_value))

    def _current_annee_int(self):
        val = self.entries.get("annee").get().strip() if "annee" in self.entries else ""
        if val:
            try:
                return int(float(val))
            except ValueError:
                return None
        return datetime.date.today().year

    def _fill_next_numero(self):
        annee = self._current_annee_int()
        next_num = db.get_next_numero(annee)
        widget = self.entries["numero"]
        widget.delete(0, tk.END)
        widget.insert(0, str(next_num))
        self._numero_auto = True

    def _on_annee_changed_for_numero(self, event=None):
        # Ne recalcule que si l'utilisateur n'a pas déjà modifié le N° à la main
        if self._numero_auto:
            self._fill_next_numero()

    def _on_numero_manually_edited(self, event=None):
        self._numero_auto = False

    def _recalculate(self, event=None):
        """Recalcule les champs dérivés sans bloquer la saisie si une date est incomplète."""
        def get_date(key):
            value = self.entries.get(key).get().strip() if key in self.entries else ""
            return parse_date_input(value)

        def get_float(key):
            value = self.entries.get(key).get().strip().replace(" ", "").replace(",", ".") if key in self.entries else ""
            try:
                return float(value) if value else None
            except ValueError:
                return None

        d_exp, d_pv = get_date("date_expertise"), get_date("date_reception_pv")
        if d_exp and d_pv:
            self._set_entry_value("delai_pv_jours", (d_pv - d_exp).days)

        m_exp = get_float("montant_pv_expert")
        m_reg = get_float("montant_reglement_avant_rp")
        if m_exp is not None and m_reg is not None:
            self._set_entry_value("ecart", round(m_reg - m_exp, 2))

        d_conf, d_reg = get_date("date_confirmation_pv"), get_date("date_reglement")
        if d_conf and d_reg:
            self._set_entry_value("delai_reg", (d_reg - d_conf).days)

    def _load_suggestions(self):
        suggestions = {key: [] for key in AUTOCOMPLETE_FIELDS}
        suggestions["statut_reglement"] = []
        try:
            rows = db.fetch_all()
            for r in rows:
                for key in suggestions:
                    value = (r.get(key) or "").strip()
                    if value and value not in suggestions[key]:
                        suggestions[key].append(value)
            for key in suggestions:
                suggestions[key].sort(key=lambda s: s.lower())
        except Exception:
            pass
        return suggestions

    def _build_linked_index(self):
        """Construit un index camion <-> immatriculation/code CAM/type pour le
        remplissage automatique des champs liés (§10)."""
        index = {"camion": {}, "immatriculation": {}}
        try:
            rows = db.fetch_all()
            for r in rows:
                camion = (r.get("camion") or "").strip()
                immat = (r.get("immatriculation") or "").strip()
                info = {
                    "camion": camion, "immatriculation": immat,
                    "code_cam": (r.get("code_cam") or "").strip(),
                    "type_vehicule": (r.get("type_vehicule") or "").strip(),
                }
                if camion and camion not in index["camion"]:
                    index["camion"][camion] = info
                if immat and immat not in index["immatriculation"]:
                    index["immatriculation"][immat] = info
        except Exception:
            pass
        return index

    def _apply_linked_fields(self, source_key, target_keys):
        source_value = self.entries[source_key].get().strip()
        info = self.linked_index.get(source_key, {}).get(source_value)
        if not info:
            return
        for target_key in target_keys:
            if target_key not in self.entries:
                continue
            current = self.entries[target_key].get().strip()
            new_value = info.get(target_key, "")
            if not current and new_value:
                widget = self.entries[target_key]
                if isinstance(widget, ttk.Combobox):
                    widget.set(new_value)
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, new_value)

    def _attach_autocomplete(self, entry, key):
        if key not in self.suggestions:
            return
        values = self.suggestions[key]
        if not values:
            return

        popup = tk.Listbox(self, height=6, exportselection=False)
        popup.place_forget()

        def show_popup(event=None):
            text = entry.get().strip().lower()
            popup.delete(0, tk.END)
            if not text:
                items = values[:8]
            else:
                items = [v for v in values if text in v.lower()][:8]
            for item in items:
                popup.insert(tk.END, item)
            if items:
                x = entry.winfo_rootx() - self.winfo_rootx()
                y = entry.winfo_rooty() - self.winfo_rooty() + entry.winfo_height()
                popup.place(x=x, y=y, width=entry.winfo_width())
                popup.lift()
            else:
                popup.place_forget()

        def hide_popup(event=None):
            popup.place_forget()

        def delayed_hide_popup(event=None):
            # Un léger délai laisse le temps au clic sur la liste de s'exécuter avant
            # que la perte de focus du champ ne referme la liste (sinon la sélection
            # à la souris ne fonctionne jamais : le focus part du champ AVANT le clic).
            entry.after(200, hide_popup)

        def select_popup(event=None):
            if popup.curselection():
                entry.delete(0, tk.END)
                entry.insert(0, popup.get(popup.curselection()[0]))
                popup.place_forget()
                if key in dict(LINKED_FIELD_GROUPS):
                    self._apply_linked_fields(key, dict(LINKED_FIELD_GROUPS)[key])

        entry.bind("<KeyRelease>", show_popup)
        entry.bind("<FocusOut>", delayed_hide_popup)
        popup.bind("<ButtonRelease-1>", select_popup)
        popup.bind("<Return>", select_popup)
        popup.bind("<Escape>", hide_popup)

    def _save(self):
        self._recalculate()
        data = {}
        for key, _ in FIELDS_FORM:
            val = self.entries[key].get().strip()
            if key in DATE_FIELDS:
                data[key] = format_date_for_storage(val)
            elif key in ("annee", "delai_reg", "delai_pv_jours", "montant_pv_expert",
                         "montant_reglement_avant_rp", "jours_immobilisation",
                         "heures_maindoeuvre", "montant_peinture", "montant_fournitures",
                         "vetuste", "franchise", "ecart"):
                data[key] = float(val) if val else None
            else:
                data[key] = val if val else None
        if not data.get("chauffeur"):
            messagebox.showwarning("Champ requis", "Le nom du chauffeur est requis.")
            return
        if not data.get("annee") and data.get("date_sinistre"):
            try:
                data["annee"] = float(datetime.date.fromisoformat(data["date_sinistre"]).year)
            except ValueError:
                pass
        if not data.get("annee"):
            messagebox.showwarning(
                "Champ requis",
                "Veuillez indiquer l'Année (ou une Date du sinistre au format AAAA-MM-JJ) : "
                "ce champ est nécessaire pour retrouver la bonne feuille dans le fichier Excel.")
            return

        # ---- Vérification des formats de date (§22) ----
        for date_key, label in (("date_sinistre", "Date du sinistre"),
                                 ("date_declaration", "Date de déclaration"),
                                 ("date_expertise", "Date d'expertise"),
                                 ("date_reception_pv", "Date de réception du PV"),
                                 ("date_confirmation_pv", "Date de confirmation des PV"),
                                 ("date_reglement", "Date de règlement")):
            v = data.get(date_key)
            if v:
                if parse_date_input(v) is None:
                    messagebox.showwarning("Format invalide", f"« {label} » doit être au format JJ-MM-AAAA.")
                    return

        # ---- Contrôle de cohérence (§22) ----
        if data.get("date_sinistre") and data.get("date_reglement"):
            try:
                d_sin = parse_date_input(data["date_sinistre"])
                d_reg = parse_date_input(data["date_reglement"])
                if d_reg and d_sin and d_reg < d_sin:
                    if not messagebox.askyesno(
                            "Incohérence détectée",
                            "La date de règlement est antérieure à la date du sinistre.\n\n"
                            "Voulez-vous enregistrer quand même ?"):
                        return
            except ValueError:
                pass
        if (data.get("statut_reglement") or "").strip().upper() == "REGLER" and not data.get("date_reglement"):
            if not messagebox.askyesno(
                    "Incohérence détectée",
                    "Le statut est « REGLER » mais aucune date de règlement n'est renseignée.\n\n"
                    "Voulez-vous enregistrer quand même ?"):
                return

        # ---- Contrôle des doublons de N° Dossier (§22) ----
        numero_dossier = data.get("numero_dossier")
        if numero_dossier:
            existing = [r for r in db.fetch_all() if (r.get("numero_dossier") or "").strip() == numero_dossier.strip()]
            if self.is_edit:
                existing = [r for r in existing if r["id"] != self.record.get("id")]
            if existing:
                if not messagebox.askyesno(
                        "Doublon détecté",
                        f"Le numéro de dossier « {numero_dossier} » existe déjà "
                        f"(chauffeur : {existing[0].get('chauffeur') or '?'}).\n\n"
                        "Voulez-vous enregistrer quand même ?"):
                    return

        # ---- Nouvelles valeurs non encore connues (§9) ----
        # Elles sont acceptées automatiquement (et deviendront disponibles en
        # auto-complétion la prochaine fois) : on informe l'utilisateur sans
        # bloquer l'enregistrement.
        new_values = []
        for key in AUTOCOMPLETE_FIELDS:
            value = (data.get(key) or "").strip()
            known = self.suggestions.get(key, [])
            if value and value.lower() not in [k.lower() for k in known]:
                new_values.append(value)

        if self.on_save:
            self.on_save(data)
        if new_values and hasattr(self.app, "_show_notification"):
            self.app._show_notification(f"✓ Enregistré ({len(new_values)} nouvelle(s) valeur(s) ajoutée(s) à l'auto-complétion).")
        self.destroy()


class FirstAdminSetupDialog(tk.Toplevel):
    """Forcé au tout premier lancement : création du compte Administrateur (§21)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("Création du compte Administrateur")
        self.geometry("380x300")
        self.protocol("WM_DELETE_WINDOW", self._quit_app)
        self.grab_set()
        self.resizable(False, False)

        tk.Label(self, text="Bienvenue 👋", font=("Segoe UI", 13, "bold")).pack(pady=(16, 4))
        tk.Label(self, text="Aucun utilisateur n'existe encore.\nCréez le compte Administrateur principal.",
                  justify="center", fg="#555").pack(pady=(0, 14))

        form = tk.Frame(self)
        form.pack(fill="x", padx=24)
        tk.Label(form, text="Nom d'utilisateur :").grid(row=0, column=0, sticky="w", pady=4)
        self.entry_user = ttk.Entry(form, width=22)
        self.entry_user.grid(row=0, column=1, pady=4)
        tk.Label(form, text="Mot de passe :").grid(row=1, column=0, sticky="w", pady=4)
        self.entry_pass = ttk.Entry(form, width=22, show="•")
        self.entry_pass.grid(row=1, column=1, pady=4)
        tk.Label(form, text="Confirmer :").grid(row=2, column=0, sticky="w", pady=4)
        self.entry_pass2 = ttk.Entry(form, width=22, show="•")
        self.entry_pass2.grid(row=2, column=1, pady=4)

        ttk.Button(self, text="✅ Créer le compte", command=self._create).pack(pady=16)
        self.entry_user.focus_set()
        self.wait_window(self)

    def _quit_app(self):
        self.app.destroy()
        sys.exit(0)

    def _create(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get()
        password2 = self.entry_pass2.get()
        if not username or not password:
            messagebox.showwarning("Champs requis", "Le nom d'utilisateur et le mot de passe sont requis.")
            return
        if len(password) < 4:
            messagebox.showwarning("Mot de passe trop court", "Le mot de passe doit contenir au moins 4 caractères.")
            return
        if password != password2:
            messagebox.showwarning("Erreur", "Les deux mots de passe ne correspondent pas.")
            return
        db.create_user(username, password, "Administrateur")
        messagebox.showinfo("Compte créé", f"Le compte Administrateur « {username} » a été créé.\nVous allez maintenant vous connecter.")
        self.destroy()


class LoginDialog(tk.Toplevel):
    """Fenêtre de connexion (§21)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("Connexion")
        self.geometry("340x250")
        self.grab_set()
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        tk.Label(self, text="🔐 SUIVI DES SINISTRES", font=("Segoe UI", 13, "bold")).pack(pady=(18, 12))

        form = tk.Frame(self)
        form.pack(fill="x", padx=24)
        tk.Label(form, text="Utilisateur :").grid(row=0, column=0, sticky="w", pady=6)
        self.entry_user = ttk.Entry(form, width=20)
        self.entry_user.grid(row=0, column=1, pady=6)
        tk.Label(form, text="Mot de passe :").grid(row=1, column=0, sticky="w", pady=6)
        self.entry_pass = ttk.Entry(form, width=20, show="•")
        self.entry_pass.grid(row=1, column=1, pady=6)
        self.entry_pass.bind("<Return>", lambda e: self._login())

        btn_row = tk.Frame(self)
        btn_row.pack(pady=16)
        ttk.Button(btn_row, text="Connexion", command=self._login).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Quitter", command=self._quit).pack(side="left", padx=6)
        self.entry_user.focus_set()

        ttk.Button(self, text="➕ Créer un compte", command=self._open_create_account).pack(pady=(0, 12))

    def _open_create_account(self):
        CreateAccountDialog(self)

    def _quit(self):
        self.app.destroy()
        sys.exit(0)

    def _login(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get()
        user = db.authenticate(username, password)
        if user:
            self.app.current_user = user["username"]
            self.app.current_role = user["role"]
            self.destroy()
        else:
            messagebox.showerror("Connexion refusée", "Nom d'utilisateur ou mot de passe incorrect.")
            self.entry_pass.delete(0, "end")


class CreateAccountDialog(tk.Toplevel):
    """Création d'un nouveau compte depuis l'écran de connexion. Chaque compte est
    indépendant des autres (identifiants et mot de passe propres, rôle propre) ;
    par sécurité, l'auto-inscription ne permet pas de créer un compte Administrateur
    (seul un Administrateur existant peut promouvoir un compte via la Gestion des
    utilisateurs)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.login_dialog = parent
        self.title("Créer un compte")
        self.geometry("360x300")
        self.grab_set()
        self.resizable(False, False)

        tk.Label(self, text="➕ Nouveau compte", font=("Segoe UI", 13, "bold")).pack(pady=(18, 4))
        tk.Label(self, text="Ce compte sera indépendant des autres comptes\n"
                             "(identifiants et droits propres).",
                  fg="#555", justify="center").pack(pady=(0, 10))

        form = tk.Frame(self)
        form.pack(fill="x", padx=24)
        tk.Label(form, text="Nom d'utilisateur :").grid(row=0, column=0, sticky="w", pady=6)
        self.entry_user = ttk.Entry(form, width=20)
        self.entry_user.grid(row=0, column=1, pady=6)
        tk.Label(form, text="Mot de passe :").grid(row=1, column=0, sticky="w", pady=6)
        self.entry_pass = ttk.Entry(form, width=20, show="•")
        self.entry_pass.grid(row=1, column=1, pady=6)
        tk.Label(form, text="Confirmer :").grid(row=2, column=0, sticky="w", pady=6)
        self.entry_pass2 = ttk.Entry(form, width=20, show="•")
        self.entry_pass2.grid(row=2, column=1, pady=6)
        tk.Label(form, text="Rôle :").grid(row=3, column=0, sticky="w", pady=6)
        self.cb_role = ttk.Combobox(form, width=18, state="readonly", values=["Gestionnaire", "Consultation"])
        self.cb_role.set("Gestionnaire")
        self.cb_role.grid(row=3, column=1, pady=6)

        ttk.Button(self, text="✅ Créer mon compte", command=self._create).pack(pady=14)
        self.entry_user.focus_set()

    def _create(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get()
        password2 = self.entry_pass2.get()
        role = self.cb_role.get()
        if not username or not password:
            messagebox.showwarning("Champs requis", "Le nom d'utilisateur et le mot de passe sont requis.")
            return
        if len(password) < 4:
            messagebox.showwarning("Mot de passe trop court", "Le mot de passe doit contenir au moins 4 caractères.")
            return
        if password != password2:
            messagebox.showwarning("Erreur", "Les deux mots de passe ne correspondent pas.")
            return
        try:
            db.create_user(username, password, role)
        except Exception:
            messagebox.showerror("Erreur", f"Le nom d'utilisateur « {username} » existe déjà. Choisissez-en un autre.")
            return
        db.log_action(username, "CREATION_COMPTE_AUTONOME", dossier_label=username,
                       nouvelle_valeur={"username": username, "role": role})
        messagebox.showinfo("Compte créé", f"Le compte « {username} » a été créé.\nVous pouvez maintenant vous connecter.")
        self.destroy()


class LicenseRequiredDialog(tk.Toplevel):
    """Affichée au démarrage si aucune licence valide n'est active. Bloque l'accès
    à l'application tant qu'une licence valide n'est pas fournie."""

    def __init__(self, parent, status):
        super().__init__(parent)
        self.app = parent
        self.title("Licence requise")
        self.geometry("460x360")
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._quit_app)
        self.resizable(False, False)

        reasons = {
            "missing": "Aucune licence n'est enregistrée sur ce poste.",
            "expired": f"Votre licence a expiré le {status.get('expiry')}.",
            "tampered": "Le fichier de licence est invalide ou a été modifié.",
            "error": "Impossible de lire le fichier de licence.",
        }
        tk.Label(self, text="🔒 Licence requise", font=("Segoe UI", 13, "bold")).pack(pady=(18, 4))
        tk.Label(self, text=reasons.get(status.get("reason"), "Licence invalide."),
                  fg="#b00020", wraplength=400, justify="center").pack(pady=(0, 14))

        tk.Label(self, text="Si vous avez reçu un code de licence, saisissez-le ci-dessous :",
                  wraplength=400, justify="left").pack(anchor="w", padx=20)
        self.entry_token = ttk.Entry(self, width=50)
        self.entry_token.pack(padx=20, pady=8)
        ttk.Button(self, text="✅ Appliquer la licence", command=self._apply).pack(pady=(0, 16))

        ttk.Separator(self).pack(fill="x", padx=20, pady=4)
        ttk.Button(self, text="🔑 Je suis l'éditeur — Générer une licence",
                   command=self._open_generator).pack(pady=10)
        ttk.Button(self, text="Quitter l'application", command=self._quit_app).pack(pady=(0, 10))

    def _quit_app(self):
        self.destroy()

    def _apply(self):
        token = self.entry_token.get().strip()
        if not token:
            messagebox.showwarning("Champ requis", "Veuillez saisir un code de licence.")
            return
        ok, msg = licensing.apply_license_token(token)
        if ok:
            messagebox.showinfo("Licence appliquée", msg)
            self.destroy()
        else:
            messagebox.showerror("Licence invalide", msg)

    def _open_generator(self):
        LicenseGeneratorDialog(self, on_generated=self._on_generated)

    def _on_generated(self):
        self.destroy()


class LicenseGeneratorDialog(tk.Toplevel):
    """Génération d'une nouvelle licence, protégée par un mot de passe maître connu
    uniquement de l'éditeur du logiciel. Ce mot de passe est distinct des comptes
    utilisateurs de l'application et n'est jamais stocké en clair."""

    def __init__(self, parent, on_generated=None):
        super().__init__(parent)
        self.on_generated = on_generated
        self.title("Générateur de licence — éditeur")
        self.geometry("420x320")
        self.grab_set()
        self.resizable(False, False)

        first_time = not licensing.master_password_is_set()
        if first_time:
            tk.Label(self, text="🔑 Premier lancement : définissez votre\nmot de passe maître (éditeur)",
                      font=("Segoe UI", 11, "bold"), justify="center").pack(pady=(18, 6))
            tk.Label(self, text="Ce mot de passe sera nécessaire à chaque génération de\n"
                                 "licence. Conservez-le en lieu sûr : lui seul permet de\n"
                                 "renouveler ou déployer une licence.",
                      fg="#555", justify="center").pack(pady=(0, 12))
            form = tk.Frame(self)
            form.pack()
            tk.Label(form, text="Nouveau mot de passe maître :").grid(row=0, column=0, sticky="w", pady=4)
            self.entry_new = ttk.Entry(form, width=22, show="•")
            self.entry_new.grid(row=0, column=1, pady=4)
            tk.Label(form, text="Confirmer :").grid(row=1, column=0, sticky="w", pady=4)
            self.entry_new2 = ttk.Entry(form, width=22, show="•")
            self.entry_new2.grid(row=1, column=1, pady=4)
            ttk.Button(self, text="Définir et continuer", command=self._set_master).pack(pady=16)
        else:
            tk.Label(self, text="🔑 Générateur de licence", font=("Segoe UI", 13, "bold")).pack(pady=(18, 10))
            tk.Label(self, text="Mot de passe maître :").pack()
            self.entry_pass = ttk.Entry(self, width=25, show="•")
            self.entry_pass.pack(pady=6)
            self.entry_pass.bind("<Return>", lambda e: self._check_and_show_generator())
            ttk.Button(self, text="Valider", command=self._check_and_show_generator).pack(pady=10)
            self.entry_pass.focus_set()

    def _set_master(self):
        p1 = self.entry_new.get()
        p2 = self.entry_new2.get()
        if len(p1) < 6:
            messagebox.showwarning("Mot de passe trop court", "Le mot de passe maître doit contenir au moins 6 caractères.")
            return
        if p1 != p2:
            messagebox.showwarning("Erreur", "Les deux mots de passe ne correspondent pas.")
            return
        licensing.set_master_password(p1)
        messagebox.showinfo("Mot de passe défini", "Mot de passe maître enregistré. Vous pouvez maintenant générer une licence.")
        for widget in self.winfo_children():
            widget.destroy()
        self._show_generator_form()

    def _check_and_show_generator(self):
        if not licensing.check_master_password(self.entry_pass.get()):
            messagebox.showerror("Refusé", "Mot de passe maître incorrect.")
            return
        for widget in self.winfo_children():
            widget.destroy()
        self._show_generator_form()

    def _show_generator_form(self):
        tk.Label(self, text="✅ Générer une nouvelle licence", font=("Segoe UI", 12, "bold")).pack(pady=(16, 10))
        form = tk.Frame(self)
        form.pack()
        tk.Label(form, text="Durée (jours) :").grid(row=0, column=0, sticky="w", pady=4)
        self.entry_duration = ttk.Entry(form, width=10)
        self.entry_duration.insert(0, str(licensing.DEFAULT_DURATION_DAYS))
        self.entry_duration.grid(row=0, column=1, pady=4, sticky="w")
        tk.Label(form, text="Libellé (client) :").grid(row=1, column=0, sticky="w", pady=4)
        self.entry_label = ttk.Entry(form, width=22)
        self.entry_label.grid(row=1, column=1, pady=4)

        ttk.Button(self, text="🔑 Générer et appliquer sur ce poste", command=self._generate).pack(pady=12)

        tk.Label(self, text="Jeton généré (copiez-le pour un autre poste) :").pack(anchor="w", padx=16)
        self.txt_token = tk.Text(self, height=4, wrap="char", font=("Consolas", 9))
        self.txt_token.pack(fill="x", padx=16, pady=(4, 6))
        ttk.Button(self, text="📋 Copier le jeton maintenant", command=self._copy_token).pack(pady=(0, 10))

    def _copy_token(self):
        token = self.txt_token.get("1.0", "end").strip()
        if not token:
            messagebox.showinfo("Rien à copier", "Générez d'abord une licence.")
            return
        self.clipboard_clear()
        self.clipboard_append(token)
        messagebox.showinfo("Copié", "Le jeton a été copié dans le presse-papiers.")

    def _generate(self):
        try:
            duration = int(self.entry_duration.get())
        except ValueError:
            messagebox.showwarning("Valeur invalide", "La durée doit être un nombre de jours.")
            return
        token = licensing.generate_license_token(duration_days=duration, label=self.entry_label.get().strip())
        self.txt_token.delete("1.0", "end")
        self.txt_token.insert("1.0", token)
        ok, msg = licensing.apply_license_token(token)
        if ok:
            messagebox.showinfo("Licence générée", f"{msg}\n\nCliquez sur « 📋 Copier le jeton maintenant » "
                                                     "si vous voulez le déployer sur un autre poste — vous "
                                                     "pourrez aussi le retrouver plus tard dans "
                                                     "Administration → Licence.")
            if self.on_generated:
                self.on_generated()


class LicenseManagementDialog(tk.Toplevel):
    """Accessible depuis Administration > Licence. Protégée par le mot de passe
    maître : même un compte Administrateur de l'application ne peut pas consulter
    ou renouveler la licence sans le connaître (« moi seul qui peux la voir »)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("Licence — accès réservé")
        self.geometry("360x180")
        self.grab_set()
        self.resizable(False, False)

        tk.Label(self, text="🔒 Zone réservée à l'éditeur", font=("Segoe UI", 11, "bold")).pack(pady=(18, 8))
        tk.Label(self, text="Mot de passe maître :").pack()
        self.entry_pass = ttk.Entry(self, width=25, show="•")
        self.entry_pass.pack(pady=6)
        self.entry_pass.bind("<Return>", lambda e: self._check())
        ttk.Button(self, text="Valider", command=self._check).pack(pady=10)
        self.entry_pass.focus_set()

    def _check(self):
        if not licensing.master_password_is_set():
            self.destroy()
            LicenseGeneratorDialog(self.app)
            return
        if not licensing.check_master_password(self.entry_pass.get()):
            messagebox.showerror("Refusé", "Mot de passe maître incorrect.")
            return
        self.destroy()
        LicenseStatusDialog(self.app)


class LicenseStatusDialog(tk.Toplevel):
    """Affiche l'état de la licence active et permet de copier le jeton actuel
    (utile si l'utilisateur ne l'a pas noté lors de la génération)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("État de la licence")
        self.geometry("440x340")

        status = licensing.check_license()
        tk.Label(self, text="🔑 État de la licence", font=("Segoe UI", 13, "bold")).pack(pady=(16, 10))

        info = tk.Frame(self)
        info.pack(fill="x", padx=20)
        rows = [
            ("Statut", "✅ Valide" if status["valid"] else "❌ Invalide/expirée"),
            ("Expiration", status.get("expiry") or "—"),
            ("Jours restants", status.get("days_left") if status.get("days_left") is not None else "—"),
            ("Client", status.get("label") or "—"),
        ]
        for i, (label, value) in enumerate(rows):
            tk.Label(info, text=label, anchor="w").grid(row=i, column=0, sticky="w", pady=4)
            tk.Label(info, text=str(value), anchor="e", font=("Segoe UI", 9, "bold")).grid(row=i, column=1, sticky="e", pady=4)
        info.columnconfigure(1, weight=1)

        tk.Label(self, text="Jeton actuel (pour le redéployer sur un autre poste) :",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
        token = licensing.get_current_token() or "(aucun jeton enregistré)"
        self.txt_token = tk.Text(self, height=4, wrap="char", font=("Consolas", 9))
        self.txt_token.insert("1.0", token)
        self.txt_token.configure(state="disabled")
        self.txt_token.pack(fill="x", padx=20)

        def copy_token():
            self.clipboard_clear()
            self.clipboard_append(token)
            messagebox.showinfo("Copié", "Le jeton a été copié dans le presse-papiers.")

        btn_row = tk.Frame(self)
        btn_row.pack(pady=14)
        ttk.Button(btn_row, text="📋 Copier le jeton", command=copy_token).pack(side="left", padx=6)
        ttk.Button(btn_row, text="🔄 Générer une nouvelle licence", command=self._regenerate).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Fermer", command=self.destroy).pack(side="left", padx=6)

    def _regenerate(self):
        self.destroy()
        LicenseGeneratorDialog(self.app)


class AdminDashboardDialog(tk.Toplevel):
    """Tableau de bord d'administration (§24)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("Tableau de bord Administration")
        self.geometry("420x420")

        tk.Label(self, text="📊 Tableau de bord Administration", font=("Segoe UI", 12, "bold")).pack(pady=(14, 10))

        info = tk.Frame(self)
        info.pack(fill="both", expand=True, padx=20)

        total = db.count_all()
        nb_users = db.user_count()
        nb_journal = db.journal_count()
        sync_state = "✅ Actif" if parent.source_workbook_path and os.path.exists(parent.source_workbook_path) else "⚠ Non configuré"
        last_sync = "—"
        if parent.source_mtime:
            last_sync = datetime.datetime.fromtimestamp(parent.source_mtime).strftime("%d/%m/%Y %H:%M:%S")

        last_backup = "—"
        disk_usage = 0
        if parent.source_workbook_path:
            backups_dir = os.path.join(os.path.dirname(parent.source_workbook_path), "backups")
            if os.path.isdir(backups_dir):
                files = [os.path.join(backups_dir, f) for f in os.listdir(backups_dir)]
                if files:
                    latest = max(files, key=os.path.getmtime)
                    last_backup = f"{os.path.basename(latest)} ({datetime.datetime.fromtimestamp(os.path.getmtime(latest)).strftime('%d/%m/%Y %H:%M')})"
                disk_usage += sum(os.path.getsize(f) for f in files if os.path.isfile(f))
        if os.path.exists(db.get_db_path()):
            disk_usage += os.path.getsize(db.get_db_path())

        rows = [
            ("Nombre total de dossiers", str(total)),
            ("Nombre d'utilisateurs", str(nb_users)),
            ("État de la synchronisation Excel", sync_state),
            ("Dernière synchronisation", last_sync),
            ("Dernière sauvegarde", last_backup),
            ("Modifications enregistrées (journal)", str(nb_journal)),
            ("Espace disque utilisé (base + sauvegardes)", f"{disk_usage / 1024 / 1024:.2f} Mo"),
        ]
        for i, (label, value) in enumerate(rows):
            tk.Label(info, text=label, anchor="w", font=("Segoe UI", 9)).grid(row=i, column=0, sticky="w", pady=6)
            tk.Label(info, text=value, anchor="e", font=("Segoe UI", 9, "bold")).grid(row=i, column=1, sticky="e", pady=6)
        info.columnconfigure(1, weight=1)

        ttk.Button(self, text="Fermer", command=self.destroy).pack(pady=14)


class JournalDialog(tk.Toplevel):
    """Journal des opérations (§17 / §23)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("Journal des opérations")
        self.geometry("820x480")

        top = tk.Frame(self)
        top.pack(fill="x", padx=12, pady=10)
        tk.Label(top, text="Recherche :").pack(side="left")
        self.entry_search = ttk.Entry(top, width=30)
        self.entry_search.pack(side="left", padx=6)
        self.entry_search.bind("<Return>", lambda e: self._refresh())
        ttk.Button(top, text="🔎 Filtrer", command=self._refresh).pack(side="left", padx=4)
        ttk.Button(top, text="♻ Tout afficher", command=self._reset).pack(side="left", padx=4)

        cols = ["horodatage", "utilisateur", "action", "dossier_label"]
        headers = ["Date / Heure", "Utilisateur", "Action", "Dossier"]
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, h in zip(cols, headers):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=180 if c == "dossier_label" else 150, anchor="w")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._refresh()

    def _reset(self):
        self.entry_search.delete(0, "end")
        self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        search = self.entry_search.get().strip() or None
        for r in db.fetch_journal(limit=1000, search=search):
            self.tree.insert("", "end", values=[
                r.get("horodatage") or "", r.get("utilisateur") or "", r.get("action") or "",
                r.get("dossier_label") or "",
            ])


class UserManagementDialog(tk.Toplevel):
    """Gestion des utilisateurs et des rôles (§21)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("Gestion des utilisateurs")
        self.geometry("560x420")

        top = tk.Frame(self)
        top.pack(fill="x", padx=12, pady=10)
        ttk.Button(top, text="➕ Nouvel utilisateur", command=self._add_user).pack(side="left", padx=4)
        ttk.Button(top, text="🔑 Changer le rôle", command=self._change_role).pack(side="left", padx=4)
        ttk.Button(top, text="🔒 Réinitialiser le mot de passe", command=self._reset_password).pack(side="left", padx=4)
        ttk.Button(top, text="🗑 Supprimer", command=self._delete_user).pack(side="left", padx=4)

        cols = ["id", "username", "role", "created_at"]
        headers = ["ID", "Utilisateur", "Rôle", "Créé le"]
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c, h in zip(cols, headers):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=130, anchor="w")
        self.tree.column("id", width=0, stretch=False)
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for u in db.fetch_users():
            self.tree.insert("", "end", values=[u["id"], u["username"], u["role"], u.get("created_at") or ""])

    def _get_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Sélection", "Veuillez sélectionner un utilisateur.")
            return None
        values = self.tree.item(sel[0])["values"]
        return {"id": values[0], "username": values[1], "role": values[2]}

    def _add_user(self):
        dlg = tk.Toplevel(self)
        dlg.title("Nouvel utilisateur")
        dlg.geometry("320x260")
        dlg.grab_set()
        form = tk.Frame(dlg)
        form.pack(padx=20, pady=16)
        tk.Label(form, text="Nom d'utilisateur :").grid(row=0, column=0, sticky="w", pady=4)
        e_user = ttk.Entry(form, width=20)
        e_user.grid(row=0, column=1, pady=4)
        tk.Label(form, text="Mot de passe :").grid(row=1, column=0, sticky="w", pady=4)
        e_pass = ttk.Entry(form, width=20, show="•")
        e_pass.grid(row=1, column=1, pady=4)
        tk.Label(form, text="Rôle :").grid(row=2, column=0, sticky="w", pady=4)
        cb_role = ttk.Combobox(form, width=18, state="readonly", values=list(db.ROLES))
        cb_role.set("Gestionnaire")
        cb_role.grid(row=2, column=1, pady=4)

        def create():
            username = e_user.get().strip()
            password = e_pass.get()
            role = cb_role.get()
            if not username or not password:
                messagebox.showwarning("Champs requis", "Nom d'utilisateur et mot de passe requis.")
                return
            try:
                db.create_user(username, password, role)
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de créer l'utilisateur :\n{e}")
                return
            db.log_action(self.app.current_user, "CREATION_UTILISATEUR", dossier_label=username,
                           nouvelle_valeur={"username": username, "role": role})
            self._refresh()
            dlg.destroy()

        ttk.Button(dlg, text="Créer", command=create).pack(pady=10)

    def _change_role(self):
        user = self._get_selected()
        if not user:
            return
        new_role = simple_choice_dialog(self, "Changer le rôle", f"Nouveau rôle pour « {user['username']} » :", list(db.ROLES), default=user["role"])
        if new_role and new_role != user["role"]:
            db.update_user_role(user["id"], new_role)
            db.log_action(self.app.current_user, "CHANGEMENT_ROLE", dossier_label=user["username"],
                           ancienne_valeur={"role": user["role"]}, nouvelle_valeur={"role": new_role})
            self._refresh()

    def _reset_password(self):
        user = self._get_selected()
        if not user:
            return
        new_pass = simple_text_input_dialog(self, "Réinitialiser le mot de passe", f"Nouveau mot de passe pour « {user['username']} » :")
        if new_pass:
            if len(new_pass) < 4:
                messagebox.showwarning("Mot de passe trop court", "Le mot de passe doit contenir au moins 4 caractères.")
                return
            db.update_user_password(user["id"], new_pass)
            db.log_action(self.app.current_user, "REINIT_MOT_DE_PASSE", dossier_label=user["username"])
            messagebox.showinfo("Terminé", "Mot de passe réinitialisé.")

    def _delete_user(self):
        user = self._get_selected()
        if not user:
            return
        if user["username"] == self.app.current_user:
            messagebox.showwarning("Action impossible", "Vous ne pouvez pas supprimer votre propre compte.")
            return
        admins = [u for u in db.fetch_users() if u["role"] == "Administrateur"]
        if user["role"] == "Administrateur" and len(admins) <= 1:
            messagebox.showwarning("Action impossible", "Impossible de supprimer le dernier compte Administrateur.")
            return
        if not messagebox.askyesno("Confirmer", f"Supprimer l'utilisateur « {user['username']} » ?"):
            return
        db.delete_user(user["id"])
        db.log_action(self.app.current_user, "SUPPRESSION_UTILISATEUR", dossier_label=user["username"])
        self._refresh()


def simple_choice_dialog(parent, title, message, options, default=None):
    """Petite boîte de dialogue à choix unique (combobox) réutilisable."""
    result = {"value": None}
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.geometry("340x160")
    dlg.grab_set()
    tk.Label(dlg, text=message, wraplength=300, justify="left").pack(padx=16, pady=(16, 8))
    cb = ttk.Combobox(dlg, values=options, state="readonly", width=25)
    if default:
        cb.set(default)
    cb.pack(pady=6)

    def confirm():
        result["value"] = cb.get()
        dlg.destroy()

    ttk.Button(dlg, text="Valider", command=confirm).pack(pady=10)
    dlg.wait_window(dlg)
    return result["value"]


def simple_text_input_dialog(parent, title, message):
    """Petite boîte de dialogue à saisie libre réutilisable (mot de passe, etc.)."""
    result = {"value": None}
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.geometry("340x160")
    dlg.grab_set()
    tk.Label(dlg, text=message, wraplength=300, justify="left").pack(padx=16, pady=(16, 8))
    entry = ttk.Entry(dlg, width=25, show="•")
    entry.pack(pady=6)
    entry.focus_set()

    def confirm():
        result["value"] = entry.get()
        dlg.destroy()

    entry.bind("<Return>", lambda e: confirm())
    ttk.Button(dlg, text="Valider", command=confirm).pack(pady=10)
    dlg.wait_window(dlg)
    return result["value"]


class SettingsDialog(tk.Toplevel):
    """Fenêtre de paramètres (§26)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.app = parent
        self.title("Paramètres")
        self.geometry("560x480")
        self.settings = load_settings()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Onglet Général ---
        tab_general = tk.Frame(notebook)
        notebook.add(tab_general, text="Général")

        tk.Label(tab_general, text="Fichier Excel source :", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        path_row = tk.Frame(tab_general)
        path_row.pack(fill="x", padx=14)
        self.lbl_path = tk.Label(path_row, text=parent.source_workbook_path or "(aucun)", fg="#555", wraplength=380, justify="left")
        self.lbl_path.pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="Parcourir...", command=self._browse_path).pack(side="right")

        tk.Label(tab_general, text="Dossier des sauvegardes :", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        backups_dir = os.path.join(os.path.dirname(parent.source_workbook_path), "backups") if parent.source_workbook_path else "(aucun fichier source)"
        tk.Label(tab_general, text=backups_dir, fg="#555", wraplength=500, justify="left").pack(anchor="w", padx=14)

        tk.Label(tab_general, text="Thème :", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        self.cb_theme = ttk.Combobox(tab_general, values=["Clair", "Sombre"], state="readonly", width=20)
        self.cb_theme.set(self.settings.get("theme", "Clair"))
        self.cb_theme.pack(anchor="w", padx=14)
        tk.Label(tab_general, text="(le thème sombre sera appliqué au prochain démarrage)", fg="#888", font=("Segoe UI", 8)).pack(anchor="w", padx=14)

        tk.Label(tab_general, text="Synchronisation :", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        self.cb_sync = ttk.Combobox(tab_general, values=["Immédiate (à chaque modification)", "Manuelle uniquement"],
                                     state="readonly", width=32)
        self.cb_sync.set("Immédiate (à chaque modification)" if parent.auto_sync_enabled else "Manuelle uniquement")
        self.cb_sync.pack(anchor="w", padx=14)

        # --- Onglet Couleurs des statuts ---
        tab_colors = tk.Frame(notebook)
        notebook.add(tab_colors, text="Couleurs des statuts")
        tk.Label(tab_colors, text="Couleurs détectées / personnalisées :", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(14, 6))
        self.color_rows = {}
        colors = db.load_status_colors()
        color_frame = tk.Frame(tab_colors)
        color_frame.pack(fill="x", padx=14)
        for i, (statut, color) in enumerate(sorted(colors.items())):
            tk.Label(color_frame, text=statut, width=18, anchor="w").grid(row=i, column=0, sticky="w", pady=3)
            swatch = tk.Label(color_frame, text="    ", bg=color, relief="solid", borderwidth=1)
            swatch.grid(row=i, column=1, padx=6)
            ttk.Button(color_frame, text="Modifier...", command=lambda s=statut, sw=swatch: self._pick_color(s, sw)).grid(row=i, column=2, padx=4)
        if not colors:
            tk.Label(tab_colors, text="Aucune couleur détectée pour le moment (importez un fichier Excel).", fg="#777").pack(anchor="w", padx=14)

        btn_row = tk.Frame(self)
        btn_row.pack(pady=10)
        ttk.Button(btn_row, text="💾 Enregistrer", command=self._save).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Fermer", command=self.destroy).pack(side="left", padx=6)

    def _browse_path(self):
        path = filedialog.askopenfilename(filetypes=[("Fichier Excel", "*.xlsx *.xls")])
        if path:
            self.app._save_source_workbook_path(path)
            self.app.source_mtime = self.app._get_source_mtime()
            self.lbl_path.config(text=path)

    def _pick_color(self, statut, swatch_widget):
        try:
            from tkinter import colorchooser
            color = colorchooser.askcolor(title=f"Couleur pour {statut}")
            if color and color[1]:
                swatch_widget.config(bg=color[1])
                self.color_rows[statut] = color[1]
        except Exception:
            pass

    def _save(self):
        self.settings["theme"] = self.cb_theme.get()
        save_settings(self.settings)
        self.app.auto_sync_enabled = (self.cb_sync.get() == "Immédiate (à chaque modification)")
        if self.color_rows:
            db.save_status_colors(self.color_rows)
            self.app.refresh_all()
        messagebox.showinfo("Paramètres", "Paramètres enregistrés.")
        self.destroy()


def load_settings():
    path = os.path.join(db.get_app_dir(), "settings.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def save_settings(settings):
    path = os.path.join(db.get_app_dir(), "settings.json")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


if __name__ == "__main__":
    app = App()
    app.mainloop()
