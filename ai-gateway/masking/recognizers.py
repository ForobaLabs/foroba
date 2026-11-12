"""Presidio recognizers: structured IDs, labelled fields, transfer counterparties, spaCy NER.

Scores double as layer priority when the engine resolves overlaps:
structured IDs 0.95 > labelled fields 0.90 > known entities 0.85 (engine) >
transfer counterparties 0.80 > CAP 0.60 > NER 0.50.
"""

import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

LABELS = (
    "PERSONA",
    "AZIENDA",
    "INDIRIZZO",
    "LUOGO",
    "IBAN",
    "CF",
    "PIVA",
    "CARTA",
    "EMAIL",
    "TELEFONO",
    "CAP",
    "MATRICOLA",
    "DOCUMENTO",
    "DATA_NASCITA",
    "NIR",
    "CONTO",
)

S_STRUCT, S_LABELLED, S_KNOWN, S_COUNTERPARTY, S_CAP, S_NER = (
    0.95,
    0.90,
    0.85,
    0.80,
    0.60,
    0.50,
)

COMPANY_SUFFIX = re.compile(
    r"\b(?:s\.?\s?r\.?\s?l\.?s?|s\.?\s?p\.?\s?a\.?|s\.?\s?a\.?\s?s\.?|s\.?\s?n\.?\s?c\.?|s\.?\s?s\.?|soc(?:iet[àa])?\.?|coop(?:erativa)?\.?|onlus|gmbh|ltd|inc|llc)(?![\w])",
    re.IGNORECASE,
)
POS_LINE = re.compile(
    r"\bPOS\b|PAGAMENTO\s+CARTA|CARTA\s+\*\d{4}|APPLE\s+PAY|GOOGLE\s+PAY", re.IGNORECASE
)
TRANSFER_LINE = re.compile(
    r"\b(?:BONIFICO|GIROCONTO|SATISPAY|P2P|SEPA)\b", re.IGNORECASE
)

_PRE = r"(?<![\w.,/-])"  # not glued to a longer number/word/date/amount on the left
_POST = r"(?![\w/]|[.,]\d)"  # nor on the right


def line_of(text: str, pos: int) -> str:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return text[start : len(text) if end == -1 else end]


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _iban_mod97(compact: str) -> bool:
    rearranged = compact[4:] + compact[:4]
    try:
        return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1
    except ValueError:
        return False


class _Base(EntityRecognizer):
    def __init__(self, entities: list[str], name: str):
        super().__init__(
            supported_entities=entities, name=name, supported_language="it"
        )

    def load(self) -> None:  # nothing to load
        pass


class StructuredRecognizer(_Base):
    """IBAN, CF, P.IVA, PAN, email, phone, matricola, documents, birth dates, CAP."""

    _IBAN = re.compile(
        r"(?<![A-Za-z0-9])[A-Za-z]{2}\d{2}(?: ?[A-Za-z0-9]){11,30}(?![A-Za-z0-9])"
    )
    _CF = re.compile(
        r"(?<![A-Za-z0-9])[A-Za-z]{6}\d{2}[A-Za-z]\d{2}[A-Za-z]\d{3}[A-Za-z](?![A-Za-z0-9])"
    )
    _PIVA = re.compile(_PRE + r"(?:IT)?\d{11}" + _POST)
    _PAN = re.compile(_PRE + r"\d(?:[ -]?\d){12,18}" + _POST)
    _EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
    _PHONE = re.compile(
        _PRE
        + r"(?:(?:\+|00)39[ .-]?)?(?:3\d{2}[ .-]?\d{3}[ .-]?\d{3,4}|0\d{1,3}[ .-]?\d{5,8})"
        + _POST
    )
    # International numbers (+33, +221, +225, ...): the explicit prefix makes it unambiguous.
    _PHONE_INTL = re.compile(
        _PRE + r"(?:\+|00)(?!39)[1-9]\d{0,2}(?:[ .-]?\d){8,11}" + _POST
    )
    # French NIR (social security number): 15 digits, optional spaces, key = 97 - n13 % 97.
    _NIR = re.compile(_PRE + r"[12](?:[ .]?\d){14}" + _POST)
    # Bank account numbers introduced by a label (IT/FR/EN).
    _ACCOUNT = re.compile(
        r"(?i:\b(?:numero\s+di\s+conto|n\.?\s*conto|c/c|conto\s+corrente|numéro\s+de\s+compte|"
        r"n°\s*de\s+compte|account\s+(?:number|no\.?|#)|acct\.?\s*(?:no\.?|#)?))"
        r"[ \t:#.]*(?i:è|est|is|n\.?|nr\.?|n°)?[ \t:#.]*(\d{8,14})(?!\d)"
    )
    _MATRICOLA = re.compile(
        r"(?<![A-Za-z])(?:n\.?[ \t]*)?(?:matricola(?:[ \t]+inps)?|matr\.?|badge|tessera|posizione[ \t]+inps|inps[ \t]+(?:n\.?|nr\.?|numero)|cod(?:ice)?\.?[ \t]+dipendente)(?![A-Za-z])[ \t]*(?:n\.?|nr\.?|numero)?[ \t]*[:;#]?[ \t]*([A-Za-z0-9][A-Za-z0-9\-/]{2,})",
        re.IGNORECASE,
    )
    _DOC = re.compile(
        r"\b(?:carta\s+d['’]identit[àa]|c\.?\s?i\.?|passaporto|patente|documento)\b[ \t]*(?:n\.?|nr\.?|numero)?[ \t]*[:;#]?[ \t]*([A-Za-z]{0,3}[A-Za-z0-9]{6,10})",
        re.IGNORECASE,
    )
    _BIRTH = re.compile(
        r"(?:\bnat[oa]\s+(?:a\s+[A-Za-zÀ-ÿ'’ ]{2,30}?\s+)?il|\bdata\s+di\s+nascita)[ \t]*:?[ \t]*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})",
        re.IGNORECASE,
    )
    _CAP = re.compile(r"(?<![\w.,/-])(\d{5})(?![\w/]|[.,]\d)")
    _CITY_AFTER = re.compile(r"[ \t]+([A-ZÀ-Ý][A-Za-zÀ-ÿ'’]{2,})")
    _STREET_WORD = re.compile(
        r"\b(?:via|viale|piazza|piazzale|corso|largo|vicolo|strada)\b", re.IGNORECASE
    )
    _NOT_CITY = {"EUR", "EURO", "USD", "GBP", "CHF", "TOTALE", "SALDO", "IMPORTO"}

    def __init__(self):
        super().__init__(
            [
                "IBAN",
                "CF",
                "PIVA",
                "CARTA",
                "EMAIL",
                "TELEFONO",
                "CAP",
                "MATRICOLA",
                "DOCUMENTO",
                "DATA_NASCITA",
                "NIR",
                "CONTO",
            ],
            "ItStructured",
        )

    def analyze(self, text, entities=None, nlp_artifacts=None):
        out: list[RecognizerResult] = []

        def add(label, start, end, score=S_STRUCT):
            out.append(
                RecognizerResult(entity_type=label, start=start, end=end, score=score)
            )

        for m in self._IBAN.finditer(text):
            span = self._iban_span(m.group(0))
            if span:
                add("IBAN", m.start(), m.start() + span)
        for m in self._CF.finditer(text):
            add("CF", m.start(), m.end())
        for m in self._EMAIL.finditer(text):
            add("EMAIL", m.start(), m.end())
        for m in self._PIVA.finditer(text):
            digits = m.group(0)[-11:]
            if _luhn(digits):
                add("PIVA", m.start(), m.end())
        for m in self._PAN.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if 13 <= len(digits) <= 19 and _luhn(digits):
                add("CARTA", m.start(), m.end())
        for m in self._PHONE.finditer(text):
            if len(re.sub(r"\D", "", m.group(0))) >= 9:
                add("TELEFONO", m.start(), m.end())
        for m in self._PHONE_INTL.finditer(text):
            if 9 <= len(re.sub(r"\D", "", m.group(0))) <= 15:
                add("TELEFONO", m.start(), m.end())
        for m in self._NIR.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if len(digits) == 15 and 97 - int(digits[:13]) % 97 == int(digits[13:]):
                add("NIR", m.start(), m.end())
        for m in self._ACCOUNT.finditer(text):
            add("CONTO", m.start(1), m.end(1))
        for rx, label in (
            (self._MATRICOLA, "MATRICOLA"),
            (self._DOC, "DOCUMENTO"),
            (self._BIRTH, "DATA_NASCITA"),
        ):
            for m in rx.finditer(text):
                value = m.group(1)
                if label != "DATA_NASCITA" and not any(c.isdigit() for c in value):
                    continue
                add(label, m.start(1), m.end(1))
        for m in self._CAP.finditer(text):
            if self._cap_in_address_context(text, m):
                add("CAP", m.start(1), m.end(1), S_CAP)
        return out

    @staticmethod
    def _iban_span(raw: str) -> int | None:
        """Length of the IBAN prefix of ``raw`` (spaces kept), or None."""
        compact_idx = [i for i, c in enumerate(raw) if c != " "]
        compact = "".join(raw[i] for i in compact_idx).upper()
        if compact.startswith("IT") and len(compact) >= 27:
            return (
                compact_idx[26] + 1
            )  # conservative: IT + 25 chars even with a bad checksum
        for n in range(min(len(compact), 34), 14, -1):
            if _iban_mod97(compact[:n]):
                return compact_idx[n - 1] + 1
        return None

    def _cap_in_address_context(self, text: str, m: re.Match) -> bool:
        before = text[max(0, m.start() - 6) : m.start()]
        if re.search(r"cap[ \t:.]*$", before, re.IGNORECASE):
            return True
        after = self._CITY_AFTER.match(text, m.end(1))
        if after and after.group(1).upper() not in self._NOT_CITY:
            return True
        line = line_of(text, m.start())
        return bool(self._STREET_WORD.search(line)) and bool(
            re.search(r",[ \t]*$", before)
        )


class LabelledRecognizer(_Base):
    """Value following ``Datore di lavoro: …``, ``Indirizzo; …``, plus street forms."""

    _LABELS = {
        "AZIENDA": r"datore\s+di\s+lavoro|ragione\s+sociale|azienda",
        "INDIRIZZO": r"indirizzo|residenza|sede",
        "PERSONA": r"dipendente|intestatario|titolare|beneficiario|ordinante",
    }
    _ALL = "|".join(f"(?:{v})" for v in _LABELS.values())
    _HEAD = re.compile(
        r"(?<![\w])(?P<label>"
        + _ALL
        + r")(?:[ \t]+(?:legale|operativa|sociale|dipendente))?[ \t]*(?:[:;=\t]|[ \t]{2,})[ \t]*",
        re.IGNORECASE,
    )
    _NEXT_LABEL = re.compile(
        r"(?<![\w])(?:"
        + _ALL
        + r")(?:[ \t]+(?:legale|operativa|sociale|dipendente))?[ \t]*[:;=]",
        re.IGNORECASE,
    )
    _STREET = re.compile(
        r"(?i:\b(?:via|viale|piazza|piazzale|corso|largo|vicolo|strada))[ \t]+"
        r"(?:(?:[A-ZÀ-Ý][\w'’.À-ÿ]*|(?i:di|del|della|dei|degli|delle|dello|dell['’]|d['’]|da)|dei)[ \t]+){0,3}"
        r"(?:[A-ZÀ-Ý][\w'’.À-ÿ]*)"
        r"(?:,?[ \t]*(?:n\.?[ \t]*)?\d{1,4}[A-Za-z]?(?![\w/]|[.,]\d))?"
    )

    def __init__(self):
        super().__init__(["PERSONA", "AZIENDA", "INDIRIZZO"], "ItLabelled")

    def analyze(self, text, entities=None, nlp_artifacts=None):
        out: list[RecognizerResult] = []
        for m in self._HEAD.finditer(text):
            label = m.group("label")
            kind = next(
                k
                for k, pat in self._LABELS.items()
                if re.fullmatch(pat, re.sub(r"\s+", " ", label), re.IGNORECASE)
                or re.fullmatch(pat, label, re.IGNORECASE)
            )
            start = m.end()
            line_end = text.find("\n", start)
            line_end = len(text) if line_end == -1 else line_end
            seg = text[start:line_end]
            cut = re.search(r"[;\t|\"]|[ \t]{2,}", seg)
            if cut:
                seg = seg[: cut.start()]
            nxt = self._NEXT_LABEL.search(seg)
            if nxt:
                seg = seg[: nxt.start()]
            value = seg.rstrip(" ,;")
            if len(value) < 2 or not any(c.isalpha() for c in value):
                continue
            if kind == "PERSONA" and COMPANY_SUFFIX.search(value):
                kind = "AZIENDA"
            out.append(
                RecognizerResult(
                    entity_type=kind,
                    start=start,
                    end=start + len(value),
                    score=S_LABELLED,
                )
            )
        for m in self._STREET.finditer(text):
            out.append(
                RecognizerResult(
                    entity_type="INDIRIZZO",
                    start=m.start(),
                    end=m.end(),
                    score=S_LABELLED,
                )
            )
        return out


class CuePersonRecognizer(_Base):
    """Person names introduced by an unambiguous cue phrase (IT/FR/EN). The Italian NER model
    misses many French/English names, so a cue such as "Transfer to" or "Virement au bénéfice
    de" is treated as a labelled field."""

    _CUE = (
        r"transfer\s+to|payment\s+to|sent\s+to|spoke\s+with|account\s+holder\s+is|holder\s+is|"
        r"virement\s+(?:au\s+bénéfice\s+de|à|a)|titulaire\s+du\s+compte\s+est|parlé\s+avec|"
        r"a\s+favore\s+di|intestato\s+a|titolare\s+del\s+conto\s+è|parlato\s+con|"
        r"pagamento\s+a|bonifico\s+a"
    )
    _WORD = r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]+"
    _RX = re.compile(
        rf"(?i:\b(?:{_CUE}))[ \t]+({_WORD}(?:[ \t]+(?:(?:de|da|di|van|von|le|la|del)[ \t]+)?{_WORD}){{1,2}})"
    )

    def __init__(self):
        super().__init__(["PERSONA"], "CuePerson")

    def analyze(self, text, entities=None, nlp_artifacts=None):
        return [
            RecognizerResult(
                entity_type="PERSONA", start=m.start(1), end=m.end(1), score=S_LABELLED
            )
            for m in self._RX.finditer(text)
        ]


class CounterpartyRecognizer(_Base):
    """On transfer lines the counterparty is masked regardless of what NER thinks."""

    _LEAD = re.compile(
        r"(?:\bA\s+FAVORE\s+DI|\bFAVORE\s+DI|\bORDINANTE|\bBENEFICIARIO|\bBENEF\.?|\bCONTROPARTE|\bDISPOSTO\s+DA|\bDA|\bA|\bP2P|\bSATISPAY)[ \t]+(?:(?:P2P|SATISPAY)[ \t]+)?",
        re.IGNORECASE,
    )
    _WORD = re.compile(r"[A-ZÀ-Ý][A-Za-zÀ-ÿ'’.&\-]*")
    _STOP = {
        "CAUSALE",
        "RIF",
        "RIF.",
        "CRO",
        "TRN",
        "IBAN",
        "PER",
        "AFFITTO",
        "STIPENDIO",
        "RATA",
        "MUTUO",
        "SPESA",
        "REGALO",
        "CENA",
        "RIMBORSO",
        "PAGAMENTO",
        "FATTURA",
        "QUOTA",
        "BOLLETTA",
        "EUR",
        "DEL",
        "DATA",
        "IMPORTO",
        "SEPA",
        "P2P",
        "SATISPAY",
        "BONIFICO",
        "GIROCONTO",
    }
    _MONTHS = {
        "GENNAIO",
        "FEBBRAIO",
        "MARZO",
        "APRILE",
        "MAGGIO",
        "GIUGNO",
        "LUGLIO",
        "AGOSTO",
        "SETTEMBRE",
        "OTTOBRE",
        "NOVEMBRE",
        "DICEMBRE",
    }

    def __init__(self):
        super().__init__(["PERSONA", "AZIENDA"], "ItCounterparty")

    def analyze(self, text, entities=None, nlp_artifacts=None):
        out: list[RecognizerResult] = []
        pos = 0
        for line in text.split("\n"):
            if TRANSFER_LINE.search(line):
                out.extend(self._line(line, pos))
            pos += len(line) + 1
        return out

    def _line(self, line: str, base: int) -> list[RecognizerResult]:
        res: list[RecognizerResult] = []
        used_until = 0
        for lead in self._LEAD.finditer(line):
            if lead.start() < used_until:
                continue
            i = lead.end()
            words: list[tuple[int, int]] = []
            while len(words) < 4:
                w = self._WORD.match(line, i)
                if not w:
                    break
                up = w.group(0).upper().rstrip(".")
                if up in self._STOP or up in self._MONTHS:
                    break
                words.append((w.start(), w.end()))
                i = w.end()
                if COMPANY_SUFFIX.fullmatch(w.group(0)):
                    break  # the legal form closes a company name
                gap = re.match(r"[ \t]+", line[i:])
                if not gap:
                    break
                i += gap.end()
            if not words:
                continue
            s, e = words[0][0], words[-1][1]
            kind = "AZIENDA" if COMPANY_SUFFIX.search(line[s:e]) else "PERSONA"
            res.append(
                RecognizerResult(
                    entity_type=kind, start=base + s, end=base + e, score=S_COUNTERPARTY
                )
            )
            used_until = e
        return res


_NER_MAP = {
    "PERSON": "PERSONA",
    "ORGANIZATION": "AZIENDA",
    "LOCATION": "LUOGO",
    "PER": "PERSONA",
    "ORG": "AZIENDA",
    "LOC": "LUOGO",
}
_NER_STOP = {
    "inps",
    "inail",
    "irpef",
    "irap",
    "tfr",
    "iva",
    "ccnl",
    "euro",
    "eur",
    "usd",
    "netto",
    "lordo",
    "totale",
    "saldo",
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
    "estratto conto",
    "busta paga",
    "cedolino",
    "iban",
    "pos",
    "sepa",
    "sdd",
    "paypal",
    "satispay",
    "visa",
    "mastercard",
    "pagamento",
    "nata",
    "nato",
    "data",
    "sede",
    "indirizzo",
    "residenza",
    "titolare",
    "intestatario",
    "dipendente",
    "descrizione",
    "importo",
    "causale",
    "conto",
    "carta",
    "operazione",
    "tredicesima",
    "retribuzione",
    "contributi",
    "trattenute",
    "competenze",
    "payslip",
    "bonifico",
    "addebito",
    "accredito",
    "matricola",
    "badge",
}
_NER_LABEL_TAIL = re.compile(r"[ \t]*[:;\t]")


class NerRecognizer(_Base):
    """spaCy entities: PER/LOC always, ORG except on card/POS lines."""

    def __init__(self):
        super().__init__(["PERSONA", "AZIENDA", "LUOGO"], "ItNer")

    def analyze(self, text, entities=None, nlp_artifacts=None):
        if nlp_artifacts is None:
            return []
        out: list[RecognizerResult] = []
        for ent in nlp_artifacts.entities:
            label = _NER_MAP.get(ent.label_)
            if not label:
                continue
            raw = ent.text
            if "\n" in raw or any(c.isdigit() for c in raw) or len(raw.strip()) < 3:
                continue
            if any(c in raw for c in ";:\t|"):
                continue  # spans a field boundary: not a real entity
            if raw.strip().casefold() in _NER_STOP:
                continue
            if raw.isupper() or _NER_LABEL_TAIL.match(text, ent.end_char):
                continue  # shouted text is mostly labels; a "Label:" is not a value
            if label == "AZIENDA":
                line = line_of(text, ent.start_char)
                if POS_LINE.search(line) and not TRANSFER_LINE.search(line):
                    continue
            end = ent.end_char
            if (
                label == "AZIENDA"
                and text[end : end + 1] == "."
                and COMPANY_SUFFIX.search(raw)
            ):
                end += 1  # "S.r.l" -> "S.r.l."
            out.append(
                RecognizerResult(
                    entity_type=label, start=ent.start_char, end=end, score=S_NER
                )
            )
        return out
