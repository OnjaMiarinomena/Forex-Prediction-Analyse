# EURUSD AI Scalping Intelligence

Outil d'aide à la décision pour EUR/USD. Vous choisissez le timeframe ; le système récupère les bougies, calcule la heatmap et les probabilités historiques, puis affiche une décision finale : BUY, SELL ou NO TRADE.

> Aucun ordre n'est envoyé. Les probabilités sont des fréquences passées, pas des garanties.

## Comment la décision est prise

Un signal BUY (ou SELL) n'apparaît que si trois éléments sont d'accord :

1. **Setup technique** sur M30 et M5 : structure, Order Block, figure de chandelier M5, BOS M5, plan de risque valide.
2. **Probabilités historiques** : après un contexte semblable, la hausse (ou la baisse) dépasse les autres d'au moins 10 points.
3. **Heatmap** : le mouvement moyen de l'heure courante (UTC) et du jour va dans le même sens, avec assez d'observations.

Sinon : NO TRADE, avec la liste exacte de ce qui manque.

## Installation (Kali Linux / Debian)

```bash
sudo apt install python3-tk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # puis renseignez OANDA_API_KEY
```

Pour obtenir une clé, créez un compte démo chez OANDA et générez un token API. Restez en `practice` tant que vous n'avez pas validé le fonctionnement.

## Lancement

Interface graphique (par défaut) :

```bash
python main.py
```

Choisissez la source (OANDA ou CSV), le timeframe, puis cliquez sur **Analyser**. Avec OANDA, les bougies sont récupérées au moment de l'analyse.

Mode texte :

```bash
python main.py --cli --source oanda --tf H1
python main.py --cli --source csv --csv data/raw/EURUSD_M5.csv --tf M30 --replay
```

Le système travaille à partir des bougies M5 : M15, M30 et H1 sont reconstruites par agrégation, en supprimant les tranches incomplètes.

## Limites importantes

- **Les heatmaps demandent beaucoup de données.** Avec 20 000 bougies M5 (environ 2 à 3 mois), chaque cellule M5 a une centaine d'observations, mais une cellule H1 en a beaucoup moins. Les cellules trop pauvres sont grisées et ne comptent pas dans la décision. Une cellule colorée peut aussi être du bruit : un test aléatoire le montre.
- **Pas de test de significativité encore.** Un écart de 10 points peut être dû au hasard sur de petits échantillons. C'est la prochaine étape à ajouter.
- **Pas de connexion temps réel.** Chaque analyse récupère les dernières bougies clôturées. Les bougies en cours ne sont jamais utilisées.
- **Compte en USD supposé** pour la taille de position. Vérifiez la valeur du pip et le spread chez votre courtier.
- **Non implémenté** : backtest complet, Machine Learning, calendrier économique.

## Paramètres

Tous les seuils sont dans `config/settings.yaml` : horizon des probabilités, seuil de mouvement, taille minimale d'échantillon, écart minimal et seuil de la heatmap, nombre de bougies récupérées, environnement OANDA.

## Tests

```bash
python -m pytest
```

Les tests de récupération OANDA utilisent des réponses simulées : ils ne font aucun appel réseau.

## Dépannage

- « OANDA_API_KEY absente » : vérifiez le fichier `.env` à la racine du projet.
- « OANDA a répondu HTTP 401 » : clé invalide, ou clé `practice` utilisée avec l'environnement `live` (ou l'inverse).
- « Interface graphique indisponible » : installez `python3-tk`. Le mode `--cli` reste disponible.
