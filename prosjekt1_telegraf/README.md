# Prosjekt 1: Telegraflikningen

Rapport og programkode for prosjektoppgaven om telegraflikningen (tema 3:
«Telegrafligningen. Dispersjon.»).

- **Rapport:** [`rapport/rapport.pdf`](rapport/rapport.pdf) (kilde: `rapport/rapport.tex`)
- **Kode:** [`kode/`](kode/)

## Innhold

| Fil | Innhold |
|---|---|
| `kode/linje.py` | Linjeparametre R, L, G, C; γ, Z_c, α, β, v_p, v_g; tilfellene A–D og telefonkabelen |
| `kode/analytisk.py` | Heaviside-puls, Fourier-rekke (separasjon av variable), Talbot-inversjon av Laplace-løsningen, t₅₀, gitterdiagram |
| `kode/fdtd.py` | FDTD-løser (leapfrog på forskjøvet gitter) med kilde, last og energiregnskap |
| `kode/stil.py` | Felles figurstil (desimalkomma, fargepalett) |
| `kode/lag_figurer.py` | Lager alle figurer og tabeller i rapporten |
| `kode/test_telegraf.py` | Automatiske tester (konvergens, Fourier-rekke, Laplace, energi, refleksjon) |

## Kjøre koden

```bash
pip install -r requirements.txt
cd kode
python lag_figurer.py     # lager rapport/figurer/*.pdf og rapport/tabeller/*.tex (ca. 1 min)
pytest                    # kjører testene
```

Figurene bruker LaTeX-tekst hvis `latex` og `cm-super` er installert, ellers
Matplotlibs innebygde matematikkskrift.

## Bygge rapporten

```bash
cd rapport
latexmk -pdf rapport.tex
```

Krever en TeX-distribusjon med `circuitikz`, `siunitx` og norsk `babel`
(TeX Live eller MiKTeX). Rapporten kan også lastes opp til Overleaf sammen med
mappene `figurer/` og `tabeller/` og `../kode/fdtd.py`/`../kode/analytisk.py`
(som vises i vedlegget).

## Før innlevering

- Fyll inn emne, navn, gruppenummer, klasse og dato øverst i `rapport.tex`
  (makroene `\Emne`, `\Forfattere`, `\Gruppe`, `\Klasse`, `\DatoUtfort`).
- Kontroller telefonkabelens parameterverdier mot kilden [10] (Reeve 1995).
