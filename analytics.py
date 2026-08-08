# -*- coding: utf-8 -*-
"""
Calculs analytiques à partir des données de sinistres.
"""
import datetime
from collections import defaultdict

import database as db


def _parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.date.fromisoformat(text)
        except ValueError:
            return None
    return None


def get_effective_reglement_delay(record):
    if not record:
        return None
    d_conf = _parse_date(record.get("date_confirmation_pv"))
    d_reg = _parse_date(record.get("date_reglement"))
    if d_conf and d_reg:
        return (d_reg - d_conf).days
    value = record.get("delai_reg")
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def kpis(records):
    total = len(records)
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=6)
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    montant_total_pv = sum(r.get("montant_pv_expert") or 0 for r in records)
    montant_total_reglement = sum(r.get("montant_reglement_avant_rp") or 0 for r in records)
    regles = [r for r in records if (r.get("statut_reglement") or "").upper().strip() == "REGLER"]
    non_regles = total - len(regles)

    def date_in_period(value, start_date, end_date):
        parsed = _parse_date(value)
        return parsed is not None and start_date <= parsed <= end_date

    sinistres_jour = sum(1 for r in records if date_in_period(r.get("date_sinistre"), today, today))
    sinistres_semaine = sum(1 for r in records if date_in_period(r.get("date_sinistre"), week_start, today))
    sinistres_mois = sum(1 for r in records if date_in_period(r.get("date_sinistre"), month_start, today))
    sinistres_annee = sum(1 for r in records if date_in_period(r.get("date_sinistre"), year_start, today))

    dossiers_attente = sum(1 for r in records if (r.get("statut_reglement") or "").upper().strip() != "REGLER")
    dossiers_sans_expertise = sum(1 for r in records if not (r.get("date_expertise") or ""))
    dossiers_sans_pv = sum(1 for r in records if not (r.get("date_reception_pv") or ""))

    delais = [get_effective_reglement_delay(r) for r in records]
    delais = [d for d in delais if d is not None]
    delai_moyen = sum(delais) / len(delais) if delais else 0

    return {
        "total": total,
        "montant_total_pv": montant_total_pv,
        "montant_total_reglement": montant_total_reglement,
        "regles": len(regles),
        "non_regles": non_regles,
        "delai_moyen": round(delai_moyen, 1),
        "sinistres_jour": sinistres_jour,
        "sinistres_semaine": sinistres_semaine,
        "sinistres_mois": sinistres_mois,
        "sinistres_annee": sinistres_annee,
        "dossiers_attente": dossiers_attente,
        "dossiers_sans_expertise": dossiers_sans_expertise,
        "dossiers_sans_pv": dossiers_sans_pv,
    }


def par_annee(records):
    """Nombre de sinistres et montants totaux (PV Expert et Règlement, séparés) par année."""
    data = defaultdict(lambda: {"count": 0, "montant_pv": 0.0, "montant_reglement": 0.0})
    for r in records:
        a = r.get("annee")
        if not a:
            continue
        data[a]["count"] += 1
        data[a]["montant_pv"] += r.get("montant_pv_expert") or 0
        data[a]["montant_reglement"] += r.get("montant_reglement_avant_rp") or 0
    return dict(sorted(data.items()))


def par_mois(records, annee=None):
    """Nombre de sinistres par mois (pour une année donnée ou toutes années confondues)."""
    data = defaultdict(int)
    for r in records:
        ds = r.get("date_sinistre")
        if not ds:
            continue
        try:
            d = datetime.date.fromisoformat(ds)
        except ValueError:
            continue
        if annee and d.year != annee:
            continue
        key = d.month
        data[key] += 1
    return dict(sorted(data.items()))


def par_mois_toutes_annees(records, mois):
    """Nombre de sinistres pour UN mois donné (1-12), réparti par année.
    Permet par exemple de comparer tous les « janvier » entre 2017 et 2026."""
    data = defaultdict(int)
    for r in records:
        ds = r.get("date_sinistre")
        if not ds:
            continue
        try:
            d = datetime.date.fromisoformat(ds)
        except ValueError:
            continue
        if d.month != mois:
            continue
        data[d.year] += 1
    return dict(sorted(data.items()))


def par_jour(records, annee=None, mois=None):
    """Nombre de sinistres par jour du mois, pour une année et un mois donnés
    (si non précisés, agrège tous les jours toutes années/mois confondus)."""
    data = defaultdict(int)
    for r in records:
        ds = r.get("date_sinistre")
        if not ds:
            continue
        try:
            d = datetime.date.fromisoformat(ds)
        except ValueError:
            continue
        if annee and d.year != annee:
            continue
        if mois and d.month != mois:
            continue
        data[d.day] += 1
    return dict(sorted(data.items()))


def par_chauffeur(records):
    """Statistiques agrégées par chauffeur : nb sinistres, fautif/non fautif, montants, délai moyen."""
    data = defaultdict(lambda: {
        "nb": 0, "fautif": 0, "non_fautif": 0, "montant_pv": 0.0, "montant_reglement": 0.0, "delais": []
    })
    for r in records:
        c = (r.get("chauffeur") or "").strip()
        if not c:
            continue
        d = data[c]
        d["nb"] += 1
        f = (r.get("fautif") or "").upper().strip()
        if f == "FAUTIF":
            d["fautif"] += 1
        elif "NON" in f:
            d["non_fautif"] += 1
        d["montant_pv"] += r.get("montant_pv_expert") or 0
        d["montant_reglement"] += r.get("montant_reglement_avant_rp") or 0
        delay = get_effective_reglement_delay(r)
        if delay is not None:
            d["delais"].append(delay)

    result = []
    for chauffeur, d in data.items():
        delai_moyen = sum(d["delais"]) / len(d["delais"]) if d["delais"] else 0
        result.append({
            "chauffeur": chauffeur,
            "nb": d["nb"],
            "fautif": d["fautif"],
            "non_fautif": d["non_fautif"],
            "montant_pv": round(d["montant_pv"], 2),
            "montant_reglement": round(d["montant_reglement"], 2),
            "delai_moyen": round(delai_moyen, 1),
        })
    result.sort(key=lambda x: x["nb"], reverse=True)
    return result


def couts_et_delais_par_annee(records):
    """Montants moyens/totaux (PV Expert et Règlement, séparés) et délai moyen de règlement, par année."""
    data = defaultdict(lambda: {"pv": [], "reglement": [], "delais": []})
    for r in records:
        a = r.get("annee")
        if not a:
            continue
        if r.get("montant_pv_expert"):
            data[a]["pv"].append(r["montant_pv_expert"])
        if r.get("montant_reglement_avant_rp"):
            data[a]["reglement"].append(r["montant_reglement_avant_rp"])
        delay = get_effective_reglement_delay(r)
        if delay is not None:
            data[a]["delais"].append(delay)
    result = {}
    for a, d in sorted(data.items()):
        result[a] = {
            "montant_pv_moyen": round(sum(d["pv"]) / len(d["pv"]), 2) if d["pv"] else 0,
            "montant_pv_total": round(sum(d["pv"]), 2),
            "montant_reglement_moyen": round(sum(d["reglement"]) / len(d["reglement"]), 2) if d["reglement"] else 0,
            "montant_reglement_total": round(sum(d["reglement"]), 2),
            "delai_moyen": round(sum(d["delais"]) / len(d["delais"]), 1) if d["delais"] else 0,
        }
    return result


def alertes(records, seuil_jours=30):
    """Retourne les dossiers non réglés, triés par ancienneté avec priorité et motif."""
    today = datetime.date.today()
    out = []
    for r in records:
        statut = (r.get("statut_reglement") or "").upper().strip()
        if statut == "REGLER":
            continue
        ds = r.get("date_sinistre")
        jours_ecoules = None
        if ds:
            parsed = _parse_date(ds)
            if parsed:
                jours_ecoules = (today - parsed).days

        reasons = []
        priority = "moyenne"
        if not r.get("date_expertise"):
            reasons.append("expertise non réalisée")
            priority = "haute"
        if not r.get("date_reception_pv"):
            reasons.append("PV non reçu")
            if priority != "haute":
                priority = "moyenne"
        if jours_ecoules is not None and jours_ecoules > seuil_jours:
            reasons.append("dossier ancien")
            if priority != "haute":
                priority = "moyenne"
        if not reasons:
            reasons.append("suivi en attente")

        out.append({
            **r,
            "jours_ecoules": jours_ecoules,
            "reason": "; ".join(reasons),
            "priority": priority,
        })
    out.sort(key=lambda x: (x["jours_ecoules"] is None, -(x["jours_ecoules"] or 0)))
    return out


def repartition_fautif(records):
    fautif = sum(1 for r in records if (r.get("fautif") or "").upper().strip() == "FAUTIF")
    non_fautif = sum(1 for r in records if "NON" in (r.get("fautif") or "").upper())
    return {"FAUTIF": fautif, "NON FAUTIF": non_fautif}


def top_lieux(records, n=10):
    data = defaultdict(int)
    for r in records:
        lieu = (r.get("lieu_accident") or "").strip()
        if lieu:
            data[lieu] += 1
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    return items[:n]


def top_types_accident(records, n=10):
    data = defaultdict(int)
    for r in records:
        t = (r.get("type_accident") or "").strip()
        if t:
            data[t] += 1
    items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    return items[:n]
