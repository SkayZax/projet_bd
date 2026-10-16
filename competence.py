# FRAYSSE Nathan 3-FI-B et POIRIER Mathis 3-FI-B

import os
import sys

from py2neo import Graph

MOT_DE_PASSE = os.environ.get("NEO4J_PASSWORD", "azertyuiop")
MAX_RESULTATS = 10


def chercher(graphe, terme):
    # competences et connaissances dont le nom contient le terme
    resultats = graphe.run(
        "MATCH (n) WHERE (n:Competence OR n:Connaissance) AND toLower(n.nom) CONTAINS toLower($terme) "
        "RETURN labels(n)[0] AS categorie, n.nom AS nom, "
        "[(m:Metier)-[:REQUIERT]->(n) | m.nom] AS requis, "
        "[(m:Metier)-[:OPTIONNEL]->(n) | m.nom] AS optionnel "
        "ORDER BY nom", terme=terme).data()
    # si le nom correspond au terme, on hgarde que lui
    exacts = [r for r in resultats if r["nom"].lower() == terme.lower()]
    return exacts if exacts else resultats


def afficher(resultat):
    print("=" * 70)
    print(resultat["categorie"], ":", resultat["nom"])
    for titre, metiers in [("Requise pour", resultat["requis"]), ("Optionnelle pour", resultat["optionnel"])]:
        print("\n" + titre, "(" + str(len(metiers)) + " metier(s))")
        for metier in sorted(metiers):
            print("  -", metier)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Utilisation : python competence.py "nom de la competence ou connaissance"')
        sys.exit(1)

    try:
        graphe = Graph("bolt://localhost:7687", auth=("neo4j", MOT_DE_PASSE))
        resultats = chercher(graphe, " ".join(sys.argv[1:]).strip())
        if not resultats:
            print("Aucune competence ou connaissance trouvee")
        for resultat in resultats[:MAX_RESULTATS]:
            afficher(resultat)
        if len(resultats) > MAX_RESULTATS:
            print("\n... et", len(resultats) - MAX_RESULTATS, "autre(s) resultat(s), precisez votre recherche")
    except Exception as e:
        print("Erreur :", e)
