import ast
from typing import List, Optional, Set
from .models import CodeUnreachable


class DetecteurUnreachable(ast.NodeVisitor):
    def __init__(self):
        self.problemes: List[CodeUnreachable] = []
        # Fonctions qui interrompent définitivement l'exécution
        self.fonctions_terminatrices = {'exit', 'quit', 'sys.exit', 'os._exit', 'os.abort'}
        
        # Hiérarchie pour détecter le masquage d'exceptions
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

    def visit_For(self, node):
        self._analyser_corps(node.body, node.lineno)
        if node.orelse:
            self._analyser_corps(node.orelse, node.lineno)
    
    def visit_While(self, node):
        if self._est_condition_toujours_fausse(node.test):
            self.problemes.append(CodeUnreachable(
                ligne_debut=node.lineno,
                ligne_fin=self._derniere_ligne(node),
                type='while_false',
                description="Boucle while avec condition toujours fausse"
            ))
        else:
            self._analyser_corps(node.body, node.lineno)
        
        if node.orelse:
            self._analyser_corps(node.orelse, node.lineno)
    
    def visit_If(self, node):
        # Détecte if False ou if 0
        if self._est_condition_toujours_fausse(node.test):
            debut = node.body[0].lineno if node.body else node.lineno
            self.problemes.append(CodeUnreachable(
                ligne_debut=debut,
                ligne_fin=self._derniere_ligne_liste(node.body) if node.body else node.lineno,
                type='if_false',
                description="Bloc if avec condition toujours fausse"
            ))
            if node.orelse:
                self._analyser_corps(node.orelse, node.lineno)
        elif self._est_condition_toujours_vraie(node.test):
            # if True: le else est unreachable
            self._analyser_corps(node.body, node.lineno)
            if node.orelse:
                self.problemes.append(CodeUnreachable(
                    ligne_debut=node.orelse[0].lineno,
                    ligne_fin=self._derniere_ligne_liste(node.orelse),
                    type='if_true_else_dead',
                    description="Bloc else inaccessible (condition toujours vraie)"
                ))
        else:
            self._analyser_corps(node.body, node.lineno)
            if node.orelse:
                self._analyser_corps(node.orelse, node.lineno)

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
                        description=f"Bloc except {nom_ex or ''} inatteignable : masqué par {vue} plus haut"
                    ))
            
            if nom_ex: exceptions_vues.add(nom_ex)
            self._analyser_corps(handler.body, handler.lineno)

        # 4. Bloc finally
        if node.finalbody:
            self._analyser_corps(node.finalbody, node.lineno)

    def visit_Match(self, node):
        """Support pour Python 3.10+ match-case."""
        wildcard_trouve = False
        for case in node.cases:
            if wildcard_trouve:
                self.problemes.append(CodeUnreachable(
                    ligne_debut=case.pattern.lineno,
                    ligne_fin=self._derniere_ligne(case),
                    type='shadowed_case',
                    description="Case inatteignable : déjà capturé par un pattern universel (_ ou variable)"
                ))
            
            if self._est_pattern_universel(case.pattern):
                wildcard_trouve = True
            
            if case.guard and self._est_condition_toujours_fausse(case.guard):
                self.problemes.append(CodeUnreachable(
                    ligne_debut=case.body[0].lineno if case.body else case.pattern.lineno,
                    ligne_fin=self._derniere_ligne_liste(case.body),
                    type='match_guard_false',
                    description="Corps du case inatteignable (garde toujours fausse)"
                ))
            else:
                self._analyser_corps(case.body, case.pattern.lineno)

    def _analyser_corps(self, corps: List[ast.stmt], ligne_parent: int):
        """Analyse une suite d'instructions pour détecter le code après sortie."""
        if not corps:
            return
            
        for i, instruction in enumerate(corps):
            # Récursion pour les blocs imbriqués (Try, If, etc.)
            self.visit(instruction)

            if self._est_une_sortie_definitive(instruction):
                if i + 1 < len(corps):
                    suivante = corps[i + 1]
                    derniere = corps[-1]
                    self.problemes.append(CodeUnreachable(
                        ligne_debut=suivante.lineno,
                        ligne_fin=self._derniere_ligne(derniere),
                        type='after_exit',
                        description=f"Code inatteignable après une sortie définitive (ligne {instruction.lineno})"
                    ))
                break 

    def _est_une_sortie_definitive(self, node) -> bool:
        """Vérifie si l'instruction coupe le flux (return, raise, break, continue, sys.exit)."""
        if isinstance(node, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return True
        
        # Détection des appels terminaux (sys.exit, etc.)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            nom_func = ""
            if isinstance(func, ast.Name):
                nom_func = func.id
            elif isinstance(func, ast.Attribute):
                if isinstance(func.value, ast.Name):
                    nom_func = f"{func.value.id}.{func.attr}"
                else:
                    nom_func = func.attr
            
            if nom_func in self.fonctions_terminatrices:
                return True
        return False

    def _est_pattern_universel(self, pattern) -> bool:
        # case _: ou case x:
        return isinstance(pattern, ast.MatchAs)

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
        return self._est_une_sortie_definitive(corps[-1])

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
        if isinstance(node, ast.Name) and node.id == 'True':
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