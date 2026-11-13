#!/usr/bin/python3
"""Cases for sensitive-scan with card numbers generated at run time (Luhn-valid
fakes), plus mutation checks for the Luhn and prefix gates."""
import importlib.machinery, importlib.util, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
loader = importlib.machinery.SourceFileLoader("ss", os.path.join(HERE, "..", "sensitive-scan"))
spec = importlib.util.spec_from_loader("ss", loader)
ss = importlib.util.module_from_spec(spec)
loader.exec_module(ss)


def luhn_complete(prefix, length):
    d = prefix + "".join(random.choice("0123456789") for _ in range(length - len(prefix) - 1))
    for c in "0123456789":
        if ss.luhn(d + c):
            return d + c


def kinds(text):
    return sorted(k for k, _ in ss.card_findings(text))


visa = luhn_complete("4", 16)
mc = luhn_complete("53", 16)
amex = luhn_complete("37", 15)
no_prefix = luhn_complete("9", 16)
bad_luhn = visa[:-1] + str((int(visa[-1]) + 1) % 10)
spaced = " ".join(visa[i:i + 4] for i in range(0, 16, 4))

CASES = [
    (f"cartão {visa}", ["pan"]),
    (f"cartão {spaced}", ["pan"]),
    (f"mc {mc}-x", ["pan"]),
    (f"amex {amex}", ["pan"]),
    (f"cartao {visa} 12/29", ["expiry", "pan"]),
    ("CVV: 123", ["cvv"]),
    ("código de segurança 4321", ["cvv"]),
    ("Validade 07/2031", ["expiry"]),
    ("valid thru 11/28", ["expiry"]),
    # must NOT fire
    (f"pedido {no_prefix}", []),
    (f"pedido {bad_luhn}", []),
    ("cartão final **** **** **** 1234", []),
    ("Fatura de 10/2026, total R$ 1.234,56", []),
    ("NF 0000000000000000", []),
    ("id 1793906717", []),
    ("Domínio x Criado em: 03/11/2025 Expiração: 12/10/2026", []),
    (f"msg <ab{visa}cd@google.com>", []),
    (f"linha 34191.79001 01043.510047 {luhn_complete('5', 15)}", []),
    (f"conta {luhn_complete('5', 13)}", []),
]


def main():
    bad = 0
    for text, want in CASES:
        got = kinds(text)
        ok = got == want
        bad += not ok
        print("PASS" if ok else "FAIL", want, "got", got)
    # mutations
    orig_luhn, orig_prefix = ss.luhn, ss.is_card
    ss.luhn = lambda d: True
    m1 = kinds(f"pedido {bad_luhn}") == ["pan"]
    ss.luhn = orig_luhn
    ss.is_card = lambda d: True
    m2 = kinds(f"pedido {no_prefix}") == ["pan"]
    ss.is_card = orig_prefix
    for name, ok in (("sem Luhn, número inválido vira achado", m1), ("sem prefixo, número sem bandeira vira achado", m2)):
        bad += not ok
        print("PASS" if ok else "FAIL", "mutation:", name)
    # secret path through gitleaks
    fake = "ghp_" + "".join(random.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(36))
    f = ss.scan_records([("Aba!B7", f"token {fake}"), ("Aba!B8", "nada")])
    ok = [(k, s) for k, s, _ in f] == [("github-pat", "Aba!B7")]
    bad += not ok
    print("PASS" if ok else "FAIL", "gitleaks mapeia célula", [(k, s) for k, s, _ in f])
    print("FALHAS:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
