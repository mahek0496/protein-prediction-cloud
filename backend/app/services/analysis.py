"""Tasks C-G: independent sequence-based analyses.

Every result carries a `result_type` so the UI can label it honestly:
  - "calculation"         deterministic physicochemical calculation from the sequence
  - "empirical_estimate"  classic statistical method with limited accuracy (NOT a structure prediction)
  - "rule_based_screen"   pattern/threshold screen that flags candidates only
"""
import math
import re

from Bio.SeqUtils.ProtParam import ProteinAnalysis

# Chou & Fasman (1978) conformational parameters: (P_alpha, P_beta)
CHOU_FASMAN = {
    "A": (1.42, 0.83), "R": (0.98, 0.93), "N": (0.67, 0.89), "D": (1.01, 0.54), "C": (0.70, 1.19),
    "Q": (1.11, 1.10), "E": (1.51, 0.37), "G": (0.57, 0.75), "H": (1.00, 0.87), "I": (1.08, 1.60),
    "L": (1.21, 1.30), "K": (1.16, 0.74), "M": (1.45, 1.05), "F": (1.13, 1.38), "P": (0.57, 0.55),
    "S": (0.77, 0.75), "T": (0.83, 1.19), "W": (1.08, 1.37), "Y": (0.69, 1.47), "V": (1.06, 1.70),
}

# Kyte & Doolittle (1982) hydropathy scale
KYTE_DOOLITTLE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5, "G": -0.4, "H": -3.2,
    "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9,
    "Y": -1.3, "V": 4.2,
}


def _window_avg(values, window):
    half = window // 2
    out = []
    for i in range(len(values)):
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def _segments(flags, symbol, min_len=1):
    """Return [(start, end)] 1-based runs where flags[i] == symbol."""
    runs, start = [], None
    for i, f in enumerate(list(flags) + [None]):
        if f == symbol and start is None:
            start = i
        elif f != symbol and start is not None:
            if i - start >= min_len:
                runs.append({"start": start + 1, "end": i, "length": i - start})
            start = None
    return runs


# ---------------- Task C ----------------
def secondary_structure_propensity(seq: str) -> dict:
    pa_vals = [CHOU_FASMAN[a][0] for a in seq]
    pb_vals = [CHOU_FASMAN[a][1] for a in seq]
    pa_avg, pb_avg = _window_avg(pa_vals, 6), _window_avg(pb_vals, 6)
    states = []
    for a, b in zip(pa_avg, pb_avg):
        if a > 1.03 and a >= b:
            states.append("H")
        elif b > 1.05:
            states.append("E")
        else:
            states.append("C")
    n = len(seq)
    helix, turn, sheet = ProteinAnalysis(seq).secondary_structure_fraction()
    return {
        "result_type": "empirical_estimate",
        "method": "Simplified Chou-Fasman propensity scan (window 6) + Biopython residue-class fractions",
        "disclaimer": "Empirical propensity estimate (typically ~50-60% per-residue accuracy). "
                      "It is NOT a 3D structure prediction.",
        "per_residue_states": "".join(states),
        "fractions_percent": {
            "helix": round(100 * states.count("H") / n, 1),
            "strand": round(100 * states.count("E") / n, 1),
            "coil": round(100 * states.count("C") / n, 1),
        },
        "biopython_residue_class_fractions": {
            "helix_favouring": round(helix, 3), "turn_favouring": round(turn, 3), "sheet_favouring": round(sheet, 3)
        },
        "helix_segments": _segments(states, "H", 4),
        "strand_segments": _segments(states, "E", 3),
        "summary": f"Propensity estimate: {states.count('H')} helix-favouring, "
                   f"{states.count('E')} strand-favouring, {states.count('C')} coil residues.",
    }


# ---------------- Task D ----------------
def physicochemical_profile(seq: str) -> dict:
    pa = ProteinAnalysis(seq)
    instability = pa.instability_index()
    gravy = pa.gravy()
    ext_reduced, ext_disulfide = pa.molar_extinction_coefficient()
    return {
        "result_type": "calculation",
        "method": "Biopython ProtParam (ExPASy ProtParam equivalents)",
        "molecular_weight_da": round(pa.molecular_weight(), 2),
        "isoelectric_point": round(pa.isoelectric_point(), 2),
        "gravy": round(gravy, 3),
        "aromaticity": round(pa.aromaticity(), 3),
        "instability_index": round(instability, 2),
        "stability_class": "stable" if instability < 40 else "unstable",
        "hydropathy_class": "hydrophobic" if gravy > 0 else "hydrophilic",
        "mean_flexibility": round(sum(pa.flexibility()) / max(1, len(seq) - 8), 4),
        "extinction_coefficient_reduced_cys": ext_reduced,
        "extinction_coefficient_cystines": ext_disulfide,
        "summary": f"MW {pa.molecular_weight() / 1000:.1f} kDa, pI {pa.isoelectric_point():.2f}, "
                   f"predicted {'stable' if instability < 40 else 'unstable'} in vitro "
                   f"(instability index {instability:.1f}; Guruprasad et al. 1990 rule).",
    }


# ---------------- Task E ----------------
def hydropathy_transmembrane(seq: str) -> dict:
    scores = [KYTE_DOOLITTLE[a] for a in seq]
    plot_profile = _window_avg(scores, 9)
    tm_profile = _window_avg(scores, 19)
    flags = ["T" if v > 1.6 else "-" for v in tm_profile] if len(seq) >= 19 else ["-"] * len(seq)
    segments = _segments(flags, "T", 15)
    return {
        "result_type": "rule_based_screen",
        "method": "Kyte-Doolittle hydropathy (window 9 for plot; window 19, threshold 1.6 for TM screen)",
        "disclaimer": "Hydropathy screen flags CANDIDATE transmembrane segments only.",
        "profile": [{"position": i + 1, "score": round(v, 3)} for i, v in enumerate(plot_profile)],
        "candidate_transmembrane_segments": segments,
        "membrane_protein_candidate": bool(segments),
        "summary": f"{len(segments)} candidate transmembrane segment(s) found by hydropathy screen.",
    }


# ---------------- Task F ----------------
def charge_profile(seq: str) -> dict:
    pa = ProteinAnalysis(seq)
    curve = [{"pH": ph, "charge": round(pa.charge_at_pH(ph), 3)} for ph in [x * 0.5 for x in range(2, 29)]]
    pi = pa.isoelectric_point()
    category = "acidic" if pi < 6.5 else "basic" if pi > 7.5 else "near-neutral"
    return {
        "result_type": "calculation",
        "method": "Henderson-Hasselbalch net charge (Biopython IsoelectricPoint pKa set)",
        "charge_curve": curve,
        "charge_at_pH7_4": round(pa.charge_at_pH(7.4), 3),
        "isoelectric_point": round(pi, 2),
        "pi_category": category,
        "positive_residues": sum(seq.count(a) for a in "KR"),
        "negative_residues": sum(seq.count(a) for a in "DE"),
        "summary": f"Net charge {pa.charge_at_pH(7.4):+.2f} at pH 7.4; {category} protein (pI {pi:.2f}).",
    }


# ---------------- Task G ----------------
def _shannon_entropy(s: str) -> float:
    n = len(s)
    return -sum((s.count(c) / n) * math.log2(s.count(c) / n) for c in set(s))


def motif_scan(seq: str) -> dict:
    glyco = [{"position": m.start() + 1, "motif": m.group(1)}
             for m in re.finditer(r"(?=(N[^P][ST][^P]))", seq)]
    window = 12
    low = ["L" if len(seq) >= window and _shannon_entropy(seq[max(0, i - 6):i + 6]) < 2.2 else "-"
           for i in range(len(seq))]
    low_regions = _segments(low, "L", window)
    cys = seq.count("C")
    return {
        "result_type": "rule_based_screen",
        "method": "PROSITE PS00001 pattern N-{P}-[ST]-{P}; Shannon-entropy low-complexity scan (window 12, < 2.2 bits)",
        "disclaimer": "Pattern matches are potential sites, not experimentally confirmed modifications.",
        "n_glycosylation_sites": glyco,
        "cysteine_count": cys,
        "max_possible_disulfide_bonds": cys // 2,
        "low_complexity_regions": low_regions,
        "proline_percent": round(100 * seq.count("P") / len(seq), 2),
        "glycine_percent": round(100 * seq.count("G") / len(seq), 2),
        "summary": f"{len(glyco)} potential N-glycosylation site(s), {cys} cysteine(s), "
                   f"{len(low_regions)} low-complexity region(s).",
    }
