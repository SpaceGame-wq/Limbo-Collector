class Utilisateur:
    """UTILISÉE - importée dans main.py"""
    def __init__(self, nom):
        self.nom = nom

class Commande:
    """PEUT-ÊTRE MORTE - définie mais jamais importée"""
    def __init__(self):
        self.items = []