import ast
from typing import List, Optional, Set
from .models import CodeUnreachable


class DetecteurUnreachable(ast.NodeVisitor):
    def __init__(self):
        self.problemes: List[CodeUnreachable] = []
        self.scope_actuel: Optional[ast.AST] = None
        # Hiérarchie simplifiée pour détecter le masquage d'exceptions
        self.exceptions_parentes = {
            'Exception': ['ArithmeticError', 'AssertionError', 'AttributeError', 'BufferError', 
                         'EOFError', 'ImportError', 'LookupError', 'MemoryError', 'NameError', 
                         'OSError', 'ReferenceError', 'RuntimeError', 'SyntaxError', 
                         'SystemError', 'TypeError', 'ValueError', 'Warning'],
            'ArithmeticError': ['FloatingPointError', 'OverflowError', 'ZeroDivisionError'],
            'LookupError': ['IndexError', 'KeyError'],
            'OSError': ['FileNotFoundError', 'PermissionError', 'IsADirectoryError'],
        }
        
    def analyser(self, contenu: str) -> List[CodeUnreachable]:
        try:
            arbre = ast.parse(contenu)
            self.visit(arbre)
            return self.problemes
        except SyntaxError:
            return []
    
    def visit_FunctionDef(self, node):
        self._analyser_corps(node.body, node.lineno)
    
    def visit_AsyncFunctionDef(self, node):
        self._analyser_corps(node.body, node.lineno)
        self.generic_visit(node)
    
    def visit_For(self, node):
        self._analyser_corps(node.body, node.lineno)
        if node.orelse:
            self._analyser_corps(node.orelse, node.lineno)
        self.generic_visit(node)
    
    def visit_While(self, node):
        # Détecte while False ou while 0
        if self._est_condition_toujours_fausse(node.test):
            self.problemes.append(CodeUnreachable(
                ligne_debut=node.lineno,
                ligne_fin=self._derniere_ligne(node),
                type='while_false',
                description=f"Boucle while avec condition toujours fausse"
            ))
        else:
            self._analyser_corps(node.body, node.lineno)
        
        if node.orelse:
            self._analyser_corps(node.orelse, node.lineno)
        self.generic_visit(node)
    
    def visit_If(self, node):
        # Détecte if False ou if 0
        if self._est_condition_toujours_fausse(node.test):
            # Le corps du if est unreachable
            self.problemes.append(CodeUnreachable(
                ligne_debut=node.body[0].lineno if node.body else node.lineno,
                ligne_fin=self._derniere_ligne(node),
                type='if_false',
                description=f"Bloc if avec condition toujours fausse"
            ))
            # Mais le else est exécuté
            if node.orelse:
                self._analyser_corps(node.orelse, node.lineno)
        elif self._est_condition_toujours_vraie(node.test):
            # if True: le else est unreachable
            self._analyser_corps(node.body, node.lineno)
            if node.orelse:
                self.problemes.append(CodeUnreachable(
                    ligne_debut=node.orelse[0].lineno if node.orelse else node.lineno,
                    ligne_fin=self._derniere_ligne_liste(node.orelse),
                    type='if_false',
                    description=f"Bloc else inaccessible (condition toujours vraie)"
                ))
        else:
            self._analyser_corps(node.body, node.lineno)
            if node.orelse:
                self._analyser_corps(node.orelse, node.lineno)
        self.generic_visit(node)

    def visit_Try(self, node):
        """Analyse les blocs try/except/else/finally."""
        # 1. Corps du try
        self._analyser_corps(node.body, node.lineno)

        # 2. Détection else inatteignable (si le try finit par un return/raise)
        if self._bloc_sort_systematiquement(node.body) and node.orelse:
            self.problemes.append(CodeUnreachable(
                ligne_debut=node.orelse[0].lineno,
                ligne_fin=self._derniere_ligne_liste(node.orelse),
                type='unreachable_else',
                description="Bloc 'else' inatteignable : le bloc 'try' sort systématiquement"
            ))

        # 3. Analyse des except (Handlers)
        exceptions_vues: Set[str] = set()
        for handler in node.handlers:
            nom_ex = self._extraire_nom_exception(handler.type)
            
            # Détection de masquage (shadowing) d'exceptions
            for vue in exceptions_vues:
                if vue == 'Exception' or nom_ex in self.exceptions_parentes.get(vue, []):
                    self.problemes.append(CodeUnreachable(
                        ligne_debut=handler.lineno,
                        ligne_fin=self._derniere_ligne(handler),
                        type='shadowed_except',
                        description=f"Bloc except {nom_ex or ''} inatteignable : déjà capturé par {vue} plus haut"
                    ))
            
            if nom_ex: exceptions_vues.add(nom_ex)
            self._analyser_corps(handler.body, handler.lineno)

        # 4. Bloc finally
        if node.finalbody:
            self._analyser_corps(node.finalbody, node.lineno)
            
        self.generic_visit(node)
    
    def _analyser_corps(self, corps: List[ast.stmt], ligne_parent: int):
        """Analyse une suite d'instructions pour détecter le code après sortie."""
        if not corps:
            return
            
        for i, instruction in enumerate(corps):
            # Récursion pour les blocs imbriqués (Try, If, etc.)
            if isinstance(instruction, (ast.If, ast.Try, ast.For, ast.While)):
                self.visit(instruction)

            # Vérifie les instructions de sortie
            if isinstance(instruction, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                if i + 1 < len(corps):
                    suivante = corps[i + 1]
                    derniere = corps[-1]
                    type_nom = type(instruction).__name__.lower()
                    
                    self.problemes.append(CodeUnreachable(
                        ligne_debut=suivante.lineno,
                        ligne_fin=self._derniere_ligne(derniere),
                        type=f'after_{type_nom}',
                        description=f"Code après {type_nom} (ligne {instruction.lineno})"
                    ))
                break 

    def _extraire_nom_exception(self, type_node) -> Optional[str]:
        """Récupère le nom de l'exception dans un except."""
        if isinstance(type_node, ast.Name):
            return type_node.id
        if isinstance(type_node, ast.Attribute):
            return type_node.attr
        return None

    def _bloc_sort_systematiquement(self, corps: List[ast.stmt]) -> bool:
        """Vérifie si la dernière instruction d'un bloc est une sortie."""
        if not corps: return False
        return isinstance(corps[-1], (ast.Return, ast.Raise, ast.Break, ast.Continue))

    def _est_condition_toujours_fausse(self, node: ast.expr) -> bool:
        """Vérifie si une condition est littéralement False/0/''/None/[]/{}/()."""
        if isinstance(node, ast.Constant):
            return not bool(node.value)
        elif isinstance(node, ast.Name) and node.id == 'False':
            return True
        return False
    
    def _est_condition_toujours_vraie(self, node: ast.expr) -> bool:
        """Vérifie si une condition est littéralement True."""
        if isinstance(node, ast.Constant):
            return bool(node.value) is True
        elif isinstance(node, ast.Name) and node.id == 'True':
            return True
        return False
    
    def _derniere_ligne(self, node: ast.AST) -> int:
        """Trouve la dernière ligne d'un nœud AST."""
        derniere = getattr(node, 'lineno', 0)
        for child in ast.walk(node):
            if hasattr(child, 'lineno'):
                derniere = max(derniere, child.lineno)
        return derniere
    
    def _derniere_ligne_liste(self, nodes: List[ast.AST]) -> int:
        """Trouve la dernière ligne d'une liste de nœuds."""
        if not nodes:
            return 0
        return max(self._derniere_ligne(n) for n in nodes)


def trouver_code_unreachable(chemin_fichier: str) -> List[CodeUnreachable]:
    """Trouve le code unreachable dans un fichier."""
    from pathlib import Path
    contenu = Path(chemin_fichier).read_text(encoding='utf-8')
    detecteur = DetecteurUnreachable()
    return detecteur.analyser(contenu)