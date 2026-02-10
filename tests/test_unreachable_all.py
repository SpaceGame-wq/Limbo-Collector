"""
Fichier de test complet pour Limbo Collector (Module Unreachable).
Version corrigée (sans SyntaxError).
"""
import sys

def demo_interruption_flux():
    print("Début du flux")
    sys.exit(0)
    print("JE SUIS MORT : après sys.exit()") # DÉTECTÉ

def demo_if_while():
    if False:
        print("JE SUIS MORT : bloc if False") # DÉTECTÉ
    
    if True:
        print("Bloc If True")
    else:
        print("JE SUIS MORT : bloc else après if True") # DÉTECTÉ
        
    while False:
        print("JE SUIS MORT : boucle while False") # DÉTECTÉ

def demo_try_except_else():
    # Test 1 : Shadowing d'exceptions
    try:
        x = 1 / 0
    except Exception:
        print("Capture tout")
    except ZeroDivisionError:
        print("JE SUIS MORT : masqué par 'except Exception'") # DÉTECTÉ

    # Test 2 : Else inatteignable
    try:
        print("Action")
        return True
    except:
        print("Erreur")
    else:
        print("JE SUIS MORT : le try finit toujours par un return") # DÉTECTÉ

def demo_match_case(valeur):
    """Note : Syntaxiquement correct en Python 3.10+"""
    match valeur:
        case 1:
            return "Un"
            print("JE SUIS MORT : après return dans un case") # DÉTECTÉ
        case 2 if False:
            print("JE SUIS MORT : garde toujours fausse") # DÉTECTÉ
        case _:
            print("Wildcard (capture tout)")

def demo_boucles_et_sorties():
    for i in range(5):
        if i == 2:
            break
            print("JE SUIS MORT : après break") # DÉTECTÉ
        
        if i == 1:
            continue
            print("JE SUIS MORT : après continue") # DÉTECTÉ

    return "Fin"
    print("JE SUIS MORT : après return final") # DÉTECTÉ

def demo_raise():
    raise ValueError("Erreur fatale")
    print("JE SUIS MORT : après raise") # DÉTECTÉ

if __name__ == "__main__":
    demo_if_while()
    demo_try_except_else()
    demo_match_case(1)