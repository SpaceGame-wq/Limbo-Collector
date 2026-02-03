import ast
from typing import List, Set
from .models import ParametreInutilise


class DetecteurParametres(ast.NodeVisitor):
    def __init__(self):
        self.problemes: List[ParametreInutilise] = []
        self.noms_self_cls: Set[str] = {'self', 'cls', 'klass'}
        
    def analyser(self, contenu: str) -> List[ParametreInutilise]:
        try:
            arbre = ast.parse(contenu)
            self.visit(arbre)
            return self.problemes
        except SyntaxError:
            return []
    
    def visit_FunctionDef(self, node):
        self._analyser_fonction(node)
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        self._analyser_fonction(node)
        self.generic_visit(node)
    
    def _analyser_fonction(self, node):
        """Analyse les paramètres d'une fonction."""
        noms_params = []
        params_info = {}  # nom -> info
        
        # Args positionnels
        for i, arg in enumerate(node.args.args):
            nom = arg.arg
            # Ignore self/cls des méthodes
            if i == 0 and nom in self.noms_self_cls:
                continue
            noms_params.append(nom)
            params_info[nom] = {
                'ligne': node.lineno,
                'position': i,
                'est_args': False,
                'est_kwargs': False
            }
        
        # *args
        if node.args.vararg:
            nom = node.args.vararg.arg
            noms_params.append(nom)
            params_info[nom] = {
                'ligne': node.lineno,
                'position': len(noms_params) - 1,
                'est_args': True,
                'est_kwargs': False
            }
        
        # Args avec valeur par défaut (sont après les args sans défaut)
        # Déjà inclus dans node.args.args
        
        # **kwargs
        if node.args.kwarg:
            nom = node.args.kwarg.arg
            noms_params.append(nom)
            params_info[nom] = {
                'ligne': node.lineno,
                'position': len(noms_params) - 1,
                'est_args': False,
                'est_kwargs': True
            }
        
        if not noms_params:
            return
        
        # Trouve les noms utilisés dans le corps de la fonction
        noms_utilises = self._trouver_noms_utilises(node.body)
        
        # Détecte les paramètres non utilisés
        for nom in noms_params:
            if nom not in noms_utilises:
                info = params_info[nom]
                self.problemes.append(ParametreInutilise(
                    nom=nom,
                    ligne=info['ligne'],
                    fonction=node.name,
                    position=info['position'],
                    est_args=info['est_args'],
                    est_kwargs=info['est_kwargs']
                ))
    
    def _trouver_noms_utilises(self, corps: List[ast.stmt]) -> Set[str]:
        """Trouve tous les noms utilisés dans un bloc de code."""
        noms = set()
        
        for node in ast.walk(ast.Module(body=corps, type_ignores=[])):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                noms.add(node.id)
            elif isinstance(node, ast.Attribute):
                # Si on fait obj.attr, obj est utilisé
                if isinstance(node.value, ast.Name):
                    noms.add(node.value.id)
        
        return noms


def trouver_parametres_inutilises(chemin_fichier: str) -> List[ParametreInutilise]:
    """Trouve les paramètres inutilisés dans un fichier."""
    from pathlib import Path
    contenu = Path(chemin_fichier).read_text(encoding='utf-8')
    detecteur = DetecteurParametres()
    return detecteur.analyser(contenu)