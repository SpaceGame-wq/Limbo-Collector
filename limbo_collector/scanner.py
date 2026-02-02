import ast
from pathlib import Path
from dataclasses import dataclass
from typing import List, Set, Tuple
from .imports import analyser_imports_fichier, ImportInutile


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


def trouver_code_mort(chemin_fichier: str) -> Tuple[List[ObjetCode], List[ObjetCode]]:
    """Renvoie (code_surement_mort, code_peut_etre_mort)."""
    scanner = ScannerLimbo(chemin_fichier)
    definitions, appels = scanner.analyser()
    
    morts = []
    peut_etre = []
    
    for obj in definitions:
        if obj.nom in appels:
            continue  # C'est utilisé, tout va bien
            
        # Si c'est une classe, elle pourrait servir de type hint sans être appelée
        if obj.type == 'classe':
            peut_etre.append(obj)
        else:
            morts.append(obj)
            
    return morts, peut_etre


def trouver_imports_morts(chemin_fichier: str) -> List[ImportInutile]:
    """Trouve les imports inutilisés dans un fichier."""
    return analyser_imports_fichier(chemin_fichier)