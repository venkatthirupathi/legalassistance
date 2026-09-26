"""
test_guardrails.py

Basic sanity tests judges can run without any API key:
  pytest tests/

These exercise the heuristic (Stage 1) guardrail path and the document
loaders, which don't require network access. LLM-dependent paths (Stage 2
classification, summaries, risk radar) are intentionally not covered here
since they require a live API key — judges can verify those interactively
via the Streamlit UI.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

from core_guardrails import check_is_legal_document, validate_not_empty
from core_loaders import DocumentLoadError, load_document, load_txt

SAMPLES_DIR = os.path.dirname(__file__)


def _read_sample(name: str) -> str:
    with open(os.path.join(SAMPLES_DIR, name), "r", encoding="utf-8") as f:
        return f.read()


class TestGuardrailsHeuristic:
    def test_risky_contract_passes_as_legal(self):
        text = _read_sample("sample_freelance_agreement_risky.txt")
        result = check_is_legal_document(text, llm=None)
        assert result.is_legal_document is True
        assert result.signal_hits >= 3

    def test_fair_contract_passes_as_legal(self):
        text = _read_sample("sample_freelance_agreement_fair.txt")
        result = check_is_legal_document(text, llm=None)
        assert result.is_legal_document is True

    def test_recipe_rejected_as_not_legal(self):
        recipe = """
        Grandma's Chocolate Chip Cookies

        Ingredients:
        - 2 cups flour
        - 1 cup butter, softened
        - 3/4 cup sugar
        - 3/4 cup brown sugar
        - 2 eggs
        - 1 tsp vanilla extract
        - 1 tsp baking soda
        - 2 cups chocolate chips

        Instructions:
        1. Preheat oven to 375F.
        2. Cream together butter and sugars until fluffy.
        3. Beat in eggs and vanilla.
        4. Mix in flour and baking soda.
        5. Fold in chocolate chips.
        6. Drop spoonfuls onto a baking sheet and bake for 9-11 minutes.
        7. Let cool before serving to friends and family at your next gathering.
        This recipe makes about two dozen delicious cookies that everyone loves.
        """
        result = check_is_legal_document(recipe, llm=None)
        assert result.is_legal_document is False

    def test_empty_document_rejected(self):
        result = check_is_legal_document("", llm=None)
        assert result.is_legal_document is False

    def test_too_short_document_rejected(self):
        result = check_is_legal_document("This agreement is short.", llm=None)
        assert result.is_legal_document is False


class TestInputValidation:
    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            validate_not_empty("", "question")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError):
            validate_not_empty("   \n\t  ", "question")

    def test_valid_string_passes(self):
        validate_not_empty("What is the payment term?", "question")  # should not raise


class TestLoaders:
    def test_load_txt_bytes(self):
        content = "SECTION 1. This is a valid test agreement with enough content to pass length checks and more."
        loaded = load_txt(content.encode("utf-8"), "test.txt")
        assert "SECTION 1" in loaded.text

    def test_load_empty_txt_raises(self):
        with pytest.raises(DocumentLoadError):
            load_txt(b"", "empty.txt")

    def test_unsupported_extension_raises(self):
        with pytest.raises(DocumentLoadError):
            load_document(b"some bytes", "file.xyz")

    def test_zero_byte_file_raises(self):
        with pytest.raises(DocumentLoadError):
            load_document(b"", "empty.pdf")

    def test_sample_files_load_correctly(self):
        for filename in ("sample_freelance_agreement_fair.txt", "sample_freelance_agreement_risky.txt"):
            path = os.path.join(SAMPLES_DIR, filename)
            with open(path, "rb") as f:
                loaded = load_document(f.read(), filename)
            assert len(loaded.text) > 500


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
