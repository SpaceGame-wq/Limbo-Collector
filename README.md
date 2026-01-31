# Limbo Collector

Trouve automatiquement le code Python défini mais jamais utilisé.

## Installation

```bash
git clone https://github.com/SpaceGame-wq/limbo-collector.git
cd limbo-collector
pip install -e .
```

## Utilisation

```bash
limbo-collector tests/exemple_mort.py
```

## Fonctionnement

- Détecte les fonctions et classes non appelées
- Ignore les méthodes spéciales Python (__init__, etc.)
- Sépare le "sûrement mort" du "peut-être mort"
```

## Premier commit : les commandes exactes

```bash
# 1. Crée le repo sur GitHub (vide), puis :
git init
git add .
git commit -m "Premier commit: MVP detection basique"
git branch -M main
git remote add origin https://github.com/TON-USER/limbo-collector.git
git push -u origin main
```

## Test immédiat

Une fois installé (`pip install -e .`), lance :

```bash
limbo-collector tests/exemple_mort.py
```
