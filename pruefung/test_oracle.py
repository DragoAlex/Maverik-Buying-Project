# test_oracle.py — Orakel-Tests: stats_core gegen NumPy als unabhängige
# Referenzimplementierung. Der Kern selbst bleibt NumPy-frei; nur diese
# Prüfschicht benötigt NumPy. Feste Seeds machen die Läufe reproduzierbar.

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from analyse_definition import stats_core


def zufallsreihe(n, seed):
    rnd = random.Random(seed)
    return [rnd.uniform(-100, 100) for _ in range(n)]


class TestOrakelStatsCore(unittest.TestCase):
    def test_mittelwert_gegen_numpy(self):
        for seed in range(5):
            werte = zufallsreihe(37, seed)
            self.assertAlmostEqual(
                stats_core.mittelwert(werte), float(np.mean(werte)), places=10
            )

    def test_varianz_gegen_numpy_ddof1(self):
        for seed in range(5):
            werte = zufallsreihe(41, seed)
            self.assertAlmostEqual(
                stats_core.varianz(werte), float(np.var(werte, ddof=1)), places=8
            )
            self.assertAlmostEqual(
                stats_core.standardabweichung(werte),
                float(np.std(werte, ddof=1)),
                places=8,
            )

    def test_quantil_typ7_gegen_numpy_linear(self):
        for seed in range(5):
            werte = zufallsreihe(29, seed)
            for p in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0):
                self.assertAlmostEqual(
                    stats_core.quantil(werte, p),
                    float(np.quantile(werte, p, method="linear")),
                    places=10,
                )

    def test_mad_roh_gegen_numpy(self):
        for seed in range(5):
            werte = zufallsreihe(33, seed)
            erwartet = float(np.median(np.abs(np.array(werte) - np.median(werte))))
            self.assertAlmostEqual(stats_core.mad(werte), erwartet, places=10)

    def test_pearson_gegen_numpy(self):
        for seed in range(5):
            x = zufallsreihe(50, seed)
            grund = zufallsreihe(50, seed + 100)
            # Teilweise abhängige Reihe, damit rho weder 0 noch ±1 ist.
            y = [a * 0.6 + b * 0.4 for a, b in zip(x, grund)]
            self.assertAlmostEqual(
                stats_core.pearson(x, y), float(np.corrcoef(x, y)[0, 1]), places=10
            )

    def test_spearman_gegen_numpy_rangkorrelation(self):
        # Referenz: Ränge über doppeltes argsort (stetige Zufallswerte,
        # Bindungen praktisch ausgeschlossen), dann Pearson via NumPy.
        for seed in range(5):
            x = zufallsreihe(50, seed)
            y = zufallsreihe(50, seed + 200)
            rang_x = np.argsort(np.argsort(x)) + 1
            rang_y = np.argsort(np.argsort(y)) + 1
            erwartet = float(np.corrcoef(rang_x, rang_y)[0, 1])
            self.assertAlmostEqual(stats_core.spearman(x, y), erwartet, places=10)


if __name__ == "__main__":
    unittest.main()
