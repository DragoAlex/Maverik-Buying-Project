# zeitreihen.py — Phase 0: Zeitreihen-Fundament des Category-Management-Pakets.
#
# Der Stack kannte bisher keine Zeitdimension. Dieses Modul erzeugt aus
# P2P-Belegzeilen Monats-Zeitreihen je Schlüsselkombination (Material,
# Warengruppe, Lieferant, Material×Lieferant) und ist die einzige Quelle
# von Zeitreihen für alle Folgephasen (Spend, XYZ, Korrelation, Index).
#
# Grundsätze:
# - Monat = Kalendermonat aus dem Belegdatum, Schlüssel "YYYY-MM".
# - Durchschnittspreis je Bucket ist MENGENGEWICHTET (Summe Wert / Summe
#   Menge). Das ungewichtete Mittel der Einzelpreise wäre falsch, weil
#   kleine Bestellungen den Preis gleich stark prägen würden wie große.
# - Monate ohne Belege bleiben Lücke. Kein Auffüllen mit 0: null
#   Bestellungen ist keine Preisinformation, und eine 0 würde jede
#   Statistik auf der Reihe verfälschen. Funktionen, die durchgängige
#   Reihen brauchen, dokumentieren ihren Lücken-Umgang selbst.
# - Preisbasis konfigurierbar: Bestellpreis oder Rechnungs-Ist-Preis.
#   Default "auto" = Rechnung, wenn zur Bestellung vorhanden, sonst
#   Bestellung — jeder Bucket trägt ein Kennzeichen, welche Basis
#   eingeflossen ist ("bestellung", "rechnung" oder "gemischt").
# - Fehlende oder unbrauchbare Angaben erzeugen Befunde statt stiller
#   Annahmen; Zeilen ohne Datum oder ohne Menge/Wert werden unter Befund
#   ausgeschlossen, fehlende Warengruppe wird als Befund gemeldet und
#   unter dem Platzhalter geführt, damit kein Spend verloren geht.

from datetime import date, datetime

KONFIG = {
    # "auto" = Rechnung wenn vorhanden, sonst Bestellung; alternativ
    # "bestellung" oder "rechnung" als alleinige Basis.
    "preisbasis": "auto",
    # Unter dieser Historientiefe weisen Auswertungen "Aussagekraft
    # eingeschränkt, n=X Monate" aus (Datenannahme: ideal 12–24 Monate).
    "min_monate_aussagekraft": 12,
}

# Schlüsselfelder je auswertbarer Dimension.
DIMENSIONEN = {
    "material": ("materialnummer",),
    "warengruppe": ("warengruppe",),
    "lieferant": ("lieferant",),
    "material_lieferant": ("materialnummer", "lieferant"),
    "warengruppe_lieferant": ("warengruppe", "lieferant"),
}

PLATZHALTER_WARENGRUPPE = "(ohne Warengruppe)"


def _konfig(ueberschreibung):
    zusammen = dict(KONFIG)
    if ueberschreibung:
        zusammen.update(ueberschreibung)
    return zusammen


def monat_aus_datum(wert):
    # Akzeptiert date/datetime und ISO-Strings ("YYYY-MM-DD..."); alles
    # andere liefert None — der Aufrufer erzeugt daraus einen Befund,
    # statt ein Datum zu raten.
    if isinstance(wert, (date, datetime)):
        return "%04d-%02d" % (wert.year, wert.month)
    if isinstance(wert, str):
        text = wert.strip()
        if len(text) >= 7 and text[4] == "-":
            try:
                jahr = int(text[0:4])
                monat = int(text[5:7])
            except ValueError:
                return None
            if 1 <= monat <= 12:
                return "%04d-%02d" % (jahr, monat)
    return None


def monatsspanne(von, bis):
    # Alle Kalendermonate von "YYYY-MM" bis "YYYY-MM" einschließlich.
    jahr, monat = int(von[0:4]), int(von[5:7])
    ende_jahr, ende_monat = int(bis[0:4]), int(bis[5:7])
    spanne = []
    while (jahr, monat) <= (ende_jahr, ende_monat):
        spanne.append("%04d-%02d" % (jahr, monat))
        monat += 1
        if monat > 12:
            monat = 1
            jahr += 1
    return spanne


def monatsluecken(monatsreihe):
    # Fehlende Monate zwischen erstem und letztem belegten Monat.
    monate = sorted(monatsreihe)
    if len(monate) < 2:
        return []
    return [m for m in monatsspanne(monate[0], monate[-1]) if m not in monatsreihe]


def vereinige_preisbasis(bestellungen, rechnungen, konfig=None):
    # Führt Bestell- und Rechnungszeilen gemäß Preisbasis-Konfiguration zu
    # einer Belegzeilenliste zusammen; jede Zeile trägt ihr
    # "preisbasis"-Kennzeichen. Rückgabe: (zeilen, befunde).
    konfig = _konfig(konfig)
    modus = konfig["preisbasis"]
    befunde = []

    def mit_kennzeichen(zeilen, kennzeichen):
        markiert = []
        for zeile in zeilen:
            kopie = dict(zeile)
            kopie["preisbasis"] = kennzeichen
            markiert.append(kopie)
        return markiert

    if modus == "bestellung":
        return mit_kennzeichen(bestellungen, "bestellung"), befunde
    if modus == "rechnung":
        if not rechnungen:
            befunde.append(
                "Preisbasis 'rechnung' konfiguriert, aber keine Rechnungszeilen vorhanden."
            )
        return mit_kennzeichen(rechnungen, "rechnung"), befunde

    # Modus "auto": Rechnung ersetzt die zugehörige Bestellung; Bestellungen
    # ohne Rechnung bleiben mit Bestellpreis erhalten.
    fakturierte_bestellungen = set()
    for zeile in rechnungen:
        nummer = zeile.get("bestellnummer")
        if nummer not in (None, ""):
            fakturierte_bestellungen.add(nummer)
    zeilen = mit_kennzeichen(rechnungen, "rechnung")
    for zeile in bestellungen:
        if zeile.get("bestellnummer") in fakturierte_bestellungen:
            continue
        kopie = dict(zeile)
        kopie["preisbasis"] = "bestellung"
        zeilen.append(kopie)
    return zeilen, befunde


def pruefe_belegzeilen(zeilen):
    # Datenqualitäts-Befunde, die keine Zeile ausschließen, aber im
    # Bericht auftauchen müssen (z. B. fehlende Warengruppe).
    befunde = []
    ohne_warengruppe = sum(
        1 for z in zeilen if z.get("warengruppe") in (None, "")
    )
    if ohne_warengruppe:
        befunde.append(
            "%d Belegzeile(n) ohne Warengruppe — im Bucketing unter '%s' geführt."
            % (ohne_warengruppe, PLATZHALTER_WARENGRUPPE)
        )
    return befunde


def _wert_und_menge(zeile):
    # Wert = explizites Feld "wert", sonst menge × preis; None bei
    # unbrauchbaren Angaben.
    menge = zeile.get("menge")
    if not isinstance(menge, (int, float)):
        return None, None
    wert = zeile.get("wert")
    if isinstance(wert, (int, float)):
        return float(menge), float(wert)
    preis = zeile.get("preis")
    if not isinstance(preis, (int, float)):
        return None, None
    return float(menge), float(menge) * float(preis)


def baue_monatsreihe(zeilen, dimension, konfig=None):
    # Kernfunktion: Belegzeilen → {schluessel: {monat: bucket}}.
    # Bucket: summe_menge, summe_wert, durchschnittspreis (gewichtet),
    # anzahl_belege, preisbasis. Rückgabe: (reihen, befunde).
    if dimension not in DIMENSIONEN:
        raise ValueError("Unbekannte Dimension: %r" % (dimension,))
    felder = DIMENSIONEN[dimension]
    befunde = list(pruefe_belegzeilen(zeilen))
    roh = {}

    for index, zeile in enumerate(zeilen):
        monat = monat_aus_datum(zeile.get("belegdatum"))
        if monat is None:
            befunde.append(
                "Zeile %d: Belegdatum fehlt oder unlesbar (%r) — ausgeschlossen."
                % (index, zeile.get("belegdatum"))
            )
            continue
        menge, wert = _wert_und_menge(zeile)
        if menge is None:
            befunde.append(
                "Zeile %d: Menge/Preis/Wert unbrauchbar — ausgeschlossen." % index
            )
            continue

        schluessel_teile = []
        for feld in felder:
            teil = zeile.get(feld)
            if teil in (None, ""):
                teil = PLATZHALTER_WARENGRUPPE if feld == "warengruppe" else "(unbekannt)"
            schluessel_teile.append(teil)
        schluessel = tuple(schluessel_teile)

        bucket = roh.setdefault(schluessel, {}).setdefault(
            monat,
            {"summe_menge": 0.0, "summe_wert": 0.0, "anzahl_belege": 0, "basen": set()},
        )
        bucket["summe_menge"] += menge
        bucket["summe_wert"] += wert
        bucket["anzahl_belege"] += 1
        bucket["basen"].add(zeile.get("preisbasis", "bestellung"))

    # Abschluss: gewichteten Preis berechnen, Preisbasis-Kennzeichen setzen.
    reihen = {}
    for schluessel, monate in roh.items():
        reihen[schluessel] = {}
        for monat, bucket in monate.items():
            if bucket["summe_menge"] != 0:
                preis = bucket["summe_wert"] / bucket["summe_menge"]
            else:
                # Ohne Menge ist kein Stückpreis definierbar (z. B. reine
                # Wertkorrektur) — None statt Division durch 0.
                preis = None
            basen = bucket["basen"]
            reihen[schluessel][monat] = {
                "summe_menge": bucket["summe_menge"],
                "summe_wert": bucket["summe_wert"],
                "durchschnittspreis": preis,
                "anzahl_belege": bucket["anzahl_belege"],
                "preisbasis": basen.pop() if len(basen) == 1 else "gemischt",
            }
    return reihen, befunde


def historientiefe(monatsreihe, konfig=None):
    # Datenlage einer einzelnen Monatsreihe: Umfang, Spanne, Lücken und
    # Hinweis, wenn die Historie unter der konfigurierten Schwelle liegt.
    konfig = _konfig(konfig)
    monate = sorted(monatsreihe)
    tiefe = {
        "n_monate": len(monate),
        "von": monate[0] if monate else None,
        "bis": monate[-1] if monate else None,
        "luecken": monatsluecken(monatsreihe),
        "aussagekraft_eingeschraenkt": len(monate) < konfig["min_monate_aussagekraft"],
    }
    tiefe["hinweis"] = (
        "Aussagekraft eingeschränkt, n=%d Monate" % len(monate)
        if tiefe["aussagekraft_eingeschraenkt"]
        else ""
    )
    return tiefe
