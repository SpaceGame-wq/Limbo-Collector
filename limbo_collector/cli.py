import argparse
import sys
from pathlib import Path

from .scanner import trouver_code_mort, trouver_imports_morts
from .project import LimboProject


def afficher_resultats_fichier(morts, peut_etre, imports_morts, nom_fichier):
    """Affiche les résultats pour un seul fichier."""
    total_problemes = len(morts) + len(imports_morts)
    
    print("=" * 55)
    print(f"LIMBO COLLECTOR - {nom_fichier}")
    print("=" * 55)
    
    # Imports inutilisés (nouveau)
    if imports_morts:
        print(f"\nImports inutilisés ({len(imports_morts)}):")
        for imp in imports_morts:
            if imp.type == 'from':
                print(f"  Ligne {imp.ligne:3d} → from {imp.module_source} import {imp.nom}")
            else:
                print(f"  Ligne {imp.ligne:3d} → import {imp.nom}")
    
    # Fonctions mortes
    if morts:
        print(f"\nFonctions sûrement mortes ({len(morts)}):")
        for obj in morts:
            print(f"  Ligne {obj.ligne:3d} → def {obj.nom}()")
    
    # Classes mortes
    if peut_etre:
        print(f"\nClasses peut-être mortes ({len(peut_etre)}):")
        for obj in peut_etre:
            print(f"  Ligne {obj.ligne:3d} → class {obj.nom}")
    
    if not morts and not peut_etre and not imports_morts:
        print("\nAucun code mort détecté. Fichier propre !")
    
    print("-" * 50)
    return total_problemes


def afficher_resultats_projet(projet, imports_par_fichier):
    """Affiche les résultats pour un projet entier."""
    morts, peut_etre = projet.trouver_mort_global()
    total_imports = sum(len(v) for v in imports_par_fichier.values())
    
    print("=" * 60)
    print("LIMBO COLLECTOR - Rapport d'analyse projet")
    print("=" * 60)
    print(f"Dossier: {projet.racine}")
    print(f"Fichiers analysés: {len(projet.fichiers_python)}")
    
    # Imports inutilisés par fichier
    if total_imports > 0:
        print(f"\nIMPORTS INUTILISÉS ({total_imports} total):")
        for fichier, imports in imports_par_fichier.items():
            if imports:
                print(f"\n  {fichier}:")
                for imp in imports:
                    if imp.type == 'from':
                        print(f"    Ligne {imp.ligne:3d}: from {imp.module_source} import {imp.nom}")
                    else:
                        print(f"    Ligne {imp.ligne:3d}: import {imp.nom}")
    
    # Code mort
    if morts:
        print(f"\nFONCTIONS SÛREMENT MORTES ({len(morts)}):")
        for obj in morts:
            print(f"  {obj.fichier}:{obj.ligne} → {obj.nom}()")
    
    if peut_etre:
        print(f"\nCLASSES PEUT-ÊTRE MORTES ({len(peut_etre)}):")
        for obj in peut_etre:
            print(f"  {obj.fichier}:{obj.ligne} → class {obj.nom}")
    
    if not morts and not peut_etre and total_imports == 0:
        print("\nAucun code mort détecté. Projet impeccable !")
    
    print("-" * 60)
    return len(morts) + total_imports


def main():
    # Configuration du parser d'arguments
    parser = argparse.ArgumentParser(
        description="Limbo Collector - Trouve le code Python oublié",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  limbo-collector script.py              # Analyse un fichier
  limbo-collector ./projet/              # Analyse un dossier
  limbo-collector . --json               # Export JSON pour CI/CD
  limbo-collector . --no-imports         # Ignore les imports inutilisés
        """
    )
    parser.add_argument("chemin", help="Fichier .py ou dossier à analyser")
    parser.add_argument("--json", action="store_true", help="Exporte en JSON")
    parser.add_argument("--no-imports", action="store_true", help="Ignore les imports")
    parser.add_argument("--strict", action="store_true", help="Inclut les éléments incertains (classes, etc.)")
    
    args = parser.parse_args()
    cible = Path(args.chemin)
    
    if not cible.exists():
        print(f"❌ Erreur: {cible} n'existe pas", file=sys.stderr)
        sys.exit(1)
    
    try:
        if cible.is_file():
            # Mode fichier unique
            if cible.suffix != '.py':
                print(f"⚠️  Avertissement: {cible} ne semble pas être un fichier Python", file=sys.stderr)
            
            morts, peut_etre = trouver_code_mort(str(cible))
            imports_morts = [] if args.no_imports else trouver_imports_morts(str(cible))
            
            if args.json:
                import json
                resultat = {
                    "mode": "fichier",
                    "fichier": str(cible),
                    "imports_inutilises": [{"nom": i.nom, "ligne": i.ligne, "type": i.type, "module": i.module_source} for i in imports_morts],
                    "fonctions_mortes": [{"nom": o.nom, "ligne": o.ligne} for o in morts],
                    "classes_douteuses": [{"nom": o.nom, "ligne": o.ligne} for o in peut_etre]
                }
                print(json.dumps(resultat, indent=2))
            else:
                total = afficher_resultats_fichier(morts, peut_etre, imports_morts, cible.name)
                sys.exit(1 if total > 0 else 0)
                
        else:
            # Mode projet
            print(f"Analyse du projet: {cible.absolute()}\n")
            
            projet = LimboProject(str(cible))
            projet.scanner_dossier()
            
            # Analyse des imports pour chaque fichier
            imports_par_fichier = {}
            if not args.no_imports:
                for fichier in projet.fichiers_python:
                    if "venv" in str(fichier) or "__pycache__" in str(fichier):
                        continue
                    try:
                        imports = trouver_imports_morts(str(fichier))
                        if imports:
                            rel_path = str(fichier.relative_to(cible))
                            imports_par_fichier[rel_path] = imports
                    except Exception:
                        pass
            
            if args.json:
                import json
                morts, peut_etre = projet.trouver_mort_global()
                resultat = {
                    "mode": "projet",
                    "projet": str(cible),
                    "fichiers_analyses": len(projet.fichiers_python),
                    "imports_inutilises": {
                        f: [{"nom": i.nom, "ligne": i.ligne, "type": i.type} for i in imports]
                        for f, imports in imports_par_fichier.items()
                    },
                    "fonctions_mortes": [{"nom": o.nom, "fichier": o.fichier, "ligne": o.ligne} for o in morts],
                    "classes_douteuses": [{"nom": o.nom, "fichier": o.fichier, "ligne": o.ligne} for o in peut_etre]
                }
                print(json.dumps(resultat, indent=2))
            else:
                total = afficher_resultats_projet(projet, imports_par_fichier)
                sys.exit(1 if total > 0 else 0)
                
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()