def calculer_total(items):
    """Utilisée dans main.py"""
    return sum(items)

def formater_nom(prenom, nom):
    """Utilisée dans main.py"""
    return f"{prenom.title()} {nom.upper()}"

def formater_date(date_str):
    """SÛREMENT MORTE - jamais importée"""
    return date_str.replace("-", "/")

def ancienne_fonction_api():
    """SÛREMENT MORTE - code legacy oublié"""
    return "Cette API n'existe plus"