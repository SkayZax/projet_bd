# Mobilite professionnelle : couverture des competences d'un metier cible.

import argparse
import os

from py2neo import Graph


MOT_DE_PASSE = os.environ.get("NEO4J_PASSWORD", "azertyuiop")
POIDS_STATUT = {"REQUIERT": 1.0, "OPTIONNEL": 0.5}
NOM_STATUT = {"REQUIERT": "obligatoire", "OPTIONNEL": "facultative"}


def trouver_metiers(graphe, terme):
    """Cherche un metier par nom ou appellation, exact puis partiel."""
    conditions = [
        "toLower(m.nom) = toLower($terme)",
        "any(a IN coalesce(m.appellations, []) WHERE toLower(a) = toLower($terme))",
        "toLower(m.nom) CONTAINS toLower($terme) OR "
        "any(a IN coalesce(m.appellations, []) WHERE toLower(a) CONTAINS toLower($terme))",
    ]
    for condition in conditions:
        lignes = graphe.run(
            "MATCH (m:Metier) WHERE " + condition + " "
            "RETURN DISTINCT m.nom AS nom ORDER BY nom",
            terme=terme.strip(),
        ).data()
        if lignes:
            return [ligne["nom"] for ligne in lignes]
    return []


def choisir_metier(graphe, terme):
    """Retourne un nom canonique, ou None si la recherche est ambigue/inconnue."""
    noms = trouver_metiers(graphe, terme)
    if not noms:
        print(f'Aucun métier trouvé pour "{terme}".')
        return None
    if len(noms) > 1:
        print(f'Plusieurs métiers correspondent à "{terme}" :')
        for nom in noms[:10]:
            print("  -", nom)
        if len(noms) > 10:
            print(f"  ... et {len(noms) - 10} autre(s)")
        return None
    return noms[0]


def competences_metier(graphe, metier, connaissances=False):
    """Retourne les competences cible avec leur statut obligatoire/optionnel."""
    filtre = "(c:Competence OR c:Connaissance)" if connaissances else "c:Competence"
    lignes = graphe.run(
        "MATCH (:Metier {nom: $metier})-[r:REQUIERT|OPTIONNEL]->(c) "
        "WHERE " + filtre + " "
        "RETURN c.nom AS nom, type(r) AS statut, "
        "CASE WHEN c:Connaissance THEN 'connaissance' ELSE 'competence' END AS categorie",
        metier=metier,
    ).data()

    cible = {}
    for ligne in lignes:
        nom = ligne["nom"]
        statut = ligne["statut"]
        element = {"nom": nom, "statut": statut, "categorie": ligne["categorie"],
                   "poids": POIDS_STATUT.get(statut, 0.0)}
        cle = nom.casefold()
        # En cas de doublon de relation, une competence requise est prioritaire.
        if cle not in cible or element["poids"] > cible[cle]["poids"]:
            cible[cle] = element
    return cible


def evaluer_mobilite(competences_cible, competences_candidat):
    """Calcule la couverture ponderee et les competences cibles manquantes.

    competences_cible est le dictionnaire renvoye par competences_metier.
    Les competences du candidat sont les competences qu'il possede, quel que
    soit son metier actuel.
    """
    possedees = {nom.strip().casefold() for nom in competences_candidat if nom.strip()}
    total = sum(element["poids"] for element in competences_cible.values())
    acquises = [element for cle, element in competences_cible.items() if cle in possedees]
    manquantes = [element for cle, element in competences_cible.items() if cle not in possedees]
    poids_acquis = sum(element["poids"] for element in acquises)

    manquantes.sort(key=lambda e: (e["statut"] != "REQUIERT", e["nom"].casefold()))
    acquises.sort(key=lambda e: e["nom"].casefold())
    return {
        "score": poids_acquis / total if total else 0.0,
        "poids_acquis": poids_acquis,
        "poids_total": total,
        "acquises": acquises,
        "manquantes": manquantes,
    }


def mobilite(graphe, metier_actuel, competences_candidat, metier_cible,
             connaissances=False):
    """Compare toutes les competences fournies du candidat aux attentes cible."""
    cible = competences_metier(graphe, metier_cible, connaissances)
    resultat = evaluer_mobilite(cible, competences_candidat)
    resultat["metier_actuel"] = metier_actuel
    resultat["metier_cible"] = metier_cible
    resultat["nombre_competences_candidat"] = len(
        {nom.strip().casefold() for nom in competences_candidat if nom.strip()}
    )
    return resultat


def afficher(resultat):
    print(f"\nTransition : {resultat['metier_actuel']} -> {resultat['metier_cible']}")
    print("Compétences fournies par le candidat :", resultat["nombre_competences_candidat"])
    print("Compétences acquises pour la cible : {}/{}".format(
        len(resultat["acquises"]), len(resultat["acquises"]) + len(resultat["manquantes"])))
    print("Correspondance : {:.1f} %".format(resultat["score"] * 100))

    if resultat["acquises"]:
        print("\nCompétences déjà acquises :")
        for element in resultat["acquises"]:
            print(f"  - {element['nom']} ({NOM_STATUT.get(element['statut'], element['statut'])})")

    print("\nCompétences manquantes :")
    if resultat["manquantes"]:
        for element in resultat["manquantes"]:
            categorie = "connaissance" if element["categorie"] == "connaissance" else "compétence"
            print(
                f"  - {element['nom']} ({categorie} {NOM_STATUT.get(element['statut'], element['statut'])})"
            )
    else:
        print("  Aucune")


def main():
    parseur = argparse.ArgumentParser(
        description="Evalue la transition d'un candidat vers un metier cible."
    )
    parseur.add_argument(
        "--connaissances", action="store_true",
        help="inclut aussi les connaissances requises ou optionnelles par la cible",
    )
    arguments = parseur.parse_args()

    metier_actuel = input("Métier actuel : ").strip()
    texte_competences = input(
        "Toutes les compétences du candidat (séparées par des points-virgules) : "
    ).strip()
    metier_cible = input("Métier cible : ").strip()
    competences_candidat = [nom.strip() for nom in texte_competences.split(";") if nom.strip()]
    if not metier_actuel or not metier_cible or not competences_candidat:
        print("Saisissez le métier actuel, le métier cible et au moins une compétence.")
        return

    try:
        graphe = Graph("bolt://localhost:7687", auth=("neo4j", MOT_DE_PASSE))
        actuel = choisir_metier(graphe, metier_actuel)
        cible = choisir_metier(graphe, metier_cible)
        if not actuel or not cible:
            return
        resultat = mobilite(
            graphe, actuel, competences_candidat, cible, arguments.connaissances
        )
        if not resultat["poids_total"]:
            print("Le métier cible n'a aucune compétence associée dans la base.")
            return
        afficher(resultat)
    except Exception as erreur:
        print("Erreur de connexion ou de requête Neo4j :", erreur)


if __name__ == "__main__":
    main()
