import json
import math
from pathlib import Path
from datetime import datetime
from collections import Counter
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .project_scanner import ResultatProjet

# Fonction pour formater les grands nombres
def number_format_filter(value):
    return "{:,}".format(value).replace(',', ' ')

# Filtre pour créer un chemin absolu (utile pour les liens VS Code/PyCharm)
def absolute_path_filter(rel_path):
    # Chemin absolu du fichier analysé (nécessaire pour les liens externes)
    return str(Path.cwd() / rel_path).replace('\\', '/')

def generer_rapport_html(resultat: ResultatProjet, chemin_sortie: str):
    """Génère un rapport HTML riche et interactif."""
    
    score = resultat.calculer_score_sante()
    
    if score >= 90:
        appreciation_titre = "Excellent"
        appreciation_detail = "Le projet est dans un état de propreté remarquable. Continuez comme ça !"
        score_color = "#3fb950"
    elif score >= 75:
        appreciation_titre = "Bon"
        appreciation_detail = "La base de code est saine, avec quelques axes d'amélioration mineurs."
        score_color = "#9be9a8"
    elif score >= 50:
        appreciation_titre = "Passable"
        appreciation_detail = "La dette technique commence à s'accumuler. Une session de nettoyage est recommandée."
        score_color = "#d29922"
    else:
        appreciation_titre = "Critique"
        appreciation_detail = "Le projet contient une quantité significative de code mort ou inutile. Action requise."
        score_color = "#f85149"
        
    # Calculs pour le cercle de score SVG
    radius = 85
    circumference = 2 * math.pi * radius
    progress_offset = circumference * (1 - score / 100)
    
    # Préparation des données pour les graphiques et totaux
    total_imports = sum(len(v) for v in resultat.imports_morts_par_fichier.values())
    total_vars = sum(len(v) for v in resultat.variables_mortes_par_fichier.values())
    total_code_mort_certain = len(resultat.code_mort)
    
    # Distribution des problèmes pour le graphique
    distribution_counts = Counter({
        "Code Mort Sévère": total_code_mort_certain,
        "Imports Orphelins": total_imports,
        "Variables Fantômes": total_vars,
        "Code Suspect": len(resultat.code_suspect)
    })
    
    # Compter les problèmes par fichier pour le Top Files
    problemes_par_fichier = Counter()
    for chemin, _ in resultat.code_mort: problemes_par_fichier[chemin] += 1
    for chemin, items in resultat.imports_morts_par_fichier.items(): problemes_par_fichier[chemin] += len(items)
    for chemin, items in resultat.variables_mortes_par_fichier.items(): problemes_par_fichier[chemin] += len(items)
    for chemin, _ in resultat.code_suspect: problemes_par_fichier[chemin] += 0.5 # Suspects comptent pour 0.5 problème
    
    top_files = problemes_par_fichier.most_common(5)

    # Aplatir et structurer les listes pour le template
    imports_plats = [{'nom': i.nom, 'chemin': c, 'ligne': i.ligne} for c, v in resultat.imports_morts_par_fichier.items() for i in v]
    variables_plates = [{'nom': v.nom, 'chemin': c, 'ligne': v.ligne, 'fonction_parent': v.fonction_parent} for c, v in resultat.variables_mortes_par_fichier.items() for v in v]
    code_mort_details = [{'chemin': c, 'entite': e} for c, e in resultat.code_mort]
    code_suspect_details = [{'chemin': c, 'entite': e} for c, e in resultat.code_suspect]

    context = {
        "projet_chemin": Path.cwd().name,
        "date_generation": datetime.now().strftime("%d %B %Y à %H:%M"),
        "score": score,
        "score_color": score_color,
        "appreciation_titre": appreciation_titre,
        "appreciation_detail": appreciation_detail,
        "svg_circumference": circumference,
        "svg_progress_offset": progress_offset,
        "stats": {
            "fichiers_analyses": resultat.fichiers_analyses,
            "total_lignes": resultat.total_lignes,
            "problemes_critiques": total_code_mort_certain,
        },
        "chart_data": {
            "distribution": {
                "labels": list(distribution_counts.keys()),
                "data": list(distribution_counts.values())
            },
            "top_files": {
                "labels": [f for f, c in top_files],
                "data": [c for f, c in top_files]
            }
        },
        "details": {
            "code_mort": code_mort_details,
            "code_suspect": code_suspect_details,
            "imports_morts": imports_plats,
            "variables_mortes": variables_plates,
            "doublons": resultat.doublons # Liste de GroupeDuplique
        }
    }
    
    # Configuration de Jinja2
    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent),
        autoescape=select_autoescape(['html', 'xml'])
    )
    env.filters['numberformat'] = number_format_filter
    env.filters['absolute_path'] = absolute_path_filter
    template = env.get_template("report_template.html")
    html_content = template.render(context)
    
    # Sauvegarde du fichier
    Path(chemin_sortie).write_text(html_content, encoding="utf-8")
    print(f"✨ Rapport HTML interactif généré : file://{Path(chemin_sortie).resolve()}")