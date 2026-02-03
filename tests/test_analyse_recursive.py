def racine(): # Vivante (ex: point d'entrée API)
    etape_1()

def etape_1(): # Vivante (appelée par racine)
    etape_2()

def etape_2(): # Vivante (appelée par etape_1)
    print("Action")

def fonction_isolee(): # MORTE
    aide_isolee()

def aide_isolee(): # MORTE (appelée uniquement par une fonction morte)
    print("Je ne sers à rien")