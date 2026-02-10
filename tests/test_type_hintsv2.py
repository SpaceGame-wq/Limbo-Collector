class User:
    def save(self):
        """Cette méthode doit être VIVANTE car sync(u: User) l'appelle."""
        print("User sauvegardé")

class Product:
    def save(self):
        """Cette méthode doit être MORTE car personne n'appelle Product.save."""
        print("Product sauvegardé")

def main_process(u: User):
    # Ici, le Type Hint 'User' permet à Limbo de savoir 
    # que u.save() appelle User.save et NON Product.save
    u.save()

if __name__ == "__main__":
    # Point d'entrée pour rendre main_process vivant
    from unittest.mock import Mock
    main_process(Mock(spec=User))