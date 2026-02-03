import ast
from pathlib import Path
from typing import List, Set, Dict
from collections import defaultdict
from .models import ImportInutile


class AnalyseurImports(ast.NodeVisitor):
    def __init__(self, contenu: str, nom_fichier: str = ""):
        self.contenu = contenu
        self.fichier = nom_fichier
        self.imports: List[ImportInutile] = []
        self.utilisations: Dict[str, Set[str]] = defaultdict(set)
        self.aliases: Dict[str, str] = {}  # alias -> vrai nom
        
    def analyser(self):
        """Trouve tous les imports et leurs utilisations."""
        try:
            arbre = ast.parse(self.contenu)
            self.visit(arbre)
            return self.trouver_inutilises()
        except SyntaxError:
            return []
    
    def visit_Import(self, node):
        """from : import os, sys"""
        for alias in node.names:
            nom = alias.asname if alias.asname else alias.name
            self.imports.append(ImportInutile(
                nom=nom,
                ligne=node.lineno,
                type='import',
                module_source=alias.name
            ))
            # Si alias, on garde la trace
            if alias.asname:
                self.aliases[alias.asname] = alias.name
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """from collections import defaultdict"""
        module = node.module or ""
        for alias in node.names:
            nom = alias.asname if alias.asname else alias.name
            self.imports.append(ImportInutile(
                nom=nom,
                ligne=node.lineno,
                type='from',
                module_source=module
            ))
            if alias.asname:
                self.aliases[alias.asname] = nom
        self.generic_visit(node)
    
    def visit_Name(self, node):
        """Détecte l'utilisation d'un nom simple"""
        self.utilisations[node.id].add('direct')
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        """Détecte os.path.join -> utilise 'os'"""
        # Remonte la chaîne d'attributs
        valeur = node.value
        noms = [node.attr]
        
        while isinstance(valeur, ast.Attribute):
            noms.append(valeur.attr)
            valeur = valeur.value
        
        if isinstance(valeur, ast.Name):
            noms.append(valeur.id)
            nom_base = valeur.id
            # os.path.join utilise 'os'
            self.utilisations[nom_base].add('.'.join(reversed(noms)))
        
        self.generic_visit(node)
    
    def trouver_inutilises(self) -> List[ImportInutile]:
        """Renvoie les imports jamais utilisés."""
        inutilises = []
        
        for imp in self.imports:
            nom_a_verifier = imp.nom
            
            # Vérifie si utilisé directement
            if nom_a_verifier in self.utilisations:
                continue
            
            # Vérifie si c'est un alias d'un nom utilisé
            if nom_a_verifier in self.aliases:
                vrai_nom = self.aliases[nom_a_verifier]
                if vrai_nom in self.utilisations:
                    continue
            
            # Exceptions : imports utilisés pour leurs effets de bord
            if self._est_import_special(imp):
                continue
            
            inutilises.append(imp)
        
        return inutilises
    
    def _est_import_special(self, imp: ImportInutile) -> bool:
        """Certains imports ont des effets de bord même non utilisés."""
        modules_effet_bord = {
            'pytest', 'unittest', 'doctest',  # Frameworks de test
            'matplotlib', 'seaborn',  # Configurations globales
            'django', 'flask', 'fastapi',  # Frameworks web
            'atexit', 'signal', 'warnings',  # Système
        }
        
        # Si c'est un sous-module de ces frameworks
        if any(imp.module_source.startswith(m) for m in modules_effet_bord):
            return True
            
        # __future__ toujours considéré comme utilisé
        if imp.module_source == '__future__':
            return True
            
        return False


def analyser_imports_fichier(chemin: str) -> List[ImportInutile]:
    """Analyse un fichier pour trouver les imports inutilisés."""
    contenu = Path(chemin).read_text(encoding='utf-8')
    analyseur = AnalyseurImports(contenu, chemin)
    return analyseur.analyser()