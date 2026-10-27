import pytest

from app.services.features import build_feature_vector
from app.services.sequence import SequenceError, parse_sequence, validate_sequence
from tests.conftest import UBIQUITIN


def test_parse_fasta_header_and_whitespace():
    name, seq = parse_sequence(">sp|P0CG48|UBQ test\nMQIFV KTLTG\n10 KTITL*\n>second\nAAAA")
    assert name == "sp|P0CG48|UBQ test"
    assert seq == "MQIFVKTLTGKTITL"


def test_plain_lowercase_is_uppercased():
    assert parse_sequence("mqifvktltg")[1] == "MQIFVKTLTG"


def test_invalid_characters_reported():
    with pytest.raises(SequenceError, match="Invalid character"):
        validate_sequence("MQIFVKTLTGBXZ", 10, 400)


def test_dna_hint():
    with pytest.raises(SequenceError, match="DNA/RNA"):
        validate_sequence("ATGCGTACGTTAGC", 10, 400)


@pytest.mark.parametrize("seq,msg", [("MQIF", "too short"), ("L" * 401, "too long"), ("", "empty")])
def test_length_limits(seq, msg):
    with pytest.raises(SequenceError, match=msg):
        validate_sequence(seq, 10, 400)


def test_empty_input():
    with pytest.raises(SequenceError):
        parse_sequence("   ")


def test_feature_vector_shape_and_values():
    fv = build_feature_vector(UBIQUITIN)
    assert fv["dimension"] == len(fv["feature_names"]) == 31
    assert abs(sum(fv["vector"][:20]) - 1.0) < 1e-3          # composition fractions sum to 1
    assert 8400 < fv["physicochemical"]["molecular_weight"] < 8700  # ubiquitin is ~8.6 kDa
