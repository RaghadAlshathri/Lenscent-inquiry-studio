"""Shared data, privacy and splitting logic for the LensCent capstone."""
import hashlib
import json
from pathlib import Path
import re
import unicodedata

import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SEED = 37
LABELS = {
    "session_booking": "حجز الجلسات", "package_pricing": "أسعار الباقات",
    "edit_request": "تعديل الصور", "gallery_access": "معرض الصور", "outside": "خارج النطاق",
}
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
LETTERS = str.maketrans("أإآٱىة", "اااايه")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
ARABIC_ELONGATION = re.compile(r"([\u0621-\u064a])\1{2,}")
PHONE = re.compile(r"(?<![0-9])(?:\+?966[\s().-]*0?|00966[\s().-]*0?|0)5(?:[\s().-]*[0-9]){8}(?![0-9])")


def mask(text):
    text = unicodedata.normalize("NFKC", str(text)).translate(DIGITS)
    return PHONE.sub("[PHONE]", EMAIL.sub("[EMAIL]", text))


def clean(text):
    text = mask(text).replace("[PHONE]", " ").replace("[EMAIL]", " ").lower().translate(LETTERS)
    text = re.sub(r"[\u0610-\u061a\u064b-\u065f\u0670\u0640]", "", text)
    # Three or more identical Arabic letters mark expressive elongation.
    # Existing pairs remain intact in words such as Allah and repeated prefixes.
    text = ARABIC_ELONGATION.sub(r"\1", text)
    return " ".join(re.findall(r"[a-z0-9\u0621-\u064a]+", text))


def read_data():
    data = pd.read_csv(DATA / "messages.csv")
    assert set(data.topic) == set(LABELS) and not data.text.map(clean).duplicated().any()
    faq = json.loads((DATA / "faq.json").read_text(encoding="utf-8"))
    return data, faq


def split_customers(data):
    # Stratification is by the authored dialect of each fictional customer.
    customers = data[["customer_id", "dialect"]].drop_duplicates()
    assert customers.customer_id.is_unique
    development, test = train_test_split(customers, test_size=0.25, random_state=SEED,
                                         stratify=customers.dialect)
    train, valid = train_test_split(development, test_size=0.20, random_state=SEED,
                                    stratify=development.dialect)
    parts = [data[data.customer_id.isin(part.customer_id)].reset_index(drop=True)
             for part in (train, valid, test)]
    ids = [set(part.customer_id) for part in parts]
    assert sum(map(len, ids)) == len(set.union(*ids))
    assert sum(map(len, parts)) == len(data)
    assert all(set(part.topic) == set(LABELS) for part in parts)
    return parts


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def faq_digest(faq):
    # Replies can be edited independently of the retrieval questions.
    return digest(json.dumps([(f["id"], f["queries"]) for f in faq], ensure_ascii=False))
