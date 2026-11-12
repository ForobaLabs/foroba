"""Deterministic generator for pii_corpus.jsonl (Task 2.5 step 2). All values are synthetic:
IBAN/PAN/NIR/codice fiscale carry valid check digits so validators accept them.
Run: .venv/bin/python tests/fixtures/gen_pii_corpus.py > tests/fixtures/pii_corpus.jsonl"""
import json
import random
import string

R = random.Random(20261112)


def iban(cc, length, bban_digits=True):
    body_len = length - 4
    bban = "".join(R.choice(string.digits) for _ in range(body_len))
    s = bban + cc + "00"
    num = "".join(str(int(c, 36)) for c in s)
    check = 98 - int(num) % 97
    return f"{cc}{check:02d}{bban}"


def group4(s):
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))


def pan():
    base = "4" + "".join(R.choice(string.digits) for _ in range(14))
    total = 0
    for i, ch in enumerate(reversed(base)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return base + str((10 - total % 10) % 10)


ODD = {**{str(i): v for i, v in enumerate([1, 0, 5, 7, 9, 13, 15, 17, 19, 21])},
       **{c: v for c, v in zip(string.ascii_uppercase, [1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23])}}


def cf():
    L = lambda n: "".join(R.choice(string.ascii_uppercase.replace("Z", "")) for _ in range(n))
    D = lambda n: "".join(R.choice(string.digits) for _ in range(n))
    body = L(3) + L(3) + D(2) + R.choice("ABCDEHLMPRST") + D(2) + "H" + D(3)
    total = 0
    for i, ch in enumerate(body):
        if i % 2 == 0:
            total += ODD[ch]
        else:
            total += int(ch) if ch.isdigit() else ord(ch) - 65
    return body + chr(65 + total % 26)


def nir():
    n = R.choice("12") + "".join(R.choice(string.digits) for _ in range(12))
    return n + f"{97 - int(n) % 97:02d}"


FIRST = {"it": ["Marco", "Giulia", "Francesca", "Luca", "Alessandro", "Chiara", "Matteo", "Elena", "Davide", "Sara"],
         "fr": ["Camille", "Julien", "Aurélie", "Mathieu", "Sophie", "Nicolas", "Élodie", "Thomas", "Margaux", "Antoine"],
         "en": ["James", "Emily", "Oliver", "Charlotte", "William", "Amelia", "Henry", "Grace", "Jack", "Sophia"]}
LAST = {"it": ["Rossi", "Bianchi", "Ferrari", "Esposito", "Romano", "Colombo", "Ricci", "Marino", "Greco", "Conti"],
        "fr": ["Dubois", "Lefèvre", "Moreau", "Fournier", "Girard", "Bonnet", "Dupont", "Lambert", "Fontaine", "Rousseau"],
        "en": ["Smith", "Johnson", "Taylor", "Brown", "Wilson", "Davies", "Evans", "Thomas", "Walker", "Wright"]}
PH = {"+39": lambda: f"+39 3{R.randint(20,99)} {R.randint(100,999)} {R.randint(1000,9999)}",
      "+33": lambda: f"+33 {R.choice('67')} {R.randint(10,99)} {R.randint(10,99)} {R.randint(10,99)} {R.randint(10,99)}",
      "+221": lambda: f"+221 77 {R.randint(100,999)} {R.randint(10,99)} {R.randint(10,99)}",
      "+225": lambda: f"+225 07 {R.randint(10,99)} {R.randint(10,99)} {R.randint(10,99)} {R.randint(10,99)}"}
STREETS = [("Via {n} {x}, {cap} {city}", "it", ["Giuseppe Verdi", "Alessandro Manzoni", "Dante Alighieri", "Roma", "Garibaldi"], [("20121", "Milano"), ("00184", "Roma"), ("10121", "Torino"), ("40121", "Bologna")]),
           ("{x} rue {n}, {cap} {city}", "fr", ["de la Paix", "Victor Hugo", "des Lilas", "Pasteur"], [("75002", "Paris"), ("69003", "Lyon"), ("13001", "Marseille"), ("31000", "Toulouse")]),
           ("{x}straße {n}, {cap} {city}", "de", ["Haupt", "Berliner", "Goethe", "Schiller"], [("10115", "Berlin"), ("80331", "München"), ("20095", "Hamburg")])]
DOMAINS = ["gmail.com", "outlook.fr", "libero.it", "yahoo.com", "orange.fr", "proton.me"]


def name(lang):
    return f"{R.choice(FIRST[lang])} {R.choice(LAST[lang])}"


def addr():
    tpl, _, xs, cities = R.choice(STREETS)
    cap, city = R.choice(cities)
    return tpl.format(n=R.randint(1, 120), x=R.choice(xs), cap=cap, city=city)


def email(nm):
    f, l = nm.lower().split()[:2]
    return f"{f}.{l}{R.randint(1,99)}@{R.choice(DOMAINS)}".replace("é", "e").replace("è", "e").replace("É", "e")


rows = []


def add(cat, text, pii):
    rows.append({"cat": cat, "text": text, "pii": pii})


for i in range(25):
    cc, ln = [("IT", 27), ("FR", 27), ("DE", 22), ("ES", 24), ("NL", 18)][i % 5]
    v = iban(cc, ln)
    shown = group4(v) if i % 2 else v
    add("iban", R.choice(["Bonifico verso {}", "Veuillez virer sur l'IBAN {}", "My IBAN is {} please check", "IBAN: {} intestato a mio fratello"]).format(shown), [v if not i % 2 else shown])
for i in range(25):
    v = pan()
    shown = {0: v, 1: group4(v), 2: "-".join(group4(v).split())}[i % 3]
    add("card", R.choice(["Carta {} scade 09/28", "Ma carte bancaire {} a été bloquée", "card number {} was declined", "Pagato con carta n. {}"]).format(shown), [shown])
for i in range(15):
    v = cf()
    add("cf", R.choice(["Codice fiscale {}", "CF: {} del titolare", "Il mio codice fiscale è {}"]).format(v), [v])
for i in range(10):
    v = nir()
    shown = f"{v[0]} {v[1:3]} {v[3:5]} {v[5:7]} {v[7:10]} {v[10:13]} {v[13:]}"
    add("nir", R.choice(["Numéro de sécurité sociale {}", "Mon NIR : {}", "N° INSEE {}"]).format(shown), [shown])
for i in range(20):
    lang = ["it", "fr", "en"][i % 3]
    nm = name(lang)
    v = email(nm)
    add("email", R.choice(["Scrivimi a {}", "Contactez-moi sur {}", "Please send the receipt to {}", "Email: {}"]).format(v), [v])
for i in range(20):
    k = ["+39", "+33", "+221", "+225"][i % 4]
    v = PH[k]()
    add("phone", R.choice(["Chiamami al {}", "Mon numéro est le {}", "Tel. {}", "Reach me on {}"]).format(v), [v])
for i in range(25):
    v = addr()
    add("address", R.choice(["Spedire a {}", "J'habite au {}", "Billing address: {}", "Residente in {}"]).format(v), [v])
for i in range(45):
    lang = ["it", "fr", "en"][i % 3]
    nm = name(lang)
    tpl = {"it": ["Bonifico a favore di {}", "Il titolare del conto è {}", "Ho parlato con {} ieri"],
           "fr": ["Virement au bénéfice de {}", "Le titulaire du compte est {}", "J'ai parlé avec {} hier"],
           "en": ["Transfer to {}", "The account holder is {}", "I spoke with {} yesterday"]}[lang]
    add("person", R.choice(tpl).format(nm), [nm])
for i in range(15):
    v = "".join(R.choice(string.digits) for _ in range(R.choice([10, 11, 12])))
    add("account", R.choice(["Il mio numero di conto è {}", "numéro de compte {} chez ma banque", "account number {} at my bank", "c/c n. {} filiale 123"]).format(v), [v])
assert len(rows) == 200, len(rows)
for r in rows:
    print(json.dumps(r, ensure_ascii=False))
