"""Export a presentation-sized figure from the current held-out predictions."""
import json

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from pipeline import ROOT

SHORT = {"session_booking":"Booking", "package_pricing":"Pricing", "edit_request":"Editing",
         "gallery_access":"Gallery", "outside":"Outside scope"}


def plot_evaluation():
    report = json.loads((ROOT / "outputs" / "metrics.json").read_text(encoding="utf-8"))
    wine, gold, paper = "#360D15", "#C6A98E", "#FBF8F3"
    fig, (bars, matrix) = plt.subplots(1, 2, figsize=(12.6, 5.6), gridspec_kw={"width_ratios":[1,1.12]})
    fig.patch.set_facecolor(paper)
    for ax in (bars, matrix):
        ax.set_facecolor(paper)
        for spine in ax.spines.values():
            spine.set_visible(False)
    fig.subplots_adjust(left=.115, right=.975, bottom=.18, top=.74, wspace=.46)
    fig.text(.05,.935,"LensCent   /   Model evaluation",color=wine,fontsize=21,fontweight="bold")
    n=report["split"]["test"]["messages"]
    fig.text(.05,.865,f"{n} held-out messages   ·   {report['split']['test']['customers']} unseen customers   ·   Accuracy {report['accuracy']:.1%}   ·   Macro-F1 {report['macro_f1']:.3f}",fontsize=11,color="#594B46")
    items=report["per_class"]
    y=np.arange(len(items))
    bars.barh(y,np.ones(len(items)),color="#EBE2D7",height=.44)
    bars.barh(y,[s["f1"] for s in items],color=wine,height=.44)
    bars.set(xlim=(0,1.05),yticks=y,yticklabels=[SHORT[s["key"]] for s in items],xticks=[0,.5,1])
    bars.invert_yaxis()
    bars.set_title("F1 by topic",loc="left",fontsize=14,pad=14,color=wine)
    for i,s in enumerate(items):
        bars.text(s["f1"]-.016,i,f"{s['f1']:.2f}",ha="right",va="center",color="white",fontsize=10)
    labels=[SHORT[k].replace("Outside scope","Outside") for k in report["labels"]]
    cm=np.array(report["confusion"])
    cmap=LinearSegmentedColormap.from_list("lenscent",[paper,gold,wine])
    matrix.imshow(cm,cmap=cmap,vmin=0,vmax=max(1,cm.max()))
    matrix.set(xticks=range(len(labels)),xticklabels=labels,yticks=range(len(labels)),yticklabels=labels,
               xlabel="Predicted topic",ylabel="Actual topic")
    matrix.tick_params(labelsize=9)
    matrix.set_title("Confusion matrix",loc="left",fontsize=14,pad=14,color=wine)
    for (row,col),count in np.ndenumerate(cm):
        matrix.text(col,row,str(count),ha="center",va="center",color="white" if count>.65*cm.max() else wine)
    fig.text(.05,.045,"Source: fictional Arabic and English inquiries. Counts and F1 are computed before clarification or handoff.",fontsize=9,color="#65564E")
    dest=ROOT/"outputs"/"evaluation.png"
    fig.savefig(dest,dpi=165,facecolor=paper)
    plt.close(fig)
    return dest


if __name__ == "__main__":
    print(plot_evaluation())
