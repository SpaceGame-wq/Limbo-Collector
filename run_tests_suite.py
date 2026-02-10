import subprocess
import os
import json
from pathlib import Path

# Couleurs pour la console
class Colors:
    OK = '\033[92m'
    FAIL = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def run_command(cmd_args):
    """Exécute une commande et retourne le résultat avec gestion d'encodage."""
    # Sur Windows, on appelle directement le script python si l'entrée pip ne fonctionne pas
    full_cmd = ["limbo-collector"] + cmd_args
    print(f"Exécution : {' '.join(full_cmd)}")
    
    try:
        # Utilisation de errors='replace' pour éviter de crash sur un caractère spécial
        result = subprocess.run(
            full_cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            shell=True
        )
        return result
    except Exception as e:
        print(f"Erreur système lors de l'exécution : {e}")
        return None

def check_file_exists(filepath):
    if Path(filepath).exists():
        print(f"  {Colors.OK}✅ Fichier généré : {filepath}{Colors.END}")
        return True
    else:
        print(f"  {Colors.FAIL}❌ Échec : {filepath} n'a pas été trouvé{Colors.END}")
        return False

def test_suite():
    print(f"\n{Colors.BOLD}=== DÉBUT DE LA SUITE DE TESTS COMPLÈTE ==={Colors.END}\n")

    # 1. TEST DE BASE SUR FICHIER UNIQUE
    print(f"{Colors.BOLD}--- Phase 1 : Fichier Unique ---{Colors.END}")
    
    # Test simple
    run_command(["tests/exemple_mort.py"])
    
    # Test avec tous les drapeaux actifs
    run_command(["tests/test_unreachable_argument.py", "--unreachable", "--params", "--strict"])

    # Test export JSON sur fichier
    json_file = "test_output.json"
    res = run_command(["tests/exemple_mort_avec_import.py", "--json"])
    if res and res.stdout:
        try:
            data = json.loads(res.stdout)
            print(f"  {Colors.OK}✅ JSON valide reçu pour le fichier{Colors.END}")
        except:
            print(f"  {Colors.FAIL}❌ Le format JSON du fichier est invalide{Colors.END}")

    # 2. TEST SUR PROJET COMPLET (DOSSIER)
    print(f"\n{Colors.BOLD}--- Phase 2 : Dossiers et Projets ---{Colors.END}")
    
    # Analyse de base du dossier test dynamique
    run_command(["tests/test_dynamic_imports/"])
    
    # Analyse profonde (deep) sur la hiérarchie de robots
    run_command(["tests/test_hierarchy_project/", "--deep"])

    # 3. TEST DES OPTIONS D'EXCLUSION
    print(f"\n{Colors.BOLD}--- Phase 3 : Options d'exclusion ---{Colors.END}")
    
    # Désactivation des imports et variables
    run_command(["tests/exemple_variable_import.py", "--no-imports", "--no-variables"])
    
    # Désactivation des fonctions
    run_command(["tests/test_classes.py", "--no-functions"])

    # 4. TEST DE LA GÉNÉRATION DE RAPPORTS (HTML)
    print(f"\n{Colors.BOLD}--- Phase 4 : Rapports Visuels ---{Colors.END}")
    
    # HTML pour un fichier
    html_file_1 = "rapport_fichier.html"
    if Path(html_file_1).exists(): os.remove(html_file_1)
    run_command(["tests/exemple_mort.py", "--html", html_file_1])
    check_file_exists(html_file_1)

    # HTML pour un projet
    html_file_2 = "rapport_projet.html"
    if Path(html_file_2).exists(): os.remove(html_file_2)
    run_command(["tests/test_dynamic_imports/", "--html", html_file_2])
    check_file_exists(html_file_2)

    # 5. TEST DES FONCTIONNALITÉS AVANCÉES
    print(f"\n{Colors.BOLD}--- Phase 5 : Fonctionnalités Avancées ---{Colors.END}")
    
    # Unreachable code
    res = run_command(["tests/test_unreachable_argument.py", "--unreachable"])
    if "Code unreachable" in res.stdout:
        print(f"  {Colors.OK}✅ Détection 'unreachable' confirmée{Colors.END}")

    # Paramètres inutilisés
    res = run_command(["tests/test_unreachable_argument.py", "--params"])
    if "Paramètres inutilisés" in res.stdout:
        print(f"  {Colors.OK}✅ Détection 'paramètres' confirmée{Colors.END}")

    # Doublons (Duplication)
    res = run_command(["tests/test_duplication_code.py"])
    if "Code potentiellement dupliqué" in res.stdout:
        print(f"  {Colors.OK}✅ Détection 'doublons' confirmée{Colors.END}")

    # 6. TEST DE LA CONFIGURATION
    print(f"\n{Colors.BOLD}--- Phase 6 : Configuration ---{Colors.END}")
    
    # Initialisation de la config
    config_example = "limbo.json.example"
    if Path(config_example).exists(): os.remove(config_example)
    run_command(["--init-config"])
    check_file_exists(config_example)

    # 7. TEST DU MODE RÉCURSIF (DEEP)
    print(f"\n{Colors.BOLD}--- Phase 7 : Analyse Récursive ---{Colors.END}")
    
    # Sans deep
    res_normal = run_command(["tests/test_analyse_recursive.py"])
    # Avec deep
    res_deep = run_command(["tests/test_analyse_recursive.py", "--deep"])
    
    if res_deep and "aide_isolee" in res_deep.stdout:
        print(f"  {Colors.OK}✅ Analyse récursive (Deep) opérationnelle{Colors.END}")

    # 8. TEST DES IMPORTS DYNAMIQUES (Le plus important récemment)
    print(f"\n{Colors.BOLD}--- Phase 8 : Imports Dynamiques (F-Strings) ---{Colors.END}")
    
    res = run_command(["tests/test_dynamic_imports/"])
    # On vérifie que plugins/auth.py n'est PAS dans les morts
    if "plugins\\auth.py" not in res.stdout:
        print(f"  {Colors.OK}✅ Succès : Les imports dynamiques sont protégés{Colors.END}")
    else:
        print(f"  {Colors.FAIL}❌ Échec : Les imports dynamiques ont été marqués comme morts{Colors.END}")

    print(f"\n{Colors.BOLD}=== FIN DES TESTS ==={Colors.END}")

if __name__ == "__main__":
    # Vérification que limbo-collector est installé
    try:
        subprocess.run(["limbo-collector", "--version"], capture_output=True)
    except FileNotFoundError:
        print(f"{Colors.FAIL}Erreur : 'limbo-collector' n'est pas installé ou n'est pas dans le PATH.{Colors.END}")
        print("Veuillez lancer : pip install -e .")
    else:
        test_suite()