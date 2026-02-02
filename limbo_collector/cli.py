import argparse
import sys
from pathlib import Path

from .scanner import trouver_code_mort, trouver_imports_morts, trouver_variables_mortes
from .project import LimboProject
from .config import LimboConfig


def afficher_resultats_fichier(morts, peut_etre, imports_morts, variables_morts, nom_fichier, config: LimboConfig):
    """Affiche les résultats pour un seul fichier."""
    total_problemes = len(morts) + len(imports_morts) + len(variables_morts)
    
    print("=" * 55)
    print(f"LIMBO COLLECTOR - {nom_fichier}")
    print("=" * 55)
    
    # Imports inutilisés
    if imports_morts:
        print(f"\nImports inutilisés ({len(imports_morts)}):")
        for imp in imports_morts:
            if imp.type == 'from':
                print(f"  Ligne {imp.ligne:3d} → from {imp.module_source} import {imp.nom}")
            else:
                print(f"  Ligne {imp.ligne:3d} → import {imp.nom}")
    
    # Variables inutilisées
    if variables_morts:
        print(f"\n🔧 Variables inutilisées ({len(variables_morts)}):")
        for var in variables_morts:
            print(f"  Ligne {var.ligne:3d} → '{var.nom}' dans {var.fonction_parent}()")
            if var.type_assignation == 'loop':
                print(f"         (variable de boucle jamais utilisée)")
    
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
    
    if total_problemes == 0:
        print("\nAucun code mort détecté. Fichier propre !")
    
    print("-" * 50)
    return total_problemes


def afficher_resultats_projet(projet, imports_par_fichier, variables_par_fichier, config):
    """Affiche les résultats pour un projet entier."""
    morts, peut_etre = projet.trouver_mort_global()
    total_imports = sum(len(v) for v in imports_par_fichier.values())
    total_vars = sum(len(v) for v in variables_par_fichier.values())
    total = len(morts) + total_imports + total_vars
    
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
                    ligne = f"Ligne {imp.ligne}"
                    if imp.type == 'from':
                        print(f"    {ligne:12} → from {imp.module_source} import {imp.nom}")
                    else:
                        print(f"    {ligne:12} → import {imp.nom}")
    
    # Variables
    if total_vars > 0:
        print(f"\n🔧 VARIABLES INUTILISÉES ({total_vars} total):")
        for fichier, vars_list in variables_par_fichier.items():
            if vars_list:
                print(f"\n  {fichier}:")
                for var in vars_list:
                    print(f"    Ligne {var.ligne:3d} → '{var.nom}' dans {var.fonction_parent}()")
    
    # Fonctions/Classes
    if morts:
        print(f"\nFONCTIONS SÛREMENT MORTES ({len(morts)}):")
        for obj in morts:
            print(f"  {obj.fichier}:{obj.ligne} → {obj.nom}()")
    
    if peut_etre:
        print(f"\nCLASSES PEUT-ÊTRE MORTES ({len(peut_etre)}):")
        for obj in peut_etre:
            print(f"  {obj.fichier}:{obj.ligne} → class {obj.nom}")
    
    if total == 0:
        print("\n✅ Aucun code mort détecté. Projet impeccable !")
    
    print("-" * 60)
    return total


def creer_config_exemple():
    """Crée un fichier limbo.json exemple."""
    config = LimboConfig()
    config.sauvegarder('limbo.json.example')
    print("✅ Fichier limbo.json.example créé")
    print("Renommez-le en limbo.json et modifiez-le selon vos besoins")


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
  limbo-collector . --no-variables       # Ignore les variables
  limbo-collector --init-config          # Crée un fichier config exemple
        """
    )
    parser.add_argument("chemin", nargs='?', help="Fichier .py ou dossier à analyser")
    parser.add_argument("--json", action="store_true", help="Exporte en JSON")
    parser.add_argument("--no-imports", action="store_true", help="Ignore les imports")
    parser.add_argument("--no-variables", action="store_true", help="Ignore les variables")
    parser.add_argument("--no-functions", action="store_true", help="Ignore fonctions/classes")
    parser.add_argument("--strict", action="store_true", help="Inclut les éléments incertains (classes, etc.)")
    parser.add_argument("--init-config", action="store_true", help="Crée config exemple")
    
    args = parser.parse_args()
    
    if args.init_config:
        creer_config_exemple()
        return
    
    if not args.chemin:
        parser.print_help()
        sys.exit(1)
    
    cible = Path(args.chemin)
    
    if not cible.exists():
        print(f"❌ Erreur: {cible} n'existe pas", file=sys.stderr)
        sys.exit(1)
    
    # Charge config si existe
    config = LimboConfig.depuis_fichier() if Path('limbo.json').exists() else LimboConfig()
    if args.strict:
        config.strict_mode = True
    
    try:
        if cible.is_file():
            # Mode fichier unique
            if cible.suffix != '.py':
                print(f"⚠️  Avertissement: {cible} ne semble pas être un fichier Python", file=sys.stderr)
            
            morts, peut_etre = ([], []) if args.no_functions else trouver_code_mort(str(cible))
            imports_morts = [] if args.no_imports else trouver_imports_morts(str(cible))
            variables_morts = [] if args.no_variables else trouver_variables_mortes(str(cible))
            
            if args.json:
                import json
                resultat = {
                    "mode": "fichier",
                    "fichier": str(cible),
                    "imports_inutilises": [{"nom": i.nom, "ligne": i.ligne} for i in imports_morts],
                    "variables_inutilisees": [{"nom": v.nom, "ligne": v.ligne, "fonction": v.fonction_parent} for v in variables_morts],
                    "fonctions_mortes": [{"nom": o.nom, "ligne": o.ligne} for o in morts],
                    "classes_douteuses": [{"nom": o.nom, "ligne": o.ligne} for o in peut_etre]
                }
                print(json.dumps(resultat, indent=2))
            else:
                total = afficher_resultats_fichier(morts, peut_etre, imports_morts, variables_morts, cible.name, config)
                sys.exit(1 if total > 0 else 0)
                
        else:
            # Mode projet
            print(f"Analyse du projet: {cible.absolute()}\n")
            
            projet = LimboProject(str(cible))
            projet.scanner_dossier()
            
            # Filtre les fichiers selon config
            fichiers_a_analyser = []
            for f in projet.fichiers_python:
                rel = str(f.relative_to(cible))
                if not config.doit_ignorer_fichier(rel):
                    fichiers_a_analyser.append(f)
            
            # Analyses
            imports_par_fichier = {}
            variables_par_fichier = {}
            
            if not args.no_imports:
                for fichier in fichiers_a_analyser:
                    try:
                        imports = trouver_imports_morts(str(fichier))
                        imports = [i for i in imports if not config.est_import_ignore(i.module_source)]
                        if imports:
                            rel_path = str(fichier.relative_to(cible))
                            imports_par_fichier[rel_path] = imports
                    except Exception:
                        pass
            
            if not args.no_variables:
                for fichier in fichiers_a_analyser:
                    try:
                        vars_list = trouver_variables_mortes(str(fichier))
                        vars_list = [v for v in vars_list if not config.est_variable_ignoree(v.nom)]
                        if vars_list:
                            rel_path = str(fichier.relative_to(cible))
                            variables_par_fichier[rel_path] = vars_list
                    except Exception:
                        pass
            
            if args.json:
                import json
                morts, peut_etre = projet.trouver_mort_global()
                resultat = {
                    "mode": "projet",
                    "projet": str(cible),
                    "fichiers_analyses": len(fichiers_a_analyser),
                    "imports_inutilises": {f: [{"nom": i.nom, "ligne": i.ligne} for i in imports] 
                                          for f, imports in imports_par_fichier.items()},
                    "variables_inutilisees": {f: [{"nom": v.nom, "ligne": v.ligne, "fonction": v.fonction_parent} for v in vars_list]
                                             for f, vars_list in variables_par_fichier.items()},
                    "fonctions_mortes": [{"nom": o.nom, "fichier": o.fichier, "ligne": o.ligne} for o in morts],
                    "classes_douteuses": [{"nom": o.nom, "fichier": o.fichier, "ligne": o.ligne} for o in peut_etre]
                }
                print(json.dumps(resultat, indent=2))
            else:
                total = afficher_resultats_projet(projet, imports_par_fichier, variables_par_fichier, config)
                sys.exit(1 if total > 0 else 0)
                
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()