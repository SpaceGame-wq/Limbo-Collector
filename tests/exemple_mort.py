# Ce fichier sert à tester Limbo Collector
# Certaines fonctions sont utilisées, d'autres non

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