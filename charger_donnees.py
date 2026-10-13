# FRAYSSE Nathan 3-FI-B
# Application ESCO - question 1 : chargement du CSV dans Neo4j

import csv
import os

from py2neo import Graph

MOT_DE_PASSE = os.environ.get("NEO4J_PASSWORD", "azertyuiop")
FICHIER = "full_occupation_fr.csv"

# colonne du CSV -> (label du noeud cible, type de la relation)
COLONNES = {
    "requeredSkills": ("Competence", "REQUIERT"),
    "optionalSkills": ("Competence", "OPTIONNEL"),
    "requeredKnowledges": ("Connaissance", "REQUIERT"),
    "optionalKnowledge": ("Connaissance", "OPTIONNEL"),
}


def separer(valeur):
    # les listes sont separees par des virgules, mais certains noms en contiennent aussi
    # ("sécurité, hygiène et ..."), ces morceaux commencent par un espace : on les recolle
    if valeur is None or valeur.strip() in ("", "none"):
        return []
    elements = []
    for morceau in valeur.split(","):
        if morceau.startswith(" ") and elements:
            elements[-1] += "," + morceau
        elif morceau.strip():
            elements.append(morceau.strip())
    return [e.strip() for e in elements]


try:
    graphe = Graph("bolt://localhost:7687", auth=("neo4j", MOT_DE_PASSE))

    # on repart de zero
    for label in ["Metier", "Competence", "Connaissance"]:
        graphe.run("MATCH (n:" + label + ") DETACH DELETE n")

    # contraintes d'unicite (le code ESCO n'est pas unique : c'est un code de groupe ISCO)
    graphe.run("CREATE CONSTRAINT metier_unique IF NOT EXISTS FOR (m:Metier) REQUIRE m.nom IS UNIQUE")
    graphe.run("CREATE CONSTRAINT competence_unique IF NOT EXISTS FOR (c:Competence) REQUIRE c.nom IS UNIQUE")
    graphe.run("CREATE CONSTRAINT connaissance_unique IF NOT EXISTS FOR (c:Connaissance) REQUIRE c.nom IS UNIQUE")

    def envoyer(requete, lignes):
        for i in range(0, len(lignes), 1000):
            graphe.run(requete, lignes=lignes[i:i + 1000])

    # lecture du fichier en memoire
    metiers = {}
    with open(FICHIER, encoding="utf-8", newline="") as f:
        for ligne in csv.DictReader(f):
            nom = ligne["occupation"].strip()
            # un metier apparait deux fois dans le fichier : on fusionne ses listes
            if nom not in metiers:
                metiers[nom] = {"nom": nom, "code": ligne["code"], "appellations": set(),
                                "liens": {c: set() for c in COLONNES}}
            metiers[nom]["appellations"].update(separer(ligne["alt"]))
            for colonne in COLONNES:
                metiers[nom]["liens"][colonne].update(separer(ligne[colonne]))

    # noeuds Metier (les appellations sont une propriete de type liste)
    envoyer("UNWIND $lignes AS l MERGE (m:Metier {nom: l.nom}) "
            "SET m.code = l.code, m.appellations = l.appellations",
            [{"nom": m["nom"], "code": m["code"], "appellations": sorted(m["appellations"])}
             for m in metiers.values()])

    # noeuds Competence / Connaissance et relations REQUIERT / OPTIONNEL
    for colonne, (label, relation) in COLONNES.items():
        lignes = [{"metier": m["nom"], "nom": nom}
                  for m in metiers.values() for nom in sorted(m["liens"][colonne])]
        envoyer("UNWIND $lignes AS l MERGE (c:" + label + " {nom: l.nom})", lignes)
        envoyer("UNWIND $lignes AS l MATCH (m:Metier {nom: l.metier}), (c:" + label + " {nom: l.nom}) "
                "MERGE (m)-[:" + relation + "]->(c)", lignes)

    print("Chargement termine")
    for label in ["Metier", "Competence", "Connaissance"]:
        total = graphe.run("MATCH (n:" + label + ") RETURN count(n) AS total").data()[0]["total"]
        print(label, ":", total)
    for relation in ["REQUIERT", "OPTIONNEL"]:
        total = graphe.run("MATCH ()-[r:" + relation + "]->() RETURN count(r) AS total").data()[0]["total"]
        print(relation, ":", total)

except Exception as e:
    print("Erreur :", e)
