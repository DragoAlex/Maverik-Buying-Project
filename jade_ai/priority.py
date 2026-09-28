"""Schritte 6 und 17: Maße berechnen, Priorität vergeben, Bewertung für Test."""

import numpy as np
import pandas as pd

from .config import CONFIG


def _label(value, bounds):
    for lower, name in bounds:
        if value >= lower:
            return name
    return bounds[-1][1]


def compute_measures(chains, strategic=None, group_cols=("werk", "archetype")):
    """Maße je Prozess (Werk x Archetyp). strategic: Serie/Dict Kunde -> Wert 1-10 (optional)."""
    group_cols = [c for c in group_cols if c in chains.columns]
    g = chains.groupby(group_cols)
    m = pd.DataFrame({"frequency": g.size(),
                      "break_probability": g["has_break"].mean()})
    if "volume" in chains:
        m["volume"] = g["volume"].sum()
    if "quantity" in chains:
        m["quantity"] = g["quantity"].sum()
    if "customer" in chains:
        m["customer_frequency"] = g["customer"].apply(lambda s: s.value_counts().max())
        if strategic is not None:
            strat = pd.Series(strategic)
            m["strategic"] = g["customer"].apply(lambda s: strat.reindex(s).max())
    return m.reset_index()


def prioritize(measures, config=CONFIG):
    """Priorisierungskennzahl = Summe(10 * Gewicht * Anteil des Maßes); Maße ohne Daten entfallen."""
    used = [k for k in config["weights"] if k in measures.columns and measures[k].notna().any()]
    w = pd.Series({k: config["weights"][k] for k in used})
    w = w / w.sum()

    shares = pd.DataFrame(index=measures.index)
    for k in used:
        vals = measures[k].fillna(0).astype(float)
        denom = vals.max() if config["share_mode"] == "max" else vals.sum()
        shares[k] = vals / denom if denom else 0.0

    out = measures.copy()
    out["priority_score"] = 10 * (shares[used] * w).sum(axis=1)
    out["priority"] = out["priority_score"].map(lambda v: _label(v, config["priority_bounds"]))
    out.attrs["measures_used"] = used
    return out


def rate(df, column, config=CONFIG):
    """Bewertung für Test: Min-Max-Normierung innerhalb der Stufe, dann Quantilgrenzen."""
    span = df[column].max() - df[column].min()
    norm = (df[column] - df[column].min()) / span if span else pd.Series(0.0, index=df.index)
    out = df.copy()
    out[column + "_norm"] = norm
    out[column + "_rating"] = norm.map(lambda v: _label(v, config["rating_bounds"]))
    return out
