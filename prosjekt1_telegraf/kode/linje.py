"""Overføringslinje beskrevet med primærparametre R, L, G og C (per meter).

Alle størrelser er i SI-enheter:
    R  [ohm/m]  seriemotstand
    L  [H/m]    serieinduktans
    G  [S/m]    shuntkonduktans (lekkasje)
    C  [F/m]    shuntkapasitans

Modulen samler de avledede størrelsene som brukes i rapporten: bølgefart,
karakteristisk impedans, dempingsrater, forplantningskonstant og fase- og
gruppehastighet.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Linje:
    navn: str
    R: float
    L: float
    G: float
    C: float

    # --- Størrelser i tidsdomenet -----------------------------------------
    @property
    def v(self):
        """Bølgefart for den tapsfrie linja, v = 1/sqrt(LC) [m/s]."""
        return 1.0 / np.sqrt(self.L * self.C)

    @property
    def Z0(self):
        """Karakteristisk impedans for den tapsfrie linja, sqrt(L/C) [ohm]."""
        return np.sqrt(self.L / self.C)

    @property
    def a(self):
        """Dempingsrate a = (R/L + G/C)/2 [1/s]."""
        return 0.5 * (self.R / self.L + self.G / self.C)

    @property
    def b(self):
        """b = (R/L - G/C)/2 [1/s]. b = 0 er Heaviside-betingelsen."""
        return 0.5 * (self.R / self.L - self.G / self.C)

    @property
    def D(self):
        """Diffusjonskoeffisient 1/(RC) i diffusjonsgrensen [m^2/s]."""
        return np.inf if self.R == 0 else 1.0 / (self.R * self.C)

    def rho(self, lengde):
        """Dimensjonsløst serietap R*l/Z0."""
        return self.R * lengde / self.Z0

    def sigma(self, lengde):
        """Dimensjonsløst shunttap G*l*Z0."""
        return self.G * lengde * self.Z0

    def er_forvrengningsfri(self, rtol=1e-12):
        return np.isclose(self.R / self.L, self.G / self.C, rtol=rtol, atol=0.0)

    # --- Størrelser i frekvensdomenet (fasor e^{j w t}) ---------------------
    def gamma(self, omega):
        """Forplantningskonstant gamma = alpha + j beta [1/m]."""
        omega = np.asarray(omega, dtype=float)
        return np.sqrt((self.R + 1j * omega * self.L) * (self.G + 1j * omega * self.C))

    def Zc(self, omega):
        """Karakteristisk impedans (kompleks) Zc = sqrt((R+jwL)/(G+jwC))."""
        omega = np.asarray(omega, dtype=float)
        return np.sqrt((self.R + 1j * omega * self.L) / (self.G + 1j * omega * self.C))

    def alpha(self, omega):
        """Dempningskonstant [Np/m]."""
        return self.gamma(omega).real

    def beta(self, omega):
        """Fasekonstant [rad/m]."""
        return self.gamma(omega).imag

    def fasehastighet(self, omega):
        omega = np.asarray(omega, dtype=float)
        return omega / self.beta(omega)

    def gruppehastighet(self, omega):
        """v_g = d omega / d beta, regnet ut analytisk fra d gamma / d omega."""
        omega = np.asarray(omega, dtype=float)
        Z = self.R + 1j * omega * self.L
        Y = self.G + 1j * omega * self.C
        dgamma = 1j * (self.L * Y + self.C * Z) / (2.0 * np.sqrt(Z * Y))
        return 1.0 / dgamma.imag

    # --- Laplace-domenet ----------------------------------------------------
    def gamma_s(self, s):
        """gamma(s) = sqrt((R+sL)(G+sC)) med grenkutt kun mellom -R/L og -G/C.

        Produktet av to prinsipale kvadratrøtter gir en funksjon som er analytisk
        utenfor linjestykket mellom greinpunktene, noe Talbot-inversjonen trenger.
        """
        s = np.asarray(s, dtype=complex)
        return np.sqrt(self.L * self.C) * np.sqrt(s + self.R / self.L) * np.sqrt(s + self.G / self.C)


# ---------------------------------------------------------------------------
# Modellinje brukt i simuleringene: Z0 = 50 ohm og v = 2e8 m/s (typisk koaks).
Z0_MODELL = 50.0
V_MODELL = 2.0e8
L_MODELL = Z0_MODELL / V_MODELL          # 0.25 uH/m
C_MODELL = 1.0 / (Z0_MODELL * V_MODELL)  # 100 pF/m

R_B = 1.0  # ohm/m


def modellinje(navn, R=0.0, G=0.0):
    return Linje(navn, R=R, L=L_MODELL, G=G, C=C_MODELL)


TILFELLE_A = modellinje("A: tapsfri")
TILFELLE_B = modellinje("B: serietap", R=R_B)
TILFELLE_C = modellinje("C: Heaviside", R=R_B, G=R_B * C_MODELL / L_MODELL)
TILFELLE_D = modellinje("D: sterk demping", R=20.0)

TILFELLER = [TILFELLE_A, TILFELLE_B, TILFELLE_C, TILFELLE_D]


# ---------------------------------------------------------------------------
# Telefonkabel (24 AWG, PIC-isolert) ved 1 kHz, avrundede typiske verdier
# (Reeve 1995). Pupin-/H88-pupinisering: 88 mH hver 1829 m (6000 fot).
TELEFON = Linje("Telefonkabel", R=172e-3, L=0.612e-6, G=0.072e-9, C=51.57e-12)

L_SPOLE = 88e-3
AVSTAND_SPOLE = 1829.0
TELEFON_PUPIN = Linje(
    "Pupinisert (H88)",
    R=TELEFON.R,
    L=TELEFON.L + L_SPOLE / AVSTAND_SPOLE,
    G=TELEFON.G,
    C=TELEFON.C,
)
TELEFON_HEAVISIDE = Linje(
    "Heaviside-betingelse", R=TELEFON.R, L=TELEFON.R * TELEFON.C / TELEFON.G, G=TELEFON.G, C=TELEFON.C
)
