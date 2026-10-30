"""1.0.172: "the web address" is called "the VIP address" everywhere - the one
transform for the sources (pages, daemon) and for their translations, so a
translated text follows its source."""
import re

EN = [
    (r'\bThe web address \(VIP\)', 'The VIP address'),
    (r'\bthe web address \(VIP\)', 'the VIP address'),
    (r'\bweb address \(VIP\)', 'VIP address'),
    (r'\bTHE WEB ADDRESS \(VIP\)', 'THE VIP ADDRESS'),
    (r'\bThe web address\b', 'The VIP address'),
    (r'\bthe web address\b', 'the VIP address'),
    (r'\bWeb address\b', 'VIP address'),
    (r'\bweb address\b', 'VIP address'),
    (r'\bweb addresses\b', 'VIP addresses'),
]


def en(text):
    for a, b in EN:
        text = re.sub(a, b, text)
    return text


def cs(text):
    text = re.sub(r'\b[Ww]ebov(?:á|é|ou|ých|ým|ými|ého|ému|ém)\s+(adres\w*)', r'VIP \1', text)
    text = re.sub(r'\bVIP (adres\w*) \(VIP\)', r'VIP \1', text)
    return text
