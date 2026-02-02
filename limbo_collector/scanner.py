import ast
from pathlib import Path
from dataclasses import dataclass
from typing import List, Set, Tuple
from .imports import analyser_imports_fichier, ImportInutile
from .variables import trouver_variables_inutilisees, VariableInutilisee
from .analyzer_advanced import analyser_fichier_avance, CodeEntity


@dataclass
class ObjetCode:
    nom: str
    type: str  # 'fonction' ou 'classe'
    ligne: int
    fichier: str


class ScannerLimbo(ast.NodeVisitor):
    def __init__(self, chemin_fichier: str):
        self.chemin = chemin_fichier
        self.definitions: List[ObjetCode] = []
        self.appels: Set[str] = set()
        
    def analyser(self, contenu: str = None):
        if contenu is None:
            contenu = Path(self.chemin).read_text(encoding='utf-8')
            
        arbre = ast.parse(contenu)
        
        # Ajoute les références parent à chaque nœud
        for node in ast.walk(arbre):
            for child in ast.iter_child_nodes(node):
                child.parent = node
        
        self.visit(arbre)
        return self.definitions, self.appels
    
    def visit_FunctionDef(self, node):
        if isinstance(getattr(node, 'parent', None), ast.ClassDef):
            return self.generic_visit(node)
            
        if not (node.name.startswith('__') and node.name.endswith('__')):
            self.definitions.append(ObjetCode(
                nom=node.name,
                type='fonction',
                ligne=node.lineno,
                fichier=self.chemin
            ))
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        """Quand on croise : class MaClasse:"""
        self.definitions.append(ObjetCode(
            nom=node.name,
            type='classe',
            ligne=node.lineno,
            fichier=self.chemin
        ))
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Quand on croise : une_fonction()"""
        if isinstance(node.func, ast.Name):
            self.appels.add(node.func.id)
        self.generic_visit(node)


def trouver_code_mort(chemin_fichier: str) -> Tuple[List[CodeEntity], List[CodeEntity], List[CodeEntity]]:
    """
    Analyse complète d'un fichier.
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