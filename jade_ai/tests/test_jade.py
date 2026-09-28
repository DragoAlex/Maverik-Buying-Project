import pandas as pd

from jade_ai.demo_data import make_demo_tables
from jade_ai.doc_graph import build_chains
from jade_ai.priority import compute_measures, prioritize, rate
from jade_ai.quality import available_steps, normalize, quality_report


def test_chain_count_equals_customer_pos():
    tables = make_demo_tables(n=100)
    chains, _ = build_chains(tables)
    assert len(chains) == 100


def test_breaks_detected():
    tables = make_demo_tables(n=300, seed=1)
    chains, _ = build_chains(tables)
    assert chains["early_end"].any() and chains["late_start"].any() and chains["gap"].any()
    full = chains[~chains["has_break"]]
    assert (full["stages"].str.count(",") == 6).all()


def test_missing_table_is_reported_and_graph_still_builds():
    tables = make_demo_tables(n=50)
    del tables["ZAHLUNG"]
    report = quality_report(tables)
    assert (report["issue"] == "Tabelle fehlt").any()
    steps = available_steps(tables).set_index("step")
    assert not steps.loc["Zahlungsabschluss", "possible"]
    chains, _ = build_chains(tables)
    assert chains["early_end"].all()


def test_priority_scores_within_scale_and_ranked():
    tables = make_demo_tables(n=200)
    chains, _ = build_chains(tables)
    res = prioritize(compute_measures(chains))
    assert res["priority_score"].between(0, 10).all()
    top = res.sort_values("priority_score").iloc[-1]
    assert top["priority"] in ("sehr hoch", "hoch", "mittel")


def test_rating_bounds():
    df = pd.DataFrame({"s": [0.0, 1.0, 5.0, 9.0, 10.0]})
    out = rate(df, "s")
    assert list(out["s_rating"]) == ["sehr gering", "sehr gering", "mittel", "sehr hoch", "sehr hoch"]


def test_normalize_keeps_leading_zeros_as_text():
    df = normalize(pd.DataFrame({" Beleg ": ["0001", " 0002 ", ""]}))
    assert list(df["beleg"].dropna()) == ["0001", "0002"]
