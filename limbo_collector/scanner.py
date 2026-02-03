from pathlib import Path
from typing import List, Tuple
from .models import CodeEntity, ImportInutile, VariableInutilisee, CodeUnreachable, ParametreInutilise
from .analyzer_advanced import analyser_fichier_avance
from .imports import analyser_imports_fichier
from .variables import trouver_variables_inutilisees
from .unreachable import trouver_code_unreachable
from .parameters import trouver_parametres_inutilises


def trouver_code_mort(chemin_fichier: str) -> Tuple[List[CodeEntity], List[CodeEntity], List[CodeEntity]]:
    """
    Analyse complète d'un fichier pour trouver fonctions et classes inutilisées.
    Retourne: (morts, probablement_morts, utilises)
    """
    return analyser_fichier_avance(chemin_fichier)


def trouver_imports_morts(chemin_fichier: str) -> List[ImportInutile]:
    """Trouve les imports inutilisés dans un fichier."""
    return analyser_imports_fichier(chemin_fichier)


def trouver_variables_mortes(chemin_fichier: str) -> List[VariableInutilisee]:
    """Trouve les variables locales inutilisées."""
    contenu = Path(chemin_fichier).read_text(encoding='utf-8')
    return trouver_variables_inutilisees(contenu)


def trouver_unreachable(chemin_fichier: str) -> List[CodeUnreachable]:
    """Trouve le code unreachable."""
    return trouver_code_unreachable(chemin_fichier)


def trouver_params_morts(chemin_fichier: str) -> List[ParametreInutilise]:
    """Trouve les paramètres inutilisés."""
    return trouver_parametres_inutilises(chemin_fichier)