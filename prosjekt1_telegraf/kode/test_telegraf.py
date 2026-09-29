"""Automatiske tester for løseren og de analytiske løsningene.  Kjør:  pytest"""

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")

from analytisk import (diffusjon_erfc, fourierrekke, gauss, heaviside_puls,  # noqa: E402
                       lastspenning_tapsfri, sprangrespons, t50)
from fdtd import AAPEN, KORTSLUTNING, Terminering, simuler  # noqa: E402
from linje import (TILFELLE_A, TILFELLE_B, TILFELLE_C, TILFELLE_D, Linje,  # noqa: E402
                   modellinje)


def _rampe(t, tr=10e-9):
    """Glatt sprang (hevet cosinus) med stigetid tr."""
    t = np.asarray(t, dtype=float)
    return np.where(t <= 0, 0.0, np.where(t >= tr, 1.0, 0.5 * (1 - np.cos(np.pi * t / tr))))


def _heaviside_feil(dx):
    f = gauss(60.0, 2.0)
    lin = TILFELLE_C
    res = simuler(lin, 200.0, dx, 0.3e-6,
                  V0=lambda x: heaviside_puls(lin, f, x, 0.0)[0],
                  I0=lambda x: heaviside_puls(lin, f, x, 0.0)[1],
                  venstre=Terminering(lin.Z0), hoyre=Terminering(lin.Z0),
                  cfl=0.5, t_bilder=[0.3e-6])
    Vex, _ = heaviside_puls(lin, f, res.x, res.t_bilder[0])
    return np.max(np.abs(res.V[0] - Vex))


def test_andre_ordens_konvergens():
    orden = np.log2(_heaviside_feil(0.2) / _heaviside_feil(0.1))
    assert orden == pytest.approx(2.0, abs=0.1)


def test_fourierrekke_mot_fdtd():
    f = gauss(30.0, 2.0)
    res = simuler(TILFELLE_B, 100.0, 0.05, 0.4e-6, V0=f, venstre=KORTSLUTNING,
                  hoyre=KORTSLUTNING, cfl=0.5, t_bilder=[0.4e-6])
    Vf = fourierrekke(TILFELLE_B, 100.0, f, res.x, res.t_bilder[0])
    assert np.max(np.abs(res.V[0] - Vf)) < 5e-4


def test_energibalanse():
    f = gauss(50.0, 2.0)
    res = simuler(TILFELLE_B, 100.0, 0.1, 0.4e-6, V0=f, venstre=AAPEN, hoyre=AAPEN)
    avvik = np.max(np.abs(res.energi + res.tap - res.energi[0])) / res.energi[0]
    assert avvik < 1e-3


def test_talbot_mot_erfc():
    lin = Linje("RC", R=20.0, L=1e-12, G=0.0, C=1e-10)
    t = np.array([1e-6, 5e-6, 2e-5])
    assert np.allclose(sprangrespons(lin, 50.0, t), diffusjon_erfc(lin, 50.0, t), atol=1e-7)


def test_sprangrespons_fdtd_mot_laplace():
    res = simuler(TILFELLE_D, 200.0, 0.1, 1e-6, venstre=Terminering(0.0, lambda t: _rampe(t, 1e-9)),
                  hoyre=AAPEN,
                  x_maal=[10.0])
    n = len(res.t) - 1
    assert res.V_maal[n, 0] == pytest.approx(sprangrespons(TILFELLE_D, 10.0, res.t[n])[0], abs=2e-3)


def test_gruppehastighet_mot_numerisk_derivert():
    w = np.logspace(5, 8, 400)
    for lin in [TILFELLE_B, TILFELLE_D]:
        vg_num = 1.0 / np.gradient(lin.beta(w), w)
        assert np.allclose(lin.gruppehastighet(w)[5:-5], vg_num[5:-5], rtol=1e-3)


def test_heaviside_er_dispersjonsfri():
    w = np.logspace(2, 9, 50)
    assert np.allclose(TILFELLE_C.fasehastighet(w), TILFELLE_C.v)
    assert np.allclose(TILFELLE_C.alpha(w), np.sqrt(TILFELLE_C.R * TILFELLE_C.G))


def test_refleksjon_mot_gitterdiagram():
    res = simuler(TILFELLE_A, 100.0, 0.1, 2e-6, venstre=Terminering(12.5, _rampe), hoyre=AAPEN,
                  x_maal=[100.0])
    teori = lastspenning_tapsfri(res.t, 100.0, TILFELLE_A.v, 50.0, 12.5, np.inf, _rampe)
    assert np.median(np.abs(res.V_maal[:, 0] - teori)) < 1e-3


def test_t50_bolgegrense_og_skalering():
    lin = modellinje("", R=2.0)
    x = 10.0  # xi = 0.4 < 2 ln 2, altså ren bølgeforsinkelse
    assert t50(lin, x) == pytest.approx(x / lin.v)
    # Samme xi og tau for to ulike R (universell kurve)
    l1, l2 = modellinje("", R=2.0), modellinje("", R=20.0)
    tau1 = t50(l1, 100.0) * l1.R / l1.L
    tau2 = t50(l2, 10.0) * l2.R / l2.L
    assert tau1 == pytest.approx(tau2, rel=1e-6)
