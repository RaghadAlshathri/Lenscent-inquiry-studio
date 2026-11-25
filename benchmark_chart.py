"""Render the classification and retrieval benchmarks from the evaluation report."""
import json
from pathlib import Path

import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
report = json.loads((root / "outputs/metrics.json").read_text())
retrieval = report["retrieval"]
names = ["Word SVM", "Character SVM"]
values = [report["word_f1"], report["macro_f1"]]
if "camelbert_f1" in report:
    names.append("CAMeLBERT")
    values.append(report["camelbert_f1"])

fig, axes = plt.subplots(1, 2, figsize=(10.8, 3.4), layout="constrained")
fig.patch.set_facecolor("#fbf8f4")
panels = [
    ("Intent classification", names, values, "Macro-F1"),
    ("FAQ retrieval", ["MiniLM + FAISS", "Browser ranker"],
     [retrieval[k]["top1"] for k in ("teacher", "student")], "Top-1 accuracy"),
]
for ax, (title, labels, scores, metric) in zip(axes, panels):
    ax.set_facecolor("#fbf8f4")
    bars = ax.barh(labels, scores, height=.45, color="#54202b")
    ax.invert_yaxis()
    ax.set(xlim=(0, 1), xlabel=metric, xticks=[0, .25, .5, .75, 1])
    ax.set_title(title, loc="left", pad=12, weight="bold", color="#360d15")
    ax.bar_label(bars, labels=[f"{s:.3f}" if metric=="Macro-F1" else f"{s:.1%}" for s in scores],
                 padding=-44, color="white")
    for spine in ax.spines.values():
        spine.set_visible(False)
fig.savefig(root / "outputs/benchmark.png", dpi=160)
plt.close(fig)
