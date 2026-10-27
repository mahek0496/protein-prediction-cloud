"""Task A helpers: parse FASTA / plain text and validate an amino-acid sequence."""
import re
from collections import Counter

STANDARD_AA = "ACDEFGHIKLMNPQRSTVWY"


class SequenceError(ValueError):
    """Raised when the submitted sequence is not a usable protein sequence."""


def parse_sequence(raw: str) -> tuple:
    """Return (name, sequence) from FASTA or plain text. Only the first FASTA record is used."""
    if raw is None or not raw.strip():
        raise SequenceError("Please enter a protein sequence.")
    lines = [ln.strip() for ln in raw.strip().splitlines() if ln.strip()]
    name = "Unnamed sequence"
    if lines[0].startswith(">"):
        name = lines[0][1:].strip() or name
        body = []
        for ln in lines[1:]:
            if ln.startswith(">"):
                break  # ignore further records
            body.append(ln)
        lines = body
    seq = re.sub(r"[\s\d*]", "", "".join(lines)).upper()  # drop spaces, numbering, stop '*'
    return name[:120], seq


def validate_sequence(seq: str, min_len: int, max_len: int) -> dict:
    """Validate and return a summary. Raises SequenceError with a readable message."""
    if not seq:
        raise SequenceError("The sequence is empty after removing whitespace and FASTA headers.")
    if len(seq) >= 10 and set(seq) <= set("ACGTUN"):
        raise SequenceError("This looks like a DNA/RNA sequence (only A, C, G, T/U, N). "
                            "Please translate it to a protein sequence first.")
    invalid = sorted(set(seq) - set(STANDARD_AA))
    if invalid:
        positions = [i + 1 for i, aa in enumerate(seq) if aa not in STANDARD_AA][:5]
        raise SequenceError(
            f"Invalid character(s) {', '.join(invalid)} at position(s) {positions}. "
            f"Only the 20 standard amino-acid letters ({STANDARD_AA}) are accepted."
        )
    if len(seq) < min_len:
        raise SequenceError(f"Sequence is too short ({len(seq)} residues). Minimum is {min_len}.")
    if len(seq) > max_len:
        raise SequenceError(f"Sequence is too long ({len(seq)} residues). Maximum is {max_len}.")

    counts = Counter(seq)
    composition = {aa: counts.get(aa, 0) for aa in STANDARD_AA}
    return {
        "length": len(seq),
        "composition_counts": composition,
        "composition_percent": {aa: round(100 * c / len(seq), 2) for aa, c in composition.items()},
        "most_common": [{"residue": aa, "count": c} for aa, c in counts.most_common(5)],
        "starts_with_methionine": seq[0] == "M",
    }
