import argparse
import sys
from pathlib import Path

from .scanner import trouver_code_mort, ObjetCode
from .project import LimboProject


def afficher_resultats_fichier(morts: list, peut_etre: list, nom_fichier: str):
    """Affiche les résultats pour un seul fichier (format compact)."""
    print("=" * 50)
    print(f"LIMBO COLLECTOR - {nom_fichier}")
    print("=" * 50)
    
    if morts:
        print(f"\nFonctions sûrement mortes ({len(morts)}):")
        for obj in morts:
            print(f"  Ligne {obj.ligne:3d} → {obj.nom}()")
    
    if peut_etre:
        print(f"\nClasses peut-être mortes ({len(peut_etre)}):")
        for obj in peut_etre:
            print(f"  Ligne {obj.ligne:3d} → class {obj.nom}")
    
    if not morts and not peut_etre:
        print("\nAucun code mort détecté. Fichier propre !")
    
    print("-" * 50)


def main():
    # Configuration du parser d'arguments
    parser = argparse.ArgumentParser(
        description="Limbo Collector - Trouve le code Python oublié",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  limbo-collector mon_script.py          # Analyse un fichier
  limbo-collector ./mon_projet/          # Analyse tout un dossier
  limbo-collector . --json               # Export JSON pour CI/CD
        """
    )
    parser.add_argument(
        "chemin",
        help="Fichier .py ou dossier à analyser"
    )
    parser.add_argument(
        "--json", 
        action="store_true",
        help="Exporte les résultats en JSON"
    )
    parser.add_argument(
        "--strict",
        action="store_true", 
        help="Inclut aussi les éléments incertains (classes, etc.)"
    )
    
    args = parser.parse_args()
    cible = Path(args.chemin)
    
    if not cible.exists():
        print(f"❌ Erreur: {cible} n'existe pas", file=sys.stderr)
        sys.exit(1)
    
    try:
        if cible.is_file():
            # Mode fichier unique
            if not cible.suffix == '.py':
                print(f"⚠️  Avertissement: {cible} ne semble pas être un fichier Python", file=sys.stderr)
            
            morts, peut_etre = trouver_code_mort(str(cible))
            
            if args.json:
                import json
                resultat = {
                    "fichier": str(cible),
                    "morts": [{"nom": o.nom, "ligne": o.ligne, "type": o.type} for o in morts],
                    "peut_etre": [{"nom": o.nom, "ligne": o.ligne, "type": o.type} for o in peut_etre]
                }
                print(json.dumps(resultat, indent=2))
            else:
                afficher_resultats_fichier(morts, peut_etre, cible.name)
                
            # Code de retour pour CI/CD (1 si mort trouvé, 0 sinon)
            sys.exit(1 if morts else 0)
            
        else:
            # Mode dossier/projet
            print(f"🔍 Analyse du projet: {cible.absolute()}")
            print()
            
            projet = LimboProject(str(cible))
            projet.scanner_dossier()
            
            if args.json:
                import json
                morts, peut_etre = projet.trouver_mort_global()
                resultat = {
                    "projet": str(cible),
                    "fichiers_analyses": len(projet.fichiers_python),
                    "morts": [{"nom": o.nom, "fichier": o.fichier, "ligne": o.ligne, "type": o.type} for o in morts],
                    "peut_etre": [{"nom": o.nom, "fichier": o.fichier, "ligne": o.ligne, "type": o.type} for o in peut_etre]
                }
                print(json.dumps(resultat, indent=2))
            else:
                print(projet.rapport())
            
            morts, _ = projet.trouver_mort_global()
            sys.exit(1 if morts else 0)
            
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()