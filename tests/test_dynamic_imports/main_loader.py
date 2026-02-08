import importlib

def charger_plugins_dynamiquement():
    plugins_a_charger = ["payment", "auth"]
    
    for nom in plugins_a_charger:
        # CAS 1 : F-String
        # Le scanner doit détecter le préfixe "plugins." et sauver tout ce qui commence par ça
        try:
            mod = importlib.import_module(f"plugins.{nom}")
            mod.process()
        except ImportError:
            pass

def charger_legacy():
    # CAS 2 : Chaîne exacte via __import__
    # Le scanner doit sauver le fichier "legacy_lib.py"
    ancien_module = __import__("legacy_lib")
    ancien_module.run()

def charger_avec_concat(nom_service):
    # CAS 3 : Concaténation (supporté par votre nouveau code)
    # Le scanner doit détecter "plugins."
    importlib.import_module("plugins." + nom_service)

if __name__ == "__main__":
    charger_plugins_dynamiquement()
    charger_legacy()