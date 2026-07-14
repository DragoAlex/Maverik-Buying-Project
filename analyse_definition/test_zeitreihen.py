# Tests für zeitreihen.py — inkl. der Pflichttests aus der Phase-0-Definition:
# Monatsgrenzen, ein Beleg im Monat, Mengengewichtung gegen Handrechnung,
# Lücken bleiben Lücken, Preisbasis-Kennzeichnung.

import unittest
from datetime import date, datetime

from analyse_definition import zeitreihen


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


class TestMonatAusDatum(unittest.TestCase):
    def test_datumstypen(self):
        self.assertEqual(zeitreihen.monat_aus_datum(date(2025, 1, 31)), "2025-01")
        self.assertEqual(
            zeitreihen.monat_aus_datum(datetime(2025, 12, 1, 8, 30)), "2025-12"
        )
        self.assertEqual(zeitreihen.monat_aus_datum("2025-06-15"), "2025-06")
        self.assertEqual(zeitreihen.monat_aus_datum("2025-06-15T10:00:00"), "2025-06")

    def test_unlesbares_datum(self):
        self.assertIsNone(zeitreihen.monat_aus_datum("15.06.2025"))
        self.assertIsNone(zeitreihen.monat_aus_datum("2025-13-01"))
        self.assertIsNone(zeitreihen.monat_aus_datum(None))
        self.assertIsNone(zeitreihen.monat_aus_datum(20250615))


class TestMonatsBucketing(unittest.TestCase):
    def test_monatsgrenze_31_und_01(self):
        # Pflichttest: Beleg am 31.01. und am 01.02. landen in zwei Buckets.
        zeilen = [beleg("2025-01-31"), beleg("2025-02-01")]
        reihen, befunde = zeitreihen.baue_monatsreihe(zeilen, "material")
        self.assertEqual(sorted(reihen[("M1",)]), ["2025-01", "2025-02"])
        self.assertEqual(reihen[("M1",)]["2025-01"]["anzahl_belege"], 1)
        self.assertEqual(reihen[("M1",)]["2025-02"]["anzahl_belege"], 1)
        self.assertEqual(befunde, [])

    def test_ein_beleg_im_monat(self):
        # Pflichttest: ein einzelner Beleg bildet den Bucket exakt ab.
        zeilen = [beleg("2025-03-10", menge=7.0, preis=3.0)]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        bucket = reihen[("M1",)]["2025-03"]
        self.assertEqual(bucket["summe_menge"], 7.0)
        self.assertEqual(bucket["summe_wert"], 21.0)
        self.assertEqual(bucket["durchschnittspreis"], 3.0)
        self.assertEqual(bucket["anzahl_belege"], 1)

    def test_mengengewichtung_handrechnung(self):
        # Pflichttest: 10 Stück à 2 € + 30 Stück à 4 € →
        # (20 + 120) / 40 = 3.50 €. Das ungewichtete Mittel wäre 3.00 €.
        zeilen = [
            beleg("2025-04-05", menge=10.0, preis=2.0),
            beleg("2025-04-20", menge=30.0, preis=4.0),
        ]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        bucket = reihen[("M1",)]["2025-04"]
        self.assertAlmostEqual(bucket["durchschnittspreis"], 3.5)
        self.assertNotAlmostEqual(bucket["durchschnittspreis"], 3.0)

    def test_luecken_bleiben_luecken(self):
        # Pflichttest: Februar ohne Beleg taucht nicht als 0-Bucket auf.
        zeilen = [beleg("2025-01-15"), beleg("2025-03-15")]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        monatsreihe = reihen[("M1",)]
        self.assertNotIn("2025-02", monatsreihe)
        self.assertEqual(zeitreihen.monatsluecken(monatsreihe), ["2025-02"])

    def test_dimension_material_lieferant(self):
        zeilen = [
            beleg("2025-01-10", lieferant="L1"),
            beleg("2025-01-10", lieferant="L2"),
        ]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material_lieferant")
        self.assertIn(("M1", "L1"), reihen)
        self.assertIn(("M1", "L2"), reihen)

    def test_fehlende_warengruppe_erzeugt_befund(self):
        zeilen = [beleg("2025-01-10", warengruppe=None)]
        reihen, befunde = zeitreihen.baue_monatsreihe(zeilen, "warengruppe")
        self.assertIn((zeitreihen.PLATZHALTER_WARENGRUPPE,), reihen)
        self.assertTrue(any("ohne Warengruppe" in b for b in befunde))

    def test_unbrauchbare_zeilen_erzeugen_befund(self):
        zeilen = [
            beleg("kein-datum"),
            beleg("2025-01-10", menge=None),
            beleg("2025-01-10"),
        ]
        reihen, befunde = zeitreihen.baue_monatsreihe(zeilen, "material")
        self.assertEqual(reihen[("M1",)]["2025-01"]["anzahl_belege"], 1)
        self.assertEqual(len(befunde), 2)

    def test_explizites_wert_feld_hat_vorrang(self):
        zeilen = [beleg("2025-01-10", menge=10.0, preis=99.0, wert=50.0)]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        self.assertEqual(reihen[("M1",)]["2025-01"]["durchschnittspreis"], 5.0)


class TestPreisbasis(unittest.TestCase):
    def test_auto_rechnung_ersetzt_bestellung(self):
        bestellungen = [beleg("2025-01-10", preis=10.0, bestellnummer="B1")]
        rechnungen = [beleg("2025-01-20", preis=11.0, bestellnummer="B1")]
        zeilen, befunde = zeitreihen.vereinige_preisbasis(bestellungen, rechnungen)
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        bucket = reihen[("M1",)]["2025-01"]
        self.assertEqual(bucket["durchschnittspreis"], 11.0)
        self.assertEqual(bucket["preisbasis"], "rechnung")
        self.assertEqual(befunde, [])

    def test_auto_faellt_auf_bestellung_zurueck(self):
        bestellungen = [beleg("2025-01-10", bestellnummer="B1")]
        zeilen, _ = zeitreihen.vereinige_preisbasis(bestellungen, [])
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        self.assertEqual(reihen[("M1",)]["2025-01"]["preisbasis"], "bestellung")

    def test_auto_gemischt_im_bucket(self):
        bestellungen = [
            beleg("2025-01-05", bestellnummer="B1"),
            beleg("2025-01-25", bestellnummer="B2"),
        ]
        rechnungen = [beleg("2025-01-15", bestellnummer="B1")]
        zeilen, _ = zeitreihen.vereinige_preisbasis(bestellungen, rechnungen)
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        self.assertEqual(reihen[("M1",)]["2025-01"]["preisbasis"], "gemischt")

    def test_modus_nur_bestellung(self):
        bestellungen = [beleg("2025-01-10", bestellnummer="B1")]
        rechnungen = [beleg("2025-01-20", preis=99.0, bestellnummer="B1")]
        zeilen, _ = zeitreihen.vereinige_preisbasis(
            bestellungen, rechnungen, {"preisbasis": "bestellung"}
        )
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        bucket = reihen[("M1",)]["2025-01"]
        self.assertEqual(bucket["durchschnittspreis"], 10.0)
        self.assertEqual(bucket["preisbasis"], "bestellung")

    def test_modus_rechnung_ohne_rechnungen_befund(self):
        zeilen, befunde = zeitreihen.vereinige_preisbasis(
            [beleg("2025-01-10")], [], {"preisbasis": "rechnung"}
        )
        self.assertEqual(zeilen, [])
        self.assertEqual(len(befunde), 1)


class TestHistorientiefe(unittest.TestCase):
    def test_kurze_historie_wird_ausgewiesen(self):
        zeilen = [beleg("2025-0%d-10" % m) for m in range(1, 6)]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        tiefe = zeitreihen.historientiefe(reihen[("M1",)])
        self.assertEqual(tiefe["n_monate"], 5)
        self.assertTrue(tiefe["aussagekraft_eingeschraenkt"])
        self.assertEqual(tiefe["hinweis"], "Aussagekraft eingeschränkt, n=5 Monate")

    def test_lange_historie_ohne_hinweis(self):
        zeilen = [
            beleg("%04d-%02d-10" % (2024 + (m - 1) // 12, (m - 1) % 12 + 1))
            for m in range(1, 13)
        ]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        tiefe = zeitreihen.historientiefe(reihen[("M1",)])
        self.assertEqual(tiefe["n_monate"], 12)
        self.assertFalse(tiefe["aussagekraft_eingeschraenkt"])
        self.assertEqual(tiefe["hinweis"], "")

    def test_jahreswechsel_in_spanne_und_luecken(self):
        self.assertEqual(
            zeitreihen.monatsspanne("2024-11", "2025-02"),
            ["2024-11", "2024-12", "2025-01", "2025-02"],
        )
        zeilen = [beleg("2024-11-15"), beleg("2025-02-15")]
        reihen, _ = zeitreihen.baue_monatsreihe(zeilen, "material")
        self.assertEqual(
            zeitreihen.monatsluecken(reihen[("M1",)]), ["2024-12", "2025-01"]
        )


if __name__ == "__main__":
    unittest.main()
