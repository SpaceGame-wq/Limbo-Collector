import ast
import builtins
import copy
from typing import List, Optional, Set, Any, Dict, Union, Tuple, Callable
from .models import CodeUnreachable

# ==============================================================================
# CONSTANTES ET TYPES
# ==============================================================================

class UnknownValue:
    """Représente une valeur impossible à déterminer statiquement."""
    def __repr__(self): return "<UNKNOWN>"
    def __bool__(self): raise TypeError("Cannot bool() an UnknownValue")
    def __eq__(self, other): return isinstance(other, UnknownValue)

UNKNOWN = UnknownValue()
StateDict = Dict[str, Any]

# ==============================================================================
# CLASSE PRINCIPALE : MOTEUR D'ANALYSE
# ==============================================================================

class DetecteurUnreachable(ast.NodeVisitor):
    def __init__(self):
        self.problemes: List[CodeUnreachable] = []
        self.lignes_signalees: Set[int] = set() # Empêche les rapports multiples
        
        # Pile de scopes pour la mémoire des variables
        # Chaque élément est un dictionnaire {nom_variable: valeur}
        self.scopes: List[StateDict] = [{}] 
        
        # Fonctions qui arrêtent le programme
        self.fonctions_terminatrices = {
            'exit', 'quit', 'sys.exit', 'os._exit', 'os.abort', 'pytest.exit'
        }
        
        # Mapping des fonctions built-in pures (sans effets de bord majeurs)
        # que nous pouvons exécuter sans risque pendant l'analyse
        self.pure_builtins = {
            'len': len, 'str': str, 'int': int, 'float': float, 
            'bool': bool, 'list': list, 'tuple': tuple, 'set': set, 'dict': dict,
            'abs': abs, 'min': min, 'max': max, 'sum': sum, 'ord': ord, 'chr': chr,
            'sorted': sorted, 'reversed': reversed, 'range': range,
            'all': all, 'any': any, 'bin': bin, 'hex': hex, 'oct': oct
        }

        # Mapping pour l'évaluation de isinstance()
        self.type_mapping = {
            'str': str, 'int': int, 'float': float, 'bool': bool, 
            'list': list, 'dict': dict, 'tuple': tuple, 'set': set, 
            'None': type(None), 'object': object
        }

        # Hiérarchie pour détecter le masquage d'exceptions (Shadowing)
        self.exceptions_parentes = {
            'Exception': ['ArithmeticError', 'AssertionError', 'AttributeError', 'BufferError', 
                         'EOFError', 'ImportError', 'LookupError', 'MemoryError', 'NameError', 
                         'OSError', 'ReferenceError', 'RuntimeError', 'SyntaxError', 
                         'SystemError', 'TypeError', 'ValueError', 'Warning'],
            'ArithmeticError': ['FloatingPointError', 'OverflowError', 'ZeroDivisionError'],
            'LookupError': ['IndexError', 'KeyError'],
            'OSError': ['FileNotFoundError', 'PermissionError', 'IsADirectoryError', 
                        'TimeoutError', 'ConnectionError']
        }

        # Flags temporaires pour la communication entre visiteurs
        self.force_exit_detection = False

    def analyser(self, contenu: str) -> List[CodeUnreachable]:
        """Point d'entrée de l'analyse."""
        try:
            arbre = ast.parse(contenu)
            self.visit(arbre)
            return self.problemes
        except SyntaxError:
            return []

    # ==========================================================================
    # GESTION DE LA MÉMOIRE ET DES ÉTATS (STATE MANAGEMENT)
    # ==========================================================================

    @property
    def current_scope(self) -> StateDict:
        """Retourne le scope local actuel."""
        return self.scopes[-1]

    def _set_var(self, name: str, value: Any):
        """Enregistre une variable dans le scope actuel."""
        # On ne stocke pas les valeurs trop complexes ou infinies (iterateurs)
        if hasattr(value, '__next__'): 
            value = UNKNOWN
        self.current_scope[name] = value

    def _get_var(self, name: str) -> Any:
        """Récupère une variable en remontant la pile des scopes."""
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return UNKNOWN

    def _push_scope(self):
        """Entre dans un nouveau bloc (fonction)."""
        self.scopes.append({})

    def _pop_scope(self):
        """Sort d'un bloc."""
        if len(self.scopes) > 1:
            self.scopes.pop()

    def _merge_states(self, state1: StateDict, state2: StateDict) -> StateDict:
        """
        Fusionne deux états de mémoire (ex: après un if/else).
        Si une variable a la même valeur dans les deux branches, elle est conservée.
        Sinon, elle devient UNKNOWN.
        """
        merged = {}
        all_keys = set(state1.keys()) | set(state2.keys())
        
        for k in all_keys:
            val1 = state1.get(k, UNKNOWN)
            val2 = state2.get(k, UNKNOWN)
            
            # On ne fusionne pas les structures mutables complexes pour éviter 
            # les erreurs de référence, sauf si elles sont identiques par valeur
            if val1 is not UNKNOWN and val2 is not UNKNOWN and val1 == val2:
                 # Limitation, on évite de propager des listes géantes
                if isinstance(val1, (list, dict, set, tuple)) and len(val1) > 50:
                    merged[k] = UNKNOWN
                else:
                    merged[k] = val1
            else:
                merged[k] = UNKNOWN
        return merged

    # ==========================================================================
    # MOTEUR D'ÉVALUATION (INTERPRÉTEUR ABSTRAIT)
    # ==========================================================================

    def _eval(self, node: ast.AST) -> Any:
        """
        Tente d'évaluer statiquement une expression AST.
        Retourne la valeur Python réelle ou UNKNOWN.
        """
        if node is None: return UNKNOWN

        # 1. Constantes (Littéraux)
        if isinstance(node, ast.Constant):
            return node.value

        # 2. Variables (Lookup)
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                val = self._get_var(node.id)
                # Gestion spéciale pour True/False/None en Python < 3.8
                if val is UNKNOWN:
                    if node.id == 'True': return True
                    if node.id == 'False': return False
                    if node.id == 'None': return None
                return val

        # 3. Structures de données (Construction)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            elts = [self._eval(e) for e in node.elts]
            # Si un seul élément est inconnu, la structure entière est compromise pour l'analyse stricte
            if any(e is UNKNOWN for e in elts): return UNKNOWN
            if isinstance(node, ast.List): return list(elts)
            if isinstance(node, ast.Tuple): return tuple(elts)
            if isinstance(node, ast.Set): 
                try: return set(elts) # Peut échouer si éléments non hashables
                except: return UNKNOWN
        
        if isinstance(node, ast.Dict):
            keys = [self._eval(k) for k in node.keys]
            vals = [self._eval(v) for v in node.values]
            if any(k is UNKNOWN for k in keys) or any(v is UNKNOWN for v in vals): return UNKNOWN
            try: return dict(zip(keys, vals))
            except: return UNKNOWN

        # 4. Opérations Unaires (not, -, +)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval(node.operand)
            if operand is UNKNOWN: return UNKNOWN
            try:
                if isinstance(node.op, ast.Not): return not operand
                if isinstance(node.op, ast.USub): return -operand
                if isinstance(node.op, ast.UAdd): return +operand
                if isinstance(node.op, ast.Invert): return ~operand
            except: return UNKNOWN

        # 5. Opérations Binaires (Maths)
        if isinstance(node, ast.BinOp):
            l = self._eval(node.left)
            r = self._eval(node.right)
            if l is UNKNOWN or r is UNKNOWN: return UNKNOWN
            try:
                op_type = type(node.op)
                if op_type == ast.Add: return l + r
                if op_type == ast.Sub: return l - r
                if op_type == ast.Mult: return l * r
                if op_type == ast.Div: return l / r
                if op_type == ast.FloorDiv: return l // r
                if op_type == ast.Mod: return l % r
                if op_type == ast.Pow: return l ** r
                if op_type == ast.BitAnd: return l & r
                if op_type == ast.BitOr: return l | r
                if op_type == ast.BitXor: return l ^ r
            except: return UNKNOWN

        # 6. Opérations Booléennes (and, or)
        if isinstance(node, ast.BoolOp):
            vals = [self._eval(v) for v in node.values]
            if isinstance(node.op, ast.And):
                # Short-circuit, si un seul False est trouvé, le résultat est False
                if any(v is False for v in vals): return False
                if any(v is UNKNOWN for v in vals): return UNKNOWN
                return vals[-1] # Retourne le dernier si tout est True
            if isinstance(node.op, ast.Or):
                # Short-circuit, si un seul True est trouvé
                for v in vals:
                    if v is UNKNOWN: return UNKNOWN # On ne peut pas être sûr
                    if v: return v
                return vals[-1]

        # 7. Comparaisons
        if isinstance(node, ast.Compare):
            left = self._eval(node.left)
            if left is UNKNOWN: return UNKNOWN
            # Simplification: on gère principalement les comparaisons simples (a == b)
            # Les chaînes (a < b < c) sont complexes à évaluer récursivement ici
            right = self._eval(node.comparators[0])
            if right is UNKNOWN: return UNKNOWN
            
            op_type = type(node.ops[0])
            try:
                if op_type == ast.Eq: return left == right
                if op_type == ast.NotEq: return left != right
                if op_type == ast.Lt: return left < right
                if op_type == ast.LtE: return left <= right
                if op_type == ast.Gt: return left > right
                if op_type == ast.GtE: return left >= right
                if op_type == ast.Is: return left is right
                if op_type == ast.IsNot: return left is not right
                if op_type == ast.In: return left in right
                if op_type == ast.NotIn: return left not in right
            except: return UNKNOWN

        # 8. Subscript (Index et Slices) : l[0], d['key']
        if isinstance(node, ast.Subscript):
            val = self._eval(node.value)
            idx = self._eval(node.slice)
            if val is UNKNOWN or idx is UNKNOWN: return UNKNOWN
            try: return val[idx]
            except: return UNKNOWN

        # 9. Appels de fonctions (Built-ins purs et isinstance)
        if isinstance(node, ast.Call):
            # Gestion isinstance(obj, type)
            if isinstance(node.func, ast.Name) and node.func.id == 'isinstance':
                if len(node.args) == 2:
                    obj = self._eval(node.args[0])
                    typ_node = node.args[1]
                    if obj is not UNKNOWN:
                        # On tente de résoudre le type Python
                        py_type = None
                        if isinstance(typ_node, ast.Name):
                            py_type = self.type_mapping.get(typ_node.id)
                        elif isinstance(typ_node, (ast.Tuple, ast.List)):
                            # isinstance(x, (int, float))
                            types = []
                            for t in typ_node.elts:
                                if isinstance(t, ast.Name):
                                    pt = self.type_mapping.get(t.id)
                                    if pt: types.append(pt)
                            if types: py_type = tuple(types)
                        
                        if py_type:
                            return isinstance(obj, py_type)

            # Autres built-ins
            if isinstance(node.func, ast.Name) and node.func.id in self.pure_builtins:
                args = [self._eval(a) for a in node.args]
                if all(a is not UNKNOWN for a in args):
                    try:
                        func = self.pure_builtins[node.func.id]
                        return func(*args)
                    except: return UNKNOWN

        return UNKNOWN

    # ==========================================================================
    # VISITEURS DE FLUX DE CONTRÔLE (LOGIQUE PRINCIPALE)
    # ==========================================================================

    def visit_Assign(self, node):
        """Met à jour l'état des variables."""
        valeur = self._eval(node.value)
        
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._set_var(target.id, valeur)
            elif isinstance(target, (ast.Tuple, ast.List)):
                # Gestion du unpacking: a, b = [1, 2]
                if isinstance(valeur, (list, tuple)) and len(valeur) == len(target.elts):
                    for i, elt in enumerate(target.elts):
                        if isinstance(elt, ast.Name):
                            self._set_var(elt.id, valeur[i])
                else:
                    # Si on ne peut pas unpacker proprement, on invalide tout
                    for elt in target.elts:
                        if isinstance(elt, ast.Name): self._set_var(elt.id, UNKNOWN)
            # Support basic target.attr = val (on ignore l'effet de bord sur l'objet pour l'instant)

    def visit_AugAssign(self, node):
        """Gère +=, -=, etc."""
        if isinstance(node.target, ast.Name):
            current_val = self._get_var(node.target.id)
            operand = self._eval(node.value)
            
            new_val = UNKNOWN
            if current_val is not UNKNOWN and operand is not UNKNOWN:
                try:
                    op_type = type(node.op)
                    
                    # --- Opérateurs Arithmétiques ---
                    if op_type == ast.Add:        new_val = current_val + operand
                    elif op_type == ast.Sub:      new_val = current_val - operand
                    elif op_type == ast.Mult:     new_val = current_val * operand
                    elif op_type == ast.Div:      new_val = current_val / operand
                    elif op_type == ast.FloorDiv: new_val = current_val // operand
                    elif op_type == ast.Mod:      new_val = current_val % operand
                    elif op_type == ast.Pow:      new_val = current_val ** operand
                    
                    # --- Opérateurs Bit à Bit (Bitwise) ---
                    elif op_type == ast.BitAnd:   new_val = current_val & operand
                    elif op_type == ast.BitOr:    new_val = current_val | operand
                    elif op_type == ast.BitXor:   new_val = current_val ^ operand
                    elif op_type == ast.LShift:   new_val = current_val << operand
                    elif op_type == ast.RShift:   new_val = current_val >> operand
                    
                    # --- Opérateur Matrice (Python 3.5+) ---
                    elif op_type == ast.MatMult:  new_val = current_val @ operand
                except: pass
            
            self._set_var(node.target.id, new_val)

    def visit_Assert(self, node):
        """
        Gère les assertions. 
        Si assert False, le code suivant est mort.
        """
        test = self._eval(node.test)
        if test is False:
            self.force_exit_detection = True # Le flux est coupé ici
            # On pourrait aussi raffiner l'état si l'assert est True (ex: assert isinstance(x, int))
            # ceci est complexe, on l'implémentera plus tard

    def visit_If(self, node):
        """Gère les branchements conditionnels."""
        condition = self._eval(node.test)

        # 1. Condition VRAIE statiquement
        if condition is True:
            self._analyser_block(node.body)
            if node.orelse:
                self._marquer_mort(node.orelse, "ELSE inatteignable (IF toujours vrai)")
            return

        # 2. Condition FAUSSE statiquement
        if condition is False:
            self._marquer_mort(node.body, "IF inatteignable (condition fausse)")
            if node.orelse:
                self._analyser_block(node.orelse)
            return

        # 3. Condition INCONNUE (Branching)
        # On doit simuler les deux mondes parallèles
        state_before = self.current_scope.copy()
        
        # Branche IF
        self._analyser_block(node.body)
        state_after_if = self.current_scope.copy()
        
        # Reset pour branche ELSE
        self.scopes[-1] = state_before.copy()
        
        # Branche ELSE
        if node.orelse:
            self._analyser_block(node.orelse)
        state_after_else = self.current_scope.copy()
        
        # FUSION DES ÉTATS
        self.scopes[-1] = self._merge_states(state_after_if, state_after_else)

    def visit_While(self, node):
        """Gère les boucles While."""
        condition = self._eval(node.test)

        # Cas 1 : While False -> Mort
        if condition is False:
            self._marquer_mort(node.body, "WHILE inatteignable (False)")
            if node.orelse: self._analyser_block(node.orelse)
            return

        # Cas 2 : While True (Boucle potentiellement infinie)
        if condition is True:
            # On vérifie s'il y a un break statique accessible
            has_break = self._contient_break_accessible(node.body)
            
            # Si pas de break -> Boucle Infinie
            if not has_break:
                # On invalide les vars modifiées au cas où (pour l'analyse interne)
                modified = self._get_modified_vars(node.body)
                for v in modified: self._set_var(v, UNKNOWN)
                
                self._analyser_block(node.body)
                
                self.force_exit_detection = True # Tout ce qui suit la boucle est mort
                if node.orelse:
                    self._marquer_mort(node.orelse, "ELSE inatteignable (boucle infinie)")
                return

        # Cas 3 : While Unknown ou Normal
        # On doit invalider toutes les variables modifiées dans la boucle
        # car on ne sait pas combien de fois elle s'exécute
        modified_vars = self._get_modified_vars(node.body)
        for var in modified_vars:
            self._set_var(var, UNKNOWN)
            
        self._analyser_block(node.body)
        if node.orelse: self._analyser_block(node.orelse)

    def visit_For(self, node):
        """Gère les boucles For avec déroulement (Loop Unrolling)."""
        iterateur = self._eval(node.iter)
        
        # LOOP UNROLLING : Si on itère sur une petite constante connue
        if isinstance(iterateur, (list, tuple, str, range)) and len(iterateur) < 25:
            target_name = node.target.id if isinstance(node.target, ast.Name) else None
            
            state_before = self.current_scope.copy()
            final_states = []
            
            # On simule chaque itération
            for val in iterateur:
                if target_name: self._set_var(target_name, val)
                self._analyser_block(node.body)
                # On sauve l'état à la fin de chaque tour
                final_states.append(self.current_scope.copy())
            
            # État final : si la boucle a tourné, on est dans l'état du dernier tour
            # (Approximation : on devrait fusionner tous les états possibles si break existe)
            if final_states:
                self.scopes[-1] = final_states[-1]
            else:
                # Boucle vide (ex: range(0)) -> L'état ne change pas
                self.scopes[-1] = state_before
        
        else:
            # Cas générique : on invalide tout ce qui bouge
            if isinstance(node.target, ast.Name): 
                self._set_var(node.target.id, UNKNOWN)
            elif isinstance(node.target, (ast.Tuple, ast.List)):
                for elt in node.target.elts:
                    if isinstance(elt, ast.Name): self._set_var(elt.id, UNKNOWN)
            
            modified = self._get_modified_vars(node.body)
            for v in modified: self._set_var(v, UNKNOWN)
            
            self._analyser_block(node.body)

        if node.orelse: self._analyser_block(node.orelse)

    def visit_FunctionDef(self, node):
        """Analyse une fonction dans son propre scope."""
        self._push_scope()
        # Les arguments sont inconnus
        for arg in node.args.args:
            self._set_var(arg.arg, UNKNOWN)
        self._analyser_block(node.body)
        self._pop_scope()

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Try(self, node):
        """Gère les blocs Try/Except complexes."""
        state_before = self.current_scope.copy()
        
        # 1. Analyse du bloc TRY
        self._analyser_block(node.body)
        
        # Vérifie si le try sort tout le temps (return/raise)
        try_always_exits = self._bloc_sort_systematiquement(node.body)
        if try_always_exits and node.orelse:
            self._marquer_mort(node.orelse, "ELSE du TRY inatteignable (sortie systématique dans try)")
        
        state_after_try = self.current_scope.copy()
        possible_end_states = []
        
        # Si le try ne plante pas, c'est un état final possible
        if not try_always_exits:
            possible_end_states.append(state_after_try)
        
        # 2. Analyse des EXCEPT
        exceptions_vues = set()
        for handler in node.handlers:
            # Chaque except part (théoriquement) de l'état "avant" ou "pendant" le try.
            # Pour simplifier, on reset à l'état avant le try + invalidation partielle si on voulait être puriste.
            self.scopes[-1] = state_before.copy()
            
            nom_ex = self._get_exception_name(handler.type)
            
            # Shadowing detection
            is_shadowed = False
            for vue in exceptions_vues:
                if vue == 'Exception' or nom_ex in self.exceptions_parentes.get(vue, []):
                    self._marquer_mort(handler.body, f"EXCEPT {nom_ex} masqué par {vue}")
                    is_shadowed = True; break
            
            if not is_shadowed:
                if nom_ex: exceptions_vues.add(nom_ex)
                if handler.name: self._set_var(handler.name, UNKNOWN) # L'instance d'erreur est inconnue
                
                self._analyser_block(handler.body)
                possible_end_states.append(self.current_scope.copy())

        # 3. Fusion de tous les chemins
        if possible_end_states:
            merged = possible_end_states[0]
            for s in possible_end_states[1:]:
                merged = self._merge_states(merged, s)
            self.scopes[-1] = merged
        
        # 4. Finally (s'exécute toujours par-dessus)
        if node.finalbody:
            self._analyser_block(node.finalbody)

    def visit_Match(self, node):
        """Gère le Pattern Matching (Python 3.10+)."""
        subject = self._eval(node.subject)
        wildcard_found = False
        
        state_before = self.current_scope.copy()
        end_states = []

        for case in node.cases:
            self.scopes[-1] = state_before.copy()
            
            # Code mort structurel (après un wildcard)
            if wildcard_found:
                self._marquer_mort(case.body, "CASE inatteignable (wildcard précédent)")
                continue

            # Check si c'est un wildcard
            if self._is_wildcard(case.pattern):
                wildcard_found = True
            
            # Tentative d'évaluation du match (si sujet constant et pattern constant)
            is_match_impossible = False
            if isinstance(case.pattern, ast.MatchValue) and subject is not UNKNOWN:
                pat_val = self._eval(case.pattern.value)
                if pat_val is not UNKNOWN and pat_val != subject:
                    is_match_impossible = True
            
            # Guards (case x if False)
            if case.guard:
                guard_val = self._eval(case.guard)
                if guard_val is False:
                    is_match_impossible = True

            if is_match_impossible:
                self._marquer_mort(case.body, "CASE inatteignable (Match ou Guard impossible)")
                continue

            self._analyser_block(case.body)
            end_states.append(self.current_scope.copy())
            
            # Si match certain (sujet == pattern), on arrête d'évaluer les suivants pour le flux
            if isinstance(case.pattern, ast.MatchValue) and subject is not UNKNOWN:
                pat_val = self._eval(case.pattern.value)
                if pat_val == subject and not case.guard:
                    break

        # Fusion
        if end_states:
            merged = end_states[0]
            for s in end_states[1:]:
                merged = self._merge_states(merged, s)
            self.scopes[-1] = merged

    # ==========================================================================
    # CŒUR DE L'ANALYSE DE FLUX (SÉQUENTIEL)
    # ==========================================================================

    def _analyser_block(self, stmts: List[ast.stmt]):
        """
        Analyse une liste d'instructions séquentiellement.
        Détecte si le flux est interrompu (return, raise, assert False, etc.)
        et marque le code suivant comme mort.
        """
        if not stmts: return
        
        dead_code_detected = False
        
        for i, stmt in enumerate(stmts):
            self.visit(stmt)
            
            # Vérification des conditions d'arrêt
            is_exit = self._est_une_sortie_definitive(stmt)
            
            # Vérification des flags spéciaux (Assert False, Infinite Loop)
            if getattr(self, 'force_exit_detection', False):
                self.force_exit_detection = False
                is_exit = True
            
            if is_exit and not dead_code_detected:
                if i + 1 < len(stmts):
                    debut = stmts[i+1].lineno
                    if debut not in self.lignes_signalees:
                        self.problemes.append(CodeUnreachable(
                            ligne_debut=debut,
                            ligne_fin=self._derniere_ligne_liste(stmts),
                            type='dead_code_flow',
                            description=f"Code inatteignable (flux interrompu ligne {stmt.lineno})"
                        ))
                        self.lignes_signalees.add(debut)
                    dead_code_detected = True # On arrête de flaguer pour ce bloc
                    # On continue la visite au cas où il y aurait des structures internes à analyser
                    # mais le flag est posé.

    # ==========================================================================
    # UTILITAIRES ET HELPERS
    # ==========================================================================

    def _est_une_sortie_definitive(self, node) -> bool:
        """Vérifie si un nœud (ou un bloc choisi) coupe le flux."""
        if isinstance(node, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
            return True
        
        # Propagation récursive. Si c'est un IF/TRY dont la branche active sort
        if isinstance(node, ast.If):
            cond = self._eval(node.test)
            if cond is True: return self._bloc_sort_systematiquement(node.body)
            if cond is False: return self._bloc_sort_systematiquement(node.orelse)
        
        if isinstance(node, ast.Try):
            # Un TRY est terminal si le corps sort ET tous les except sortent (simplifié)
            # Ou si le corps sort systématiquement
            return self._bloc_sort_systematiquement(node.body)

        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            func = node.value.func
            nom = ""
            if isinstance(func, ast.Name): nom = func.id
            elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name): 
                nom = f"{func.value.id}.{func.attr}"
            return nom in self.fonctions_terminatrices
        
        return False

    def _marquer_mort(self, stmts: List[ast.stmt], raison: str):
        """Helper pour créer un problème CodeUnreachable sur un bloc."""
        if not stmts: return

        ligne = stmts[0].lineno
        if ligne in self.lignes_signalees: return # Déjà rapporté

        self.problemes.append(CodeUnreachable(
            ligne_debut=ligne,
            ligne_fin=self._derniere_ligne_liste(stmts),
            type='dead_block',
            description=raison
        ))
        self.lignes_signalees.add(ligne)

    def _get_modified_vars(self, nodes: List[ast.stmt]) -> Set[str]:
        """Récupère récursivement les noms des variables modifiées dans un bloc."""
        modified = set()
        for n in nodes:
            for child in ast.walk(n):
                if isinstance(child, ast.Assign):
                    for t in child.targets:
                        if isinstance(t, ast.Name): modified.add(t.id)
                elif isinstance(child, ast.AugAssign):
                    if isinstance(child.target, ast.Name): modified.add(child.target.id)
        return modified

    def _contient_break_accessible(self, nodes: List[ast.stmt]) -> bool:
        """
        Vérifie s'il y a un break dans le bloc, en ignorant les sous-boucles.
        (Version simplifiée : traverse tout, donc peut faire des faux négatifs sur boucles imbriquées
        mais c'est plus sûr pour éviter de rater une sortie. Une version future règlera ceci).
        """
        # Pour faire ça bien, il faudrait un NodeVisitor dédié qui ne descend pas dans les While/For.
        class BreakFinder(ast.NodeVisitor):
            def __init__(self): self.found = False
            def visit_Break(self, n): self.found = True
            def visit_While(self, n): pass # On n'entre pas dans les sous-boucles
            def visit_For(self, n): pass
            def visit_AsyncFor(self, n): pass
        
        finder = BreakFinder()
        for n in nodes: finder.visit(n)
        return finder.found

    def _get_exception_name(self, node) -> Optional[str]:
        if isinstance(node, ast.Name): return node.id
        if isinstance(node, ast.Attribute): return node.attr
        return None

    def _is_wildcard(self, pattern) -> bool:
        """Detecte 'case _:' ou 'case x:' (qui match tout)."""
        return isinstance(pattern, ast.MatchAs)

    def _bloc_sort_systematiquement(self, stmts: List[ast.stmt]) -> bool:
        """Vérifie si la dernière instruction est une sortie."""
        if not stmts: return False
        return self._est_une_sortie_definitive(stmts[-1])

    def _derniere_ligne(self, node: ast.AST) -> int:
        """Trouve la ligne de fin max d'un nœud."""
        derniere = getattr(node, 'end_lineno', getattr(node, 'lineno', 0))
        for child in ast.walk(node):
            if hasattr(child, 'lineno'):
                val = getattr(child, 'end_lineno', getattr(child, 'lineno', 0))
                derniere = max(derniere, val)
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