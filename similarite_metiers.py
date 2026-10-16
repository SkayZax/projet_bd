# FRAYSSE Nathan 3-FI-B et POIRIER Mathis 3-FI-B

import os
import sys

from py2neo import Graph

MOT_DE_PASSE = os.environ.get("NEO4J_PASSWORD", "azertyuiop")
MAX_CANDIDATS = 10


def trouver_metier(graphe, terme):
    # on cherche par nom exact, appellation exacte, puis nom ou appellation contenant le terme
    requetes = [
        "toLower(m.nom) = toLower($terme)",
        "any(a IN m.appellations WHERE toLower(a) = toLower($terme))",
        "toLower(m.nom) CONTAINS toLower($terme) OR any(a IN m.appellations WHERE toLower(a) CONTAINS toLower($terme))",
    ]
    for condition in requetes:
        noms = [r["nom"] for r in graphe.run(
            "MATCH (m:Metier) WHERE " + condition + " RETURN m.nom AS nom ORDER BY nom", terme=terme).data()]
        if noms:
            return noms
    return []


def competences(graphe, metier, connaissances=False):
    # competences (et connaissances si demandée) du metier
    labels = "(c:Competence OR c:Connaissance)" if connaissances else "c:Competence"
    return {r["nom"] for r in graphe.run(
        "MATCH (:Metier {nom: $metier})-[:REQUIERT|OPTIONNEL]->(c) WHERE " + labels + " RETURN DISTINCT c.nom AS nom",
        metier=metier).data()}


def similarite(graphe, metier1, metier2, connaissances=False):
    # a inter b / b inter a
    a = competences(graphe, metier1, connaissances)
    b = competences(graphe, metier2, connaissances)
    union = a | b
    score = len(a & b) / len(union) if union else 0.0
    return {"score": score, "communes": sorted(a & b), "union": len(union),
            "seulement1": len(a - b), "seulement2": len(b - a), "total1": len(a), "total2": len(b)}


def choisir(graphe, terme):
    # renvoie le nom du metier correspondant au terme, ou None si asbent
    noms = trouver_metier(graphe, terme)
    if not noms:
        print('Aucun metier trouve pour "' + terme + '"')
        return None
    if len(noms) > 1:
        print('"' + terme + '" correspond a', len(noms), "metiers, precisez votre recherche :")
        for nom in noms[:MAX_CANDIDATS]:
            print("  -", nom)
        if len(noms) > MAX_CANDIDATS:
            print("  ... et", len(noms) - MAX_CANDIDATS, "autre(s)")
        return None
    return noms[0]


if __name__ == "__main__":
    arguments = [a for a in sys.argv[1:] if a != "--connaissances"]
    avec_connaissances = "--connaissances" in sys.argv
    if len(arguments) != 2:
        print('Utilisation : python similarite_metiers.py "metier 1" "metier 2" [--connaissances]')
        sys.exit(1)

    try:
        graphe = Graph("bolt://localhost:7687", auth=("neo4j", MOT_DE_PASSE))
        metier1 = choisir(graphe, arguments[0])
        metier2 = choisir(graphe, arguments[1])
        if metier1 and metier2:
            resultat = similarite(graphe, metier1, metier2, avec_connaissances)
            element = "competences et connaissances" if avec_connaissances else "competences"
            print("Metier 1 :", metier1, "(" + str(resultat["total1"]), element + ")")
            print("Metier 2 :", metier2, "(" + str(resultat["total2"]), element + ")")
            print("\nIntersection :", len(resultat["communes"]), "| Union :", resultat["union"])
            print("Seulement metier 1 :", resultat["seulement1"], "| Seulement metier 2 :", resultat["seulement2"])
            print("Similarite de Jaccard : {:.3f} ({:.1f} %)".format(resultat["score"], resultat["score"] * 100))
            if resultat["communes"]:
                print("\nElements en commun :")
                for nom in resultat["communes"]:
                    print("  -", nom)
    except Exception as e:
        print("Erreur :", e)
