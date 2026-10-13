# Fiche métier ESCO : recherche et affichage des appellations,
# compétences et connaissances obligatoires ou optionnelles.

import os

from py2neo import Graph


MOT_DE_PASSE = os.environ.get("NEO4J_PASSWORD", "azertyuiop")

REQUETE_FICHE = """
MATCH (m:Metier)
WHERE toLower(m.nom) = toLower($nom)
   OR any(appellation IN coalesce(m.appellations, [])
          WHERE toLower(appellation) = toLower($nom))
OPTIONAL MATCH (m)-[r:REQUIERT|OPTIONNEL]->(c)
WHERE c:Competence OR c:Connaissance
RETURN m.nom AS metier,
       coalesce(m.appellations, []) AS appellations,
       collect(DISTINCT {
           nom: c.nom,
           type: type(r),
           categorie: CASE
               WHEN c:Competence THEN 'competence'
               WHEN c:Connaissance THEN 'connaissance'
               ELSE null
           END
       }) AS elements
"""


def obtenir_fiche(graphe, nom):
    """Retourne la fiche du métier ou None si aucun métier ne correspond."""
    lignes = graphe.run(REQUETE_FICHE, nom=nom.strip()).data()
    if not lignes:
        return None

    ligne = lignes[0]
    fiche = {
        "metier": ligne["metier"],
        "appellations": sorted(set(ligne["appellations"] or []), key=str.casefold),
        "competences_requises": [],
        "competences_optionnelles": [],
        "connaissances_requises": [],
        "connaissances_optionnelles": [],
    }

    destinations = {
        ("competence", "REQUIERT"): "competences_requises",
        ("competence", "OPTIONNEL"): "competences_optionnelles",
        ("connaissance", "REQUIERT"): "connaissances_requises",
        ("connaissance", "OPTIONNEL"): "connaissances_optionnelles",
    }
    for element in ligne["elements"]:
        if element["nom"] is None:
            continue
        cle = destinations.get((element["categorie"], element["type"]))
        if cle:
            fiche[cle].append(element["nom"])

    for cle in destinations.values():
        fiche[cle] = sorted(set(fiche[cle]), key=str.casefold)
    return fiche


def afficher_liste(titre, valeurs):
    print(f"\n{titre} ({len(valeurs)}) :")
    if valeurs:
        for valeur in valeurs:
            print(f"  - {valeur}")
    else:
        print("  Aucune")


def afficher_fiche(fiche):
    """Affiche lisiblement une fiche retournée par obtenir_fiche."""
    print(f"\nMétier : {fiche['metier']}")
    afficher_liste("Autres appellations", fiche["appellations"])
    afficher_liste("Compétences requises", fiche["competences_requises"])
    afficher_liste("Compétences optionnelles", fiche["competences_optionnelles"])
    afficher_liste("Connaissances requises", fiche["connaissances_requises"])
    afficher_liste("Connaissances optionnelles", fiche["connaissances_optionnelles"])


def main():
    try:
        graphe = Graph("bolt://localhost:7687", auth=("neo4j", MOT_DE_PASSE))
        nom = input("Nom du métier ou autre appellation : ").strip()
        if not nom:
            print("Veuillez saisir un nom de métier.")
            return

        fiche = obtenir_fiche(graphe, nom)
        if fiche is None:
            print(f"Aucun métier trouvé pour « {nom} ».")
        else:
            afficher_fiche(fiche)
    except Exception as erreur:
        print("Erreur de connexion ou de requête Neo4j :", erreur)


if __name__ == "__main__":
    main()
