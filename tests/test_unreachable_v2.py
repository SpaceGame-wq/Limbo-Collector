"""
TEST ULTIME POUR LIMBO COLLECTOR (MOTEUR D'INTERPRÉTATION ABSTRAITE).
Ce fichier contient du code qui semble vivant syntaxiquement,
mais qui est mort logiquement selon l'état de la mémoire simulée.
"""
import sys
import os

def test_arithmetique_et_logique():
    """Test 1: Le moteur sait calculer."""
    x = 10
    y = 5
    z = x + y  # 15
    
    if z == 15:
        print("Vivant : 10 + 5 font bien 15")
    else:
        print("MORT : Impossible mathématiquement")  # DÉTECTION ATTENDUE

    if (x > y) and (z < 20):
        print("Vivant : Conditions multiples")
    else:
        print("MORT : Logique booléenne")  # DÉTECTION ATTENDUE

def test_structures_donnees():
    """Test 2: Le moteur comprend les Listes et Dicts."""
    ma_liste = [10, 20, 30]
    mon_dict = {"cle": "valeur"}
    
    # Test accès index
    if ma_liste[1] == 20:
        print("Vivant : Accès index correct")
    else:
        print("MORT : ma_liste[1] vaut 20")  # DÉTECTION ATTENDUE

    # Test accès dictionnaire
    if mon_dict["cle"] == "valeur":
        print("Vivant : Accès clé correct")
    else:
        print("MORT : mon_dict['cle'] vaut 'valeur'")  # DÉTECTION ATTENDUE
    
    # Test len()
    if len(ma_liste) == 3:
        pass
    else:
        print("MORT : len() incorrect")  # DÉTECTION ATTENDUE

def test_state_merging(condition_externe):
    """Test 3: Fusion d'états (Branching & Merging)."""
    x = 0
    
    # Peu importe la branche, x devient 5
    if condition_externe:
        x = 5
    else:
        x = 5
    
    # Ici, le moteur doit savoir que x vaut 5, même si la condition était inconnue
    if x == 5:
        print("Vivant : Fusion d'états réussie")
    else:
        print("MORT : x vaut 5 dans toutes les branches")  # DÉTECTION ATTENDUE

def test_boucles_infinies_intelligentes():
    """Test 4: Boucles infinies sans 'while True' explicite."""
    running = True
    
    while running:
        print("Je tourne...")
        # Pas de break, pas de modification de 'running'
        # Le moteur doit détecter que c'est infini
    
    print("MORT : Code après boucle infinie (variable constante)")  # DÉTECTION ATTENDUE

def test_assertions_et_exit():
    """Test 5: Arrêts brutaux."""
    assert True
    print("Vivant")
    
    if 1 == 1:
        sys.exit(0)
    
    print("MORT : Après sys.exit()")  # DÉTECTION ATTENDUE

    assert False
    print("MORT : Après assert False")  # DÉTECTION ATTENDUE

def test_loop_unrolling():
    """Test 6: Simulation de boucle For sur constantes."""
    # Le moteur va dérouler cette boucle : i=1, i=2, i=3
    last_val = 0
    for i in [1, 2, 3]:
        last_val = i
        if i == 4:
            print("MORT : 4 n'est pas dans la liste")  # DÉTECTION ATTENDUE (Interne à la boucle)

    if last_val == 3:
        print("Vivant : État final de boucle connu")
    else:
        print("MORT : last_val doit valoir 3")  # DÉTECTION ATTENDUE

def test_types_isinstance():
    """Test 7: Vérification de types."""
    txt = "Hello"
    num = 42
    
    if isinstance(txt, str):
        print("Vivant")
    else:
        print("MORT : txt est une string")  # DÉTECTION ATTENDUE

    if isinstance(num, list):
        print("MORT : num n'est pas une liste")  # DÉTECTION ATTENDUE

def test_try_except_complex():
    """Test 8: Flux d'exceptions."""
    try:
        return "Sortie"
    except ValueError:
        pass
    else:
        print("MORT : Else inatteignable car return dans Try")  # DÉTECTION ATTENDUE

    try:
        x = 1/0
    except Exception:
        print("Générique")
    except ZeroDivisionError:
        print("MORT : Masqué par Exception")  # DÉTECTION ATTENDUE

if __name__ == "__main__":
    # Pour que Python ne râle pas si on l'exécute, 
    # mais Limbo l'analyse statiquement.
    pass