from typing import List, Optional, Dict
from datetime import datetime  # Utilisé via type hint
import os  # MORT - pas de type hint

# Classe utilisée uniquement comme type hint
class Config:
    valeur: str
    
    def load(self):
        pass

class Service:
    """Utilisée via instanciation ET type hint."""
    def process(self):
        return "ok"

class Repository:
    """Utilisée uniquement comme type hint."""
    def find(self):
        pass

class Unused:
    """Jamais utilisée."""
    pass

def traiter(config: Config, repo: Repository) -> Service:
    """
    'Config' et 'Repository' utilisés comme type hint.
    Retourne Service.
    """
    s = Service()  # Instanciation
    return s

def liste_configs() -> List[Config]:
    """Retourne List[Config] - Config utilisé comme type hint."""
    return []

def optional_repo(repo: Optional[Repository] = None) -> Dict[str, Config]:
    """Optional et Dict utilisés, Repository et Config aussi."""
    return {}

def mauvais(x: datetime) -> os:  # 'os' n'est pas un type valide, mais est utilisé comme hint
    return x

# Code actif
if __name__ == "__main__":
    resultat = traiter(Config(), Repository())  # Ici Config et Repository sont instanciés