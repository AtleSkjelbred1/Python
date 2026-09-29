"""Analytiske og semianalytiske løsninger av telegraflikningen.

    V_xx = LC V_tt + (RC + GL) V_t + RG V

Funksjonene her brukes både som fasit for den numeriske løseren og som
selvstendige resultater i rapporten.
"""

import numpy as np
from scipy.optimize import brentq
from scipy.special import erfc, erfcinv


def gauss(x0, w, V0=1.0):
    """Gaussisk puls med sentrum x0 og standardavvik w."""
    return lambda x: V0 * np.exp(-0.5 * ((np.asarray(x) - x0) / w) ** 2)


# ---------------------------------------------------------------------------
# 1) Forvrengningsfri linje (R/L = G/C): V = e^{-at} f(x - vt), I = V/Z0
def heaviside_puls(linje, f, x, t):
    if not linje.er_forvrengningsfri():
        raise ValueError("Linja oppfyller ikke Heaviside-betingelsen R/L = G/C")
    V = np.exp(-linje.a * t) * f(np.asarray(x) - linje.v * t)
    return V, V / linje.Z0


# ---------------------------------------------------------------------------
# 2) Separasjon av variable på en endelig linje, V(0,t) = V(l,t) = 0
def moderotter(linje, k):
    """Røttene r = -a +- sqrt(b^2 - v^2 k^2) til T'' + 2a T' + (v^2k^2 + RG/LC) T = 0."""
    rot = np.sqrt(linje.b ** 2 - (linje.v * np.asarray(k)) ** 2 + 0j)
    return -linje.a + rot, -linje.a - rot


def fourierrekke(linje, lengde, f, x, t, n_moder=600, n_kvad=40001):
    """Løsning som sinusrekke. Startkrav: V(x,0) = f(x), I(x,0) = 0.

    Da gir den andre telegraflikningen V_t(x,0) = -(G/C) f(x).
    """
    xs = np.linspace(0.0, lengde, n_kvad)
    n = np.arange(1, n_moder + 1)
    k = n * np.pi / lengde
    F = 2.0 / lengde * np.trapezoid(np.sin(np.outer(k, xs)) * f(xs), xs, axis=1)
    r1, r2 = moderotter(linje, k)
    T0 = F
    dT0 = -(linje.G / linje.C) * F
    A = (dT0 - r2 * T0) / (r1 - r2)
    B = T0 - A
    T = A * np.exp(r1 * t) + B * np.exp(r2 * t)
    return (np.sin(np.outer(np.asarray(x), k)) @ T).real


# ---------------------------------------------------------------------------
# 3) Laplace-transformasjon og numerisk invertering (Talbot)
def talbot(F, t, M=24):
    """Numerisk invers Laplace-transformasjon, fast Talbot-kontur.

    J. Abate og P. Valko, Int. J. Numer. Meth. Engng. 60 (2004) 979-993.
    F må ta imot en matrise med komplekse s-verdier.
    """
    t = np.atleast_1d(np.asarray(t, dtype=float))
    theta = np.arange(1, M) * np.pi / M
    cot = 1.0 / np.tan(theta)
    sigma = theta + (theta * cot - 1.0) * cot
    r = 2.0 * M / (5.0 * t)[:, None]
    s = r * theta * (cot + 1j)
    ledd = np.exp(t[:, None] * s) * F(s) * (1.0 + 1j * sigma)
    F_r = F(r.astype(complex))[:, 0]
    return (r[:, 0] / M) * (0.5 * (np.exp(r[:, 0] * t) * F_r).real + ledd.real.sum(axis=1))


def sprangrespons(linje, x, t, V0=1.0, M=24):
    """V(x,t) på en halvuendelig linje når V(0,t) = V0 for t > 0.

    I Laplace-domenet er V(x,s) = (V0/s) exp(-gamma(s) x). Forsinkelsen x/v
    skilles ut, slik at bare en glatt funksjon W(x, tau) inverteres:
        V(x,t) = W(x, t - x/v),   W = L^{-1}{ (V0/s) exp(-x (gamma(s) - s/v)) }.
    Differansen gamma - s/v skrives om for å unngå kansellering for stor |s|.
    """
    t = np.atleast_1d(np.asarray(t, dtype=float))
    tau = t - x / linje.v
    LC = linje.L * linje.C
    p1, p2 = linje.R / linje.L, linje.G / linje.C

    def F(s):
        diff = LC * ((p1 + p2) * s + p1 * p2) / (linje.gamma_s(s) + s / linje.v)
        return V0 / s * np.exp(-x * diff)

    V = np.zeros_like(t)
    pos = tau > 0
    if np.any(pos):
        V[pos] = talbot(F, tau[pos], M=M)
    return V


def bolgefront(linje, x, V0=1.0):
    """Spranget ved bølgefronten t = x/v: V0 exp(-a x / v)."""
    return V0 * np.exp(-linje.a * x / linje.v)


def diffusjon_erfc(linje, x, t, V0=1.0):
    """Diffusjonsgrensen (L -> 0, G = 0): V = V0 erfc(x sqrt(RC) / (2 sqrt(t)))."""
    t = np.asarray(t, dtype=float)
    return V0 * erfc(x * np.sqrt(linje.R * linje.C) / (2.0 * np.sqrt(np.maximum(t, 1e-300))))


ERFCINV_HALV = erfcinv(0.5)  # 0.476936...


def t50_diffusjon(linje, x):
    return x ** 2 * linje.R * linje.C / (4.0 * ERFCINV_HALV ** 2)


def t50(linje, x, V0=1.0):
    """Tiden før V(x,t) når V0/2 etter et sprang ved x = 0 (G = 0)."""
    t_front = x / linje.v
    if bolgefront(linje, x, V0) >= 0.5 * V0:
        return t_front
    t_hoy = max(4.0 * t50_diffusjon(linje, x), 4.0 * t_front)
    g = lambda t: sprangrespons(linje, x, t, V0)[0] - 0.5 * V0
    while g(t_hoy) < 0:
        t_hoy *= 2.0
    return brentq(g, t_front * (1 + 1e-9), t_hoy, xtol=1e-14 * t_hoy, rtol=1e-10)


# ---------------------------------------------------------------------------
# 4) Refleksjoner på en tapsfri linje (gitterdiagram)
def refleksjonskoeffisient(Z, Z0):
    if np.isinf(Z):
        return 1.0
    return (Z - Z0) / (Z + Z0)


def lastspenning_tapsfri(t, lengde, v, Z0, Rs, RL, kilde, n_refl=40):
    """Spenningen over lasten når kilden er kilde(t) i serie med Rs.

    Summerer bølgene i gitterdiagrammet: den første når lasten ved T = l/v, og
    hver ny rundtur (2T) multipliseres med Gamma_L * Gamma_s.
    """
    T = lengde / v
    Gs = refleksjonskoeffisient(Rs, Z0)
    GL = refleksjonskoeffisient(RL, Z0)
    t = np.asarray(t, dtype=float)
    V = np.zeros_like(t)
    for m in range(n_refl):
        V += Z0 / (Rs + Z0) * (1.0 + GL) * (GL * Gs) ** m * kilde(t - (2 * m + 1) * T)
    return V
