import ast
from pathlib import Path
from typing import List, Set, Dict, Optional, Tuple, Any
from collections import defaultdict
from .models import CodeEntity
from .frameworks import FRAMEWORK_RULES

class AnalyseurAvance(ast.NodeVisitor):
    def __init__(self, chemin_fichier: str, contenu: str):
        self.chemin = chemin_fichier
        self.contenu = contenu
        try:
            self.arbre = ast.parse(contenu)
        except SyntaxError:
            self.arbre = ast.Module(body=[], type_ignores=[])
        
        self.entites: Dict[str, CodeEntity] = {}
        self.appels: Set[str] = set()
        self.instanciations: Set[str] = set()
        self.references_attributs: Dict[str, Set[str]] = defaultdict(set)
        self.imports: Dict[str, str] = {}
        self.type_hints: Set[str] = set()
        
        self.exports_all: Set[str] = set() # Pour __all__
        self.lignes_ignorees: Set[int] = set() # Pour # limbo: ignore
        
        self.imports_dynamiques: Set[Tuple[str, str]] = set()
        
        self.classe_actuelle: Optional[str] = None
        self.dans_fonction = False
        self.entite_actuelle: Optional[str] = None

        self.scope_types: Dict[str, str] = {} # Mapping nom_variable -> NomClasse
        self.appels_specifiques_globaux: Set[str] = set()

        self.appels_racines: Set[str] = set()
        
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
    
    def _extraire_nom_type(self, node) -> Optional[str]:
        """Extrait le nom simple d'un type depuis une annotation."""
        if isinstance(node, ast.Name): return node.id
        if isinstance(node, ast.Attribute): return node.attr
        if isinstance(node, ast.Subscript): return self._extraire_nom_type(node.value)
        return None


    def analyser(self):
        self.visit(self.arbre)
        # Note: self._resoudre_heritages() est géré globalement maintenant
        return (self.entites, self.appels, self.instanciations, 
                self.references_attributs, self.type_hints, self.exports_all, 
                self.imports_dynamiques, self.appels_specifiques_globaux,
                self.appels_racines)
    
    def visit_AnnAssign(self, node):
        """Capte x: MyClass = ..."""
        if isinstance(node.target, ast.Name):
            type_nom = self._extraire_nom_type(node.annotation)
            if type_nom:
                self.scope_types[node.target.id] = type_nom
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        # Nouveau : On entre dans une fonction, on réinitialise le scope des types
        ancien_scope = self.scope_types.copy()
        
        # On enregistre les types des arguments
        for arg in node.args.args:
            if arg.annotation:
                type_nom = self._extraire_nom_type(arg.annotation)
                if type_nom:
                    self.scope_types[arg.arg] = type_nom

        self.dans_fonction = True
        self._traiter_fonction_ou_methode(node)
        
        # On nettoie le scope en sortant
        self.scope_types = ancien_scope
        self.dans_fonction = False

    def visit_Attribute(self, node):
        """Capte user.save() et tente de lier 'user' à une classe."""
        if isinstance(node.value, ast.Name):
            var_nom = node.value.id
            if var_nom in self.scope_types:
                type_classe = self.scope_types[var_nom]
                methode_nom = node.attr
                # On a trouvé un appel sémantique ! Ex: "User.save"
                appel_complet = f"{type_classe}.{methode_nom}"
                self.appels_specifiques_globaux.add(appel_complet)
                
                if self.entite_actuelle and self.entite_actuelle in self.entites:
                    self.entites[self.entite_actuelle].appels_specifiques.add(appel_complet)
        
        self.generic_visit(node)

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
        
        # Extraction des noms des classes parentes
        bases_classe = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases_classe.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases_classe.append(base.attr)
        
        # Enregistrement pour les Type Hints
        for b in bases_classe:
            self.type_hints.add(b)

        doc = ast.get_docstring(node) or ""
        
        ignoree = (node.lineno in self.lignes_ignorees or 
                   (node.lineno - 1) in self.lignes_ignorees)

        clef = f"{self.chemin}::{nom_classe}"
        self.entites[clef] = CodeEntity(
            nom=nom_classe,
            type='classe',
            ligne=node.lineno,
            fichier=self.chemin,
            bases=bases_classe,
            decorateurs=[self._nom_decorateur(d) for d in node.decorator_list],
            est_ignoree=ignoree,
            docstring=doc
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
        
        # On capture les types utilisés dans la signature
        types_trouves = set()
        if node.returns: 
            t = self._extraire_nom_type(node.returns)
            if t: types_trouves.add(t)
        for arg in node.args.args:
            if arg.annotation:
                t = self._extraire_nom_type(arg.annotation)
                if t: types_trouves.add(t)
        
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
        doc = ast.get_docstring(node) or ""
        
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
                signature_structurelle=sig,
                docstring=doc,
                types_utilises=types_trouves
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
                signature_structurelle=sig,
                docstring=doc,
                types_utilises=types_trouves
            )
        
        ancienne_entite = self.entite_actuelle
        self.entite_actuelle = clef
        
        self.generic_visit(node)
        self.entite_actuelle = ancienne_entite

    def visit_Call(self, node):
        nom_appele = ""
        est_dynamique = False
        
        # Analyse standard des appels
        if isinstance(node.func, ast.Name):
            nom_appele = node.func.id
            if nom_appele in ('__import__', 'exec', 'eval'):
                est_dynamique = True
        elif isinstance(node.func, ast.Attribute):
            nom_appele = node.func.attr
            # Détection importlib.import_module
            if nom_appele == 'import_module':
                est_dynamique = True
        
        if nom_appele:
            self.appels.add(nom_appele)
            if self.entite_actuelle and self.entite_actuelle in self.entites:
                self.entites[self.entite_actuelle].appels_sortants.add(nom_appele)
            else:
                self.appels_racines.add(nom_appele)
        
        # Analyse spécifique pour imports dynamiques
        if est_dynamique and node.args:
            arg = node.args[0]
            self._analyser_argument_dynamique(arg)
            
        self.generic_visit(node)
        
    def _analyser_argument_dynamique(self, node_arg):
        """Tente de deviner le module importé dynamiquement."""
        
        # Cas 1: Chaîne simple ("mon_module")
        if isinstance(node_arg, ast.Constant) and isinstance(node_arg.value, str):
            self.imports_dynamiques.add(('exact', node_arg.value))
            return

        # Cas 2: F-String (f"plugins.{name}")
        if isinstance(node_arg, ast.JoinedStr):
            prefixe = ""
            # On regarde le premier élément de la f-string
            if node_arg.values and isinstance(node_arg.values[0], ast.Constant):
                val = node_arg.values[0].value
                if isinstance(val, str) and ('.' in val or '/' in val):
                    # Ex: f"plugins.{x}" -> prefixe "plugins."
                    prefixe = val
                    self.imports_dynamiques.add(('prefix', prefixe))
            return

        # Cas 3: Concaténation ("plugins." + name)
        if isinstance(node_arg, ast.BinOp) and isinstance(node_arg.op, ast.Add):
            # On cherche récursivement à gauche
            left = node_arg.left
            if isinstance(left, ast.Constant) and isinstance(left.value, str):
                self.imports_dynamiques.add(('prefix', left.value))

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


class DetecteurLimbo:
    def __init__(self, entites: Dict[str, CodeEntity], appels: Set[str], 
                 instanciations: Set[str], references_attributs: Dict[str, Set[str]],
                 type_hints: Set[str], exports_all: Set[str], 
                 appels_specifiques_projet: Set[str] = None, appels_racines: Set[str] = None):
        self.entites = entites
        self.appels = appels
        self.instanciations = instanciations
        self.references_attributs = references_attributs
        self.type_hints = type_hints
        self.exports_all = exports_all
        self.appels_specifiques_projet = appels_specifiques_projet or set()
        self.vivants_finaux: Set[str] = set()
        self.appels_racines = appels_racines or set()
        
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
            # Si déjà marqué utilisé (ex: import dynamique), on le considère comme racine
            if entite.est_utilisee or self._est_racine(entite):
                self.vivants_finaux.add(clef)
                file_a_traiter.append(clef)
        
        # 2. On part des appels faits au niveau global (Top-level / __main__)
        for nom_appele in self.appels_racines:
            for clef_cible, entite_cible in self.entites.items():
                if entite_cible.nom == nom_appele and clef_cible not in self.vivants_finaux:
                    self.vivants_finaux.add(clef_cible)
                    file_a_traiter.append(clef_cible)

        # 3. Propagation
        while file_a_traiter:
            clef_actuelle = file_a_traiter.pop(0)
            entite_actuelle = self.entites[clef_actuelle]
            
            # 1. Propagation par appels classiques (noms de fonctions)
            noms_a_chercher = entite_actuelle.appels_sortants | entite_actuelle.types_utilises
            
            # 2. Propagation par appels typés (User.save)
            # On transforme "User.save" en nom de méthode "save" pour la recherche
            for appel_spec in entite_actuelle.appels_specifiques:
                if "." in appel_spec:
                    noms_a_chercher.add(appel_spec.split(".")[-1])
                    noms_a_chercher.add(appel_spec.split(".")[0]) # On sauve aussi la Classe

            for nom in noms_a_chercher:
                for clef_cible, entite_cible in self.entites.items():
                    if entite_cible.nom == nom and clef_cible not in self.vivants_finaux:
                        self.vivants_finaux.add(clef_cible)
                        file_a_traiter.append(clef_cible)

        # 4. Récupération des résultats
        for clef, entite in self.entites.items():
            if clef in self.vivants_finaux:
                entite.est_utilisee = True
                utilises.append(entite)
            else:
                morts.append(entite)
        
        return morts, [], utilises
    

    def _est_racine(self, entite: CodeEntity) -> bool:
        """Détermine si une entité est un point d'entrée du programme (Standard + Frameworks)."""
        # On combine les deux nouvelles logiques de détection
        return self._est_racine_standard(entite) or self._est_une_racine_framework(entite)


    def _est_une_racine_framework(self, entite: CodeEntity) -> bool:
        """Vérifie si l'entité est un point d'entrée selon les frameworks connus."""
        
        # 1. Vérification par décorateurs (FastAPI, Flask, Celery, Pytest)
        tous_les_decos_racines = (
            FRAMEWORK_RULES["fastapi_flask"]["decorateurs_racines"] | 
            FRAMEWORK_RULES["pytest"]["decorateurs_racines"] |
            FRAMEWORK_RULES["django"]["decorateurs_racines"]
        )
        
        if any(deco in tous_les_decos_racines for deco in entite.decorateurs):
            entite.raison_utilisation = "Point d'entrée Framework (décorateur)"
            return True

        # 2. Cas spécifique Pytest (fichiers de test ou fonctions test_*)
        if entite.nom.startswith("test_") or entite.nom.startswith("pytest_"):
             if "test" in entite.fichier or "conftest.py" in entite.fichier:
                return True

        # 3. Cas spécifique Django (Classes Meta, méthodes de commande management)
        if entite.type == 'classe' and entite.nom in FRAMEWORK_RULES["django"]["classes_vivantes"]:
            return True
        
        if entite.type in ['methode', 'fonction'] and entite.nom in FRAMEWORK_RULES["django"]["methodes_vivantes"]:
            # On pourrait vérifier ici si la classe parente hérite de Model/View pour être plus précis
            return True

        # 4. Cas Pydantic / Tortoise ORM / etc.
        if entite.nom in FRAMEWORK_RULES["pydantic"]["classes_vivantes"]:
            return True

        return False

    def _evaluer_entite(self, entite: CodeEntity) -> str:
        # --- NIVEAU 0 : DÉJÀ SAUVÉ ---
        # C'est la ligne CRITIQUE qui manquait. 
        # Si le ProjectScanner a dit "c'est vivant (import dynamique)", on ne discute pas.
        if entite.est_utilisee:
            return "utilise"

        # --- NIVEAU 1 : RAISONS CERTAINES DE SURVIE ---

        # 1a. Priorité absolue : L'utilisateur l'a ignoré
        if entite.est_ignoree:
            entite.raison_utilisation = "Ignoré par commentaire"
            return "utilise"

        # 1b. Points d'entrée (standard, frameworks)
        if self._est_racine_standard(entite) or self._est_une_racine_framework(entite):
            # La raison est définie dans les méthodes appelées
            return "utilise"

        # 1c. Utilisation directe par appel ou instanciation
        if entite.nom in self.appels:
            entite.raison_utilisation = "Appelé directement"
            return "utilise"
        
        if entite.type == 'classe' and entite.nom in self.instanciations:
            entite.raison_utilisation = "Instanciée"
            return "utilise"

        # 1d. Exposition publique ou typage
        if entite.nom in self.exports_all:
            entite.raison_utilisation = "Exporté via __all__"
            return "utilise"
        
        if entite.type == 'classe' and entite.nom in self.type_hints:
            entite.raison_utilisation = "Utilisé comme Type Hint"
            return "utilise"
        
        # --- NIVEAU 2 : CAS SPÉCIFIQUES ---
        if entite.type == 'variable_globale':
            if entite.nom in self.references_attributs or entite.nom in self.appels:
                entite.raison_utilisation = "Variable globale référencée"
                return "utilise"
            return "mort"
        
        if entite.type == 'classe':
            # Si on arrive ici, la classe n'est ni instanciée, ni type hint, etc.
            # On vérifie une dernière utilisation "probable" : un accès statique.
            if entite.nom in self.references_attributs:
                entite.raison_utilisation = "Référence statique (ex: MaClasse.CONSTANTE)"
                return "probable"
            return "mort"

        # 6. Cas des méthodes
        if entite.type in ['methode', 'staticmethod', 'classmethod', 'property']:
            
            # A. VÉRIFICATION SÉMANTIQUE (TYPE HINTS)
            # On vérifie si un appel précis vers CETTE classe a été détecté
            clef_specifique = f"{entite.classe_parent}.{entite.nom}"
            if clef_specifique in self.appels_specifiques_projet:
                entite.raison_utilisation = f"Appel typé détecté ({clef_specifique})"
                return "utilise"

            # B. TA LOGIQUE EXISTANTE (GARDÉE INTACTE)
            # On regarde les cas "probables" si ce n'est pas une méthode privée
            if not entite.nom.startswith('_'):
                parent_clef = f"{entite.fichier}::{entite.classe_parent}"
                parent_entite = self.entites.get(parent_clef)
                
                # Si la classe parente est utilisée OU si elle hérite de qqch (polymorphisme)
                if parent_entite and (parent_entite.est_utilisee or parent_entite.bases):
                    entite.raison_utilisation = "Méthode publique d'une classe vivante"
                    return "probable"
            
            # Sinon, elle est considérée comme morte à ce stade.
            return "mort"

        # --- NIVEAU 3 : DERNIER RECOURS ---
        # Si c'est une fonction simple qui n'a été ni appelée, ni marquée comme racine...
        if entite.type == 'fonction':
            return "mort"
            
        # Par défaut, si rien ne l'a sauvé, c'est mort.
        return "mort"

    def _est_racine_standard(self, entite: CodeEntity) -> bool:
        """Points d'entrée Python standards."""
        if entite.nom in self.methodes_magiques:
            entite.raison_utilisation = "Méthode magique Python"
            return True
        
        noms_entrees = {'main', 'run', 'app', 'create_app', 'cli', 'application', 'wsgi_app', 'asgi_app'}
        if entite.nom in noms_entrees:
            entite.raison_utilisation = "Point d'entrée standard"
            return True
            
        return False


def analyser_fichier_avance(chemin: str, deep: bool = False) -> Tuple[List[CodeEntity], List[CodeEntity], List[CodeEntity]]:
    contenu = Path(chemin).read_text(encoding='utf-8')
    analyseur = AnalyseurAvance(chemin, contenu)
    entites, appels, instanciations, references, type_hints, exports_all, imports_dynamiques, appels_spec, racines = analyseur.analyser()
    
    detecteur = DetecteurLimbo(entites, appels, instanciations, references, type_hints, exports_all, appels_spec, racines)
    return detecteur.analyser(recursive=deep)