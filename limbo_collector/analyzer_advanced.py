import ast
from pathlib import Path
from typing import List, Set, Dict, Optional, Tuple, Any
from collections import defaultdict
from .models import CodeEntity

class AnalyseurAvance(ast.NodeVisitor):
    def __init__(self, chemin_fichier: str, contenu: str):
        self.chemin = chemin_fichier
        self.contenu = contenu
        try:
            self.arbre = ast.parse(contenu)
        except SyntaxError:
            self.arbre = ast.Module(body=[], type_ignores=[])
        
        self.entites: Dict[str, CodeEntity] = {}
        self.heritages: Dict[str, str] = {}
        self.appels: Set[str] = set()
        self.instanciations: Set[str] = set()
        self.references_attributs: Dict[str, Set[str]] = defaultdict(set)
        self.imports: Dict[str, str] = {}
        self.type_hints: Set[str] = set()
        
        self.exports_all: Set[str] = set() # Pour __all__
        self.lignes_ignorees: Set[int] = set() # Pour # limbo: ignore
        self.classe_actuelle: Optional[str] = None
        self.dans_fonction = False

        self.entite_actuelle: Optional[str] = None
        
        self._scanner_commentaires()

    def _scanner_commentaires(self):
        """Repère les lignes contenant le tag d'ignorance."""
        for i, ligne in enumerate(self.contenu.splitlines(), 1):
            if "# limbo: ignore" in ligne or "# no-limbo" in ligne:
                self.lignes_ignorees.add(i)
    
    def _generer_signature_structurelle(self, func_node: ast.FunctionDef) -> str:
        """Génère une signature basée sur la structure logique purifiée."""
        structure = []
        
        # On enregistre les éléments clés sans les noms variables
        for node in ast.walk(ast.Module(body=func_node.body, type_ignores=[])):
            # 1. On ignore les noms de variables locales (Name), mais on garde les types d'actions
            if isinstance(node, (ast.If, ast.IfExp)):
                structure.append("BRANCH")
            elif isinstance(node, (ast.For, ast.While, ast.ListComp)):
                structure.append("LOOP")
            elif isinstance(node, ast.Call):
                # Pour les appels, on ne garde que le nom de la fonction appelée
                # car c'est elle qui définit l'action sémantique
                if isinstance(node.func, ast.Name):
                    structure.append(f"CALL:{node.func.id}")
                elif isinstance(node.func, ast.Attribute):
                    structure.append(f"CALL:{node.func.attr}")
            elif isinstance(node, ast.Return):
                structure.append("RETURN")
            elif isinstance(node, ast.Raise):
                structure.append("RAISE")
            elif isinstance(node, ast.Constant):
                # On ne garde que le type de la constante (str, int, None)
                # sauf pour les valeurs critiques comme 0, 1, True, False
                val = node.value
                if val in (0, 1, True, False, None):
                    structure.append(f"CONST:{val}")
                else:
                    structure.append(f"CONST:{type(val).__name__}")

        return "-".join(structure)

    def analyser(self):
        self.visit(self.arbre)
        self._resoudre_heritages()
        return self.entites, self.appels, self.instanciations, self.references_attributs, self.type_hints, self.exports_all

    def visit_Assign(self, node):
        for target in node.targets:
            # On cherche __all__ = [...]
            if isinstance(target, ast.Name) and target.id == "__all__":
                if isinstance(node.value, (ast.List, ast.Tuple)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            self.exports_all.add(elt.value)
                        elif isinstance(elt, ast.Str): # Pour compatibilité Python < 3.8
                            self.exports_all.add(elt.s)

            # Détection des variables globales
            # Si on n'est ni dans une classe, ni dans une fonction
            if not self.classe_actuelle and not self.dans_fonction:
                if isinstance(target, ast.Name):
                    self._enregistrer_variable_globale(target)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            self._enregistrer_variable_globale(elt)
        self.generic_visit(node)
        
    def visit_Import(self, node):
        for alias in node.names:
            nom = alias.asname or alias.name
            self.imports[nom] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            nom = alias.asname or alias.name
            self.imports[nom] = f"{module}.{alias.name}"
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        nom_classe = node.name
        
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.heritages[nom_classe] = base.id
                self.type_hints.add(base.id)
        
        ignoree = (node.lineno in self.lignes_ignorees or 
                   (node.lineno - 1) in self.lignes_ignorees)

        clef = f"{self.chemin}::{nom_classe}"
        self.entites[clef] = CodeEntity(
            nom=nom_classe,
            type='classe',
            ligne=node.lineno,
            fichier=self.chemin,
            decorateurs=[self._nom_decorateur(d) for d in node.decorator_list],
            est_ignoree=ignoree
        )
        
        ancien_contexte = self.classe_actuelle
        self.classe_actuelle = nom_classe
        self.generic_visit(node)
        self.classe_actuelle = ancien_contexte

    def visit_FunctionDef(self, node):
        ancienne_valeur = self.dans_fonction
        self.dans_fonction = True
        self._traiter_fonction_ou_methode(node)
        self.dans_fonction = ancienne_valeur
        
    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)
    
    def _enregistrer_variable_globale(self, node_name: ast.Name):
        nom = node_name.id
        # On ignore les variables privées par convention (_nom)
        if nom.startswith('_') and not nom.startswith('__'):
            return
        # On ignore les constantes spéciales
        if nom in ('__version__', '__author__', '__license__'):
            return

        clef = f"{self.chemin}::{nom}"
        self.entites[clef] = CodeEntity(
            nom=nom,
            type='variable_globale',
            ligne=node_name.lineno,
            fichier=self.chemin,
            est_ignoree=(node_name.lineno in self.lignes_ignorees)
        )

    def _traiter_fonction_ou_methode(self, node):
        # Récupération des types (retour et arguments)
        if node.returns:
            self._extraire_types_annotation(node.returns)
        for arg in node.args.args:
            if arg.annotation:
                self._extraire_types_annotation(arg.annotation)
        
        ignoree = (node.lineno in self.lignes_ignorees or 
                   (node.lineno - 1) in self.lignes_ignorees)
        
        nom = node.name
        decorateurs = [self._nom_decorateur(d) for d in node.decorator_list]

        # On ne calcule la signature que pour les fonctions assez grandes (> 3 nœuds)
        # pour éviter de marquer "return None" comme un doublon partout.
        sig = ""
        if len(node.body) > 0:
            sig = self._generer_signature_structurelle(node)
            # On ignore les fonctions trop simples (ex: pass ou un seul return simple)
            if sig.count('-') < 3: 
                sig = ""
        
        if self.classe_actuelle:
            type_methode = 'methode'
            if 'staticmethod' in decorateurs:
                type_methode = 'staticmethod'
            elif 'classmethod' in decorateurs:
                type_methode = 'classmethod'
            elif 'property' in decorateurs:
                type_methode = 'property'
            
            clef = f"{self.chemin}::{self.classe_actuelle}.{nom}"
            self.entites[clef] = CodeEntity(
                nom=nom,
                type=type_methode,
                ligne=node.lineno,
                fichier=self.chemin,
                classe_parent=self.classe_actuelle,
                decorateurs=decorateurs,
                est_ignoree=ignoree,
                signature_structurelle=sig
            )
        else:
            clef = f"{self.chemin}::{nom}"
            self.entites[clef] = CodeEntity(
                nom=nom,
                type='fonction',
                ligne=node.lineno,
                fichier=self.chemin,
                decorateurs=decorateurs,
                est_ignoree=ignoree,
                signature_structurelle=sig
            )
        
        ancienne_entite = self.entite_actuelle
        self.entite_actuelle = clef
        
        self.generic_visit(node)
        self.entite_actuelle = ancienne_entite

    def visit_Call(self, node):
        nom_appele = ""
        if isinstance(node.func, ast.Name):
            nom_appele = node.func.id
        elif isinstance(node.func, ast.Attribute):
            nom_appele = node.func.attr
        
        if nom_appele:
            self.appels.add(nom_appele)
            if self.entite_actuelle and self.entite_actuelle in self.entites:
                self.entites[self.entite_actuelle].appels_sortants.add(nom_appele)
        
        self.generic_visit(node)
        
    def visit_AnnAssign(self, node):
        """Pour x: MyClass = ..."""
        self._extraire_types_annotation(node.annotation)
        self.generic_visit(node)

    def _extraire_types_annotation(self, node: Any):
        if node is None:
            return

        if isinstance(node, ast.Name):
            self.type_hints.add(node.id)
        elif isinstance(node, ast.Attribute):
            self.type_hints.add(node.attr)
            if isinstance(node.value, ast.Name):
                self.type_hints.add(node.value.id)
        elif isinstance(node, ast.Subscript): # List[User]
            self._extraire_types_annotation(node.value)
            self._extraire_types_annotation(node.slice)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                self._extraire_types_annotation(elt)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str): # "User"
            self.type_hints.add(node.value.strip("'\""))
        elif isinstance(node, ast.BinOp): # User | None
             self._extraire_types_annotation(node.left)
             self._extraire_types_annotation(node.right)

    def _nom_decorateur(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        return ""
    
    def _resoudre_heritages(self):
        pass


class DetecteurLimbo:
    def __init__(self, entites: Dict[str, CodeEntity], appels: Set[str], 
                 instanciations: Set[str], references_attributs: Dict[str, Set[str]],
                 type_hints: Set[str], exports_all: Set[str]):
        self.entites = entites
        self.appels = appels
        self.instanciations = instanciations
        self.references_attributs = references_attributs
        self.type_hints = type_hints
        self.exports_all = exports_all
        self.vivants_finaux: Set[str] = set()
        
        self.methodes_magiques = {
            '__init__', '__del__', '__repr__', '__str__', '__eq__', '__ne__',
            '__lt__', '__le__', '__gt__', '__ge__', '__hash__', '__bool__',
            '__getattr__', '__setattr__', '__delattr__', '__getattribute__',
            '__getitem__', '__setitem__', '__delitem__', '__iter__', '__next__',
            '__enter__', '__exit__', '__call__', '__len__', '__contains__',
            '__add__', '__sub__', '__mul__', '__truediv__', '__floordiv__',
            '__mod__', '__pow__', '__and__', '__or__', '__xor__',
            '__await__', '__aiter__', '__anext__', '__aenter__', '__aexit__'
        }
        
        self.methodes_framework = {
            'save', 'delete', 'clean', 'full_clean', 'get_absolute_url',
            'Meta', 'DoesNotExist', 'MultipleObjectsReturned',
            'setup', 'teardown', 'setUp', 'tearDown',
            'test'
        }
    
    def analyser(self, recursive: bool = False) -> Tuple[List[CodeEntity], List[CodeEntity], List[CodeEntity]]:
        if not recursive:
            # Mode classique
            morts = []
            probablement_morts = []
            utilises = []
            
            for clef, entite in self.entites.items():
                statut = self._evaluer_entite(entite)
                
                if statut == "utilise":
                    utilises.append(entite)
                    entite.est_utilisee = True
                elif statut == "mort":
                    morts.append(entite)
                elif statut == "probable":
                    probablement_morts.append(entite)
            
            return morts, probablement_morts, utilises
        
        # Mode recursive
        return self._analyser_recursive()

    def _analyser_recursive(self) -> Tuple[List[CodeEntity], List[CodeEntity], List[CodeEntity]]:
        morts = []
        utilises = []
        file_a_traiter = []
        self.vivants_finaux = set()

        # 1. On ne part QUE des vraies racines
        for clef, entite in self.entites.items():
            if self._est_racine(entite):
                self.vivants_finaux.add(clef)
                file_a_traiter.append(clef)

        # 2. Propagation
        while file_a_traiter:
            clef_actuelle = file_a_traiter.pop(0)
            entite_actuelle = self.entites[clef_actuelle]
            
            for nom_appele in entite_actuelle.appels_sortants:
                # On cherche l'entité correspondante dans LE MÊME FICHIER ou via import
                for clef_cible, entite_cible in self.entites.items():
                    if entite_cible.nom == nom_appele and clef_cible not in self.vivants_finaux:
                        self.vivants_finaux.add(clef_cible)
                        file_a_traiter.append(clef_cible)

        # 3. Récupération des résultats
        for clef, entite in self.entites.items():
            if clef in self.vivants_finaux:
                entite.est_utilisee = True
                utilises.append(entite)
            else:
                morts.append(entite)
        
        return morts, [], utilises

    def _est_racine(self, entite: CodeEntity) -> bool:
        """Détermine si une entité est un point d'entrée du programme."""
        if entite.est_ignoree: return True
        if entite.nom in self.exports_all: return True
        if entite.nom in self.methodes_magiques: return True
        
        # Décorateurs de frameworks (API, Tâches, etc.)
        deco_root = ['app.route', 'router.get', 'task', 'pytest.fixture', 'fixture']
        if any(d in deco_root for d in entite.decorateurs): return True
        
        # Noms standards d'entrée
        if entite.nom in ['main', 'run', 'app', 'create_app', 'cli', 'application']:
            return True
            
        # Tests
        if (entite.fichier.startswith('test_') or '/test_' in entite.fichier) and entite.nom.startswith('test_'):
            return True
            
        return False       

    def _evaluer_entite(self, entite: CodeEntity) -> str:
            
        if entite.est_ignoree:
            entite.raison_utilisation = "Ignoré par commentaire"
            return "utilise"

        if entite.nom in self.exports_all:
            entite.raison_utilisation = "Exporté via __all__"
            return "utilise"
        
        if entite.fichier.startswith('test_') or '/test_' in entite.fichier or '/tests/' in entite.fichier:
            if entite.nom.startswith('test_'):
                return "utilise"

        if entite.nom in self.methodes_magiques:
            return "utilise"
        
        if entite.nom in self.methodes_framework:
            return "probable"
        
        deco_special = ['app.route', 'router.get', 'task', 'property', 'pytest.fixture', 'fixture']
        if any(d in deco_special for d in entite.decorateurs):
            return "utilise"
        
        if entite.nom in ['main', 'run', 'app', 'create_app', 'cli', 'application']:
            return "utilise"
        
        if entite.nom in self.appels:
            return "utilise"
        
        if entite.type == 'classe' and entite.nom in self.type_hints:
            entite.raison_utilisation = "Utilisé comme Type Hint"
            return "utilise"
        
        if entite.type == 'classe':
            if entite.nom in self.instanciations:
                return "utilise"
            if entite.nom in self.references_attributs:
                return "probable"
            return "mort"
        
        if entite.type in ['staticmethod', 'classmethod']:
            if (entite.classe_parent in self.instanciations or 
                entite.classe_parent in self.type_hints):
                if not entite.nom.startswith('_'):
                    return "probable"
            if entite.classe_parent in self.instanciations:
                return "utilise"
            return "mort"
        
        if entite.type == 'methode':
            if (entite.classe_parent in self.instanciations or 
                entite.classe_parent in self.type_hints):
                
                if entite.nom in self.appels:
                    return "utilise"
                
                if not entite.nom.startswith('_'):
                    return "probable"
                    
                return "mort"
            return "mort"
        
        if entite.type == 'fonction':
            return "mort" if entite.nom not in self.appels else "utilise"

        if entite.type == 'variable_globale':
            if entite.nom in self.type_hints:
                return "utilise"
            if entite.nom in self.appels:
                return "utilise"
            if entite.nom in self.references_attributs:
                return "utilise"
            
            return "mort"
        
        return "probable"


def analyser_fichier_avance(chemin: str, deep: bool = False) -> Tuple[List[CodeEntity], List[CodeEntity], List[CodeEntity]]:
    contenu = Path(chemin).read_text(encoding='utf-8')
    analyseur = AnalyseurAvance(chemin, contenu)
    entites, appels, instanciations, references, type_hints, exports_all = analyseur.analyser()
    
    detecteur = DetecteurLimbo(entites, appels, instanciations, references, type_hints, exports_all)
    return detecteur.analyser(recursive=deep)