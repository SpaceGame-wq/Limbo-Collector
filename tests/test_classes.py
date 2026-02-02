# tests/test_classes.py
# Test de la détection avancée des classes

from datetime import datetime  # MORT
import json  # MORT


class Animal:
    """Classe de base - certaines méthodes seront héritées."""
    
    def __init__(self, nom):  # UTILISÉ (instanciation)
        self.nom = nom
    
    def parler(self):  # SERA UTILISÉ via héritage
        raise NotImplementedError
    
    def manger(self):  # MORT - jamais appelé
        print("miam")
    
    def __str__(self):  # UTILISÉ (méthode magique)
        return f"Animal({self.nom})"


class Chien(Animal):
    """Classe fille - hérite de Animal."""
    
    def parler(self):  # UTILISÉ (redéfinition)
        return "Wouf!"
    
    def aboyer(self):  # MORT - jamais appelé
        return self.parler()
    
    @classmethod
    def race(cls):  # MORT - classmethod non appelée
        return "Canis"


class Chat(Animal):
    """Autre classe fille."""
    
    def parler(self):  # UTILISÉ
        return "Miaou!"


class Utilitaire:
    """Classe jamais utilisée."""
    
    @staticmethod
    def helper():  # MORT (classe jamais instanciée)
        return "aide"
    
    def instance_method(self):  # MORT
        pass


# Code actif
if __name__ == "__main__":
    rex = Chien("Rex")  # Chien instancié
    print(rex.parler())  # parler() appelé
    
    felix = Chat("Felix")  # Chat instancié
    print(felix.parler())
    
    # manger() n'est jamais appelé
    # aboyer() n'est jamais appelé
    # Utilitaire n'est jamais utilisé