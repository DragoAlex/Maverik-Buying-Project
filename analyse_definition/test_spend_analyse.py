# Tests für spend_analyse.py — ABC-Handrechnung, Konzentration,
# Jahresfenster, Preisbasis-Durchgriff und Determinismus des Laufs.

import os
import tempfile
import unittest

from analyse_definition import spend_analyse, zeitreihen


def beleg(datum, material="M1", warengruppe="WG1", lieferant="L1",
          menge=1.0, preis=10.0, **extra):
    zeile = {
        "belegdatum": datum,
        "materialnummer": material,
        "warengruppe": warengruppe,
        "lieferant": lieferant,
        "menge": menge,
        "preis": preis,
    }
    zeile.update(extra)
    return zeile


class TestAbcKlassifizierung(unittest.TestCase):
    def test_handrechnung_klassengrenzen(self):
        # Spends 50/30/15/5 → Anteile 50/30/15/5 %. Kumuliert vor dem
        # Objekt: 0, 50, 80, 95 → Klassen A, A, B, C.
        abc = spend_analyse.abc_klassifizierung(
            {"a": 50.0, "b": 30.0, "c": 15.0, "d": 5.0}
        )
        self.assertEqual([e["objekt"] for e in abc], ["a", "b", "c", "d"])
        self.assertEqual([e["klasse"] for e in abc], ["A", "A", "B", "C"])
        self.assertAlmostEqual(abc[1]["kumuliert"], 0.80)
        self.assertAlmostEqual(abc[3]["kumuliert"], 1.0)

    def test_grenzen_konfigurierbar(self):
        abc = spend_analyse.abc_klassifizierung(
            {"a": 50.0, "b": 30.0, "c": 15.0, "d": 5.0},
            {"abc_grenzen": {"A": 0.50, "B": 0.80}},
        )
        self.assertEqual([e["klasse"] for e in abc], ["A", "B", "C", "C"])

    def test_gleichstand_deterministisch(self):
        abc = spend_analyse.abc_klassifizierung({"x": 10.0, "a": 10.0})
        self.assertEqual([e["objekt"] for e in abc], ["a", "x"])

    def test_gesamtspend_null_keine_scheinklassen(self):
        abc = spend_analyse.abc_klassifizierung({"a": 0.0, "b": 0.0})
        self.assertEqual([e["klasse"] for e in abc], ["?", "?"])
        self.assertIsNone(abc[0]["anteil"])


class TestJahresfenster(unittest.TestCase):
    def test_fenster_letzte_12_kalendermonate(self):
        fenster = spend_analyse.jahresfenster(["2024-03", "2025-06"])
        self.assertEqual(len(fenster), 12)
        self.assertEqual(fenster[0], "2024-07")
        self.assertEqual(fenster[-1], "2025-06")

    def test_aeltere_monate_fallen_aus_dem_jahres_spend(self):
        # 14 Monate Historie: nur die letzten 12 zählen in den Jahres-Spend.
        zeilen = [beleg("2024-01-10", menge=1, preis=1000.0),
                  beleg("2024-02-10", menge=1, preis=1000.0)]
        zeilen += [beleg("%04d-%02d-10" % (2024 + (m - 1) // 12, (m - 1) % 12 + 1),
                         menge=1, preis=10.0)
                   for m in range(3, 15)]
        fenster = spend_analyse.jahresfenster(
            sorted({zeitreihen.monat_aus_datum(z["belegdatum"]) for z in zeilen})
        )
        spend, monate = spend_analyse._spend_im_fenster(zeilen, "material", fenster)
        self.assertEqual(spend["M1"], 120.0)
        self.assertEqual(len(monate), 12)


class TestKonzentration(unittest.TestCase):
    def test_top1_und_top3_handrechnung(self):
        # WG1: L1=60, L2=25, L3=10, L4=5 → Top1 60 %, Top3 95 %.
        zeilen = [beleg("2025-01-10", lieferant="L%d" % i, menge=1, preis=p)
                  for i, p in ((1, 60.0), (2, 25.0), (3, 10.0), (4, 5.0))]
        wuerfel, _ = spend_analyse.baue_spend_wuerfel(zeilen)
        ergebnis = spend_analyse.konzentration_je_warengruppe(wuerfel, ["2025-01"])
        self.assertEqual(len(ergebnis), 1)
        k = ergebnis[0]
        self.assertEqual(k["top1_lieferant"], "L1")
        self.assertAlmostEqual(k["top1_anteil"], 0.60)
        self.assertAlmostEqual(k["top3_anteil"], 0.95)
        self.assertEqual(k["n_lieferanten"], 4)


class TestGesamtlauf(unittest.TestCase):
    def _zeilen(self):
        zeilen = []
        for m in range(1, 13):
            zeilen.append(beleg("2025-%02d-10" % m, material="M1",
                                warengruppe="WG1", lieferant="L1",
                                menge=10, preis=8.0, bestellnummer="B%d" % m))
            zeilen.append(beleg("2025-%02d-15" % m, material="M2",
                                warengruppe="WG2", lieferant="L2",
                                menge=2, preis=5.0))
        return zeilen

    def test_preisbasis_rechnung_fliesst_in_wuerfel(self):
        bestellungen = [beleg("2025-01-10", menge=10, preis=8.0, bestellnummer="B1")]
        rechnungen = [beleg("2025-01-20", menge=10, preis=9.0, bestellnummer="B1")]
        with tempfile.TemporaryDirectory() as ordner:
            ergebnis = spend_analyse.fuehre_spend_analyse_aus(
                bestellungen, rechnungen, ordner
            )
        self.assertEqual(ergebnis["wuerfel"][0]["summe_wert"], 90.0)
        self.assertEqual(ergebnis["wuerfel"][0]["preisbasis"], "rechnung")

    def test_kurze_historie_wird_ausgewiesen(self):
        with tempfile.TemporaryDirectory() as ordner:
            ergebnis = spend_analyse.fuehre_spend_analyse_aus(
                [beleg("2025-01-10"), beleg("2025-03-10")], None, ordner
            )
        self.assertEqual(ergebnis["n_monate"], 2)
        self.assertEqual(ergebnis["hinweis"],
                         "Aussagekraft eingeschränkt, n=2 Monate")

    def test_alle_ausgabedateien_mit_metazeile(self):
        with tempfile.TemporaryDirectory() as ordner:
            spend_analyse.fuehre_spend_analyse_aus(self._zeilen(), None, ordner)
            dateien = ["spend_wuerfel.csv", "abc_material.csv",
                       "abc_lieferant.csv", "konzentration.csv", "spend.md"]
            for name in dateien:
                pfad = os.path.join(ordner, name)
                self.assertTrue(os.path.exists(pfad), name)
                with open(pfad, encoding="utf-8") as datei:
                    inhalt = datei.read()
                self.assertIn("Zeitraum: 2025-01 bis 2025-12", inhalt)
                self.assertIn("n=12", inhalt)

    def test_determinismus_zwei_laeufe_identisch(self):
        # Pflichtprinzip Phase 6, hier schon je Modul: zwei Läufe auf
        # denselben Daten erzeugen byte-identische Dateien.
        with tempfile.TemporaryDirectory() as o1, \
                tempfile.TemporaryDirectory() as o2:
            spend_analyse.fuehre_spend_analyse_aus(self._zeilen(), None, o1)
            spend_analyse.fuehre_spend_analyse_aus(self._zeilen(), None, o2)
            for name in sorted(os.listdir(o1)):
                with open(os.path.join(o1, name), "rb") as d1, \
                        open(os.path.join(o2, name), "rb") as d2:
                    self.assertEqual(d1.read(), d2.read(), name)

    def test_konzentrationswarnung_im_bericht(self):
        # WG1 mit 100 % Single Source muss im Bericht auffallen.
        with tempfile.TemporaryDirectory() as ordner:
            spend_analyse.fuehre_spend_analyse_aus(self._zeilen(), None, ordner)
            with open(os.path.join(ordner, "spend.md"), encoding="utf-8") as datei:
                bericht = datei.read()
        self.assertIn("Single-Source-Risiko", bericht)
        self.assertIn("WG1", bericht)


class TestDimensionErweiterung(unittest.TestCase):
    def test_warengruppe_lieferant_dimension(self):
        zeilen = [beleg("2025-01-10", warengruppe="WG1", lieferant="L1"),
                  beleg("2025-01-10", warengruppe="WG1", lieferant="L2")]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "warengruppe_lieferant")
        self.assertIn(("WG1", "L1"), reihen)
        self.assertIn(("WG1", "L2"), reihen)


if __name__ == "__main__":
    unittest.main()
