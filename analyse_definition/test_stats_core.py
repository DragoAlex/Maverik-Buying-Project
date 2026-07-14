# Tests für stats_core.py — alle Sollwerte per Handrechnung hergeleitet.

import unittest

from analyse_definition import stats_core


class TestLagemasse(unittest.TestCase):
    def test_mittelwert(self):
        self.assertEqual(stats_core.mittelwert([2, 4, 6]), 4.0)
        self.assertIsNone(stats_core.mittelwert([]))

    def test_median_ungerade_und_gerade(self):
        self.assertEqual(stats_core.median([3, 1, 2]), 2.0)
        # Typ 7: Mittel der beiden mittleren Werte.
        self.assertEqual(stats_core.median([1, 2, 3, 4]), 2.5)

    def test_quantil_typ7_handrechnung(self):
        # [1,2,3,4], p=0.25: h = 3·0.25 = 0.75 → 1 + 0.75·(2−1) = 1.75
        self.assertAlmostEqual(stats_core.quantil([1, 2, 3, 4], 0.25), 1.75)
        self.assertEqual(stats_core.quantil([5], 0.9), 5.0)
        self.assertEqual(stats_core.quantil([1, 2, 3], 1.0), 3.0)
        self.assertIsNone(stats_core.quantil([], 0.5))
        self.assertIsNone(stats_core.quantil([1, 2], 1.5))


class TestStreuung(unittest.TestCase):
    def test_varianz_n_minus_1(self):
        # [2,4,4,4,5,5,7,9]: Mittel 5, Summe Quadrate 32, 32/7
        self.assertAlmostEqual(
            stats_core.varianz([2, 4, 4, 4, 5, 5, 7, 9]), 32 / 7
        )
        self.assertIsNone(stats_core.varianz([1]))

    def test_mad_roh(self):
        # Median 3, Abweichungen [2,1,0,1,97] → Median 1 (unskaliert)
        self.assertEqual(stats_core.mad([1, 2, 3, 4, 100]), 1.0)

    def test_variationskoeffizient(self):
        # Mittel 10, Stdabw sqrt(((−2)²+0+2²)/2) = 2 → VK 0.2
        self.assertAlmostEqual(
            stats_core.variationskoeffizient([8, 10, 12]), 0.2
        )
        self.assertIsNone(stats_core.variationskoeffizient([-1, 0, 1]))


class TestKorrelation(unittest.TestCase):
    def test_pearson_perfekt(self):
        self.assertAlmostEqual(stats_core.pearson([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertAlmostEqual(stats_core.pearson([1, 2, 3], [6, 4, 2]), -1.0)

    def test_n_sperre_und_konstante_reihe(self):
        self.assertIsNone(stats_core.pearson([1, 2], [3, 4]))
        self.assertIsNone(stats_core.pearson([1, 1, 1], [1, 2, 3]))
        self.assertIsNone(stats_core.spearman([1, 2], [3, 4]))

    def test_spearman_monoton_nichtlinear(self):
        # Monoton wachsend, aber nicht linear → Spearman exakt 1.
        x = [1, 2, 3, 4, 5]
        y = [1, 8, 27, 64, 125]
        self.assertAlmostEqual(stats_core.spearman(x, y), 1.0)

    def test_spearman_bindungen(self):
        # Durchschnittsränge: x=[1,2,2,3] → [1, 2.5, 2.5, 4]
        self.assertEqual(stats_core._raenge([1, 2, 2, 3]), [1.0, 2.5, 2.5, 4.0])

    def test_eta(self):
        # Zwei klar getrennte Gruppen ohne Binnenstreuung → η = 1.
        werte = [1, 1, 9, 9]
        gruppen = ["a", "a", "b", "b"]
        self.assertAlmostEqual(stats_core.eta(werte, gruppen), 1.0)
        self.assertIsNone(stats_core.eta([1, 2, 3], ["a", "a", "a"]))
        self.assertIsNone(stats_core.eta([5, 5, 5, 5], ["a", "a", "b", "b"]))


if __name__ == "__main__":
    unittest.main()
