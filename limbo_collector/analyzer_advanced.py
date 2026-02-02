import ast
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Tuple
from collections import defaultdict


@dataclass
class CodeEntity:
    nom: str
    type: str
    ligne: int
    fichier: str
    classe_parent: Optional[str] = None
    decorateurs: List[str] = field(default_factory=list)
    est_utilisee: bool = False
    raison_utilisation: str = ""


class AnalyseurAvance(ast.NodeVisitor):
    def __init__(self, chemin_fichier: str, contenu: str):
        self.chemin = chemin_fichier
        self.contenu = contenu
        self.arbre = ast.parse(contenu)
        
        self.entites: Dict[str, CodeEntity] = {}
        self.heritages: Dict[str, str] = {}
        self.appels: Set[str] = set()
        self.instanciations: Set[str] = set()
        self.references_attributs: Dict[str, Set[str]] = defaultdict(set)
        self.imports: Dict[str, str] = {}
        
        self.classe_actuelle: Optional[str] = None
        
    def analyser(self):
        self._collecter_definitions()
        self._collecter_utilisations()
        self._resoudre_heritages()
        return self.entites, self.appels, self.instanciations, self.references_attributs
    
    def _collecter_definitions(self):
        for node in ast.walk(self.arbre):
            if isinstance(node, ast.ClassDef):
                self._traiter_classe(node)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._traiter_fonction(node)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    nom = alias.asname or alias.name
                    self.imports[nom] = alias.name
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    nom = alias.asname or alias.name
                    self.imports[nom] = f"{module}.{alias.name}"
    
    def _traiter_classe(self, node: ast.ClassDef):
        nom_classe = node.name
        self.classe_actuelle = nom_classe
        
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.heritages[nom_classe] = base.id
        
        clef = f"{self.chemin}::{nom_classe}"
        self.entites[clef] = CodeEntity(
            nom=nom_classe,
            type='classe',
            ligne=node.lineno,
            fichier=self.chemin,
            decorateurs=[self._nom_decorateur(d) for d in node.decorator_list]
        )
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._traiter_methode(item, nom_classe)
        
        self.classe_actuelle = None
    
    def _traiter_methode(self, node: ast.FunctionDef, classe_parent: str):
        nom_methode = node.name
        
        type_methode = 'methode'
        decorateurs_noms = [self._nom_decorateur(d) for d in node.decorator_list]
        
        if 'staticmethod' in decorateurs_noms:
            type_methode = 'staticmethod'
        elif 'classmethod' in decorateurs_noms:
            type_methode = 'classmethod'
        elif 'property' in decorateurs_noms:
            type_methode = 'property'
        
        clef = f"{self.chemin}::{classe_parent}.{nom_methode}"
        self.entites[clef] = CodeEntity(
            nom=nom_methode,
            type=type_methode,
            ligne=node.lineno,
            fichier=self.chemin,
            classe_parent=classe_parent,
            decorateurs=decorateurs_noms
        )
    
    def _traiter_fonction(self, node: ast.FunctionDef):
        if self.classe_actuelle:
            return
            
        nom_fonction = node.name
        clef = f"{self.chemin}::{nom_fonction}"
        
        self.entites[clef] = CodeEntity(
            nom=nom_fonction,
            type='fonction',
            ligne=node.lineno,
            fichier=self.chemin,
            decorateurs=[self._nom_decorateur(d) for d in node.decorator_list]
        )
    
    def _nom_decorateur(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        return ""
    
    def _collecter_utilisations(self):
        for node in ast.walk(self.arbre):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    self.appels.add(func.id)
                    if func.id[0].isupper():
                        self.instanciations.add(func.id)
                elif isinstance(func, ast.Attribute):
                    self.appels.add(func.attr)
                    if isinstance(func.value, ast.Name):
                        self.references_attributs[func.value.id].add(func.attr)
            
            elif isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        self.references_attributs[base.id]
    
    def _resoudre_heritages(self):
        pass


class DetecteurLimbo:
    def __init__(self, entites: Dict[str, CodeEntity], appels: Set[str], 
                 instanciations: Set[str], references_attributs: Dict[str, Set[str]]):
        self.entites = entites
        self.appels = appels
        self.instanciations = instanciations
        self.references_attributs = references_attributs
        
        self.methodes_magiques = {
            '__init__', '__del__', '__repr__', '__str__', '__eq__', '__ne__',
            '__lt__', '__le__', '__gt__', '__ge__', '__hash__', '__bool__',
            '__getattr__', '__setattr__', '__delattr__', '__getattribute__',
            '__getitem__', '__setitem__', '__delitem__', '__iter__', '__next__',
            '__enter__', '__exit__', '__call__', '__len__', '__contains__',
            '__add__', '__sub__', '__mul__', '__truediv__', '__floordiv__',
            '__mod__', '__pow__', '__and__', '__or__', '__xor__',
        }
        
        self.methodes_framework = {
            'save', 'delete', 'clean', 'full_clean', 'get_absolute_url',
            'Meta', 'DoesNotExist', 'MultipleObjectsReturned',
            'setup', 'teardown', 'setUp', 'tearDown',
        }
    
    def analyser(self) -> Tuple[List[CodeEntity], List[CodeEntity], List[CodeEntity]]:
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
    
    def _evaluer_entite(self, entite: CodeEntity) -> str:
        if entite.nom in self.methodes_magiques:
            return "utilise"
        
        if entite.nom in self.methodes_framework:
            return "probable"
        
        deco_special = ['app.route', 'router.get', 'task', 'property', 'pytest.fixture']
        if any(d in deco_special for d in entite.decorateurs):
            return "utilise"
        
        if entite.nom in ['main', 'run', 'app', 'create_app', 'cli']:
            return "utilise"
        
        if entite.nom in self.appels:
            return "utilise"
        
        if entite.type == 'classe':
            if entite.nom in self.instanciations:
                return "utilise"
            if entite.nom in self.references_attributs:
                return "probable"
            return "mort"
        
        if entite.type in ['staticmethod', 'classmethod']:
            if entite.classe_parent in self.instanciations:
                return "utilise"
            return "mort"
        
        if entite.type == 'methode':
            if entite.classe_parent in self.instanciations:
                if entite.nom in self.appels:
                    return "utilise"
                return "mort"
            return "mort"
        
        if entite.type == 'fonction':
            return "mort" if entite.nom not in self.appels else "utilise"
        
        return "probable"


def analyser_fichier_avance(chemin: str) -> Tuple[List[CodeEntity], List[CodeEntity], List[CodeEntity]]:
    contenu = Path(chemin).read_text(encoding='utf-8')
    analyseur = AnalyseurAvance(chemin, contenu)
    entites, appels, instanciations, references = analyseur.analyser()
    
    detecteur = DetecteurLimbo(entites, appels, instanciations, references)
    return detecteur.analyser()