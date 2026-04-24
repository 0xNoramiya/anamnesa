"""Tests for the pre-LLM non-medical heuristic in the Normalizer.

Goal: obviously non-clinical queries (jokes, recipes, weather, code)
refuse instantly without paying the Haiku round-trip. Borderline
queries that could plausibly be clinical MUST still go to Haiku —
false negatives here cost a 40s Drafter round-trip, false positives
cost a real clinical query going unanswered.
"""

from __future__ import annotations

from agents.normalizer import _is_obviously_non_medical


def test_joke_request_refuses() -> None:
    assert _is_obviously_non_medical("Tell me a joke") is True


def test_recipe_request_refuses() -> None:
    assert _is_obviously_non_medical("Resep nasi goreng dong") is True


def test_capital_city_refuses() -> None:
    assert _is_obviously_non_medical("Ibukota Perancis apa?") is True


def test_weather_refuses() -> None:
    assert _is_obviously_non_medical("Cuaca Jakarta hari ini?") is True


def test_code_refuses() -> None:
    assert _is_obviously_non_medical("Write a Python function to parse JSON") is True


def test_greeting_refuses() -> None:
    assert _is_obviously_non_medical("Apa kabar?") is True


def test_stock_price_refuses() -> None:
    assert _is_obviously_non_medical("Harga emas hari ini") is True


def test_sales_tips_refuses() -> None:
    assert _is_obviously_non_medical("Tips jualan online") is True


def test_numeric_only_refuses() -> None:
    assert _is_obviously_non_medical("12345") is True


def test_dbd_query_goes_to_haiku() -> None:
    assert _is_obviously_non_medical("DBD anak 8 tahun BB 20kg, cairan awal?") is False


def test_heart_failure_query_goes_to_haiku() -> None:
    assert _is_obviously_non_medical("Obat lini pertama HFrEF") is False


def test_prescription_query_survives_resep_prefix() -> None:
    # "resep" alone is not enough to trip the non-medical heuristic —
    # "resep OAT untuk TB paru" must still go to Haiku because "tb"
    # is a clinical safety token.
    assert _is_obviously_non_medical("Resep OAT untuk TB paru dewasa") is False


def test_medicine_dose_query_goes_to_haiku() -> None:
    assert _is_obviously_non_medical("Dosis parasetamol pediatric mg/kgbb") is False


def test_mixed_bahasa_english_clinical_goes_to_haiku() -> None:
    assert (
        _is_obviously_non_medical(
            "STEMI <12 jam tanpa kapasitas PCI, indikasi fibrinolitik?"
        )
        is False
    )


def test_patient_specific_query_goes_to_haiku() -> None:
    # Haiku is the only component allowed to classify as
    # patient_specific_request — heuristic must leave it alone.
    assert (
        _is_obviously_non_medical("Pasien saya hamil 28 minggu, aman amoksisilin?")
        is False
    )


def test_short_clinical_query_goes_to_haiku() -> None:
    assert _is_obviously_non_medical("TB paru BTA positif") is False


def test_empty_query_does_not_refuse() -> None:
    # Empty should not short-circuit — let orchestrator's validation
    # path raise a 400 further up the stack.
    assert _is_obviously_non_medical("") is False


def test_long_non_medical_paragraph_refuses() -> None:
    assert (
        _is_obviously_non_medical(
            "Tolong tulis kode Python untuk parsing JSON yang bagus dan cepat"
        )
        is True
    )
