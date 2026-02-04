import ast
from pathlib import Path
import pathspec
from dataclasses import dataclass, field
from typing import List, Set, Dict, Optional, Tuple, DefaultDict
from collections import defaultdict
from .models import CodeEntity, ImportInutile, VariableInutilisee, GroupeDuplique
from .analyzer_advanced import AnalyseurAvance, DetecteurLimbo
from .imports import analyser_imports_fichier
from .variables import trouver_variables_inutilisees


@dataclass
class ResultatProjet:
    fichiers_analyses: int
    total_lignes: int
    code_mort: List[Tuple[str, CodeEntity]] # (chemin, entite)
    code_suspect: List[Tuple[str, CodeEntity]]
    imports_morts_par_fichier: Dict[str, List[ImportInutile]]
    variables_mortes_par_fichier: Dict[str, List[VariableInutilisee]]
    erreurs: List[str]
    stats_parametres: int = 0
    stats_unreachable: int = 0
    doublons: List[GroupeDuplique] = field(default_factory=list)

    def calculer_score_sante(self) -> float:
        """
        Calcule un score de santé basé sur la densité et la sévérité des problèmes.
        """
        if self.total_lignes == 0:
            return 100.0

        # 1. Définir la sévérité de chaque type de problème (points de pénalité)
        poids = {
            'classe_morte': 10,
            'fonction_morte': 6,
            'methode_morte': 4,
            'variable_globale_morte': 3,
            'unreachable': 2,
            'import_mort': 1,
            'variable_morte': 0.5,
            'param_mort': 0.5
        }

        # 2. Calculer la pénalité brute en fonction de la sévérité
        total_imports = sum(len(v) for v in self.imports_morts_par_fichier.values())
        total_vars = sum(len(v) for v in self.variables_mortes_par_fichier.values())

        penalite_brute = (
            len([e for _, e in self.code_mort if e.type == 'classe']) * poids['classe_morte'] +
            len([e for _, e in self.code_mort if e.type == 'fonction']) * poids['fonction_morte'] +
            len([e for _, e in self.code_mort if e.type.endswith('methode')]) * poids['methode_morte'] +
            len([e for _, e in self.code_mort if e.type == 'variable_globale']) * poids['variable_globale_morte'] +
            total_imports * poids['import_mort'] +
            total_vars * poids['variable_morte'] +
            self.stats_unreachable * poids['unreachable'] +
            self.stats_parametres * poids['param_mort']
        )
        
        # 3. Calculer la densité de problèmes
        densite_problemes = (penalite_brute / self.total_lignes) * 100

        # 4. Transformer la densité en score sur 100
        # k est un facteur d'agressivité. Plus k est grand, plus la chute est rapide.
        k = 0.2
        score = 100 * (1 - densite_problemes / 100) ** (1 + k * densite_problemes / 100)
        
        return round(max(0, score), 1)


@dataclass
class FichierAnalyse:
    """Résultat d'analyse d'un fichier."""
    chemin: str
    entites: Dict[str, CodeEntity]
    appels: Set[str]
    instanciations: Set[str]
    references: Dict[str, Set[str]]
    type_hints: Set[str]
    exports_all: Set[str]
    exports: Set[str]  # Ce que ce fichier exporte (pour d'autres fichiers)
    imports_externes: List[Dict] # Liste d'objets import (nom, origine, niveau, est_star)


class GrapheProjet:
    """Représente les dépendances entre fichiers d'un projet."""
    
    def __init__(self, racine: Path):
        self.racine = racine
        self.fichiers: Dict[str, FichierAnalyse] = {}
        # Map: "nom.du.module" -> "chemin/vers/fichier.py"
        self.module_to_file: Dict[str, str] = {}
        self.imports_entre_fichiers: DefaultDict[str, Set[str]] = defaultdict(set)
        
    def ajouter_fichier(self, chemin_relatif: str, analyse: FichierAnalyse):
        """Ajoute un fichier analysé au graphe."""
        self.fichiers[chemin_relatif] = analyse
        # Convertit le chemin en nom de module Python
        module_path = chemin_relatif.replace('\\', '/').replace('.py', '')
        if module_path.endswith('/__init__'):
            module_path = module_path[:-9]
        module_name = module_path.replace('/', '.')
        self.module_to_file[module_name] = chemin_relatif

    def resoudre_imports(self):
        """Détermine les liens de dépendances entre les fichiers du projet."""
        for chemin, fichier in self.fichiers.items():
            for imp in fichier.imports_externes:
                cible_chemin = self._trouver_fichier_cible(chemin, imp)
                if cible_chemin and cible_chemin in self.fichiers:
                    self.imports_entre_fichiers[cible_chemin].add(chemin)
                    
                    # Si c'est un "from module import *", on considère toutes les entités
                    # du fichier cible comme potentiellement utilisées (principe de précaution)
                    if imp.get('est_star'):
                        for entite in self.fichiers[cible_chemin].entites.values():
                            entite.est_utilisee = True
                            entite.raison_utilisation = f"Import * dans {chemin}"

    def _trouver_fichier_cible(self, source_path: str, imp: Dict) -> Optional[str]:
        origine = imp['origine']
        niveau = imp['niveau']
        
        # 1. Gestion des imports relatifs (niveau > 0)
        if niveau > 0:
            parties_source = source_path.replace('\\', '/').split('/')
            # Si le fichier est un __init__.py, il compte comme le dossier lui-même
            if parties_source[-1] == '__init__.py':
                base_dir = parties_source[:-1]
            else:
                base_dir = parties_source[:-1]
            
            # Remonter les niveaux (..)
            for _ in range(niveau - 1):
                if base_dir: base_dir.pop()
            
            prefix_relatif = '.'.join(base_dir).replace('/', '.')
            module_complet = f"{prefix_relatif}.{origine}" if origine else prefix_relatif
            return self.module_to_file.get(module_complet)

        # 2. Gestion des imports absolus
        # On vérifie si le module ou ses parents existent dans notre projet
        parties_origine = origine.split('.')
        while parties_origine:
            module_test = '.'.join(parties_origine)
            if module_test in self.module_to_file:
                return self.module_to_file[module_test]
            parties_origine.pop() # On remonte (ex: monpkg.sous.func -> monpkg.sous)
            
        return None

    def est_utilise_par_autre_fichier(self, chemin: str, nom_entite: str) -> bool:
        """Vérifie si une entité est importée par un autre fichier."""
        if chemin not in self.fichiers:
            return False
        
        for importateur in self.imports_entre_fichiers.get(chemin, set()):
            if importateur not in self.fichiers:
                continue
            fichier_importateur = self.fichiers[importateur]

            # Vérifie si l'entité est utilisée dans le fichier importateur
            if (nom_entite in fichier_importateur.appels or 
                nom_entite in fichier_importateur.instanciations or 
                nom_entite in fichier_importateur.references or 
                nom_entite in fichier_importateur.type_hints):
                return True
        return False
    
    def resoudre_heritages_globaux(self):
        """Propage le statut 'utilisé' à travers la hiérarchie de classes."""
        
        # 1. Créer une map nom_classe -> entité pour un accès rapide
        toutes_classes = {}
        for fichier in self.fichiers.values():
            for entite in fichier.entites.values():
                if entite.type == 'classe':
                    toutes_classes[entite.nom] = entite

        # 2. Propagation ascendante : Si Enfant est vivant, Parent est vivant
        # On répète pour gérer les hiérarchies profondes (A <- B <- C)
        for _ in range(3): 
            changement = False
            for nom, entite in toutes_classes.items():
                if entite.est_utilisee:
                    for nom_parent in entite.bases:
                        if nom_parent in toutes_classes:
                            parent = toutes_classes[nom_parent]
                            if not parent.est_utilisee:
                                parent.est_utilisee = True
                                parent.raison_utilisation = f"Parent de {nom}"
                                changement = True
            if not changement: break

    def est_methode_polymorphe_utilisee(self, nom_methode: str, nom_classe: str) -> bool:
        """
        Vérifie si une méthode est appelée sur n'importe quelle classe 
        de la même lignée d'héritage.
        """
        # On regarde si ce nom de méthode est appelé n'importe où dans le projet
        # C'est une approche prudente pour éviter de supprimer des surcharges.
        for f in self.fichiers.values():
            if nom_methode in f.appels:
                return True
        return False

class ScannerProjet:
    def __init__(self, chemin_racine: str, config=None):
        self.racine = Path(chemin_racine).resolve()
        self.graphe = GrapheProjet(self.racine)
        self.erreurs: List[str] = []
        self.config = config
        self.exclusions_par_defaut = {
            'venv', '.venv', 'env', '__pycache__', '.git',
            '.tox', '.pytest_cache', '.mypy_cache', 'node_modules',
            '.idea', '.vscode', 'build', 'dist', '.DS_Store'
        }
        self.spec = self._charger_gitignore()

    def _charger_gitignore(self) -> Optional[pathspec.PathSpec]:
        """Charge le fichier .gitignore s'il existe à la racine."""
        gitignore_path = self.racine / ".gitignore"
        if gitignore_path.exists():
            try:
                lignes = gitignore_path.read_text().splitlines()
                return pathspec.PathSpec.from_lines('gitwildmatch', lignes)
            except Exception as e:
                print(f"Avertissement : impossible de lire .gitignore : {e}")
        return None

    def _doit_ignorer(self, chemin_relatif: str) -> bool:
        """Vérifie si un fichier ou dossier doit être ignoré."""
        path_obj = Path(chemin_relatif)
        
        # 1. Vérification des dossiers parents et du fichier contre les défauts
        # On vérifie si un des segments du chemin est dans les exclusions par défaut
        parties = path_obj.parts
        if any(p in self.exclusions_par_defaut for p in parties):
            return True
            
        # 2. Vérification contre le .gitignore (via pathspec)
        if self.spec and self.spec.match_file(chemin_relatif):
            return True
            
        # 3. Vérification des patterns de la config utilisateur (limbo.json)
        if self.config and self.config.exclude_patterns:
            if any(p in chemin_relatif for p in self.config.exclude_patterns):
                return True
                
        return False
        
    def scanner(self, config=None) -> GrapheProjet:
        """Lance l'analyse complète du projet."""
        fichiers_python = [p for p in self.racine.rglob("*.py") if not self._doit_ignorer(str(p.relative_to(self.racine)))]
        
        # Phase 1: Analyse individuelle de chaque fichier
        for chemin_absolu in fichiers_python:
            try:
                self._analyser_fichier(chemin_absolu)
            except Exception as e:
                self.erreurs.append(f"{chemin_absolu}: {e}")
                
        # Phase 2: Résolution des dépendances inter-fichiers
        self.graphe.resoudre_imports()
        
        # Phase 3: Évaluation globale
        self._evaluer_utilisation_globale()
        
        return self.graphe

    def _analyser_fichier(self, chemin_absolu: Path):
        """Analyse un fichier individuel."""
        rel = str(chemin_absolu.relative_to(self.racine))
        contenu = chemin_absolu.read_text(encoding='utf-8')
        
        # Analyse AST
        analyseur = AnalyseurAvance(rel, contenu)
        entites, appels, instanciations, references, type_hints, exports_all = analyseur.analyser()

        # Extrait les exports (ce qui est public)
        exports = set()
        for clef, entite in entites.items():
            if not entite.nom.startswith('_'):
                exports.add(entite.nom)
                
        # Extrait les imports pour résolution ultérieure
        imports_externes = self._extraire_imports_detailles(contenu)
        
        fichier_analyse = FichierAnalyse(
            chemin=rel,
            entites=entites,
            appels=appels,
            instanciations=instanciations,
            references=references,
            type_hints=type_hints,
            exports_all=exports_all,
            exports=exports,
            imports_externes=imports_externes
        )
        
        self.graphe.ajouter_fichier(rel, fichier_analyse)

    def _extraire_imports_detailles(self, contenu: str) -> List[Dict]:
        """Extrait les imports avec niveau et détection de star import."""
        resultats = []
        try:
            arbre = ast.parse(contenu)
            for node in ast.walk(arbre):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        resultats.append({'nom': alias.asname or alias.name, 'origine': alias.name, 'niveau': 0, 'est_star': False})
                elif isinstance(node, ast.ImportFrom):
                    est_star = any(alias.name == '*' for alias in node.names)
                    for alias in node.names:
                        resultats.append({
                            'nom': alias.asname or alias.name,
                            'origine': node.module or '',
                            'niveau': node.level,
                            'est_star': est_star
                        })
        except SyntaxError:
            pass
        return resultats
        
    def _evaluer_utilisation_globale(self):
        """Marque les entités utilisées via imports inter-fichiers."""
        for chemin, fichier in self.graphe.fichiers.items():
            for clef, entite in fichier.entites.items():
                if entite.est_utilisee:
                    continue  # Déjà marquée localement
                    
                # Vérifie si utilisée par un autre fichier
                if self.graphe.est_utilise_par_autre_fichier(chemin, entite.nom):
                    entite.est_utilisee = True
                    entite.raison_utilisation = f"Importée par autre fichier"


def analyser_projet_complet(chemin: str, config=None, deep: bool = False) -> ResultatProjet:
    """Analyse complète d'un projet et retourne les résultats structurés."""
    scanner = ScannerProjet(chemin, config)
    graphe = scanner.scanner(config)
    
    # Résolution de l'héritage avant l'analyse finale
    graphe.resoudre_heritages_globaux()
    
    # --- NOUVEAU : Collecter TOUS les appels et instanciations du projet ---
    appels_globaux = set()
    instanciations_globales = set()
    for f in graphe.fichiers.values():
        appels_globaux.update(f.appels)
        instanciations_globales.update(f.instanciations)
    
    total_lignes_projet = 0

    code_mort = []
    code_suspect = []
    imports_morts = {}
    variables_mortes = {}
    
    # Analyse chaque fichier avec le détecteur + comptage lignes
    for chemin_fichier, fichier in graphe.fichiers.items():
        # Compter les lignes du fichier
        try:
            p = Path(chemin) / chemin_fichier
            total_lignes_projet += len(p.read_text(encoding='utf-8').splitlines())
        except: 
            pass

        # On passe les appels GLOBAUX au détecteur
        detecteur = DetecteurLimbo(
            fichier.entites, 
            appels_globaux,
            instanciations_globales,
            fichier.references, 
            fichier.type_hints, 
            fichier.exports_all
        )
        
        morts, suspects, utilises = detecteur.analyser(recursive=deep)
        
        # Filtre final : vérifier si mort localement mais utilisé ailleurs dans le projet
        for entite in morts[:]:
            # 1. Vérification import classique
            if graphe.est_utilise_par_autre_fichier(chemin_fichier, entite.nom):
                morts.remove(entite)
                entite.est_utilisee = True
                continue
            
            # 2. Vérification Polymorphisme (pour les méthodes)
            if entite.type in ['methode', 'staticmethod', 'classmethod']:
                if graphe.est_methode_polymorphe_utilisee(entite.nom, entite.classe_parent):
                    morts.remove(entite)
                    entite.est_utilisee = True
                    entite.raison_utilisation = "Surcharge potentielle (Polymorphisme)"
        code_mort.extend([(chemin_fichier, m) for m in morts])
        code_suspect.extend([(chemin_fichier, s) for s in suspects])
            
        try:
            abs_p = str(Path(chemin) / chemin_fichier)
            imports_morts[chemin_fichier] = analyser_imports_fichier(abs_p)
            variables_mortes[chemin_fichier] = trouver_variables_inutilisees(Path(abs_p).read_text(encoding='utf-8'))
        except:
            imports_morts[chemin_fichier] = []
            variables_mortes[chemin_fichier] = []

    # Détection des doublons
    signatures = defaultdict(list)
    for chemin_f, fichier in graphe.fichiers.items():
        for entite in fichier.entites.values():
            if entite.signature_structurelle: # On n'analyse que si une signature existe
                signatures[entite.signature_structurelle].append((chemin_f, entite))
        
    doublons = []
    for sig, membres in signatures.items():
        if len(membres) > 1:
            doublons.append(GroupeDuplique(signature=sig, entites=membres))
    
    return ResultatProjet(
        fichiers_analyses=len(graphe.fichiers),
        total_lignes=total_lignes_projet,
        code_mort=code_mort,
        code_suspect=code_suspect,
        imports_morts_par_fichier=imports_morts,
        variables_mortes_par_fichier=variables_mortes,
        erreurs=scanner.erreurs,
        doublons=doublons
    )