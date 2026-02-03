# Limbo Collector

**Trouve le code Python ni vivant ni mort.**

Limbo Collector est un outil d'analyse statique pour Python conçu pour détecter le code inutile, mort ou inaccessible (unreachable) dans vos projets. Contrairement aux linters classiques qui se concentrent sur le style, Limbo Collector cherche à alléger votre base de code en identifiant ce qui peut être supprimé sans risque.

## Fonctionnalités Actuelles

Limbo Collector est déjà capable d'analyser des fichiers isolés ou des projets entiers.

### Détection de Code Mort
- **Fonctions et Classes inutilisées :** Repère les définitions qui ne sont jamais appelées ou instanciées.
- **Analyse Inter-fichiers :** Comprend qu'une fonction n'est pas "morte" si elle est importée et utilisée dans un autre fichier du projet.
- **Méthodes et Attributs :** Analyse l'utilisation des méthodes de classe, propriétés et méthodes statiques.

### Nettoyage de Code
- **Imports Inutiles :** Détecte les `import x` et `from x import y` qui ne servent à rien.
- **Variables Locales Inutilisées :** Trouve les variables assignées mais jamais lues dans les fonctions.
- **Paramètres Inutilisés :** Signale les arguments de fonction déclarés mais ignorés dans le corps de la fonction.

### Erreurs de Logique & Code Inaccessible
- **Code Unreachable :** Détecte le code situé après un `return`, `raise`, `break` ou `continue`.
- **Branches Mortes :** Identifie les conditions toujours fausses (`if False:`, `while 0:`) qui rendent le code inatteignable.

### CLI & Configuration
- **Mode Projet :** Scanne récursivement un dossier et résout les dépendances entre fichiers.
- **Export JSON :** Format de sortie structuré pour intégration avec d'autres outils.
- **Mode Strict :** Affiche aussi le code "suspect" (probablement mort, mais avec un doute dû au dynamisme de Python).
- **Configuration :** Fichier `limbo.json` pour ignorer certains dossiers, fichiers ou patterns spécifiques.

---

## Installation

Cloner le dépôt et installer en mode éditable :

```bash
git clone https://github.com/SpaceGame-wq/Limbo-Collector.git
cd limbo-collector
pip install -e .
```

## Utilisation

### Analyser un fichier unique
```bash
limbo-collector mon_script.py
```

### Analyser tout un projet
```bash
limbo-collector mon_projet/
```

### Options utiles

| Option | Description |
|--------|-------------|
| `--strict` | Affiche le code "probablement mort" (suspects) en plus du code "sûrement mort". |
| `--json` | Exporte le résultat au format JSON (utile pour les pipelines CI/CD). |
| `--unreachable` | Active la détection du code inaccessible. |
| `--params` | Active la détection des paramètres de fonction inutilisés. |
| `--no-imports` | Désactive la vérification des imports (pour aller plus vite). |
| `--init-config` | Génère un fichier de configuration `limbo.json.example`. |

---

## Roadmap (À venir)

Voici les fonctionnalités prévues pour les prochaines versions :

### Court terme
- [ ] **Support étendu des frameworks :** Meilleure détection des "faux positifs" pour Django (modèles, vues), FastAPI (routes) et Flask.
- [ ] **Support du `.gitignore` :** Ignorer automatiquement les fichiers exclus par Git.
- [ ] **Rapport HTML :** Générer un rapport visuel avec graphiques pour voir la "santé" du projet.

### Moyen terme
- [ ] **Auto-Fix (Beta) :** Option pour supprimer automatiquement les imports inutiles et variables mortes (avec backup).
- [ ] **Analyse de complexité :** Signaler les fonctions trop longues ou trop complexes (Cyclomatic complexity).
- [ ] **Intégration CI/CD :** Création d'une GitHub Action officielle.

### Long terme
- [ ] **Type Hinting :** Utiliser les types Python pour améliorer la précision de la détection des méthodes mortes.
- [ ] **Graphe de dépendance visuel :** Exporter une image montrant qui appelle qui dans le projet.

---

## Configuration (`limbo.json`)

Vous pouvez créer un fichier `limbo.json` à la racine de votre projet pour affiner l'analyse :

```json
{
  "ignore_fonctions": ["main", "run", "app"],
  "ignore_classes": ["Meta", "Config"],
  "ignore_modules": ["pytest", "unittest"],
  "exclude_patterns": ["venv", "migrations", "tests"],
  "strict_mode": false
}
```

---

## Contribuer

Les contributions sont les bienvenues !
1. Forkez le projet.
2. Créez votre branche (`git checkout -b feature/AmazingFeature`).
3. Committez vos changements (`git commit -m 'Add some AmazingFeature'`).
4. Pushez vers la branche (`git push origin feature/AmazingFeature`).
5. Ouvrez une Pull Request.

## Licence

Ce projet est distribué sous la licence **CC BY-NC-SA 4.0**.

Cela signifie que vous êtes encouragés à:
*    Lire et utiliser le code pour des projets personnels ou non-lucratifs.
*    **Contribuer** ! Forkez le projet, améliorez-le et proposez vos changements (Pull Requests).

Mais vous ne pouvez pas :
*    Utiliser ce code à des fins commerciales.
*    Distribuer une version modifiée sous une autre licence (vous devez rester en CC BY-NC-SA).

Voir le fichier `LICENSE` pour plus de détails.