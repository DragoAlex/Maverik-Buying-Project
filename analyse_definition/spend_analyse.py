# spend_analyse.py — Phase 1: Spend-Analyse des Category-Management-Pakets.
#
# Baut auf dem Zeitreihen-Fundament (Phase 0) auf: alle Aggregation läuft
# über zeitreihen.baue_monatsreihe, hier wird keine eigene Statistik und
# kein eigenes Bucketing implementiert.
#
# Kernentscheidungen:
# - "Jahres-Spend" = die letzten 12 Kalendermonate bis zum letzten
#   belegten Monat. Liegen im Fenster weniger belegte Monate, wird das
#   ausgewiesen ("Aussagekraft eingeschränkt, n=X Monate") — nie
#   stillschweigend gerechnet, als wäre die Historie voll.
# - ABC-Regel: sortiert nach Spend absteigend; ein Objekt gehört zur
#   Klasse, in deren Bereich es STARTET (kumulierter Anteil vor dem
#   Objekt). Das Objekt, das die 80 %-Grenze überschreitet, zählt damit
#   noch zu A — die übliche Konvention, hier explizit festgelegt.
# - Gleichstand im Spend wird über den Objektnamen aufgelöst, damit
#   zwei Läufe identisch sortieren (Determinismus).
# - CSV-Ausgaben tragen die Datengrundlage als '#'-Metazeile vor dem
#   Header (Zeitraum, n Monate, Preisbasis) — Decision-Support-Pflicht;
#   Einleseprogramme können die Zeile über das '#'-Präfix überspringen.

import csv
import os

from analyse_definition import zeitreihen

KONFIG = {
    # Kumulierte Anteilsgrenzen: bis 80 % = A, bis 95 % = B, Rest = C.
    "abc_grenzen": {"A": 0.80, "B": 0.95},
    # Fensterbreite für den Jahres-Spend in Kalendermonaten.
    "jahresfenster_monate": 12,
    # Wie viele Top-Warengruppen der Bericht im Detail nennt.
    "top_warengruppen_bericht": 5,
    # Ab diesem Top-1-Lieferantenanteil gilt eine Warengruppe als
    # konzentrationsauffällig (Single-Source-Risiko).
    "konzentration_warnschwelle": 0.5,
}


def _konfig(ueberschreibung):
    zusammen = dict(KONFIG)
    if ueberschreibung:
        zusammen.update(ueberschreibung)
    return zusammen


def _monat_minus(monat, anzahl):
    jahr, m = int(monat[0:4]), int(monat[5:7])
    index = jahr * 12 + (m - 1) - anzahl
    return "%04d-%02d" % (index // 12, index % 12 + 1)


def jahresfenster(monate, konfig=None):
    # Fenster = die letzten N Kalendermonate bis zum letzten belegten
    # Monat — Kalendermonate, nicht belegte Monate, damit Lücken das
    # Fenster nicht künstlich verlängern.
    konfig = _konfig(konfig)
    if not monate:
        return []
    ende = max(monate)
    start = _monat_minus(ende, konfig["jahresfenster_monate"] - 1)
    return zeitreihen.monatsspanne(start, ende)


def baue_spend_wuerfel(zeilen, konfig=None):
    # Spend-Würfel Warengruppe × Lieferant × Monat aus den (bereits über
    # die Preisbasis-Konfiguration vereinigten) Belegzeilen.
    reihen, befunde = zeitreihen.baue_monatsreihe(zeilen, "warengruppe_lieferant")
    wuerfel = []
    for (warengruppe, lieferant), monatsreihe in reihen.items():
        for monat, bucket in monatsreihe.items():
            zeile = {"warengruppe": warengruppe, "lieferant": lieferant, "monat": monat}
            zeile.update(bucket)
            wuerfel.append(zeile)
    wuerfel.sort(key=lambda z: (z["warengruppe"], z["lieferant"], z["monat"]))
    return wuerfel, befunde


def abc_klassifizierung(spend_je_objekt, konfig=None):
    # Pareto/ABC über absolute Spends; Rückgabe absteigend sortiert mit
    # Anteil, kumuliertem Anteil und Klasse.
    konfig = _konfig(konfig)
    grenzen = konfig["abc_grenzen"]
    objekte = sorted(spend_je_objekt.items(), key=lambda paar: (-paar[1], paar[0]))
    gesamt = sum(spend for _, spend in objekte)
    ergebnis = []
    kumuliert = 0.0
    for objekt, spend in objekte:
        if gesamt <= 0:
            # Ohne positiven Gesamtspend ist keine Pareto-Aussage möglich.
            ergebnis.append({"objekt": objekt, "spend": spend, "anteil": None,
                             "kumuliert": None, "klasse": "?"})
            continue
        anteil = spend / gesamt
        # Klassenzuordnung nach dem kumulierten Anteil VOR dem Objekt:
        # das Objekt, das eine Grenze überschreitet, zählt zur besseren Klasse.
        if kumuliert < grenzen["A"]:
            klasse = "A"
        elif kumuliert < grenzen["B"]:
            klasse = "B"
        else:
            klasse = "C"
        kumuliert += anteil
        ergebnis.append({"objekt": objekt, "spend": spend, "anteil": anteil,
                         "kumuliert": kumuliert, "klasse": klasse})
    return ergebnis


def _spend_im_fenster(zeilen, dimension, fenster):
    # Jahres-Spend und belegte Monate je Schlüssel einer Dimension,
    # begrenzt auf das Fenster. Aggregation ausschließlich über Phase 0.
    reihen, _ = zeitreihen.baue_monatsreihe(zeilen, dimension)
    fenster_menge = set(fenster)
    spend = {}
    belegte_monate = set()
    for schluessel, monatsreihe in reihen.items():
        summe = 0.0
        getroffen = False
        for monat, bucket in monatsreihe.items():
            if monat in fenster_menge:
                summe += bucket["summe_wert"]
                belegte_monate.add(monat)
                getroffen = True
        if getroffen:
            # "|" kommt in Schlüsseln nicht vor; einteilige Schlüssel
            # bleiben dadurch lesbare Namen statt 1-Tupel.
            spend["|".join(schluessel)] = summe
    return spend, belegte_monate


def konzentration_je_warengruppe(wuerfel, fenster):
    # Anteil des größten und der drei größten Lieferanten am
    # Gruppenspend — Single-Source-Risiko als Zahl.
    fenster_menge = set(fenster)
    je_gruppe = {}
    for zeile in wuerfel:
        if zeile["monat"] not in fenster_menge:
            continue
        gruppe = je_gruppe.setdefault(zeile["warengruppe"], {})
        gruppe[zeile["lieferant"]] = gruppe.get(zeile["lieferant"], 0.0) + zeile["summe_wert"]
    ergebnis = []
    for warengruppe in sorted(je_gruppe):
        lieferanten = sorted(je_gruppe[warengruppe].items(),
                             key=lambda paar: (-paar[1], paar[0]))
        gesamt = sum(spend for _, spend in lieferanten)
        top1_anteil = lieferanten[0][1] / gesamt if gesamt > 0 else None
        top3_anteil = (sum(s for _, s in lieferanten[:3]) / gesamt
                       if gesamt > 0 else None)
        ergebnis.append({
            "warengruppe": warengruppe,
            "gruppenspend": gesamt,
            "n_lieferanten": len(lieferanten),
            "top1_lieferant": lieferanten[0][0],
            "top1_anteil": top1_anteil,
            "top3_anteil": top3_anteil,
        })
    return ergebnis


# --- Ausgabe: CSV-Dateien und Bericht ---

def _schreibe_csv(pfad, metazeile, kopf, zeilen):
    with open(pfad, "w", newline="", encoding="utf-8") as datei:
        datei.write("# " + metazeile + "\n")
        schreiber = csv.writer(datei)
        schreiber.writerow(kopf)
        for zeile in zeilen:
            schreiber.writerow(zeile)


def _zahl(wert, stellen=2):
    if wert is None:
        return ""
    return "%.*f" % (stellen, wert)


def fuehre_spend_analyse_aus(bestellungen, rechnungen=None, ausgabe_ordner=".",
                             konfig=None):
    # Gesamtlauf Phase 1: Preisbasis vereinigen, Würfel bauen, ABC und
    # Konzentration im Jahresfenster rechnen, Dateien schreiben.
    konfig = _konfig(konfig)
    zeilen, befunde = zeitreihen.vereinige_preisbasis(
        bestellungen, rechnungen or [], konfig
    )

    wuerfel, wuerfel_befunde = baue_spend_wuerfel(zeilen, konfig)
    befunde.extend(wuerfel_befunde)

    fenster = jahresfenster(sorted({z["monat"] for z in wuerfel}), konfig)
    spend_material, belegte_monate = _spend_im_fenster(zeilen, "material", fenster)
    spend_lieferant, _ = _spend_im_fenster(zeilen, "lieferant", fenster)
    spend_warengruppe, _ = _spend_im_fenster(zeilen, "warengruppe", fenster)

    abc_material = abc_klassifizierung(spend_material, konfig)
    abc_lieferant = abc_klassifizierung(spend_lieferant, konfig)
    abc_warengruppe = abc_klassifizierung(spend_warengruppe, konfig)
    konzentration = konzentration_je_warengruppe(wuerfel, fenster)

    n_monate = len(belegte_monate)
    hinweis = ("Aussagekraft eingeschränkt, n=%d Monate" % n_monate
               if n_monate < konfig["jahresfenster_monate"] else "")
    zeitraum = "%s bis %s" % (fenster[0], fenster[-1]) if fenster else "keine Daten"
    metazeile = ("Zeitraum: %s | belegte Monate: n=%d | Preisbasis: %s%s"
                 % (zeitraum, n_monate, konfig["preisbasis"]
                    if "preisbasis" in konfig else zeitreihen.KONFIG["preisbasis"],
                    " | " + hinweis if hinweis else ""))

    os.makedirs(ausgabe_ordner, exist_ok=True)
    _schreibe_csv(
        os.path.join(ausgabe_ordner, "spend_wuerfel.csv"), metazeile,
        ["warengruppe", "lieferant", "monat", "summe_menge", "summe_wert",
         "durchschnittspreis", "anzahl_belege", "preisbasis"],
        [[z["warengruppe"], z["lieferant"], z["monat"], _zahl(z["summe_menge"], 6),
          _zahl(z["summe_wert"], 6), _zahl(z["durchschnittspreis"], 6),
          z["anzahl_belege"], z["preisbasis"]] for z in wuerfel],
    )
    for name, abc in (("abc_material.csv", abc_material),
                      ("abc_lieferant.csv", abc_lieferant)):
        _schreibe_csv(
            os.path.join(ausgabe_ordner, name), metazeile,
            ["objekt", "jahres_spend", "anteil", "kumuliert", "klasse"],
            [[e["objekt"], _zahl(e["spend"], 6), _zahl(e["anteil"], 6),
              _zahl(e["kumuliert"], 6), e["klasse"]] for e in abc],
        )
    _schreibe_csv(
        os.path.join(ausgabe_ordner, "konzentration.csv"), metazeile,
        ["warengruppe", "gruppenspend", "n_lieferanten", "top1_lieferant",
         "top1_anteil", "top3_anteil"],
        [[k["warengruppe"], _zahl(k["gruppenspend"], 6), k["n_lieferanten"],
          k["top1_lieferant"], _zahl(k["top1_anteil"], 6),
          _zahl(k["top3_anteil"], 6)] for k in konzentration],
    )

    _schreibe_spend_bericht(
        os.path.join(ausgabe_ordner, "spend.md"), metazeile, abc_warengruppe,
        konzentration, befunde, konfig,
    )

    return {
        "wuerfel": wuerfel,
        "abc_material": abc_material,
        "abc_lieferant": abc_lieferant,
        "abc_warengruppe": abc_warengruppe,
        "konzentration": konzentration,
        "fenster": fenster,
        "n_monate": n_monate,
        "hinweis": hinweis,
        "befunde": befunde,
    }


def _schreibe_spend_bericht(pfad, metazeile, abc_warengruppe, konzentration,
                            befunde, konfig):
    # Bericht: Datengrundlage, Top-Warengruppen und Konzentrations-
    # auffälligkeiten — je Punkt zwei Sätze, mehr nicht.
    konzentration_je_gruppe = {k["warengruppe"]: k for k in konzentration}
    zeilen = ["# Spend-Analyse", "", "**Datengrundlage:** " + metazeile, ""]
    if befunde:
        zeilen.append("**Befunde:**")
        zeilen.extend("- " + b for b in befunde)
        zeilen.append("")

    zeilen.append("## Top-Warengruppen nach Jahres-Spend")
    zeilen.append("")
    for eintrag in abc_warengruppe[:konfig["top_warengruppen_bericht"]]:
        k = konzentration_je_gruppe.get(eintrag["objekt"])
        anteil = ("%.1f %%" % (eintrag["anteil"] * 100)
                  if eintrag["anteil"] is not None else "nicht bestimmbar")
        satz1 = ("**%s**: %.2f EUR Jahres-Spend (%s des Gesamtspend, Klasse %s)."
                 % (eintrag["objekt"], eintrag["spend"], anteil, eintrag["klasse"]))
        if k and k["top1_anteil"] is not None:
            satz2 = ("Der größte Lieferant %s trägt %.1f %% des Gruppenspends "
                     "über %d Lieferant(en)."
                     % (k["top1_lieferant"], k["top1_anteil"] * 100,
                        k["n_lieferanten"]))
        else:
            satz2 = "Eine Lieferantenverteilung ist mangels Daten nicht bestimmbar."
        zeilen.append("- %s %s" % (satz1, satz2))
    zeilen.append("")

    zeilen.append("## Konzentrationsauffälligkeiten (Top-1-Anteil ≥ %.0f %%)"
                  % (konfig["konzentration_warnschwelle"] * 100))
    zeilen.append("")
    auffaellig = [k for k in konzentration
                  if k["top1_anteil"] is not None
                  and k["top1_anteil"] >= konfig["konzentration_warnschwelle"]]
    if auffaellig:
        for k in sorted(auffaellig, key=lambda e: -e["top1_anteil"]):
            satz1 = ("**%s**: %s vereint %.1f %% des Gruppenspends "
                     "(Top 3: %.1f %%)."
                     % (k["warengruppe"], k["top1_lieferant"],
                        k["top1_anteil"] * 100, k["top3_anteil"] * 100))
            satz2 = ("Single-Source-Risiko prüfen — bei Ausfall oder "
                     "Preiserhöhung fehlt kurzfristig eine Alternative.")
            zeilen.append("- %s %s" % (satz1, satz2))
    else:
        zeilen.append("Keine Warengruppe überschreitet die Warnschwelle.")
    zeilen.append("")

    with open(pfad, "w", encoding="utf-8") as datei:
        datei.write("\n".join(zeilen))
