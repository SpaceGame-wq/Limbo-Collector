class Machine:
    def démarrer(self):
        print("La machine démarre...")

class Robot(Machine):
    def travailler(self):
        pass

# Cette classe n'est jamais utilisée ni héritée
class VieilleRelique:
    def ramasser_poussiere(self):
        pass