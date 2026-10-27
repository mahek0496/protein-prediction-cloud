"""Builds the human-readable Markdown report stored next to report.json."""


def build_markdown_report(r: dict) -> str:
    a = r.get("analyses", {})
    s = r.get("structure", {})
    lines = [
        f"# Protein Analysis Report: {r['name']}",
        "",
        f"- Job ID: `{r['job_id']}`",
        f"- Generated: {r['generated_at']}",
        f"- Length: {r['length']} residues",
        "",
        "## Sequence",
        "```",
        *[r["sequence"][i:i + 60] for i in range(0, len(r["sequence"]), 60)],
        "```",
        "",
        "## Task results",
        "| Task | Name | Status | Type | Summary |",
        "|---|---|---|---|---|",
    ]
    for t in r.get("task_summaries", []):
        summary = (t.get("summary") or t.get("error") or "").replace("|", "/")
        lines.append(f"| {t['id']} | {t['name']} | {t['status']} | {t.get('result_type') or '-'} | {summary} |")

    d = a.get("D") or {}
    if "molecular_weight_da" in d:
        lines += ["", "## Physicochemical properties (calculated)",
                  f"- Molecular weight: {d['molecular_weight_da']} Da",
                  f"- Isoelectric point: {d['isoelectric_point']}",
                  f"- GRAVY: {d['gravy']} ({d['hydropathy_class']})",
                  f"- Instability index: {d['instability_index']} ({d['stability_class']})",
                  f"- Aromaticity: {d['aromaticity']}"]
    c = a.get("C") or {}
    if "per_residue_states" in c:
        lines += ["", "## Secondary-structure propensity (empirical estimate, not a 3D prediction)",
                  "```", *[c["per_residue_states"][i:i + 60] for i in range(0, len(c["per_residue_states"]), 60)],
                  "```", f"Helix {c['fractions_percent']['helix']}%, strand {c['fractions_percent']['strand']}%, "
                         f"coil {c['fractions_percent']['coil']}%"]

    lines += ["", "## 3D structure prediction"]
    if s.get("available"):
        lines += [f"- Engine: {s['engine']}", f"- Mean pLDDT: {s['mean_plddt']}",
                  f"- Confidence bands: {s['confidence_bands']}",
                  "- Files: structure.pdb, structure.cif", f"- Note: {s['disclaimer']}"]
    else:
        lines += [f"Not available: {s.get('reason', 'no prediction engine')}"]

    lines += ["", "## Disclosures", *[f"- {x}" for x in r.get("disclosures", [])], ""]
    return "\n".join(lines)
