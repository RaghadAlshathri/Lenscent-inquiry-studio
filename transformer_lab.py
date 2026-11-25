"""Optional CAMeLBERT experiments from Labs 2, 3A and 3B."""
import argparse
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader
from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer, set_seed

from pipeline import DATA, LABELS, ROOT, SEED, digest, mask, read_data, split_customers

MODEL_ID = "CAMeL-Lab/bert-base-arabic-camelbert-mix"


def inspect_tokens(model_path=MODEL_ID):
    words = ["طلبت", "رغد", "تصوير", "بالرياض"]
    gold = ["O", "B-PER", "B-SERVICE", "B-LOC"]
    tokenizer = AutoTokenizer.from_pretrained(model_path, use_fast=True)
    encoded = tokenizer(words, is_split_into_words=True, return_tensors="pt")
    ids = encoded.word_ids()
    tokens = tokenizer.convert_ids_to_tokens(encoded["input_ids"][0])
    aligned = [gold[w] if w is not None and (i == 0 or w != ids[i-1]) else -100 for i,w in enumerate(ids)]
    assert sum(x != -100 for x in aligned) == len(words)
    bert = AutoModel.from_pretrained(model_path, attn_implementation="eager").eval()
    with torch.inference_mode():
        attention = bert(**encoded, output_attentions=True).attentions[0][0, 0].cpu().numpy()
    assert np.allclose(attention.sum(axis=1), 1, atol=1e-5)
    table = pd.DataFrame({"token_index":range(len(ids)), "token":tokens, "word_id":ids, "aligned_label":aligned})
    output = ROOT / "outputs"
    output.mkdir(exist_ok=True)
    table.to_csv(output / "token_alignment.csv", index=False, encoding="utf-8-sig")
    fig, ax = plt.subplots(figsize=(6.7, 4.5), layout="constrained")
    image = ax.imshow(attention, cmap="BuPu", vmin=0)
    ax.set(xticks=range(len(ids)), yticks=range(len(ids)), xlabel="Key token index", ylabel="Query token index",
           title="CAMeLBERT attention  |  Layer 1, head 1")
    fig.colorbar(image, ax=ax, label="Attention weight")
    fig.savefig(output / "attention.png", dpi=170)
    plt.close(fig)
    return table


def finetune(model_path=MODEL_ID, epochs=3):
    set_seed(SEED)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    data, _ = read_data()
    train, valid, test = split_customers(data)
    names = sorted(LABELS)
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_path, num_labels=len(names), id2label=dict(enumerate(names)),
        label2id={k:i for i,k in enumerate(names)}).to(device)

    def batches(part, shuffle=False):
        def encode(rows):
            texts, labels = zip(*rows)
            tokens = tokenizer([mask(t) for t in texts], padding=True, truncation=True,
                               max_length=64, return_tensors="pt")
            return tokens.to(device), torch.tensor([names.index(y) for y in labels], device=device)
        return DataLoader(list(zip(part.text, part.topic)), batch_size=8, shuffle=shuffle, collate_fn=encode)

    def predict(part):
        model.eval()
        predictions = []
        with torch.inference_mode():
            for tokens, _ in batches(part):
                predictions.extend(model(**tokens).logits.argmax(1).cpu().tolist())
        return [names[i] for i in predictions]

    opt = torch.optim.AdamW(model.parameters(), lr=2e-5)
    validation_f1 = []
    for epoch in range(epochs):
        model.train()
        for tokens, labels in batches(train, shuffle=True):
            opt.zero_grad(set_to_none=True)
            loss = model(**tokens, labels=labels).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            opt.step()
        validation_f1.append(float(f1_score(valid.topic, predict(valid), labels=names, average="macro", zero_division=0)))
        print(f"Epoch {epoch+1}/{epochs} | validation macro-F1 {validation_f1[-1]:.3f}", flush=True)
    # Epoch count is fixed in advance. Evaluate the final checkpoint once on the test set.
    predicted = predict(test)
    results = {"model":MODEL_ID, "epochs":epochs, "seed":SEED, "learning_rate":2e-5,
               "batch_size":8, "max_length":64, "device":device, "test_messages":len(test),
               "dataset_sha256":digest((DATA / "messages.csv").read_text(encoding="utf-8")),
               "validation_f1":validation_f1, "accuracy":float(accuracy_score(test.topic, predicted)),
               "macro_f1":float(f1_score(test.topic, predicted, labels=names, average="macro", zero_division=0))}
    output = ROOT / "outputs"
    output.mkdir(exist_ok=True)
    (output / "camelbert_metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    test[["customer_id","topic"]].assign(prediction=predicted).to_csv(output / "camelbert_predictions.csv", index=False)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=MODEL_ID)
    parser.add_argument("--task", choices=["tokens", "finetune"], default="tokens")
    args = parser.parse_args()
    print((inspect_tokens if args.task == "tokens" else finetune)(args.model))
