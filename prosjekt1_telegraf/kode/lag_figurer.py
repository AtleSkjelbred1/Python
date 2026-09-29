"""Lager alle figurer og tabeller som brukes i rapporten.

Kjøres fra mappa kode/:   python lag_figurer.py
Figurene lagres i ../rapport/figurer og tabellene i ../rapport/tabeller.
Tallene som siteres i teksten skrives som LaTeX-makroer til tabeller/tall.tex.
"""

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

import stil
from analytisk import (ERFCINV_HALV, bolgefront, diffusjon_erfc, fourierrekke, gauss,
                       heaviside_puls, lastspenning_tapsfri, moderotter, sprangrespons, t50,
                       t50_diffusjon)
from fdtd import AAPEN, KORTSLUTNING, Terminering, simuler
from linje import (TELEFON, TELEFON_HEAVISIDE, TELEFON_PUPIN, TILFELLE_A, TILFELLE_B,
                   TILFELLE_C, TILFELLE_D, TILFELLER, Z0_MODELL, modellinje)

ROT = Path(__file__).resolve().parent.parent / "rapport"
FIG = ROT / "figurer"
TAB = ROT / "tabeller"
TALL = {}

LENGDE = 100.0      # m, linjelengde i modellproblemene
W_PULS = 2.0        # m, standardavvik for den gaussiske pulsen
T_RAMPE = 10e-9     # s, stigetid for sprangkilder


def lagre(fig, navn):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{navn}.pdf")
    plt.close(fig)
    print(f"  figur: {navn}.pdf")


def skriv_tabell(navn, tekst):
    TAB.mkdir(parents=True, exist_ok=True)
    (TAB / f"{navn}.tex").write_text(tekst, encoding="utf-8")
    print(f"  tabell: {navn}.tex")


def num(x, sifre=3):
    return rf"\num{{{float(x):.{sifre}g}}}"


def tall(navn, verdi, sifre=3):
    """Tall som siteres i teksten; skrives som rå tall og formateres med siunitx."""
    TALL[navn] = f"{float(verdi):.{sifre}g}"


def rampe(t, tr=T_RAMPE):
    """Glatt sprang (hevet cosinus) med stigetid tr."""
    t = np.asarray(t, dtype=float)
    return np.where(t <= 0, 0.0, np.where(t >= tr, 1.0, 0.5 * (1 - np.cos(np.pi * t / tr))))


def fwhm(x, y):
    """Full bredde ved halv høyde, med lineær interpolasjon."""
    i = np.argmax(y)
    halv = 0.5 * y[i]
    over = np.where(y >= halv)[0]
    v, h = over[0], over[-1]
    xv = np.interp(halv, [y[v - 1], y[v]], [x[v - 1], x[v]])
    xh = np.interp(halv, [y[h + 1], y[h]], [x[h + 1], x[h]])
    return xh - xv


# ---------------------------------------------------------------------------
def tabell_tilfeller():
    rader = []
    for lin in TILFELLER:
        rader.append(" & ".join([
            lin.navn.split(":")[0] + ": " + lin.navn.split(": ")[1],
            num(lin.R), num(lin.G), num(lin.a), num(lin.b),
            num(lin.rho(LENGDE)), num(lin.sigma(LENGDE)),
        ]) + r" \\")
    skriv_tabell("tilfeller", "\n".join(rader) + "\n")
    tall("aB", TILFELLE_B.a)
    tall("aC", TILFELLE_C.a)
    tall("aD", TILFELLE_D.a)
    tall("GC", TILFELLE_C.G)
    tall("DD", TILFELLE_D.D)


# ---------------------------------------------------------------------------
def figur_dispersjon():
    f = np.logspace(3, 9.5, 800)
    w = 2 * np.pi * f
    fig, akser = plt.subplots(1, 3, figsize=(stil.BREDDE, 2.35))
    sigma_t = W_PULS / TILFELLE_A.v
    f_puls = np.sqrt(2 * np.log(100)) / (2 * np.pi * sigma_t)
    for i, lin in enumerate(TILFELLER):
        stilart = dict(color=stil.KATEGORI[i], ls=stil.LINJETYPE[i], label=lin.navn)
        if lin.R > 0:
            akser[0].loglog(f, lin.alpha(w), **stilart)
        else:
            akser[0].plot([], [], **stilart)
        akser[1].semilogx(f, lin.fasehastighet(w) / lin.v, **stilart)
        akser[2].semilogx(f, lin.gruppehastighet(w) / lin.v, **stilart)
    for ax in akser:
        ax.axvspan(f[0], f_puls, color=stil.RUTENETT, alpha=0.6, lw=0, zorder=0)
        ax.set_xlabel(r"$f$ (Hz)")
        ax.set_xlim(f[0], f[-1])
    akser[0].set_ylabel(r"$\alpha$ (Np/m)")
    akser[0].set_ylim(1e-6, 1)
    akser[1].set_ylabel(r"$v_p/v$")
    akser[2].set_ylabel(r"$v_g/v$")
    akser[1].set_ylim(0, 1.15)
    akser[2].set_ylim(0, 1.15)
    for ax, merke in zip(akser, ["(a) Dempning", "(b) Fasehastighet", "(c) Gruppehastighet"]):
        stil.panelmerke(ax, merke)
        stil.komma(ax, "y")
    akser[0].text(2e3, 2e-1, r"A: $\alpha = 0$", fontsize=7, color=stil.BLEKK2)
    fig.legend(*akser[1].get_legend_handles_labels(), loc="upper center", ncol=4,
               bbox_to_anchor=(0.5, 1.08))
    fig.tight_layout(w_pad=0.8)
    lagre(fig, "dispersjon_modell")

    # Maksimal gruppehastighet for G = 0 (universell i variabelen omega L / R)
    wf = np.logspace(-3, 3, 20001) * TILFELLE_B.R / TILFELLE_B.L
    vg = TILFELLE_B.gruppehastighet(wf) / TILFELLE_B.v
    tall("vgmaks", vg.max(), 4)
    tall("wvgmaks", wf[vg.argmax()] * TILFELLE_B.L / TILFELLE_B.R, 3)
    tall("fpuls", f_puls / 1e6, 2)


# ---------------------------------------------------------------------------
def figur_telefon():
    f = np.logspace(1.5, 4.5, 600)
    w = 2 * np.pi * f
    linjer = [TELEFON, TELEFON_PUPIN, TELEFON_HEAVISIDE]
    fig, akser = plt.subplots(1, 2, figsize=(stil.BREDDE, 2.5))
    for i, lin in enumerate(linjer):
        s = dict(color=stil.KATEGORI[i], ls=stil.LINJETYPE[i], label=lin.navn)
        akser[0].loglog(f, 8.686 * 1e3 * lin.alpha(w), **s)
        akser[1].loglog(f, lin.fasehastighet(w) / 1e3, **s)
    for ax in akser:
        ax.axvspan(300, 3400, color=stil.RUTENETT, alpha=0.6, lw=0, zorder=0)
        ax.set_xlabel(r"$f$ (Hz)")
        ax.set_xlim(f[0], f[-1])
    akser[0].set_ylabel(r"$\alpha$ (dB/km)")
    akser[1].set_ylabel(r"$v_p$ (km/s)")
    stil.panelmerke(akser[0], "(a) Dempning")
    stil.panelmerke(akser[1], "(b) Fasehastighet")
    akser[0].legend(loc="lower right")
    fig.tight_layout()
    lagre(fig, "telefonlinje")

    rader = []
    frek = [300.0, 1000.0, 3400.0]
    for lin in linjer:
        wf = 2 * np.pi * np.array(frek)
        a_db = 8.686e3 * lin.alpha(wf)
        vp = lin.fasehastighet(wf) / 1e3
        rader.append(" & ".join([lin.navn, num(lin.L * 1e6, 3)] + [num(v, 3) for v in a_db]
                                + [num(v, 3) for v in vp]) + r" \\")
    skriv_tabell("telefon", "\n".join(rader) + "\n")
    L_h = TELEFON_HEAVISIDE.L * 1e3  # H/km
    tall("LHeaviside", L_h, 3)
    tall("Lpupin", TELEFON_PUPIN.L * 1e3 * 1e3, 3)  # mH/km
    # Forsinkelsesforskjell (gruppeforsinkelse) over 300-3400 Hz for 10 km
    lengde = 10e3
    for navn, lin in [("Uten", TELEFON), ("Pupin", TELEFON_PUPIN)]:
        vg = lin.gruppehastighet(2 * np.pi * np.array(frek))
        tall(f"dtau{navn}", abs(lengde / vg[0] - lengde / vg[-1]) * 1e3, 2)  # ms
        a = 8.686e3 * lin.alpha(2 * np.pi * np.array(frek))
        tall(f"dalfa{navn}", a[-1] - a[0], 2)


# ---------------------------------------------------------------------------
def pulsforplantning():
    """Gaussisk puls som starter som en høyregående bølge (V = f, I = f/Z0)."""
    x0 = 100.0
    f = gauss(x0, W_PULS)
    t_slutt = 0.5e-6
    t_bilder = np.linspace(0, t_slutt, 51)
    resultater = {}
    for lin in TILFELLER:
        resultater[lin.navn] = simuler(
            lin, 300.0, 0.05, t_slutt, V0=f, I0=lambda x: f(x) / lin.Z0,
            venstre=Terminering(lin.Z0), hoyre=Terminering(lin.Z0), t_bilder=t_bilder)

    # Figur: øyeblikksbilder
    fig, akser = plt.subplots(2, 2, figsize=(stil.BREDDE, 4.0), sharex=True, sharey=True)
    vis = [0, 10, 20, 30, 40, 50]
    for ax, lin in zip(akser.flat, TILFELLER):
        res = resultater[lin.navn]
        for k, n in enumerate(vis):
            etikett = rf"$t = {res.t_bilder[n] * 1e6:.1f}\,\mu\mathrm{{s}}$".replace(".", "{,}")
            ax.plot(res.x, res.V[n], color=stil.SEKVENS[k], lw=1.2, label=etikett)
        stil.panelmerke(ax, lin.navn)
        ax.set_xlim(40, 260)
        ax.set_ylim(-0.05, 1.05)
        stil.komma(ax)
    for ax in akser[1]:
        ax.set_xlabel(r"$x$ (m)")
    for ax in akser[:, 0]:
        ax.set_ylabel(r"$V$ (V)")
    fig.legend(*akser[0, 0].get_legend_handles_labels(), loc="upper center", ncol=6,
               bbox_to_anchor=(0.5, 1.04))
    fig.tight_layout()
    lagre(fig, "puls_bilder")

    # Figur: mål på pulsen som funksjon av tid
    fig, akser = plt.subplots(2, 2, figsize=(stil.BREDDE, 4.0), sharex=True)
    tabellrader = []
    for i, lin in enumerate(TILFELLER):
        res = resultater[lin.navn]
        t = res.t_bilder * 1e6
        topp = res.V.max(axis=1)
        bredde = np.array([fwhm(res.x, V) for V in res.V])
        ladning = np.trapezoid(res.V, res.x, axis=1)
        E = np.interp(res.t_bilder, res.t, res.energi)
        s = dict(color=stil.KATEGORI[i], ls=stil.LINJETYPE[i], label=lin.navn)
        akser[0, 0].plot(t, topp, **s)
        akser[0, 1].plot(t, bredde, **s)
        akser[1, 0].plot(t, ladning / ladning[0], **s)
        akser[1, 1].plot(t, E / E[0], **s)
        balanse = np.max(np.abs(res.energi + res.tap - res.energi[0])) / res.energi[0]
        tabellrader.append(" & ".join([
            lin.navn, num(topp[-1]), num(bredde[-1]), num(ladning[-1] / ladning[0]),
            num(E[-1] / E[0]), num(balanse, 2)]) + r" \\")
    # Teorikurver
    tt = np.linspace(0, 0.5e-6, 200)
    akser[0, 0].plot(tt * 1e6, np.exp(-TILFELLE_C.a * tt), color=stil.BLEKK, lw=0.6,
                     label=r"$e^{-at}$ (C)")
    D = TILFELLE_D.D
    akser[0, 0].plot(tt * 1e6, W_PULS / np.sqrt(W_PULS ** 2 + 2 * D * tt), color=stil.BLEKK,
                     lw=0.6, ls=(0, (1, 1.5)), label="diffusjon (D)")
    akser[0, 1].plot(tt * 1e6, 2 * np.sqrt(2 * np.log(2)) * np.sqrt(W_PULS ** 2 + 2 * D * tt),
                     color=stil.BLEKK, lw=0.6, ls=(0, (1, 1.5)))
    akser[1, 0].plot(tt * 1e6, np.exp(-TILFELLE_C.G / TILFELLE_C.C * tt), color=stil.BLEKK,
                     lw=0.6)
    akser[1, 1].plot(tt * 1e6, np.exp(-2 * TILFELLE_C.a * tt), color=stil.BLEKK, lw=0.6)
    akser[0, 0].set_ylabel(r"$V_{\max}$ (V)")
    akser[0, 1].set_ylabel(r"Halvverdibredde (m)")
    akser[1, 0].set_ylabel(r"$Q(t)/Q(0)$")
    akser[1, 1].set_ylabel(r"$E(t)/E(0)$")
    akser[0, 1].set_yscale("log")
    akser[0, 1].set_yticks([5, 10, 20, 50])
    akser[0, 1].yaxis.set_major_formatter(plt.ScalarFormatter())
    akser[0, 1].yaxis.set_minor_formatter(plt.NullFormatter())
    for ax, merke in zip(akser.flat, ["(a) Toppverdi", "(b) Pulsbredde", "(c) Ladning",
                                      "(d) Energi"]):
        stil.panelmerke(ax, merke)
        stil.komma(ax)
    for ax in akser[1]:
        ax.set_xlabel(r"$t$ ($\mu$s)")
    fig.legend(*akser[0, 0].get_legend_handles_labels(), loc="upper center", ncol=6,
               bbox_to_anchor=(0.5, 1.05), fontsize=7)
    fig.tight_layout()
    lagre(fig, "puls_maal")
    skriv_tabell("pulsmaal", "\n".join(tabellrader) + "\n")

    res = resultater[TILFELLE_C.navn]
    Vex, _ = heaviside_puls(TILFELLE_C, f, res.x, res.t_bilder[-1])
    tall("feilC", np.max(np.abs(res.V[-1] - Vex)), 2)
    resB = resultater[TILFELLE_B.navn]
    tall("toppB", resB.V[-1].max())
    tall("toppBteori", np.exp(-TILFELLE_B.a * 0.5e-6))
    tall("toppC", res.V[-1].max())


# ---------------------------------------------------------------------------
def verifisering():
    f = gauss(60.0, W_PULS)
    linC = TILFELLE_C
    T = 0.3e-6
    dxer = [0.4, 0.2, 0.1, 0.05, 0.025]
    feil_h, feil_f = [], []
    for dx in dxer:
        res = simuler(linC, 200.0, dx, T,
                      V0=lambda x: heaviside_puls(linC, f, x, 0.0)[0],
                      I0=lambda x: heaviside_puls(linC, f, x, 0.0)[1],
                      venstre=Terminering(linC.Z0), hoyre=Terminering(linC.Z0),
                      cfl=0.5, t_bilder=[T])
        Vex, _ = heaviside_puls(linC, f, res.x, res.t_bilder[0])
        feil_h.append(np.max(np.abs(res.V[0] - Vex)))

    fB = gauss(30.0, W_PULS)
    TB = 0.4e-6
    for dx in dxer:
        res = simuler(TILFELLE_B, LENGDE, dx, TB, V0=fB, venstre=KORTSLUTNING,
                      hoyre=KORTSLUTNING, cfl=0.5, t_bilder=[TB])
        Vf = fourierrekke(TILFELLE_B, LENGDE, fB, res.x, res.t_bilder[0])
        feil_f.append(np.max(np.abs(res.V[0] - Vf)))
        if dx == 0.2:
            res_vis = res

    fig, akser = plt.subplots(1, 2, figsize=(stil.BREDDE, 2.5), gridspec_kw={"width_ratios": [1.5, 1]})
    ax = akser[0]
    xf = np.linspace(0, LENGDE, 2001)
    ax.plot(xf, fB(xf), color=stil.DEMPET, lw=0.8, ls=":", label=r"$V(x,0)$")
    ax.plot(xf, fourierrekke(TILFELLE_B, LENGDE, fB, xf, res_vis.t_bilder[0]), color=stil.BLA,
            label="Fourierrekke")
    ax.plot(res_vis.x[::5], res_vis.V[0][::5], "o", color=stil.ORANSJE, ms=2.5,
            label=r"FDTD, $\Delta x = 0{,}2$ m")
    ax.set_xlabel(r"$x$ (m)")
    ax.set_ylabel(r"$V$ (V)")
    ax.set_xlim(0, LENGDE)
    ax.legend(loc="upper left")
    stil.panelmerke(ax, r"(a) Tilfelle B, $t = 0{,}4\,\mu$s, kortsluttede ender")
    stil.komma(ax)

    ax = akser[1]
    dx = np.array(dxer)
    ax.loglog(dx, feil_h, "o-", color=stil.AKVA, label="C mot eksakt")
    ax.loglog(dx, feil_f, "s--", color=stil.BLA, label="B mot Fourierrekke")
    ax.loglog(dx, feil_h[0] * (dx / dx[0]) ** 2, color=stil.BLEKK, lw=0.6, ls=":",
              label=r"$\propto \Delta x^2$")
    ax.set_xlabel(r"$\Delta x$ (m)")
    ax.set_ylabel(r"$\max_j |V_j - V(x_j)|$ (V)")
    ax.set_xticks(dxer)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, p: f"{v:g}".replace(".", "{,}")))
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.legend(loc="upper left")
    stil.panelmerke(ax, "(b) Konvergens")
    fig.tight_layout()
    lagre(fig, "verifisering")

    rader = []
    for i, d in enumerate(dxer):
        ph = "--" if i == 0 else num(np.log2(feil_h[i - 1] / feil_h[i]), 3)
        pf = "--" if i == 0 else num(np.log2(feil_f[i - 1] / feil_f[i]), 3)
        rader.append(" & ".join([num(d), num(feil_h[i]), ph, num(feil_f[i]), pf]) + r" \\")
    skriv_tabell("konvergens", "\n".join(rader) + "\n")


# ---------------------------------------------------------------------------
def figur_moder():
    n = np.arange(1, 21)
    k = n * np.pi / LENGDE
    fig, akser = plt.subplots(1, 2, figsize=(stil.BREDDE, 2.5))
    nn = np.linspace(0, 21, 200)
    akser[0].plot(nn, TILFELLE_A.v * nn * np.pi / LENGDE / (2 * np.pi) / 1e6, color=stil.BLA,
                  lw=0.8, label=r"A: tapsfri, $vk/2\pi$")
    for i, lin in [(1, TILFELLE_B), (3, TILFELLE_D)]:
        r1, r2 = moderotter(lin, k)
        s = dict(color=stil.KATEGORI[i], ms=4, ls="none", marker="s" if i == 3 else "o",
                 mfc="none" if i == 3 else stil.KATEGORI[i])
        akser[0].plot(n, np.abs(r1.imag) / (2 * np.pi) / 1e6, label=lin.navn, **s)
        if i == 3:
            akser[1].plot(n, -r1.real / 1e6, label=r"D: $r_n^{+}$", **s)
            akser[1].plot(n, -r2.real / 1e6, label=r"D: $r_n^{-}$", **{**s, "marker": "v"})
        else:
            akser[1].plot(n, -r1.real / 1e6, label=lin.navn, **s)
    akser[1].plot(n, TILFELLE_D.D * k ** 2 / 1e6, color=stil.BLEKK, lw=0.6, ls=":",
                  label=r"$D k_n^2$")
    akser[0].set_ylabel(r"$\omega_n/2\pi$ (MHz)")
    akser[1].set_ylabel(r"Dempingsrate $-\mathrm{Re}\,r_n$ ($\mu$s$^{-1}$)")
    akser[1].set_yscale("log")
    for ax in akser:
        ax.set_xlabel(r"Modenummer $n$")
        ax.set_xlim(0, 21)
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        stil.komma(ax)
    stil.panelmerke(akser[0], "(a) Svingefrekvens")
    stil.panelmerke(akser[1], "(b) Demping")
    akser[0].legend(loc="upper left")
    akser[1].legend(loc="center right", bbox_to_anchor=(1.0, 0.47), fontsize=7)
    fig.tight_layout()
    lagre(fig, "moder")
    nc = TILFELLE_D.b * LENGDE / (np.pi * TILFELLE_D.v)
    tall("ncD", nc, 3)


# ---------------------------------------------------------------------------
def figur_refleksjon():
    lin = TILFELLE_A
    T = LENGDE / lin.v
    fig, akser = plt.subplots(1, 2, figsize=(stil.BREDDE, 2.6), sharey=True)
    laster = [(Z0_MODELL, r"$R_L = Z_0$"), (np.inf, r"$R_L = \infty$ (åpen)"),
              (0.0, r"$R_L = 0$ (kortsl.)"), (3 * Z0_MODELL, r"$R_L = 3Z_0$")]
    t_slutt = 4 * T
    for i, (RL, navn) in enumerate(laster):
        res = simuler(lin, LENGDE, 0.1, t_slutt, venstre=Terminering(Z0_MODELL, rampe),
                      hoyre=Terminering(RL), x_maal=[LENGDE])
        akser[0].plot(res.t * 1e6, res.V_maal[:, 0], color=stil.KATEGORI[i], ls=stil.LINJETYPE[i],
                      label=navn)
        teori = lastspenning_tapsfri(res.t, LENGDE, lin.v, Z0_MODELL, Z0_MODELL, RL, rampe)
        akser[0].plot(res.t[::150] * 1e6, teori[::150], "o", color=stil.BLEKK, ms=2.2, mew=0)
    akser[0].plot([], [], "o", color=stil.BLEKK, ms=2.2, label="gitterdiagram")
    akser[0].set_title(r"(a) Tapsfri linje, $R_s = Z_0$", loc="left")
    akser[0].legend(loc="upper left", fontsize=7)
    akser[0].set_ylim(-0.08, 2.05)

    Rs = Z0_MODELL / 4
    t_slutt = 16 * T
    for i, l in [(0, TILFELLE_A), (1, TILFELLE_B), (2, TILFELLE_C)]:
        res = simuler(l, LENGDE, 0.1, t_slutt, venstre=Terminering(Rs, rampe), hoyre=AAPEN,
                      x_maal=[LENGDE])
        akser[1].plot(res.t * 1e6, res.V_maal[:, 0], color=stil.KATEGORI[i], ls=stil.LINJETYPE[i],
                      label=l.navn)
        if i == 0:
            teori = lastspenning_tapsfri(res.t, LENGDE, l.v, Z0_MODELL, Rs, np.inf, rampe)
            akser[1].plot(res.t[::150] * 1e6, teori[::150], "o", color=stil.BLEKK, ms=2.2, mew=0,
                          label="gitterdiagram (A)")
        if i == 2:
            # Likestrømsløsning for en åpen linje med lekkasje
            g0 = np.sqrt(l.R * l.G)
            Zinn = np.sqrt(l.R / l.G) / np.tanh(g0 * LENGDE)
            VL = Zinn / (Zinn + Rs) / np.cosh(g0 * LENGDE)
            akser[1].axhline(VL, color=stil.BLEKK, lw=0.6, ls=(0, (1, 1.5)),
                             label="likestrømsverdi (C)")
            tall("VLdc", VL, 3)
    akser[1].set_title(r"(b) Åpen ende, $R_s = Z_0/4$", loc="left")
    akser[1].legend(loc="upper right", fontsize=6.5, borderaxespad=0.3, labelspacing=0.3)
    for ax in akser:
        ax.set_xlabel(r"$t$ ($\mu$s)")
        stil.komma(ax)
    akser[0].set_ylabel(r"$V(\ell, t)$ (V)")
    fig.tight_layout()
    lagre(fig, "refleksjon")


# ---------------------------------------------------------------------------
def figur_diffusjon():
    x = 50.0
    t = np.logspace(-7.5, -4, 400)
    fig, akser = plt.subplots(1, 2, figsize=(stil.BREDDE, 2.7))
    ax = akser[0]
    R_verdier = [1.0, 5.0, 20.0]
    for i, R in enumerate(R_verdier):
        lin = modellinje(f"R{R}", R=R)
        ax.semilogx(t * 1e6, sprangrespons(lin, x, t), color=stil.KATEGORI[i + 1],
                    ls=stil.LINJETYPE[i + 1], label=rf"$R = {R:g}\,\Omega$/m")
        ax.semilogx(t * 1e6, diffusjon_erfc(lin, x, t), color=stil.KATEGORI[i + 1], lw=0.6,
                    ls=(0, (1, 1.5)))
    ax.semilogx(t * 1e6, (t > x / TILFELLE_A.v).astype(float), color=stil.BLA, label=r"$R = 0$")
    ax.plot([], [], color=stil.BLEKK2, lw=0.6, ls=(0, (1, 1.5)), label="diffusjonsgrense")
    # FDTD-kontroll for R = 20 ohm/m
    res = simuler(modellinje("D", R=20.0), 600.0, 0.2, t[-1] / 2, venstre=Terminering(0.0, rampe),
                  hoyre=AAPEN, x_maal=[x])
    idx = np.searchsorted(res.t, np.logspace(-7, np.log10(t[-1] / 2), 18))
    ax.plot(res.t[idx] * 1e6, res.V_maal[idx, 0], "o", color=stil.BLEKK, ms=2.5, mew=0,
            label="FDTD")
    ax.set_xlabel(r"$t$ ($\mu$s)")
    ax.set_ylabel(r"$V(50\,\mathrm{m}, t)/V_0$")
    ax.legend(loc="upper left", fontsize=6.5, frameon=True, facecolor="white", edgecolor="none",
              framealpha=0.9)
    stil.panelmerke(ax, r"(a) Sprangrespons i $x = 50$ m")
    stil.komma(ax, "y")

    ax = akser[1]
    lin = modellinje("ref", R=1.0)
    xi = np.logspace(-2, 2, 41)
    tau = np.array([t50(lin, xx * lin.Z0 / lin.R) * lin.R / lin.L for xx in xi])
    xi_s = 2 * np.log(2)
    ax.loglog(xi, tau, color=stil.BLA, label="Laplace (eksakt)")
    ax.loglog(xi, xi, color=stil.BLEKK, lw=0.6, ls="--", label=r"bølge: $\tau = \xi$")
    ax.loglog(xi, xi ** 2 / (4 * ERFCINV_HALV ** 2), color=stil.BLEKK, lw=0.6, ls=":",
              label=r"diffusjon: $\tau \approx 1{,}10\,\xi^2$")
    ax.axvline(xi_s, color=stil.DEMPET, lw=0.6)
    ax.text(xi_s * 1.1, 2e-2, r"$\xi^* = 2\ln 2$", fontsize=7, color=stil.BLEKK2)
    # FDTD-punkter for to ulike R: skal falle på samme kurve
    for j, (R, xs) in enumerate([(2.0, [10.0, 50.0, 100.0]), (20.0, [2.0, 10.0, 30.0])]):
        l = modellinje("", R=R)
        t_maks = 1.3 * max(t50(l, xx) for xx in xs)
        res = simuler(l, max(xs) + 6 * np.sqrt(l.D * t_maks) + 50.0, 0.1, t_maks,
                      venstre=Terminering(0.0, rampe), hoyre=AAPEN, x_maal=xs)
        for k, xx in enumerate(res.x_maal):
            V = res.V_maal[:, k]
            m = np.argmax(V >= 0.5)
            t_h = np.interp(0.5, V[m - 1:m + 1], res.t[m - 1:m + 1]) - 0.5 * T_RAMPE
            ax.plot(xx * R / l.Z0, t_h * R / l.L, "os"[j], color=stil.KATEGORI[j + 1], mfc="none",
                    ms=5, label=rf"FDTD, $R = {R:g}\,\Omega$/m" if k == 0 else None)
    ax.set_xlabel(r"$\xi = xR/Z_0$")
    ax.set_ylabel(r"$\tau_{50} = t_{50}R/L$")
    ax.legend(loc="upper left", fontsize=7)
    stil.panelmerke(ax, "(b) Tid til halv verdi, universell kurve")
    fig.tight_layout()
    lagre(fig, "diffusjon")

    linD = TILFELLE_D
    tall("tfemtiD", t50(linD, x) * 1e6, 3)
    tall("tfemtiDdiff", t50_diffusjon(linD, x) * 1e6, 3)
    tall("frontD", bolgefront(linD, x), 2)


# ---------------------------------------------------------------------------
def skriv_tall():
    linjer = [rf"\newcommand{{\{navn}}}{{{verdi}}}" for navn, verdi in sorted(TALL.items())]
    skriv_tabell("tall", "\n".join(linjer) + "\n")


def main():
    stil.oppsett()
    print("Lager figurer og tabeller ...")
    tabell_tilfeller()
    figur_dispersjon()
    figur_telefon()
    verifisering()
    pulsforplantning()
    figur_moder()
    figur_refleksjon()
    figur_diffusjon()
    skriv_tall()


if __name__ == "__main__":
    main()
