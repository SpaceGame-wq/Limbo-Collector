import ast
from typing import List, Dict
from .models import VariableInutilisee


class AnalyseurVariables(ast.NodeVisitor):
    def __init__(self):
        self.problemes: List[VariableInutilisee] = []
        self.fonction_actuelle = None
        self.variables_par_scope: List[Dict[str, dict]] = []
        
    def analyser(self, contenu: str) -> List[VariableInutilisee]:
        try:
            arbre = ast.parse(contenu)
            self.visit(arbre)
            return self.problemes
        except SyntaxError:
            return []
    
    def visit_FunctionDef(self, node):
        ancienne_fonction = self.fonction_actuelle
        ancien_scope = self.variables_par_scope
        
        self.fonction_actuelle = node.name
        self.variables_par_scope = [{}]  # Nouveau scope pour cette fonction
        
        self.generic_visit(node)
        
        # Vérifie les variables non utilisées dans cette fonction
        self._verifier_scope_utilisation()
        
        self.fonction_actuelle = ancienne_fonction
        self.variables_par_scope = ancien_scope
    
    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)  # Même traitement
    
    def visit_Lambda(self, node):
        # On ignore les lambdas complexes pour l'instant
        pass
    
    def visit_Assign(self, node):
        if not self.fonction_actuelle:
            return  # Variables globales, on ignore pour l'instant
            
        for target in node.targets:
            self._enregistrer_assignation(target, 'simple')
        self.generic_visit(node)
    
    def visit_For(self, node):
        if not self.fonction_actuelle:
            self.generic_visit(node)
            return
            
        # Variable de boucle : for i in range(10)
        self._enregistrer_assignation(node.target, 'loop')
        self.generic_visit(node)
    
    def visit_With(self, node):
        if not self.fonction_actuelle:
            self.generic_visit(node)
            return
            
        for item in node.items:
            if item.optional_vars:
                self._enregistrer_assignation(item.optional_vars, 'with')
        self.generic_visit(node)
    
    def visit_ExceptHandler(self, node):
        if not self.fonction_actuelle:
            self.generic_visit(node)
            return
            
        if node.name:
            self._enregistrer_assignation(ast.Name(id=node.name, ctx=ast.Store()), 'except')
        self.generic_visit(node)
    
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and self.variables_par_scope:
            # Variable lue : on la marque comme utilisée
            nom = node.id
            for scope in reversed(self.variables_par_scope):
                if nom in scope:
                    scope[nom]['utilisee'] = True
                    break
        self.generic_visit(node)
    
    def _enregistrer_assignation(self, target, type_assign: str):
        """Enregistre une variable assignée dans le scope actuel."""
        if isinstance(target, ast.Name):
            # x = 5
            if isinstance(target.ctx, ast.Store):
                self.variables_par_scope[-1][target.id] = {
                    'ligne': target.lineno,
                    'type': type_assign,
                    'utilisee': False
                }
                
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
            # a, b = 1, 2  (unpacking)
            for elt in target.elts:
                self._enregistrer_assignation(elt, 'unpack')
    
    def _verifier_scope_utilisation(self):
        """Vérifie quelles variables n'ont jamais été lues."""
        for nom, info in self.variables_par_scope[-1].items():
            if not info['utilisee']:
                # Ignore les conventions _ et __
                if nom.startswith('_'):
                    continue
                    
                self.problemes.append(VariableInutilisee(
                    nom=nom,
                    ligne=info['ligne'],
                    fonction_parent=self.fonction_actuelle,
                    type_assignation=info['type']
                ))


def trouver_variables_inutilisees(contenu: str) -> List[VariableInutilisee]:
    """Trouve les variables locales assignées mais jamais lues."""
    analyseur = AnalyseurVariables()
    return analyseur.analyser(contenu)