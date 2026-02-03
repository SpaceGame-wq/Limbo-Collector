from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set

@dataclass
class CodeEntity:
    """Représente une fonction, une méthode ou une classe."""
    nom: str
    type: str  # 'fonction', 'classe', 'methode', 'staticmethod', etc.
    ligne: int
    fichier: str
    bases: List[str] = field(default_factory=list)
    classe_parent: Optional[str] = None
    decorateurs: List[str] = field(default_factory=list)
    est_utilisee: bool = False
    raison_utilisation: str = ""
    est_ignoree: bool = False
    signature_structurelle: str = ""
    appels_sortants: Set[str] = field(default_factory=set)

@dataclass
class ImportInutile:
    """Représente un import détecté comme inutile."""
    nom: str
    ligne: int
    type: str  # 'import' ou 'from'
    module_source: str = ""

@dataclass
class VariableInutilisee:
    """Représente une variable locale assignée mais non lue."""
    nom: str
    ligne: int
    fonction_parent: str
    type_assignation: str

@dataclass
class CodeUnreachable:
    """Représente du code inaccessible (après return, break, etc.)."""
    ligne_debut: int
    ligne_fin: int
    type: str
    description: str

@dataclass
class ParametreInutilise:
    """Représente un paramètre de fonction non utilisé."""
    nom: str
    ligne: int
    fonction: str
    position: int
    est_kwargs: bool
    est_args: bool

@dataclass
class GroupeDuplique:
    signature: str
    entites: List[Tuple[str, CodeEntity]] # (chemin, entite)