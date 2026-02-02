import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Set


@dataclass
class LimboConfig:
    """Configuration pour ignorer certains patterns."""
    
    # Ignorer ces fonctions/classes (regex patterns)
    ignore_fonctions: List[str] = None
    ignore_classes: List[str] = None
    
    # Ignorer ces imports (modules toujours OK)
    ignore_modules: List[str] = None
    
    # Ignorer les variables avec ces préfixes
    ignore_variables_prefix: List[str] = None
    
    # Fichiers/dossiers à exclure de l'analyse
    exclude_patterns: List[str] = None
    
    # Seuil de confiance (0.0 à 1.0)
    strict_mode: bool = False
    
    def __post_init__(self):
        if self.ignore_fonctions is None:
            self.ignore_fonctions = ['main', 'run', 'app', 'cli', 'wsgi', 'asgi']
        if self.ignore_classes is None:
            self.ignore_classes = ['BaseModel', 'Config', 'Meta']
        if self.ignore_modules is None:
            self.ignore_modules = ['__future__', 'typing', 'pytest', 'unittest']
        if self.ignore_variables_prefix is None:
            self.ignore_variables_prefix = ['_', 'unused', 'tmp', 'temp']
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                'venv', '.venv', 'env', 
                '__pycache__', '.git', 
                'migrations', 'alembic',
                'node_modules', '.tox'
            ]
    
    @classmethod
    def depuis_fichier(cls, chemin: str = None) -> 'LimboConfig':
        """Charge depuis limbo.json ou retourne défaut."""
        if chemin is None:
            chemin = 'limbo.json'
        
        path = Path(chemin)
        if path.exists():
            data = json.loads(path.read_text(encoding='utf-8'))
            return cls(**data)
        return cls()
    
    def sauvegarder(self, chemin: str = 'limbo.json'):
        """Sauvegarde la config dans un fichier."""
        Path(chemin).write_text(
            json.dumps(asdict(self), indent=2),
            encoding='utf-8'
        )
    
    def doit_ignorer_fichier(self, chemin: str) -> bool:
        """Vérifie si un fichier doit être exclu."""
        chemin_lower = chemin.lower()
        for pattern in self.exclude_patterns:
            if pattern.lower() in chemin_lower:
                return True
        return False
    
    def est_fonction_ignoree(self, nom: str) -> bool:
        return nom in self.ignore_fonctions
    
    def est_import_ignore(self, module: str) -> bool:
        return any(module.startswith(m) for m in self.ignore_modules)
    
    def est_variable_ignoree(self, nom: str) -> bool:
        return any(nom.startswith(p) for p in self.ignore_variables_prefix)