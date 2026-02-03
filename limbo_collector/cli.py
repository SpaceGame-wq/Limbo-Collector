import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from .models import CodeEntity, ImportInutile, VariableInutilisee, CodeUnreachable, ParametreInutilise, GroupeDuplique
from .scanner import trouver_code_mort, trouver_imports_morts, trouver_variables_mortes, trouver_unreachable, trouver_params_morts
from .project_scanner import analyser_projet_complet, ResultatProjet
from .config import LimboConfig
from .analyzer_advanced import AnalyseurAvance
from collections import defaultdict


def creer_parser() -> argparse.ArgumentParser:
    """Crée et configure le parser d'arguments."""
    parser = argparse.ArgumentParser(
        prog="limbo-collector",
        description="Trouve le code Python inutilisé : imports, variables, fonctions, classes, code unreachable, paramètres et d'autes feeture a venir",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  limbo-collector mon_fichier.py
  limbo-collector mon_projet/
  limbo-collector . --strict --json
  limbo-collector . --unreachable --params
  limbo-collector --init-config
        """,
    )

    parser.add_argument(
        "chemin",
        nargs="?",
        help="Chemin du fichier ou dossier à analyser",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Affiche aussi le code probablement mort (suspects)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Exporte les résultats en format JSON",
    )

    parser.add_argument(
        "--no-imports",
        action="store_true",
        help="Ignore l'analyse des imports",
    )

    parser.add_argument(
        "--no-variables",
        action="store_true",
        help="Ignore l'analyse des variables",
    )

    parser.add_argument(
        "--no-functions",
        action="store_true",
        help="Ignore l'analyse des fonctions et classes",
    )

    parser.add_argument(
        "--init-config",
        action="store_true",
        help="Crée un fichier de configuration exemple",
    )
    parser.add_argument(
        "--unreachable",
        action="store_true",
        help="Détecte le code unreachable"
    )
    parser.add_argument(
        "--params",
        action="store_true",
        help="Détecte les paramètres inutilisés"
    )

    return parser


def valider_chemin(chemin: str) -> Optional[Path]:
    """Valide et retourne le chemin, ou None si invalide."""
    if not chemin:
        return None

    path = Path(chemin)
    if not path.exists():
        print(f"Erreur : le chemin '{chemin}' n'existe pas", file=sys.stderr)
        return None

    return path


def formater_entite(entite: CodeEntity) -> str:
    """Formate une entité code pour l'affichage."""
    if entite.type == "variable_globale":
        return entite.nom
    if entite.type == "classe":
        return f"class {entite.nom}"
    if entite.classe_parent:
        return f"{entite.classe_parent}.{entite.nom}()"
    return f"{entite.nom}()"


def afficher_section(titre: str, elements: List, formater) -> None:
    """Affiche une section de résultats si elle contient des éléments."""
    if not elements:
        return

    print(f"\n{titre} ({len(elements)}) :")

    for element in elements:
        ligne = formater(element)
        print(f"  {ligne}")


def formater_import(imp: ImportInutile) -> str:
    """Formate un import pour l'affichage."""
    if imp.type == "from":
        return f"Ligne {imp.ligne:3d} → from {imp.module_source} import {imp.nom}"
    return f"Ligne {imp.ligne:3d} → import {imp.nom}"


def formater_variable(var: VariableInutilisee) -> str:
    """Formate une variable pour l'affichage."""
    return f"Ligne {var.ligne:3d} → '{var.nom}' dans {var.fonction_parent}()"


def formater_unreachable(unreach: CodeUnreachable) -> str:
    lignes = f"{unreach.ligne_debut}-{unreach.ligne_fin}" if unreach.ligne_debut != unreach.ligne_fin else str(unreach.ligne_debut)
    return f"Lignes {lignes:7} → {unreach.description}"


def formater_parametre(param: ParametreInutilise) -> str:
    prefix = ""
    if param.est_args:
        prefix = "*"
    elif param.est_kwargs:
        prefix = "**"
    return f"Ligne {param.ligne:3d} → {prefix}{param.nom} dans {param.fonction}()"


def formater_entite_morte(entite: CodeEntity) -> str:
    """Formate une entité morte pour l'affichage."""
    symbole = "  "
    if entite.type == "classe":
        symbole = "📦 "
    elif entite.type == "variable_globale":
        symbole = "📌 "
    elif entite.type in ("staticmethod", "classmethod"):
        symbole = "🔹 "
    elif entite.type == "fonction":
        symbole = "🔸 "

    resultat = f"{symbole}Ligne {entite.ligne:3d} → {formater_entite(entite)}"

    if entite.decorateurs:
        resultat += f"\n       décorateurs : {', '.join(entite.decorateurs)}"
    
    return resultat


def formater_entite_suspecte(entite: CodeEntity) -> str:
    """Formate une entité suspecte pour l'affichage."""
    raison = ""
    if entite.nom in ("save", "delete", "clean"):
        raison = " (méthode ORM/Framework ?)"
    elif entite.type == "classe":
        raison = " (type hint possible ?)"

    return f"Ligne {entite.ligne:3d} → {formater_entite(entite)}{raison}"


def afficher_resultats_fichier(
    morts: List[CodeEntity],
    suspects: List[CodeEntity],
    imports: List[ImportInutile],
    variables: List[VariableInutilisee],
    unreachable: List[CodeUnreachable],
    params: List[ParametreInutilise],
    nom_fichier: str,
    mode_strict: bool,
) -> int:
    """Affiche résultats pour un fichier."""
    print("=" * 60)
    print(f"Limbo Collector - {nom_fichier}")
    print("=" * 60)

    afficher_section("Imports inutilisés", imports, formater_import)
    afficher_section("Variables inutilisées", variables, formater_variable)
    afficher_section("Paramètres inutilisés", params, formater_parametre)
    afficher_section("Code unreachable", unreachable, formater_unreachable)
    afficher_section("Code sûrement mort", morts, formater_entite_morte)

    if mode_strict:
        afficher_section("Code probablement mort", suspects, formater_entite_suspecte)

    total_certains = len(imports) + len(variables) + len(morts) + len(unreachable) + len(params)
    if total_certains == 0:
        print("\nAucun code mort détecté")
    elif total_certains == 0 and mode_strict:
        print(f"\n{len(suspects)} suspect(s) trouvé(s) (mode strict)")

    print("-" * 60)
    return total_certains


def exporter_json_fichier(
    morts: List[CodeEntity],
    suspects: List[CodeEntity],
    imports: List[ImportInutile],
    variables: List[VariableInutilisee],
    unreachable: List[CodeUnreachable],
    params: List[ParametreInutilise],
    chemin: str
) -> None:
    """Exporte les résultats d'un fichier en JSON."""
    resultat = {
        "mode": "fichier",
        "chemin": chemin,
        "resume": {
            "total_morts": len(morts),
            "total_suspects": len(suspects),
            "total_imports": len(imports),
            "total_variables": len(variables),
            "total_unreachable": len(unreachable),
            "total_params": len(params)
        },
        "morts": [
            {
                "nom": e.nom,
                "type": e.type,
                "ligne": e.ligne,
                "classe_parent": e.classe_parent,
                "decorateurs": e.decorateurs
            }
            for e in morts
        ],
        "suspects": [
            {
                "nom": e.nom,
                "type": e.type,
                "ligne": e.ligne,
                "classe_parent": e.classe_parent
            }
            for e in suspects
        ],
        "imports": [
            {
                "nom": i.nom,
                "ligne": i.ligne,
                "type": i.type,
                "module": i.module_source
            }
            for i in imports
        ],
        "variables": [
            {
                "nom": v.nom,
                "ligne": v.ligne,
                "fonction": v.fonction_parent,
                "type_assignation": v.type_assignation,
            }
            for v in variables
        ],
        "unreachable": [
            {
                "debut": u.ligne_debut,
                "fin": u.ligne_fin,
                "type": u.type,
                "description": u.description
            }
            for u in unreachable
        ],
        "parametres": [
            {
                "nom": p.nom,
                "ligne": p.ligne,
                "fonction": p.fonction,
                "est_args": p.est_args,
                "est_kwargs": p.est_kwargs
                }
                for p in params
            ]
    }
    print(json.dumps(resultat, indent=2, ensure_ascii=False))


def analyser_fichier(chemin: Path, args, config: LimboConfig) -> int:
    """
    Analyse un fichier unique.
    Retourne le code de sortie (0 = propre, 1 = problèmes trouvés).
    """
    if chemin.suffix != ".py":
        print(f"Avertissement : {chemin} n'est pas un fichier Python", file=sys.stderr)

    morts, suspects, _ = ([], [], []) if args.no_functions else trouver_code_mort(str(chemin))
    imports = [] if args.no_imports else trouver_imports_morts(str(chemin))
    variables = [] if args.no_variables else trouver_variables_mortes(str(chemin))
    unreachable = trouver_unreachable(str(chemin)) if args.unreachable else []
    params = trouver_params_morts(str(chemin)) if args.params else []

    contenu = chemin.read_text(encoding='utf-8')
    analyseur = AnalyseurAvance(str(chemin), contenu)
    entites, _, _, _, _, _ = analyseur.analyser()

    # Logique de détection de doublons locale
    signatures = defaultdict(list)
    for entite in entites.values():
        if entite.signature_structurelle:
            signatures[entite.signature_structurelle].append((str(chemin), entite))
    
    doublons_locaux = [
        GroupeDuplique(sig, membres) 
        for sig, membres in signatures.items() if len(membres) > 1
    ]

    if args.json:
        exporter_json_fichier(morts, suspects, imports, variables, unreachable, params, str(chemin))
    else:
        total = afficher_resultats_fichier(morts, suspects, imports, variables, unreachable, params, chemin.name, args.strict)
        if doublons_locaux:
            afficher_doublons(doublons_locaux)
        return 1 if total > 0 else 0

    return 0


def formater_entite_projet(item: Tuple[str, CodeEntity]) -> str:
    """Formate une entité de projet pour l'affichage (Dossier)."""
    chemin, entite = item
    symbole = "🔸 "
    
    if entite.type == "classe":
        symbole = "📦 "
    elif entite.type == "variable_globale":
        symbole = "📌 "
        
    return f"{symbole}{chemin}:{entite.ligne} → {formater_entite(entite)}"


def afficher_doublons(doublons: List):
    if not doublons:
        return
        
    print(f"\nCode potentiellement dupliqué ({len(doublons)} groupes) :")
    for i, groupe in enumerate(doublons, 1):
        print(f"  Groupe #{i} (Structure logique identique) :")
        for chemin, entite in groupe.entites:
            nom_complet = f"{entite.classe_parent}.{entite.nom}" if entite.classe_parent else entite.nom
            
            # On affiche la taille de la fonction pour donner une idée de l'importance
            taille = entite.signature_structurelle.count('-')
            print(f"    → {chemin}:{entite.ligne} ({nom_complet}) [Force: {taille}]")


def afficher_resultats_projet(
    resultat: ResultatProjet,
    args,
    config: LimboConfig
) -> int:
    """
    Affiche les résultats pour un projet complet.
    Retourne le nombre de problèmes certains.
    """
    print("=" * 60)
    print("Limbo Collector - Projet")
    print("=" * 60)
    print(f"Fichiers analysés : {resultat.fichiers_analyses}")

    if resultat.erreurs:
        print(f"Erreurs : {len(resultat.erreurs)}")

    # Regroupe par type
    morts = resultat.code_mort
    suspects = resultat.code_suspect

    # Compte les imports et variables
    total_imports = sum(len(v) for v in resultat.imports_morts_par_fichier.values())
    total_variables = sum(len(v) for v in resultat.variables_mortes_par_fichier.values())

    # Affichage code mort
    if not args.no_functions:
        afficher_section("Code sûrement mort (fonctions/classes)", morts, formater_entite_projet)
        if args.strict:
            afficher_section("Code probablement mort", suspects, formater_entite_projet)

    # Affichage imports
    if not args.no_imports and total_imports > 0:
        print(f"\nImports inutilisés ({total_imports}) :")
        for chemin, imports in resultat.imports_morts_par_fichier.items():
            if imports:
                print(f"  {chemin} :")
                for imp in imports:
                    print(f"    {formater_import(imp)}")

    # Affichage variables
    if not args.no_variables and total_variables > 0:
        print(f"\nVariables inutilisées ({total_variables}) :")
        for chemin, variables in resultat.variables_mortes_par_fichier.items():
            if variables:
                print(f"  {chemin} :")
                for var in variables:
                    print(f"    {formater_variable(var)}")

    total_certains = len(morts) + total_imports + total_variables
    total_suspects = len(suspects)
    if total_certains == 0:
        print("\nAucun code mort détecté")
    elif args.strict and total_certains == 0 and total_suspects != 0:
        print(f"\n{total_suspects} suspect(s) trouvé(s) (mode strict)")
    else:
        print("\nAucun code mort détecté (mode strict)")
    
    afficher_doublons(resultat.doublons)
    
    # Appel du nouveau rapport
    afficher_rapport_sante(resultat)

    print("-" * 60)
    print("")

    return total_certains


def afficher_rapport_sante(resultat: ResultatProjet):
    """Affiche un résumé statistique et un score de santé."""
    score = resultat.calculer_score_sante()
    
    # Détermination de l'appréciation
    if score >= 90: appreciation = "🌟 Excellent - Votre projet est très propre."
    elif score >= 75: appreciation = "✅ Bon - Quelques nettoyages mineurs à prévoir."
    elif score >= 50: appreciation = "⚠️ Passable - La dette technique s'accumule."
    else: appreciation = "💀 Critique - Votre projet est un cimetière de code."

    # Calcul des totaux
    total_imports = sum(len(v) for v in resultat.imports_morts_par_fichier.values())
    total_vars = sum(len(v) for v in resultat.variables_mortes_par_fichier.values())
    total_morts = len(resultat.code_mort)

    print("\n" + "="*60)
    print(f"📊 RAPPORT DE SANTÉ LIMBO : {score}/100")
    print("="*60)
    print(f"  {appreciation}")
    print("-"*60)
    print(f"  📂 Fichiers analysés     : {resultat.fichiers_analyses}")
    print(f"  📝 Lignes de code (LOC)  : {resultat.total_lignes}")
    print(f"  📦 Classes/Fonctions mortes: {total_morts}")
    print(f"  🚚 Imports inutilisés    : {total_imports}")
    print(f"  Variable(s) fantôme(s)   : {total_vars}")
    
    # Barre de progression visuelle
    barre_longueur = 30
    remplissage = int(score / 100 * barre_longueur)
    barre = "█" * remplissage + "░" * (barre_longueur - remplissage)
    print(f"\n  Score : [{barre}] {score}%")
    print("="*60 + "\n")


def exporter_json_projet(resultat: ResultatProjet, chemin: str) -> None:
    """Exporte les résultats d'un projet en JSON."""
    resultat_json = {
        "mode": "projet",
        "chemin": chemin,
        "fichiers_analyses": resultat.fichiers_analyses,
        "resume": {
            "total_morts": len(resultat.code_mort),
            "total_suspects": len(resultat.code_suspect)
        },
        "code_mort": [
            {
                "fichier": c,
                "nom": e.nom,
                "type": e.type,
                "ligne": e.ligne,
                "classe_parent": e.classe_parent,
                "raison": e.raison_utilisation
            }
            for c, e in resultat.code_mort
        ],
        "code_suspect": [
            {
                "fichier": c,
                "nom": e.nom,
                "type": e.type,
                "ligne": e.ligne
            }
            for c, e in resultat.code_suspect
        ],
        "imports_morts": {
            f: [
                {"nom": i.nom, "ligne": i.ligne, "type": i.type}
                for i in imports
            ]
            for f, imports in resultat.imports_morts_par_fichier.items()
            if imports
        },
        "variables_mortes": {
            f: [
                {
                    "nom": v.nom,
                    "ligne": v.ligne,
                    "fonction": v.fonction_parent
                }
                for v in vars_list
            ]
            for f, vars_list in resultat.variables_mortes_par_fichier.items()
            if vars_list
        }
    }

    print(json.dumps(resultat_json, indent=2, ensure_ascii=False))


def analyser_dossier(chemin: Path, args, config: LimboConfig) -> int:
    """
    Analyse un dossier complet.
    Retourne le code de sortie (0 = propre, 1 = problèmes trouvés).
    """
    resultat = analyser_projet_complet(str(chemin), config)

    if args.json:
        exporter_json_projet(resultat, str(chemin))
    else:
        total = afficher_resultats_projet(resultat, args, config)
        return 1 if total > 0 else 0

    return 0


def creer_config() -> None:
    """Crée un fichier de configuration exemple."""
    config = LimboConfig()
    config.sauvegarder("limbo.json.example")

    print("Fichier 'limbo.json.example' créé")
    print("Renommez-le en 'limbo.json' et modifiez-le selon vos besoins")


def main() -> int:
    """Point d'entrée principal."""
    parser = creer_parser()
    args = parser.parse_args()

    if args.init_config:
        creer_config()
        return 0

    if not args.chemin:
        parser.print_help()
        return 1

    chemin = valider_chemin(args.chemin)
    if chemin is None:
        return 1

    config = (
        LimboConfig.depuis_fichier()
        if Path("limbo.json").exists()
        else LimboConfig()
    )

    if args.strict:
        config.strict_mode = True

    try:
        if chemin.is_file():
            return analyser_fichier(chemin, args, config)
        else:
            return analyser_dossier(chemin, args, config)
    except Exception as erreur:
        print(f"Erreur lors de l'analyse : {erreur}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())