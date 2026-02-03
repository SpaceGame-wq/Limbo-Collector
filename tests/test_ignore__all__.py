# Ce code ne sera jamais marqué comme mort
def fonction_obsolete():  # limbo: ignore
    pass

# limbo: ignore
def une_autre_fonction():
    pass

class MaClasse:
    # Cette méthode ne sera pas rapportée
    def methode_cachee(self):  # no-limbo
        pass

# Ou via __all__ (souvent dans __init__.py)
__all__ = ["OutilPublic"]

class OutilPublic:
    pass # Sera considéré comme utilisé car présent dans __all__