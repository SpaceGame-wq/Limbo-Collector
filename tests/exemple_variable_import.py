# tests/exemple_complet.py
# Test complet de toutes les fonctionnalités

import os           # MORT
import sys          # MORT
from json import dumps  # MORT
from datetime import datetime  # UTILISÉ

def fonction_propre(x, y):
    """Fonction propre, tout est utilisé."""
    resultat = x + y  # 'resultat' est utilisé
    return resultat

def fonction_sale():
    """Fonction avec variables inutilisées."""
    inutile = 42      # MORT - jamais lu
    temp = "hello"    # MORT - jamais lu  
    utilise = 10      # OK - utilisé ci-dessous
    return utilise

def boucle_perdue():
    """Boucle avec variable inutilisée."""
    for i in range(10):  # 'i' est MORT - jamais utilisée dans la boucle
        print("iteration")
    
    data = [1, 2, 3]     # MORT - jamais utilisée
    return None

def jamais_appelée():
    """Cette fonction existe mais n'est importée nulle part."""
    x = 1  # MORT aussi (puisque fonction morte)
    return x

class Vivante:
    """Cette classe est instanciée."""
    def __init__(self):
        self.nom = "test"

class Fantome:
    """Cette classe n'est jamais utilisée."""
    pass

# Code actif
if __name__ == "__main__":
    fonction_propre(1, 2)
    fonction_sale()
    boucle_perdue()
    now = datetime.now()
    v = Vivante()