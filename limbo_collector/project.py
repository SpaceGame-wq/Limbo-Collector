import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple
from .scanner import ScannerLimbo, ObjetCode


class LimboProject:
    def __init__(self, chemin_dossier: str):
        self.racine = Path(chemin_dossier)
        self.fichiers_python: List[Path] = []
        self.definitions_globales: Dict[str, ObjetCode] = {}  # nom -> objet
        self.imports_par_fichier: Dict[str, Set[str]] = {}    # fichier -> {noms importés}
        self.appels_globaux: Set[str] = set()
        
    def scanner_dossier(self):
        """Trouve tous les .py et analyse chacun."""
        self.fichiers_python = list(self.racine.rglob("*.py"))
        
        for fichier in self.fichiers_python:
            if "venv" in str(fichier) or "__pycache__" in str(fichier):
                continue
                
            rel_path = str(fichier.relative_to(self.racine))
            scanner = ScannerLimbo(rel_path)
            
            try:
                contenu = fichier.read_text(encoding='utf-8')
                definitions, appels = scanner.analyser(contenu)
                
                # Stocke les définitions (avec préfixe fichier pour éviter collisions)
                for obj in definitions:
                    clef = f"{rel_path}::{obj.nom}"
                    self.definitions_globales[clef] = obj
                    
                self.appels_globaux.update(appels)
                
                # Extrait les imports pour analyse croisée
                self.imports_par_fichier[rel_path] = self._extraire_imports(contenu)
                
            except Exception as e:
                print(f"Erreur lecture {fichier}: {e}")
    
    def _extraire_imports(self, contenu: str) -> Set[str]:
        """Trouve tous les noms importés dans un fichier."""
        imports = set()
        try:
            arbre = ast.parse(contenu)
            for node in ast.walk(arbre):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.add(alias.asname or alias.name)
        except:
            pass
        return imports
    
    def trouver_mort_global(self) -> Tuple[List[ObjetCode], List[ObjetCode]]:
        """Détecte le code mort à l'échelle du projet."""
        morts = []
        peut_etre = []
        
        # Entry points connus (scripts exécutables)
        entry_points = {'main', 'run', 'app', 'manage'}
        
        for clef, obj in self.definitions_globales.items():
            nom_simple = obj.nom
            
            # Si c'est un entry point, on considère utilisé
            if nom_simple in entry_points:
                continue
                
            # Si appelé explicitement ailleurs
            if nom_simple in self.appels_globaux:
                continue
                
            # Si importé dans un autre fichier (même si pas appelé, c'est public)
            est_importe = any(
                nom_simple in imports 
                for imports in self.imports_par_fichier.values()
            )
            if est_importe:
                continue
                
            # Si c'est une classe, elle pourrait être utilisée via type hint
            if obj.type == 'classe':
                peut_etre.append(obj)
            else:
                morts.append(obj)
                
        return morts, peut_etre
    
    def rapport(self) -> str:
        """Génère un rapport texte complet."""
        morts, peut_etre = self.trouver_mort_global()
        
        lignes = []
        lignes.append("=" * 60)
        lignes.append("LIMBO COLLECTOR - Rapport d'analyse")
        lignes.append(f"Dossier: {self.racine}")
        lignes.append(f"Fichiers analysés: {len(self.fichiers_python)}")
        lignes.append("=" * 60)
        
        if morts:
            lignes.append(f"\nFONCTIONS SÛREMENT MORTES ({len(morts)}):")
            for obj in morts:
                lignes.append(f"  {obj.fichier}:{obj.ligne} → {obj.nom}()")
                
        if peut_etre:
            lignes.append(f"\nCLASSES PEUT-ÊTRE MORTES ({len(peut_etre)}):")
            for obj in peut_etre:
                lignes.append(f"  {obj.fichier}:{obj.ligne} → class {obj.nom}")
                
        if not morts and not peut_etre:
            lignes.append("\nAucun code mort détecté. Projet propre !")
            
        return "\n".join(lignes)