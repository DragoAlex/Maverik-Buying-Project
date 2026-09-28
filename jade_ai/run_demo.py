"""Demolauf: python -m jade_ai.run_demo  (aus dem Projektverzeichnis)"""

import pandas as pd

from .demo_data import make_demo_tables
from .doc_graph import build_chains
from .priority import compute_measures, prioritize, rate
from .quality import available_steps, quality_report


def main():
    tables = make_demo_tables()

    # --- Schritt 1: Datenqualität und verfügbare Analyseschritte ---
    print("QUALITÄT\n", quality_report(tables).to_string(index=False), "\n")
    print("ANALYSESCHRITTE\n", available_steps(tables).to_string(index=False), "\n")

    # --- Schritt 2: Ketten, Archetypen und Brüche ---
    chains, _ = build_chains(tables)
    print("KETTEN:", len(chains), "| mit Bruch:", int(chains["has_break"].sum()), "\n")

    # --- Schritt 3: Maße, Priorität und Bewertung für Test ---
    result = rate(prioritize(compute_measures(chains)), "priority_score")
    pd.set_option("display.width", 200)
    print(result.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
