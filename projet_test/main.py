from utils import calculer_total, formater_nom
from models import Utilisateur

def main():
    # On utilise calculer_total
    prix = calculer_total([10, 20, 30])
    
    # On utilise formater_nom
    nom = formater_nom("jean", "dupont")
    
    # On instancie Utilisateur
    user = Utilisateur("Alice")
    print(f"{nom}: {prix}€ - {user.nom}")

if __name__ == "__main__":
    main()