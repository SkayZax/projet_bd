# Question 5.4 : similarite entre deux competences ESCO.

import os

from py2neo import Graph


MOT_DE_PASSE = os.environ.get("NEO4J_PASSWORD", "azertyuiop")

REQUETE_OCCURRENCES = """
MATCH (c1:Competence), (c2:Competence)
WHERE toLower(c1.nom) = toLower($nom1)
  AND toLower(c2.nom) = toLower($nom2)
CALL {
    WITH c1
    MATCH (m:Metier)-[r:REQUIERT|OPTIONNEL]->(c1)
    RETURN collect({metier: m.nom, statut: type(r)}) AS occurrences1
}
CALL {
    WITH c2
    MATCH (m:Metier)-[r:REQUIERT|OPTIONNEL]->(c2)
    RETURN collect({metier: m.nom, statut: type(r)}) AS occurrences2
}
RETURN c1.nom AS competence1, c2.nom AS competence2,
       occurrences1, occurrences2
"""

POIDS_STATUT = {"REQUIERT": 1.0, "OPTIONNEL": 0.5}
NOM_STATUT = {"REQUIERT": "obligatoire", "OPTIONNEL": "facultative"}


def poids_par_metier(occurrences):
    """Associe a chaque metier le poids de la competence dans ce metier."""
    poids = {}
    statuts = {}
    for occurrence in occurrences:
        metier = occurrence["metier"]
        statut = occurrence["statut"]
        valeur = POIDS_STATUT.get(statut, 0)
        # Si une competence est a la fois requise et optionnelle, le statut
        # obligatoire est prioritaire pour ce metier.
        if valeur > poids.get(metier, 0):
            poids[metier] = valeur
            statuts[metier] = statut
    return poids, statuts


def calculer_similarite(occurrences1, occurrences2):
    """Calcule le Jaccard pondere, avec obligatoire=1 et facultative=0.5."""
    poids1, statuts1 = poids_par_metier(occurrences1)
    poids2, statuts2 = poids_par_metier(occurrences2)
    tous_les_metiers = poids1.keys() | poids2.keys()

    intersection = sum(min(poids1.get(m, 0), poids2.get(m, 0))
                       for m in tous_les_metiers)
    union = sum(max(poids1.get(m, 0), poids2.get(m, 0))
                for m in tous_les_metiers)
    score = intersection / union if union else 0.0

    metiers_communs = sorted(poids1.keys() & poids2.keys(), key=str.casefold)
    communs = [
        {
            "metier": metier,
            "statut1": NOM_STATUT.get(statuts1[metier], statuts1[metier]),
            "statut2": NOM_STATUT.get(statuts2[metier], statuts2[metier]),
        }
        for metier in metiers_communs
    ]
    return {
        "score": score,
        "metiers1": poids1,
        "metiers2": poids2,
        "communs": communs,
    }


def comparer(graphe, nom1, nom2):
    """Recherche les deux competences puis calcule leur similarite."""
    lignes = graphe.run(
        REQUETE_OCCURRENCES,
        nom1=nom1.strip(),
        nom2=nom2.strip(),
    ).data()
    if not lignes:
        return None

    ligne = lignes[0]
    resultat = calculer_similarite(ligne["occurrences1"], ligne["occurrences2"])
    resultat["competence1"] = ligne["competence1"]
    resultat["competence2"] = ligne["competence2"]
    return resultat


def afficher(resultat):
    print(f"\nCompétence 1 : {resultat['competence1']}")
    print(f"Métiers : {len(resultat['metiers1'])}")
    print(f"Compétence 2 : {resultat['competence2']}")
    print(f"Métiers : {len(resultat['metiers2'])}")
    print(f"Similarité (Jaccard pondéré) : {resultat['score']:.1%}")
    print(f"Métiers communs : {len(resultat['communs'])}")
    for commun in resultat["communs"]:
        print(
            f"  - {commun['metier']} "
            f"(compétence 1 : {commun['statut1']} ; "
            f"compétence 2 : {commun['statut2']})"
        )


def main():
    nom1 = input("Première compétence : ").strip()
    nom2 = input("Deuxième compétence : ").strip()
    if not nom1 or not nom2:
        print("Veuillez saisir les deux compétences.")
        return

    try:
        graphe = Graph("bolt://localhost:7687", auth=("neo4j", MOT_DE_PASSE))
        resultat = comparer(graphe, nom1, nom2)
        if resultat is None:
            print("Une compétence est introuvable. Saisissez leurs noms exacts.")
        else:
            afficher(resultat)
    except Exception as erreur:
        print("Erreur de connexion ou de requête Neo4j :", erreur)


if __name__ == "__main__":
    main()
