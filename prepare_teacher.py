"""Build Lab 5's exact FAQ search and cache its targets for the small browser model."""
import argparse
import json

import faiss
import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer

from pipeline import DATA, digest, faq_digest, mask, read_data, split_customers

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


class FAQSearch:
    def __init__(self, faq, model_path=MODEL_ID):
        torch.set_num_threads(min(4, torch.get_num_threads()))
        self.faq = faq
        self.aliases = [q for item in faq for q in item["queries"]]
        self.owners = np.array([i for i, item in enumerate(faq) for _ in item["queries"]])
        self.encoder = SentenceTransformer(model_path, device="cpu")
        anchors = self.encode(self.aliases)
        self.index = faiss.IndexFlatIP(anchors.shape[1])
        self.index.add(anchors)

    def encode(self, texts):
        return self.encoder.encode([mask(x) for x in texts], normalize_embeddings=True,
                                   batch_size=24, show_progress_bar=False).astype("float32")

    def scores(self, texts):
        # Each FAQ keeps its highest-scoring paraphrase. Unit-vector inner products are cosine similarities.
        values, positions = self.index.search(self.encode(texts), len(self.aliases))
        best = np.full((len(texts), len(self.faq)), -1, dtype="float32")
        for i, (row, ids) in enumerate(zip(values, positions)):
            np.maximum.at(best[i], self.owners[ids], row)
        return best.round(6)


def build(model_path=MODEL_ID):
    data, faq = read_data()
    train, _, _ = split_customers(data)
    search = FAQSearch(faq, model_path)
    texts = list(dict.fromkeys([*train.text, *search.aliases]))
    benchmark = pd.read_csv(DATA / "retrieval_test.csv")
    assert not set(texts) & set(benchmark.text)
    scores = search.scores(texts).tolist()
    # Judged questions are scored separately. They never train the student.
    reference = search.scores(benchmark.text).tolist()
    cache = {"teacher":MODEL_ID, "faq_digest":faq_digest(faq),
             "targets":{digest(t):s for t,s in zip(texts,scores)},
             "benchmark":{digest(t):s for t,s in zip(benchmark.text,reference)}}
    (DATA / "teacher_scores.json").write_text(json.dumps(cache, separators=(",", ":")), encoding="utf-8")
    print(f"Prepared {len(texts)} training targets, {len(search.aliases)} FAQ phrasings, {len(reference)} evaluation queries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL_ID, help="Hugging Face ID or local snapshot")
    build(parser.parse_args().model)
