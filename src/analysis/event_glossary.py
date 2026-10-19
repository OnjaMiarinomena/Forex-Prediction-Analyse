"""Signification des publications et effet habituel, en termes généraux.

Ce ne sont pas des prévisions : la réaction réelle d'un marché dépend des attentes et du contexte.
"""
GLOSSARY = [
    (("non-farm", "nfp", "employment change", "payroll", "nonfarm"),
     "Emploi hors agriculture (USD)",
     "emploi plus fort que prévu : souvent favorable au dollar"),
    (("cpi", "consumer price", "inflation"),
     "Inflation des prix à la consommation",
     "inflation plus forte que prévu : souvent favorable à la devise via les taux"),
    (("interest rate", "rate decision", "refinancing", "main rate", "fed funds", "monetary policy"),
     "Décision de taux directeur",
     "taux plus élevé ou ton plus ferme que prévu : souvent favorable à la devise"),
    (("gdp", "pib"),
     "Croissance économique",
     "croissance plus forte que prévu : souvent favorable à la devise"),
    (("pmi",),
     "Indice des directeurs d'achat (activité)",
     "activité plus forte que prévu : souvent favorable à la devise"),
    (("unemployment", "jobless", "chômage"),
     "Taux de chômage",
     "chômage plus bas que prévu : souvent favorable à la devise"),
    (("retail sales", "ventes au détail"),
     "Ventes au détail",
     "ventes plus fortes que prévu : souvent favorable à la devise"),
    (("trade balance", "balance commerciale"),
     "Balance commerciale",
     "effet variable selon le contexte"),
    (("confidence", "sentiment", "zew", "ifo"),
     "Indice de confiance ou de sentiment",
     "confiance plus forte que prévu : souvent favorable à la devise"),
    (("press conference", "speech", "speaks", "testimony", "remarks", "statement", "discours"),
     "Discours ou conférence de presse",
     "l'effet dépend du ton et des mots employés, difficile à anticiper"),
    (("minutes", "compte rendu"),
     "Compte rendu de réunion",
     "indique les réflexions passées de la banque centrale"),
]
DEFAULT = ("Publication économique", "l'effet dépend de l'écart avec les prévisions")


def describe(title: str) -> tuple[str, str]:
    lower = title.lower()
    for keys, meaning, effect in GLOSSARY:
        if any(k in lower for k in keys):
            return meaning, effect
    return DEFAULT
