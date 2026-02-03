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
        """Calcule un score de 0 à 100."""
        if self.total_lignes == 0: return 100.0
        
        # Pondération des problèmes
        poids = {
            'classe_morte': 8,
            'fonction_morte': 5,
            'unreachable': 4,
            'import_mort': 1,
            'variable_globale_morte': 2,
            'variable_morte': 1,
            'param_mort': 1
        }
        
        penalite = (
            len([e for _, e in self.code_mort if e.type == 'classe']) * poids['classe_morte'] +
            len([e for _, e in self.code_mort if e.type != 'classe']) * poids['fonction_morte'] +
            len([e for _, e in self.code_mort if e.type == 'variable_globale']) * poids['variable_globale_morte'] +
            sum(len(v) for v in self.imports_morts_par_fichier.values()) * poids['import_mort'] +
            sum(len(v) for v in self.variables_mortes_par_fichier.values()) * poids['variable_morte'] +
            self.stats_unreachable * poids['unreachable'] +
            self.stats_parametres * poids['param_mort']
        )
        
        # Le score est basé sur la densité de problèmes par rapport à la taille du projet
        # Plus le projet est grand, plus il "encaisse" de petites erreurs
        densite = (penalite / (self.total_lignes / 100)) * 2 
        score = max(0, 100 - densite)
        return round(score, 1)


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
    imports_externes: Dict[str, str]  # nom -> origine (fichier ou module)


class GrapheProjet:
    """Représente les dépendances entre fichiers d'un projet."""
    
    def __init__(self, racine: Path):
        self.racine = racine
        self.fichiers: Dict[str, FichierAnalyse] = {}
        self.imports_entre_fichiers: DefaultDict[str, Set[str]] = defaultdict(set)
        self.modules_projet: Set[str] = set()
        
    def ajouter_fichier(self, chemin_relatif: str, analyse: FichierAnalyse):
        """Ajoute un fichier analysé au graphe."""
        self.fichiers[chemin_relatif] = analyse
        self.modules_projet.add(chemin_relatif.replace('/', '.').replace('\\', '.').replace('.py', ''))
        
    def resoudre_imports(self):
        """Détermine quels imports pointent vers d'autres fichiers du projet."""
        for chemin, fichier in self.fichiers.items():
            for nom, origine in fichier.imports_externes.items():
                # Vérifie si l'import vient d'un fichier du projet
                if origine.startswith('.'):
                    # Import relatif
                    cible = self._resoudre_import_relatif(chemin, origine)
                    if cible and cible in self.fichiers:
                        self.imports_entre_fichiers[cible].add(chemin)
                else:
                    # Import absolu, vérifie si c'est un module du projet
                    cible = origine.replace('.', '/') + '.py'
                    if cible in self.fichiers:
                        self.imports_entre_fichiers[cible].add(chemin)
                        
    def _resoudre_import_relatif(self, source: str, import_rel: str) -> Optional[str]:
        """Résout un import relatif (ex: from . import x ou from .. import y)."""
        niveaux = 0
        i = 0
        while i < len(import_rel) and import_rel[i] == '.':
            niveaux += 1
            i += 1
            
        parties_source = source.replace('\\', '/').split('/')[:-1]  # Enlève le nom de fichier
        
        if niveaux > len(parties_source):
            return None  # Import impossible
            
        base = parties_source[:-niveaux] if niveaux > 0 else parties_source
        reste = import_rel[i:].replace('.', '/')
        
        if reste:
            return '/'.join(base + [reste]) + '.py'
        else:
            # from . import module
            return '/'.join(base) + '.py'
            
    def est_utilise_par_autre_fichier(self, chemin: str, nom_entite: str) -> bool:
        """Vérifie si une entité est importée par un autre fichier."""
        if chemin not in self.fichiers:
            return False
            
        fichier = self.fichiers[chemin]
        
        # Regarde tous les fichiers qui importent celui-ci
        for importateur in self.imports_entre_fichiers.get(chemin, set()):
            if importateur not in self.fichiers:
                continue
            fichier_importateur = self.fichiers[importateur]
            
            # Vérifie si l'entité est utilisée dans le fichier importateur
            if nom_entite in fichier_importateur.appels:
                return True
            if nom_entite in fichier_importateur.instanciations:
                return True
            if nom_entite in fichier_importateur.references:
                return True
            # Vérifie si utilisé comme type hint dans un autre fichier
            if nom_entite in fichier_importateur.type_hints:
                return True
                
        return False


class ScannerProjet:
    """Analyse complète d'un projet Python."""
    
    def __init__(self, chemin_racine: str, config=None):
        self.racine = Path(chemin_racine).resolve()
        self.graphe = GrapheProjet(self.racine)
        self.erreurs: List[str] = []
        self.config = config
        
        # Patterns d'exclusion par défaut (même sans .gitignore)
        self.exclusions_par_defaut = {
            'venv', '.venv', 'env', '__pycache__', '.git', 
            '.tox', '.pytest_cache', '.mypy_cache', 'node_modules',
            '.idea', '.vscode', 'build', 'dist', '.DS_Store'
        }
        
        # Chargement du pathspec (.gitignore)
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
        fichiers_python = self._trouver_fichiers_python()
        
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
        
    def _trouver_fichiers_python(self) -> List[Path]:
        """Trouve tous les fichiers Python en respectant les filtres."""
        fichiers = []
        for chemin in self.racine.rglob("*.py"):
            # Obtenir le chemin relatif par rapport à la racine du projet
            rel = str(chemin.relative_to(self.racine))
            
            # Application de notre nouvelle logique de filtrage
            if not self._doit_ignorer(rel):
                fichiers.append(chemin)
                
        return fichiers

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
        imports_externes = self._extraire_imports(contenu)
        
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

    def _extraire_imports(self, contenu: str) -> Dict[str, str]:
        """Extrait tous les imports d'un fichier."""
        imports = {}
        try:
            arbre = ast.parse(contenu)
            for node in ast.walk(arbre):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        nom = alias.asname or alias.name
                        imports[nom] = alias.name
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    niveau = node.level  # 0 = absolu, 1 = relatif, 2 = parent, etc.
                    
                    prefix = "." * niveau
                    if module:
                        origine = prefix + module
                    else:
                        origine = prefix
                        
                    for alias in node.names:
                        nom = alias.asname or alias.name
                        imports[nom] = origine + "." + alias.name if origine else alias.name
        except SyntaxError:
            pass
        return imports
        
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
    scanner = ScannerProjet(chemin)
    graphe = scanner.scanner(config)
    
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

        detecteur = DetecteurLimbo(
            fichier.entites,
            fichier.appels,
            fichier.instanciations,
            fichier.references,
            fichier.type_hints,
            fichier.exports_all
        )
        
        morts, suspects, utilises = detecteur.analyser(recursive=deep)
        
        # Filtre: une entité "morte" localement mais exportée et utilisée ailleurs
        # est en fait vivante
        for entite in morts[:]:
            if graphe.est_utilise_par_autre_fichier(chemin_fichier, entite.nom):
                morts.remove(entite)
                entite.raison_utilisation = "Utilisée via import"
                # Ne pas ajouter à suspects, c'est vraiment utilisée
        
        for m in morts:
            code_mort.append((chemin_fichier, m))
        for s in suspects:
            code_suspect.append((chemin_fichier, s))
            
        # Imports inutilisés (analyse locale seulement)
        try:
            chemin_absolu = Path(chemin) / chemin_fichier
            imports_morts[chemin_fichier] = analyser_imports_fichier(str(chemin_absolu))
        except Exception:
            imports_morts[chemin_fichier] = []
            
        # Variables inutilisées
        try:
            contenu = (Path(chemin) / chemin_fichier).read_text(encoding='utf-8')
            variables_mortes[chemin_fichier] = trouver_variables_inutilisees(contenu)
        except Exception:
            variables_mortes[chemin_fichier] = []

    # Après avoir collecté toutes les entités, on cherche les doublons
    toutes_les_entites = []
    for chemin_f, fichier in graphe.fichiers.items():
        for entite in fichier.entites.values():
            if entite.signature_structurelle: # On n'analyse que si une signature existe
                toutes_les_entites.append((chemin_f, entite))
                
    # Regroupement par signature
    signatures = defaultdict(list)
    for chemin_f, entite in toutes_les_entites:
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