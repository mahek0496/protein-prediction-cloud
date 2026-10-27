"""Task B: convert a sequence into a numerical feature vector (deterministic calculations)."""
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from .sequence import STANDARD_AA

HYDROPHOBIC = set("AILMFVWY")
POSITIVE = set("KRH")
NEGATIVE = set("DE")
POLAR = set("STNQCGP")


def build_feature_vector(seq: str) -> dict:
    pa = ProteinAnalysis(seq)
    n = len(seq)
    composition = [seq.count(aa) / n for aa in STANDARD_AA]
    physchem = {
        "length": float(n),
        "molecular_weight": pa.molecular_weight(),
        "isoelectric_point": pa.isoelectric_point(),
        "gravy": pa.gravy(),
        "aromaticity": pa.aromaticity(),
        "instability_index": pa.instability_index(),
        "charge_at_pH7": pa.charge_at_pH(7.0),
        "fraction_hydrophobic": sum(aa in HYDROPHOBIC for aa in seq) / n,
        "fraction_positive": sum(aa in POSITIVE for aa in seq) / n,
        "fraction_negative": sum(aa in NEGATIVE for aa in seq) / n,
        "fraction_polar": sum(aa in POLAR for aa in seq) / n,
    }
    names = [f"comp_{aa}" for aa in STANDARD_AA] + list(physchem)
    values = [round(v, 5) for v in composition + list(physchem.values())]
    return {
        "feature_names": names,
        "vector": values,
        "dimension": len(values),
        "physicochemical": {k: round(v, 4) for k, v in physchem.items()},
    }
