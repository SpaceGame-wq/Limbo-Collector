# tests/exemple_mort.py
# Ce fichier sert à tester Limbo Collector

import os           # SÛREMENT MORT - jamais utilisé
import sys          # SÛREMENT MORT - jamais utilisé  
import json as js   # SÛREMENT MORT - alias jamais utilisé
from pathlib import Path  # SÛREMENT MORT - jamais utilisé
from datetime import datetime  # UTILISÉ - utilisé ci-dessous

def calcul_active(x, y):
    """Celle-ci est utilisée ci-dessous."""
    return x + y

def fonction_oubliee():
    """Personne ne m'appelle jamais."""
    return "Je flotte dans le limbo"

class Utilisee:
    def methode(self):
        return "ok"

class ClasseIsolée:
    """Cette classe existe mais ne sert à rien."""
    pass

# Code qui tourne vraiment
resultat = calcul_active(2, 3)
print(resultat)

# Utilisation de datetime
now = datetime.now()