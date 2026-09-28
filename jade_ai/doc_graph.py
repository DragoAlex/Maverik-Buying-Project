"""Beleggraph: Belege als Knoten, Referenzen als Kanten, Prozessketten als Zusammenhangskomponenten."""

import numpy as np
import pandas as pd

from .config import CONFIG


def build_edges(tables, config=CONFIG):
    """Erzeugt alle Kanten (Beleg -> referenzierter Beleg) aus den konfigurierten Verweisspalten."""
    parts = []
    for name, spec in config["tables"].items():
        if name not in tables or spec["key"] not in tables[name].columns:
            continue
        df = tables[name]
        for ref_col, target_type in spec["refs"].items():
            if ref_col not in df.columns:
                continue
            sub = df[[spec["key"], ref_col]].dropna()
            parts.append(pd.DataFrame({
                "src": name + ":" + sub[spec["key"]].astype(str),
                "dst": target_type + ":" + sub[ref_col].astype(str),
            }))
    if not parts:
        return pd.DataFrame(columns=["src", "dst"])
    return pd.concat(parts, ignore_index=True).drop_duplicates()


def _find_components(edges, extra_nodes):
    """Union-Find über alle Knoten; liefert Knoten -> Komponenten-ID."""
    nodes = pd.unique(np.concatenate([edges["src"], edges["dst"], extra_nodes]))
    index = pd.Series(np.arange(len(nodes)), index=nodes)
    parent = np.arange(len(nodes))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in zip(index[edges["src"]].to_numpy(), index[edges["dst"]].to_numpy()):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    roots = np.array([find(i) for i in range(len(nodes))])
    return pd.Series(roots, index=nodes)


def build_chains(tables, config=CONFIG):
    """Bildet Prozessketten, ordnet Archetyp zu und erkennt Brüche und Sprünge."""
    edges = build_edges(tables, config)

    # --- Schritt 1: alle vorhandenen Belege als Knoten sammeln ---
    doc_nodes = []
    for name, spec in config["tables"].items():
        if name in tables and spec["key"] in tables[name].columns:
            keys = tables[name][spec["key"]].dropna().astype(str)
            doc_nodes.append(name + ":" + keys)
    all_docs = pd.concat(doc_nodes, ignore_index=True)

    # --- Schritt 2: Ketten als Zusammenhangskomponenten bestimmen ---
    comp = _find_components(edges, all_docs.to_numpy())
    docs = pd.DataFrame({"node": all_docs.to_numpy()})
    docs["doc_type"] = docs["node"].str.split(":", n=1).str[0]
    docs["chain_id"] = comp[docs["node"]].to_numpy()

    # --- Schritt 3: Archetyp und Bruchstellen je Kette bestimmen ---
    stages = docs.groupby("chain_id")["doc_type"].agg(lambda s: sorted(set(s)))
    rows = []
    for chain_id, present in stages.items():
        arch, template = max(config["archetypes"].items(),
                             key=lambda kv: len(set(kv[1]) & set(present)))
        pos = [template.index(s) for s in present if s in template]
        first, last = min(pos), max(pos)
        gaps = [s for s in template[first:last + 1] if s not in present]
        rows.append({
            "chain_id": chain_id, "archetype": arch,
            "n_docs": int((docs["chain_id"] == chain_id).sum()),
            "stages": ",".join(s for s in template if s in present),
            "late_start": first > 0,
            "early_end": last < len(template) - 1,
            "gap": bool(gaps), "missing_between": ",".join(gaps),
        })
    chains = pd.DataFrame(rows)
    chains["has_break"] = chains[["late_start", "early_end", "gap"]].any(axis=1)

    # --- Schritt 4: Kontext (Werk, Kunde, Menge, Wert) aus der führenden Tabelle ergänzen ---
    chains = chains.merge(_context(tables, docs, config), on="chain_id", how="left")
    return chains, docs


def _context(tables, docs, config):
    """Werk, Kunde, Menge und Wert je Kette aus den konfigurierten Kontextspalten."""
    frames = []
    for name, spec in config["tables"].items():
        ctx = spec.get("context")
        if not ctx or name not in tables:
            continue
        df = tables[name]
        cols = {k: v for k, v in ctx.items() if v in df.columns}
        sub = df[[spec["key"]] + list(cols.values())].copy()
        sub.columns = ["key"] + list(cols.keys())
        for num in ("quantity", "price"):
            if num in sub:
                sub[num] = pd.to_numeric(sub[num], errors="coerce")
        sub["node"] = name + ":" + sub["key"].astype(str)
        sub = sub.merge(docs[["node", "chain_id"]], on="node")
        frames.append(sub.drop(columns=["key", "node"]))
    if not frames:
        return pd.DataFrame({"chain_id": docs["chain_id"].unique()})
    ctx_df = pd.concat(frames, ignore_index=True)
    if {"quantity", "price"} <= set(ctx_df.columns):
        ctx_df["volume"] = ctx_df["quantity"] * ctx_df["price"]
    agg = {c: "first" for c in ("werk", "customer") if c in ctx_df}
    agg.update({c: "sum" for c in ("quantity", "volume") if c in ctx_df})
    return ctx_df.groupby("chain_id").agg(agg).reset_index()
