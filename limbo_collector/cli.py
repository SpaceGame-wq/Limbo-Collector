import argparse
import sys
from pathlib import Path

from .scanner import trouver_code_mort


def main():
    parser = argparse.ArgumentParser(
        description="Limbo Collector - Trouve le code Python oublié"
    )
    parser.add_argument(
        "fichier",
        help="Le fichier Python à analyser"
    )
    
    args = parser.parse_args()
    
    if not Path(args.fichier).exists():
        print(f"Erreur : Le fichier {args.fichier} n'existe pas.")
        sys.exit(1)
    
    print(f"Analyse de {args.fichier}...")
    print("-" * 40)
    
    morts, peut_etre = trouver_code_mort(args.fichier)
    
    if morts:
        print(f"\nCode SÛREMENT mort ({len(morts)} trouvé) :")
        for obj in morts:
            print(f"  - {obj.type} '{obj.nom}' (ligne {obj.ligne})")
    
    if peut_etre:
        print(f"\nCode PEUT-ÊTRE mort ({len(peut_etre)} trouvé) :")
        for obj in peut_etre:
            print(f"  - {obj.type} '{obj.nom}' (ligne {obj.ligne})")
    
    if not morts and not peut_etre:
        print("\nAucun code mort détecté. Fichier propre !")
        
    print("-" * 40)


if __name__ == "__main__":
    main()