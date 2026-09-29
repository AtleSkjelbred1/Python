"""Numerisk løsning av telegraflikningene med et forskjøvet leapfrog-skjema (FDTD).

    C V_t + G V = -I_x
    L I_t + R I = -V_x

V lagres i nodene x_j = j dx til heltallige tider t_n = n dt, og I lagres
midt mellom nodene, x_{j+1/2}, til halvtallige tider t_{n+1/2}. Tapsleddene
middelverdiberegnes over tidssteget (trapesregelen), slik at skjemaet er
andre ordens nøyaktig og stabilt for alle R, G >= 0 når v dt <= dx.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable, Optional

import numpy as np


@dataclass(frozen=True)
class Terminering:
    """Theveninekvivalent i en ende av linja: kilde(t) i serie med Rt.

    Rt = 0      ideell spenningskilde (kortslutning når kilde er None)
    Rt = inf    åpen ende, I = 0
    """

    Rt: float
    kilde: Optional[Callable[[float], float]] = None

    def Vs(self, t):
        return 0.0 if self.kilde is None else float(self.kilde(t))


KORTSLUTNING = Terminering(0.0)
AAPEN = Terminering(np.inf)


def _endenode(V_ende, I_inn, ende, t_ny, t_midt, c, g):
    """Oppdaterer en endenode (halv celle) med trapesregel i tid.

    (C dx/2) dV/dt + (G dx/2) V = I_inn + (Vs - V)/Rt
    """
    if ende.Rt == 0:
        return ende.Vs(t_ny)
    h = 0.0 if np.isinf(ende.Rt) else 0.5 / ende.Rt
    kilde = 0.0 if np.isinf(ende.Rt) else ende.Vs(t_midt) / ende.Rt
    return ((c - g - h) * V_ende + I_inn + kilde) / (c + g + h)


def simuler(linje, lengde, dx, t_slutt, V0=None, I0=None, venstre=AAPEN, hoyre=AAPEN,
            cfl=0.9, t_bilder=(), x_maal=(), x_start=0.0):
    """Løser telegraflikningene på [x_start, x_start + lengde] fram til t_slutt.

    V0, I0      startverdier (funksjoner av x) ved t = 0; standard er null
    t_bilder    tider der hele V(x) og I(x) lagres
    x_maal      posisjoner der V(t) lagres i hvert tidssteg
    """
    R, L, G, C = linje.R, linje.L, linje.G, linje.C
    N = int(round(lengde / dx))
    dx = lengde / N
    x = x_start + dx * np.arange(N + 1)
    xh = x[:-1] + 0.5 * dx
    nsteg = int(np.ceil(t_slutt / (cfl * dx / linje.v)))
    dt = t_slutt / nsteg

    V = np.zeros(N + 1) if V0 is None else np.asarray(V0(x), dtype=float).copy()
    I_null = np.zeros(N) if I0 is None else np.asarray(I0(xh), dtype=float).copy()
    if venstre.Rt == 0:
        V[0] = venstre.Vs(0.0)
    if hoyre.Rt == 0:
        V[-1] = hoyre.Vs(0.0)

    # Koeffisienter for det indre av linja
    av = (C / dt - G / 2) / (C / dt + G / 2)
    bv = 1.0 / (dx * (C / dt + G / 2))
    ai = (L / dt - R / 2) / (L / dt + R / 2)
    bi = 1.0 / (dx * (L / dt + R / 2))
    c_ende = C * dx / (2 * dt)
    g_ende = G * dx / 4

    # Halvt startsteg (Taylor) gir I ved t = dt/2 med feil O(dt^2)
    I = I_null - dt / (2 * L) * (np.diff(V) / dx + R * I_null)

    vekt = np.ones(N + 1)
    vekt[[0, -1]] = 0.5

    def energi(V, I_snitt):
        return 0.5 * dx * (C * np.sum(vekt * V ** 2) + L * np.sum(I_snitt ** 2))

    def tapseffekt(V, I_snitt):
        return dx * (G * np.sum(vekt * V ** 2) + R * np.sum(I_snitt ** 2))

    idx_bilder = {int(round(tb / dt)) for tb in t_bilder}
    idx_maal = np.array([int(round((xm - x_start) / dx)) for xm in x_maal], dtype=int)

    t_ut, V_ut, I_ut = [], [], []
    V_maal = np.empty((nsteg + 1, len(idx_maal)))
    E = np.empty(nsteg + 1)
    P_tap = np.empty(nsteg + 1)

    def lagre(n, V, I_snitt):
        V_maal[n] = V[idx_maal]
        E[n] = energi(V, I_snitt)
        P_tap[n] = tapseffekt(V, I_snitt)
        if n in idx_bilder:
            t_ut.append(n * dt)
            V_ut.append(V.copy())
            I_ut.append(I_snitt.copy())

    lagre(0, V, I_null)
    for n in range(nsteg):
        t_midt = (n + 0.5) * dt
        t_ny = (n + 1) * dt
        V[1:-1] = av * V[1:-1] - bv * (I[1:] - I[:-1])
        V[0] = _endenode(V[0], -I[0], venstre, t_ny, t_midt, c_ende, g_ende)
        V[-1] = _endenode(V[-1], I[-1], hoyre, t_ny, t_midt, c_ende, g_ende)
        I_gml = I
        I = ai * I - bi * np.diff(V)
        lagre(n + 1, V, 0.5 * (I + I_gml))

    # Dissipert energi i linja, W(t) = integralet av tapseffekten (trapesregel)
    W_tap = np.concatenate(([0.0], np.cumsum(0.5 * dt * (P_tap[1:] + P_tap[:-1]))))

    return SimpleNamespace(
        x=x, xh=xh, dx=dx, dt=dt, t=dt * np.arange(nsteg + 1),
        t_bilder=np.array(t_ut), V=np.array(V_ut), I=np.array(I_ut),
        x_maal=x[idx_maal], V_maal=V_maal, energi=E, tap=W_tap,
    )
