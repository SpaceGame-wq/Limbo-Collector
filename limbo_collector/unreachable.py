import ast
from typing import List, Optional
from .models import CodeUnreachable


class DetecteurUnreachable(ast.NodeVisitor):
    def __init__(self):
        self.problemes: List[CodeUnreachable] = []
        self.scope_actuel: Optional[ast.AST] = None
        
    def analyser(self, contenu: str) -> List[CodeUnreachable]:
        try:
            arbre = ast.parse(contenu)
            self.visit(arbre)
            return self.problemes
        except SyntaxError:
            return []
    
    def visit_FunctionDef(self, node):
        self._analyser_corps(node.body, node.lineno)
        self.generic_visit(node)
    
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
    
    def _analyser_corps(self, corps: List[ast.stmt], ligne_parent: int):
        """Analyse une suite d'instructions pour détecter le code après sortie."""
        if not corps:
            return
            
        for i, instruction in enumerate(corps):
            # Vérifie si c'est une instruction de sortie
            if isinstance(instruction, (ast.Return, ast.Raise)):
                # Tout ce qui suit est unreachable
                if i + 1 < len(corps):
                    suivante = corps[i + 1]
                    derniere = corps[-1]
                    type_sortie = 'after_return' if isinstance(instruction, ast.Return) else 'after_raise'
                    nom_sortie = 'return' if isinstance(instruction, ast.Return) else 'raise'
                    
                    self.problemes.append(CodeUnreachable(
                        ligne_debut=suivante.lineno,
                        ligne_fin=self._derniere_ligne(derniere),
                        type=type_sortie,
                        description=f"Code après {nom_sortie} (ligne {instruction.lineno})"
                    ))
                break  # Stoppe l'analyse de ce bloc
            
            elif isinstance(instruction, ast.Break):
                if i + 1 < len(corps):
                    suivante = corps[i + 1]
                    derniere = corps[-1]
                    self.problemes.append(CodeUnreachable(
                        ligne_debut=suivante.lineno,
                        ligne_fin=self._derniere_ligne(derniere),
                        type='after_break',
                        description=f"Code après break (ligne {instruction.lineno})"
                    ))
                break
            
            elif isinstance(instruction, ast.Continue):
                if i + 1 < len(corps):
                    suivante = corps[i + 1]
                    derniere = corps[-1]
                    self.problemes.append(CodeUnreachable(
                        ligne_debut=suivante.lineno,
                        ligne_fin=self._derniere_ligne(derniere),
                        type='after_continue',
                        description=f"Code après continue (ligne {instruction.lineno})"
                    ))
                break
            
            elif isinstance(instruction, ast.If):
                # Récursion : analyse le if pour voir si tout son corps est unreachable
                self.visit(instruction)
    
    def _est_condition_toujours_fausse(self, node: ast.expr) -> bool:
        """Vérifie si une condition est littéralement False/0/''/None/[]/{}/()."""
        if isinstance(node, ast.Constant):
            return not bool(node.value)
        elif isinstance(node, ast.NameConstant):  # Python < 3.8
            return not node.value
        elif isinstance(node, ast.Name) and node.id == 'False':
            return True
        return False
    
    def _est_condition_toujours_vraie(self, node: ast.expr) -> bool:
        """Vérifie si une condition est littéralement True."""
        if isinstance(node, ast.Constant):
            return bool(node.value) is True
        elif isinstance(node, ast.NameConstant):  # Python < 3.8
            return node.value is True
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