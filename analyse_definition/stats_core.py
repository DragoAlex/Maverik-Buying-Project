# stats_core.py — Portabler Statistik-Kern des Analyse-Stacks.
#
# Einzige Statistik-Implementierung im System: alle Module rechnen über
# diese Funktionen, nie über eigene Formeln oder externe Bibliotheken.
# Bewusst frei von Pandas/NumPy: reine Listen-Arithmetik, damit der Kern
# ohne Änderung in jede Python-Umgebung portierbar bleibt. Korrektheit
# wird extern über Orakel-Tests gegen NumPy abgesichert (pruefung/).
#
# Konventionen:
# - Quantile nach Typ 7 (lineare Interpolation, NumPy-Default)
# - MAD roh (unskaliert, kein Faktor 1.4826)
# - Varianz mit Nenner n−1 (Stichprobe)
# - Zu wenig Daten liefert None statt Ausnahme — Aufrufer müssen die
#   Datenlage ausweisen, nie stillschweigend weiterrechnen.
# - Korrelationen tragen eine n≥3-Sperre: unter drei Paaren ist jede
#   Korrelation Zufall, deshalb None.

import math


def mittelwert(werte):
    if not werte:
        return None
    return sum(werte) / len(werte)


def varianz(werte):
    # Stichprobenvarianz (Nenner n−1); unter zwei Werten nicht definiert.
    if len(werte) < 2:
        return None
    m = mittelwert(werte)
    return sum((x - m) ** 2 for x in werte) / (len(werte) - 1)


def standardabweichung(werte):
    v = varianz(werte)
    if v is None:
        return None
    return math.sqrt(v)


def variationskoeffizient(werte):
    # Streuung relativ zum Niveau; bei Mittelwert 0 nicht definiert.
    s = standardabweichung(werte)
    m = mittelwert(werte)
    if s is None or m is None or m == 0:
        return None
    return s / abs(m)


def quantil(werte, p):
    # Quantil Typ 7: h = (n−1)·p, linear interpoliert zwischen den
    # Nachbarwerten der sortierten Reihe (entspricht numpy method="linear").
    if not werte or not 0 <= p <= 1:
        return None
    sortiert = sorted(werte)
    n = len(sortiert)
    if n == 1:
        return float(sortiert[0])
    h = (n - 1) * p
    unten = int(math.floor(h))
    oben = min(unten + 1, n - 1)
    rest = h - unten
    return sortiert[unten] + rest * (sortiert[oben] - sortiert[unten])


def median(werte):
    return quantil(werte, 0.5)


def mad(werte):
    # Roher MAD: Median der absoluten Abweichungen vom Median, unskaliert.
    if not werte:
        return None
    med = median(werte)
    return median([abs(x - med) for x in werte])


def _raenge(werte):
    # Durchschnittsränge bei Bindungen (Standard für Spearman).
    reihenfolge = sorted(range(len(werte)), key=lambda i: werte[i])
    raenge = [0.0] * len(werte)
    i = 0
    while i < len(werte):
        j = i
        while j + 1 < len(werte) and werte[reihenfolge[j + 1]] == werte[reihenfolge[i]]:
            j += 1
        mittelrang = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            raenge[reihenfolge[k]] = mittelrang
        i = j + 1
    return raenge


def pearson(x, y):
    # n≥3-Sperre; bei konstanter Reihe (Nenner 0) nicht definiert.
    if len(x) != len(y) or len(x) < 3:
        return None
    mx = mittelwert(x)
    my = mittelwert(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def spearman(x, y):
    # Rangkorrelation: Pearson auf Durchschnittsrängen — robust gegen
    # Ausreißer und monotone Verzerrungen.
    if len(x) != len(y) or len(x) < 3:
        return None
    return pearson(_raenge(x), _raenge(y))


def eta(werte, gruppen):
    # Korrelationsverhältnis η für metrische Werte gegen ein nominales
    # Gruppenmerkmal: sqrt(Zwischengruppen-Streuung / Gesamtstreuung).
    if len(werte) != len(gruppen) or len(werte) < 3:
        return None
    gesamt = mittelwert(werte)
    je_gruppe = {}
    for wert, gruppe in zip(werte, gruppen):
        je_gruppe.setdefault(gruppe, []).append(wert)
    if len(je_gruppe) < 2:
        return None
    ss_gesamt = sum((x - gesamt) ** 2 for x in werte)
    if ss_gesamt == 0:
        return None
    ss_zwischen = sum(
        len(g) * (mittelwert(g) - gesamt) ** 2 for g in je_gruppe.values()
    )
    return math.sqrt(ss_zwischen / ss_gesamt)
