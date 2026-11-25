"""Train the browser models, evaluate on unseen customers and export the demo."""
import json

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import Ridge
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.pipeline import make_pipeline
from sklearn.svm import LinearSVC

from pipeline import DATA, LABELS, ROOT, SEED, clean, digest, faq_digest, mask, read_data, split_customers

# A small FAQ score gap asks the operator to clarify which of two related entries applies.
FAQ_GAP = 0.035


def tune_margin(scores, truth, classes):
    ordered = np.sort(scores, axis=1)
    gaps = ordered[:, -1] - ordered[:, -2]
    predictions = classes[scores.argmax(axis=1)]
    thresholds = np.arange(.15, 1.01, .05)
    trials = []
    for t in thresholds:
        eligible = (predictions != "outside") & (gaps >= t)
        count = int(eligible.sum())
        if count >= 5:
            precision = float(np.mean(truth[eligible] == predictions[eligible]))
            trials.append((precision, count, float(t)))
    good = [trial for trial in trials if trial[0] >= .85]
    if good:
        return max(good, key=lambda x: (x[1], -x[2]))[2]
    return max(trials)[2] if trials else 1.0


def route(scores, faq_scores, classes, faq, threshold, features):
    order = np.argsort(-scores, kind="stable")
    topic = classes[order[0]]
    gap = float(scores[order[0]] - scores[order[1]])
    if features == 0 or gap < threshold:
        return topic, "clarify_topic", "", gap
    if topic == "outside":
        return topic, "outside", "", gap
    candidates = sorted((i for i, item in enumerate(faq) if item["topic"] == topic),
                        key=lambda i: -faq_scores[i])
    best, next_best = candidates[:2]
    if faq_scores[best] - faq_scores[next_best] < FAQ_GAP:
        return topic, "clarify_faq", "", gap
    return topic, "answer", faq[best]["id"], gap


def bootstrap_by_customer(predictions):
    grouped = predictions.groupby("customer_id").correct.agg(["sum", "size"]).to_numpy()
    rng = np.random.default_rng(SEED)
    samples = rng.integers(len(grouped), size=(2000, len(grouped)))
    correct, count = grouped[samples].sum(axis=1).T
    return np.quantile(correct / count, [.025, .975]).round(4).tolist()


def ranking_metrics(rankings, truth):
    ranks = [list(order).index(label) + 1 for order, label in zip(rankings, truth)]
    return {"top1": float(np.mean(np.array(ranks) == 1)),
            "recall3": float(np.mean(np.array(ranks) <= 3)),
            "mrr3": float(np.mean([1/r if r <= 3 else 0 for r in ranks]))}


def train():
    data, faq = read_data()
    train_set, valid, test = split_customers(data)
    # One sparse character vector serves the intent classifier and the FAQ ranker.
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True,
                                 lowercase=False, dtype=np.float64)
    x = vectorizer.fit_transform(train_set.text.map(clean))
    classifier = LinearSVC(C=1.0, random_state=SEED).fit(x, train_set.topic)
    classes = classifier.classes_
    v = vectorizer.transform(valid.text.map(clean))
    threshold = tune_margin(classifier.decision_function(v), valid.topic.to_numpy(), classes)

    cache = json.loads((DATA / "teacher_scores.json").read_text(encoding="utf-8"))
    if cache["faq_digest"] != faq_digest(faq):
        raise ValueError("FAQ questions changed. Run python prepare_teacher.py, then python train.py.")
    aliases = [q for item in faq for q in item["queries"]]
    student_texts = list(dict.fromkeys([*train_set.text, *aliases]))
    try:
        targets = np.array([cache["targets"][digest(t)] for t in student_texts])
    except KeyError as exc:
        raise ValueError("Refresh the training targets with python prepare_teacher.py.") from exc
    ranker = Ridge(alpha=.45, solver="lsqr", tol=1e-7)
    ranker.fit(vectorizer.transform(map(clean, student_texts)), targets)

    tx = vectorizer.transform(test.text.map(clean))
    scores, faq_scores = classifier.decision_function(tx), ranker.predict(tx)
    rows = [route(s, f, classes, faq, threshold, n)
            for s, f, n in zip(scores, faq_scores, tx.getnnz(axis=1))]
    pred = test.copy()
    pred[["prediction", "route", "faq_id", "margin"]] = pd.DataFrame(rows, index=pred.index)
    pred["correct"] = pred.topic == pred.prediction
    pred["masked_text"] = pred.text.map(mask)
    pred["length"] = pred.text.map(lambda t: "قصيرة" if len(clean(t).split()) <= 6 else "طويلة")

    word_baseline = make_pipeline(TfidfVectorizer(), LinearSVC(random_state=SEED))
    word_baseline.fit(train_set.text.map(clean), train_set.topic)
    base = word_baseline.predict(test.text.map(clean))
    precision, recall, f1, supports = precision_recall_fscore_support(
        pred.topic, pred.prediction, labels=classes, zero_division=0)
    per_class = [{"key": k, "precision": float(p), "recall": float(r), "f1": float(f), "n": int(n)}
                 for k, p, r, f, n in zip(classes, precision, recall, f1, supports)]
    slices = {}
    for col in ["language", "dialect", "length"]:
        slices[col] = [{"name": name, "n": len(g), "accuracy": float(g.correct.mean())}
                       for name, g in pred.groupby(col, sort=True)]

    judged = pd.read_csv(DATA / "retrieval_test.csv")
    assert not (set(judged.text.map(clean)) & {clean(t) for t in [*data.text, *aliases]})
    keys = np.array([item["id"] for item in faq])
    student_scores = ranker.predict(vectorizer.transform(judged.text.map(clean)))
    teacher_scores = np.array([cache["benchmark"][digest(t)] for t in judged.text])
    student_order = keys[np.argsort(-student_scores, axis=1, kind="stable")]
    teacher_order = keys[np.argsort(-teacher_scores, axis=1, kind="stable")]
    judged["student_top1"], judged["teacher_top1"] = student_order[:, 0], teacher_order[:, 0]
    judged["student_rank"] = [list(row).index(y) + 1 for row, y in zip(student_order, judged.faq_id)]
    accepted = pred[pred.route == "answer"]
    counts = {name: {"messages":len(part), "customers":part.customer_id.nunique()}
              for name, part in [("train", train_set), ("validation", valid), ("test", test)]}
    metrics = {
        "count":len(data), "customers":data.customer_id.nunique(), "split":counts, "seed":SEED,
        "accuracy":accuracy_score(pred.topic, pred.prediction), "correct":int(pred.correct.sum()),
        "macro_f1":f1_score(pred.topic, pred.prediction, average="macro"),
        "word_f1":f1_score(pred.topic, base, average="macro"), "accuracy_ci":bootstrap_by_customer(pred),
        "per_class":per_class, "labels":classes.tolist(),
        "confusion":confusion_matrix(pred.topic, pred.prediction, labels=classes).tolist(),
        "slices":slices, "accepted":len(accepted), "accepted_correct":int(accepted.correct.sum()),
        "retrieval":{"n":len(judged), "student":ranking_metrics(student_order, judged.faq_id),
                     "teacher":ranking_metrics(teacher_order, judged.faq_id)},
        "test_rows":pred[["masked_text","topic","prediction","route"]].to_dict("records"),
    }
    output = ROOT / "outputs"
    output.mkdir(exist_ok=True)
    experiment = output / "camelbert_metrics.json"
    if experiment.exists():
        camel = json.loads(experiment.read_text(encoding="utf-8"))
        same_data = camel.get("dataset_sha256") == digest((DATA / "messages.csv").read_text(encoding="utf-8"))
        if same_data and camel["seed"] == SEED and camel["test_messages"] == len(test):
            metrics["camelbert_f1"] = camel["macro_f1"]
    pred.drop(columns="text").to_csv(output / "test_predictions.csv", index=False, encoding="utf-8-sig")
    joined = pd.concat([part.assign(split=name) for (name, part) in
                        [("train", train_set), ("validation", valid), ("test", test)]])
    joined[["customer_id", "split"]].drop_duplicates().to_csv(output / "customer_split.csv", index=False)
    judged.to_csv(output / "retrieval_predictions.csv", index=False, encoding="utf-8-sig")
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    # Columns per feature: IDF, SVM coefficients in class order, then Ridge coefficients in FAQ order.
    table = np.column_stack([vectorizer.idf_, classifier.coef_.T, ranker.coef_.T]).round(7)
    features = dict(zip(vectorizer.get_feature_names_out(), table.tolist()))
    model = {"classes":classes.tolist(), "names":LABELS, "faq":faq,
             "bias":np.r_[classifier.intercept_, ranker.intercept_].round(8).tolist(),
             "threshold":round(threshold, 6), "faqGap":FAQ_GAP, "features":features}
    for filename, name, payload in [("model.js", "LensModel", model), ("metrics.js", "LensMetrics", metrics)]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        (ROOT / "web" / filename).write_text(f"globalThis.{name}={body};\n", encoding="utf-8")
    print(f"Customers (train / validation / test): {list(counts.values())}")
    print(f"Accuracy {metrics['accuracy']:.3f} | Macro-F1 {metrics['macro_f1']:.3f} | {len(features)} features")
    print("Retrieval:", metrics["retrieval"])
    return metrics


if __name__ == "__main__":
    train()
