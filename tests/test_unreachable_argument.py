import os  # MORT
import sys  # MORT

def exemple_unreachable(x, y, z):
    """Test code unreachable et paramètres."""
    if False:  # Unreachable
        print("jamais exécuté")
    
    return x + y  # 'z' est paramètre inutilisé
    
    print("après return")  # Unreachable

def params_inutilises(a, b, c):
    """'a' et 'c' inutilisés."""
    return b * 2

def tout_utilise(x, y):
    """Correct."""
    return x + y

while False:  # Unreachable
    print("boucle inutile")

class Test:
    def methode(self, inutilise):  # 'inutilise' paramètre mort
        return "ok"