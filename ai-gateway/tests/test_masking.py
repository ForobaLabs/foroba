import json
from pathlib import Path

import pytest

from masking import engine
from masking.engine import (
    KnownEntities,
    Mapping,
    MaskingError,
    mask,
    mask_messages,
    unmask,
)

CORPUS = Path(__file__).parent / "fixtures" / "masking_corpus"
CASES = sorted(p.stem for p in CORPUS.glob("*.txt"))
NONE = KnownEntities(persons=[], orgs=[], addresses=[])


def _load(name):
    text = (CORPUS / f"{name}.txt").read_text(encoding="utf-8")
    side = json.loads((CORPUS / f"{name}.expected.json").read_text(encoding="utf-8"))
    return text, side, KnownEntities(**side["known"])


def test_corpus_has_twelve_docs():
    assert len(CASES) == 12


@pytest.mark.parametrize("name", CASES)
def test_corpus_no_known_pii_survives(name):
    text, side, known = _load(name)
    masked, _ = mask(text, known)
    leaked = [s for s in side["must_mask"] if s.lower() in masked.lower()]
    assert not leaked, f"{name}: {leaked}\n{masked}"


@pytest.mark.parametrize("name", CASES)
def test_corpus_amounts_and_dates_preserved(name):
    text, side, known = _load(name)
    masked, _ = mask(text, known)
    lost = [s for s in side["must_keep"] if s not in masked]
    assert not lost, f"{name}: {lost}\n{masked}"


def test_pos_merchant_kept_transfer_counterparty_masked():
    text = "02/10/2026 PAGAMENTO POS ESSELUNGA -54,30\n03/10/2026 BONIFICO A FAVORE DI MARIO ROSSI -650,00\n"
    masked, _ = mask(text, NONE)
    assert "ESSELUNGA" in masked
    assert "MARIO ROSSI" not in masked
    assert "-650,00" in masked


def test_employer_masked_from_label_and_known():
    text = "Datore di lavoro: Acme Logistica S.r.l.\nIl mio capo in Acme Logistica mi ha detto di si."
    masked, _ = mask(
        text, KnownEntities(persons=[], orgs=["Acme Logistica"], addresses=[])
    )
    assert "Acme" not in masked
    assert masked.count("[AZIENDA_1]") >= 2


def test_iban_invalid_checksum_still_masked_as_iban_like():
    bad = "IT00A0000000000000000000000"
    masked, mapping = mask(f"IBAN {bad} fine", NONE)
    assert bad not in masked
    assert "[IBAN_1]" in masked
    assert mapping.original("[IBAN_1]") == bad


def test_same_original_same_placeholder_across_messages():
    msgs = [
        {"role": "user", "content": "Sono Giulia Ferrari."},
        {"role": "assistant", "content": "Ciao giulia ferrari!"},
        {"role": "user", "content": "GIULIA FERRARI paga 10,00"},
    ]
    out, mapping = mask_messages(
        msgs, KnownEntities(persons=["Giulia Ferrari"], orgs=[], addresses=[])
    )
    assert [m["content"].count("[PERSONA_1]") for m in out] == [1, 1, 1]
    assert "PERSONA_2" not in json.dumps(out)
    assert isinstance(mapping, Mapping)


def test_unmask_roundtrip():
    text = "Mario Rossi (mario@example.com) ha ricevuto 650,00 da Mario Rossi."
    masked, mapping = mask(
        text, KnownEntities(persons=["Mario Rossi"], orgs=[], addresses=[])
    )
    assert "Mario" not in masked
    assert unmask(masked, mapping) == text.replace("Mario Rossi", "Mario Rossi")


@pytest.mark.parametrize(
    "variant",
    ["[PERSONA_1]", "[persona_1]", "[ PERSONA_1 ]", "PERSONA_1", "[Persona 1]"],
)
def test_unmask_tolerates_case_and_spacing(variant):
    _, mapping = mask(
        "Giulia Ferrari",
        KnownEntities(persons=["Giulia Ferrari"], orgs=[], addresses=[]),
    )
    assert (
        unmask(f"Ciao {variant}, come stai?", mapping)
        == "Ciao Giulia Ferrari, come stai?"
    )


def test_unmask_leaves_unknown_placeholders_alone():
    _, mapping = mask("nothing here", NONE)
    assert unmask("[PERSONA_9] rimane", mapping) == "[PERSONA_9] rimane"


def test_analyzer_failure_raises_masking_error(monkeypatch):
    class Boom:
        def analyze(self, **kw):
            raise RuntimeError("nlp exploded")

    monkeypatch.setattr(engine, "get_analyzer", lambda: Boom())
    with pytest.raises(MaskingError):
        mask("Mario Rossi", NONE)


def test_tool_call_arguments_masked():
    msgs = [
        {"role": "user", "content": "Cerca Mario Rossi"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "find",
                        "arguments": '{"counterparty": "Mario Rossi", "email": "m.rossi@example.com"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "c1",
            "content": '{"owner": "Mario Rossi", "total": "650,00"}',
        },
    ]
    out, mapping = mask_messages(
        msgs, KnownEntities(persons=["Mario Rossi"], orgs=[], addresses=[])
    )
    blob = json.dumps(out)
    assert "Rossi" not in blob and "example.com" not in blob
    assert "650,00" in blob
    args = out[1]["tool_calls"][0]["function"]["arguments"]
    assert json.loads(args)["counterparty"] == "[PERSONA_1]"
    assert unmask(args, mapping).count("Mario Rossi") == 1


def test_amounts_dates_never_masked():
    text = "Il 15/12/2026 ho pagato 1.234,56 EUR, poi 3.500,00 e 12345,67; CAP 20100 Milano."
    masked, _ = mask(text, NONE)
    for keep in ("15/12/2026", "1.234,56", "3.500,00", "12345,67"):
        assert keep in masked
    assert "20100" not in masked


def test_ner_masks_free_text_names_without_known_entities():
    text = "Sono Sofia Greco, lavoro per Omega Consulting S.r.l. a Milano e spendo 780,00 euro."
    masked, _ = mask(text, NONE)
    for gone in ("Sofia", "Greco", "Omega", "Milano"):
        assert gone not in masked, masked
    assert "780,00" in masked


def test_ner_org_kept_on_pos_line_but_masked_on_transfer_line():
    pos = "05/11/2026 PAGAMENTO POS Decathlon Napoli -64,90"
    assert "Decathlon" in mask(pos, NONE)[0]
    transfer = "05/11/2026 Bonifico SEPA da Omega Consulting S.r.l. 2.000,00"
    assert "Omega" not in mask(transfer, NONE)[0]
