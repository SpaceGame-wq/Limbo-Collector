from robots import RobotAspirateur

def lancer_nettoyage():
    bot = RobotAspirateur()
    bot.démarrer()   # Appel d'une méthode définie dans le grand-parent (Machine)
    bot.travailler() # Appel d'une méthode définie dans l'enfant (RobotAspirateur)

if __name__ == "__main__":
    lancer_nettoyage()