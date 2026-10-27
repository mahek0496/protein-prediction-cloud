"""Task H: genuine 3D structure prediction with ESMFold (Lin et al., Science 2023).

ESMFold runs on remote GPU servers; this app sends the sequence and receives a PDB file whose
B-factor column holds per-residue pLDDT confidence. If no engine is configured or reachable, the
task reports that clearly instead of inventing coordinates.
"""
import io
import statistics

import requests
from Bio.PDB import MMCIFIO, PDBParser

from ..config import settings


class PredictionSkipped(Exception):
    """No prediction engine configured: the task is skipped (not a failure)."""


class PredictionError(Exception):
    """The engine was configured but the prediction did not succeed."""


def _call_esmatlas(seq: str) -> str:
    resp = requests.post(settings.esmatlas_url, data=seq, timeout=settings.prediction_timeout_seconds)
    if resp.status_code != 200:
        raise PredictionError(f"ESM Atlas API returned HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.text


def _call_nvidia(seq: str) -> str:
    if not settings.nvidia_api_key:
        raise PredictionError("PREDICTION_ENGINE=nvidia but NVIDIA_API_KEY is not set.")
    resp = requests.post(
        settings.nvidia_esmfold_url,
        json={"sequence": seq},
        headers={"Authorization": f"Bearer {settings.nvidia_api_key}", "Accept": "application/json"},
        timeout=settings.prediction_timeout_seconds,
    )
    if resp.status_code != 200:
        raise PredictionError(f"NVIDIA ESMFold API returned HTTP {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    pdbs = data.get("pdbs") or ([data["pdb"]] if data.get("pdb") else [])
    if not pdbs:
        raise PredictionError("NVIDIA ESMFold response did not contain a PDB structure.")
    return pdbs[0]


ENGINES = {
    "esmatlas": ("ESMFold via Meta ESM Atlas API", _call_esmatlas),
    "nvidia": ("ESMFold via NVIDIA hosted API", _call_nvidia),
}


def parse_plddt(pdb_text: str) -> list:
    """Per-residue pLDDT (0-100) from the CA atoms' B-factor column."""
    values = []
    for line in pdb_text.splitlines():
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            try:
                values.append(float(line[60:66]))
            except ValueError:
                continue
    if values and max(values) <= 1.0:  # some ESMFold servers report 0-1
        values = [v * 100 for v in values]
    return [round(v, 2) for v in values]


def pdb_to_mmcif(pdb_text: str) -> str:
    structure = PDBParser(QUIET=True).get_structure("prediction", io.StringIO(pdb_text))
    out = io.StringIO()
    writer = MMCIFIO()
    writer.set_structure(structure)
    writer.save(out)
    return out.getvalue()


def predict_structure(seq: str) -> dict:
    engine = settings.prediction_engine
    if engine == "none":
        raise PredictionSkipped(
            "No structure prediction engine configured (PREDICTION_ENGINE=none). "
            "3D structure prediction is unavailable; no coordinates were generated."
        )
    if engine not in ENGINES:
        raise PredictionError(f"Unknown PREDICTION_ENGINE '{engine}'. Use esmatlas, nvidia or none.")
    label, call = ENGINES[engine]
    try:
        pdb_text = call(seq)
    except requests.exceptions.Timeout:
        raise PredictionError(f"{label} timed out after {settings.prediction_timeout_seconds:.0f}s.")
    except requests.exceptions.ConnectionError:
        raise PredictionError(f"Could not connect to {label}. Check internet access / outbound HTTPS.")
    if "ATOM" not in pdb_text:
        raise PredictionError(f"{label} returned no atomic coordinates.")

    plddt = parse_plddt(pdb_text)
    if len(plddt) != len(seq):
        raise PredictionError(f"Returned structure has {len(plddt)} residues but sequence has {len(seq)}.")
    mean = statistics.fmean(plddt)
    bands = {
        "very_high_>90": sum(v > 90 for v in plddt),
        "confident_70_90": sum(70 < v <= 90 for v in plddt),
        "low_50_70": sum(50 < v <= 70 for v in plddt),
        "very_low_<=50": sum(v <= 50 for v in plddt),
    }
    return {
        "result_type": "ml_prediction",
        "available": True,
        "engine": label,
        "method": "ESMFold (Lin et al., Science 2023) single-sequence structure prediction",
        "mean_plddt": round(mean, 2),
        "per_residue_plddt": plddt,
        "confidence_bands": bands,
        "disclaimer": "Computational prediction. pLDDT is the model's own confidence; low-pLDDT regions "
                      "are often disordered or unreliable. Not experimentally determined.",
        "summary": f"{label}: predicted {len(plddt)}-residue model, mean pLDDT {mean:.1f}.",
        "_files": {"structure.pdb": pdb_text, "structure.cif": pdb_to_mmcif(pdb_text)},
    }
