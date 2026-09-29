"""Felles figurstil for rapporten (matplotlib med LaTeX-tekst og desimalkomma)."""

import shutil
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import ScalarFormatter  # noqa: E402

# Kategoriske farger i fast rekkefølge (fargeblindtestet palett) + linjetyper
# som sekundær koding, slik at figurene også kan leses i gråtoner.
BLA, ORANSJE, AKVA, GUL, MAGENTA, GRONN, FIOLETT = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"
)
KATEGORI = [BLA, ORANSJE, AKVA, GUL]
LINJETYPE = ["-", "--", "-.", ":"]
# Sekvensiell blåskala (lys -> mørk) for ordnede størrelser, f.eks. tid
SEKVENS = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]

BLEKK = "#0b0b0b"
BLEKK2 = "#52514e"
DEMPET = "#898781"
RUTENETT = "#e1e0d9"
AKSE = "#c3c2b7"

BREDDE = 6.1  # tommer, tilsvarer tekstbredden i rapporten


class KommaFormatter(ScalarFormatter):
    """Som ScalarFormatter, men med desimalkomma."""

    def __call__(self, x, pos=None):
        return super().__call__(x, pos).replace(".", "{,}")


def _har_latex():
    """LaTeX-tekst krever latex og cm-super; ellers brukes matplotlibs mathtext."""
    if shutil.which("latex") is None or shutil.which("kpsewhich") is None:
        return False
    svar = subprocess.run(["kpsewhich", "type1ec.sty"], capture_output=True, text=True)
    return bool(svar.stdout.strip())


def oppsett():
    bruk_tex = _har_latex()
    plt.rcParams.update({
        "text.usetex": bruk_tex,
        "text.latex.preamble": r"\usepackage{lmodern}\usepackage{amsmath}\usepackage[T1]{fontenc}",
        "font.family": "serif",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "legend.fontsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "axes.edgecolor": AKSE,
        "axes.labelcolor": BLEKK,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": RUTENETT,
        "grid.linewidth": 0.5,
        "xtick.color": BLEKK2,
        "ytick.color": BLEKK2,
        "text.color": BLEKK,
        "lines.linewidth": 1.4,
        "lines.markersize": 4,
        "legend.frameon": False,
        "figure.dpi": 150,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "axes.formatter.use_mathtext": True,
        "mathtext.fontset": "cm",
    })


def komma(ax, akser="xy"):
    """Desimalkomma på lineære akser."""
    for navn in akser:
        akse = ax.xaxis if navn == "x" else ax.yaxis
        if akse.get_scale() == "linear":
            akse.set_major_formatter(KommaFormatter(useMathText=True))


def panelmerke(ax, tekst):
    ax.set_title(tekst, loc="left", fontsize=9)
