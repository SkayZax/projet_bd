# FRAYSSE Nathan 3-FI-B et POIRIER Mathis 3-FI-B

import argparse
import os

from py2neo import Graph

MOT_DE_PASSE = os.environ.get("NEO4J_PASSWORD", "azertyuiop")
MAX_CANDIDATS = 10


def trouver_competence(graphe, terme, connaissances=False):
    # nom exact puis avec le terme (on prend pas en comtpe la casse)
    labels = "(c:Competence OR c:Connaissance)" if connaissances else "c:Competence"
    for condition in ["toLower(c.nom) = toLower($terme)", "toLower(c.nom) CONTAINS toLower($terme)"]:
        noms = [r["nom"] for r in graphe.run(
            "MATCH (c) WHERE " + labels + " AND " + condition + " RETURN c.nom AS nom ORDER BY nom",
            terme=terme).data()]
        if noms:
            return noms
    return []


def choisir(graphe, terme, connaissances=False):
    # renvoie le nom correspondant au terme ou None si asbent
    noms = trouver_competence(graphe, terme, connaissances)
    if not noms:
        print('Aucune competence trouvee pour "' + terme + '"')
        return None
    if len(noms) > 1:
        print('"' + terme + '" correspond a', len(noms), "competences, precisez votre recherche :")
        for nom in noms[:MAX_CANDIDATS]:
            print("  -", nom)
        if len(noms) > MAX_CANDIDATS:
            print("  ... et", len(noms) - MAX_CANDIDATS, "autre(s)")
        return None
    return noms[0]


def recommander(graphe, mes_competences, connaissances=False):
    # metiers partageant au moins une competence avec l'utilisateur
    labels = "(c:Competence OR c:Connaissance)" if connaissances else "c:Competence"
    lignes = graphe.run(
        "MATCH (m:Metier)-[:REQUIERT|OPTIONNEL]->(c) WHERE " + labels + " AND c.nom IN $competences "
        "WITH DISTINCT m "
        "MATCH (m)-[r:REQUIERT|OPTIONNEL]->(x) WHERE " + labels.replace("c:", "x:") + " "
        "RETURN m.nom AS nom, collect(DISTINCT x.nom) AS toutes, "
        "collect(DISTINCT CASE WHEN type(r) = 'REQUIERT' THEN x.nom END) AS requises",
        competences=list(mes_competences)).data()

    moi = set(mes_competences)
    resultats = []
    for ligne in lignes:
        toutes = set(ligne["toutes"])
        requises = set(ligne["requises"])
        resultats.append({"nom": ligne["nom"],
                          "score": len(moi & toutes) / len(moi | toutes),
                          "communes": len(moi & toutes), "total": len(toutes),
                          "requises_communes": len(moi & requises), "requises": len(requises)})
    resultats.sort(key=lambda r: (-r["score"], -r["requises_communes"] / max(r["requises"], 1), r["nom"]))
    return resultats


if __name__ == "__main__":
    parseur = argparse.ArgumentParser(description="Recommande des metiers selon vos competences")
    parseur.add_argument("competences", nargs="+", help="competences (nom complet ou morceau de nom)")
    parseur.add_argument("--top", type=int, default=10, help="nombre de metiers recommandes (10 par defaut)")
    parseur.add_argument("--connaissances", action="store_true", help="prend aussi en compte les connaissances")
    arguments = parseur.parse_args()

    try:
        graphe = Graph("bolt://localhost:7687", auth=("neo4j", MOT_DE_PASSE))
        choisies = [choisir(graphe, terme, arguments.connaissances) for terme in arguments.competences]
        if all(choisies):
            mes_competences = sorted(set(choisies))
            print("Vos competences :")
            for nom in mes_competences:
                print("  -", nom)

            resultats = recommander(graphe, mes_competences, arguments.connaissances)
            print("\n" + str(len(resultats)), "metier(s) en commun avec vos competences, les", arguments.top, "meilleurs :\n")
            for rang, r in enumerate(resultats[:arguments.top], 1):
                print("{}. {} - similarite {:.1f} %".format(rang, r["nom"], r["score"] * 100))
                print("   competences en commun : {}/{} | requises couvertes : {}/{}".format(
                    r["communes"], r["total"], r["requises_communes"], r["requises"]))
    except Exception as e:
        print("Erreur :", e)
