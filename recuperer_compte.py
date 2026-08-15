# -*- coding: utf-8 -*-
"""
Outil de RÉCUPÉRATION DE COMPTE — à utiliser si vous ne pouvez plus vous
connecter à l'application (mot de passe oublié, par exemple).

Il fonctionne SANS avoir besoin de se connecter, car il travaille directement
sur le fichier de base de données (sinistres.db), à côté de ce script.

Il propose deux actions :
  1. Réinitialiser le mot de passe d'un compte existant ;
  2. Supprimer TOUS les comptes (pour repartir de zéro et créer un nouveau
     compte Administrateur au prochain lancement).

Utilisation : double-cliquez sur 4_recuperer_compte.bat
(ou : python recuperer_compte.py depuis une invite de commande)
"""
import getpass
import sys

import database as db


def _print_header(title):
    print("=" * 55)
    print(f"   {title}")
    print("=" * 55)
    print()


def _list_users(users):
    print("Comptes existants sur ce poste :")
    print()
    if not users:
        print("   (aucun compte)")
    for u in users:
        print(f"  - {u['username']}  (rôle : {u['role']}, créé le {u.get('created_at') or '?'})")
    print()


def reset_password(users):
    """Réinitialise le mot de passe d'un compte existant (choisi par l'utilisateur)."""
    username = input("Nom d'utilisateur pour lequel réinitialiser le mot de passe : ").strip()
    matching = [u for u in users if u["username"].lower() == username.lower()]
    if not matching:
        print(f"\n❌ Aucun compte nommé « {username} » n'a été trouvé (vérifiez l'orthographe exacte ci-dessus).")
        input("\nAppuyez sur Entrée pour fermer...")
        return

    user = matching[0]
    print(f"\nRéinitialisation du mot de passe de « {user['username']} » ({user['role']}).")
    new_password = getpass.getpass("Nouveau mot de passe (au moins 4 caractères) : ")
    confirm = getpass.getpass("Confirmez le nouveau mot de passe : ")

    if len(new_password) < 4:
        print("\n❌ Le mot de passe doit contenir au moins 4 caractères. Rien n'a été modifié.")
        input("\nAppuyez sur Entrée pour fermer...")
        return
    if new_password != confirm:
        print("\n❌ Les deux mots de passe ne correspondent pas. Rien n'a été modifié.")
        input("\nAppuyez sur Entrée pour fermer...")
        return

    db.update_user_password(user["id"], new_password)
    db.log_action(f"{user['username']} (via outil de récupération)", "REINIT_MOT_DE_PASSE",
                   dossier_label=user["username"])
    print(f"\n✅ Mot de passe de « {user['username']} » réinitialisé avec succès.")
    print("Vous pouvez maintenant relancer l'application normalement et vous connecter.")
    input("\nAppuyez sur Entrée pour fermer...")


def delete_all_accounts(users):
    """Supprime TOUS les comptes après une double confirmation, pour permettre de
    recréer un nouveau compte Administrateur au prochain lancement."""
    print()
    print("⚠️  Vous êtes sur le point de supprimer TOUS les comptes :")
    for u in users:
        print(f"      - {u['username']} ({u['role']})")
    print()
    print("   - Les sinistres, pièces jointes et sauvegardes ne seront PAS touchés ;")
    print("   - Au prochain lancement, l'application vous demandera de créer")
    print("     un nouveau compte Administrateur.")
    print()
    confirm = input("Pour confirmer, tapez SUPPRIMER (en majuscules) : ").strip()
    if confirm != "SUPPRIMER":
        print("\n❌ Opération annulée. Aucun compte n'a été supprimé.")
        input("\nAppuyez sur Entrée pour fermer...")
        return

    n = db.delete_all_users()
    print(f"\n✅ {n} compte(s) supprimé(s) avec succès.")
    print("Au prochain lancement de l'application, vous pourrez créer votre")
    print("nouveau compte Administrateur.")
    input("\nAppuyez sur Entrée pour fermer...")


def main():
    db.init_db()
    _print_header("RÉCUPÉRATION DE COMPTE - SUIVI DES SINISTRES")

    users = db.fetch_users()

    if not users:
        print("Aucun compte n'existe encore dans cette base.")
        print("Un compte Administrateur sera à créer au prochain")
        print("lancement normal de l'application (2_lancer_app.bat).")
        input("\nAppuyez sur Entrée pour fermer...")
        return

    _list_users(users)

    print("Que voulez-vous faire ?")
    print("  1) Réinitialiser le mot de passe d'un compte")
    print("  2) Supprimer TOUS les comptes (repartir de zéro)")
    print("  0) Quitter")
    print()

    choix = input("Votre choix : ").strip()

    if choix == "1":
        reset_password(users)
    elif choix == "2":
        delete_all_accounts(users)
    elif choix == "0":
        print("\nAucune modification effectuée.")
    else:
        print("\n❌ Choix invalide. Aucune modification effectuée.")
        input("\nAppuyez sur Entrée pour fermer...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
