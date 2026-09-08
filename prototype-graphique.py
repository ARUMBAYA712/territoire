"""Prototype de graphique SVG, pour mesurer le poids réel.

Aucune bibliothèque : la même contrainte que les cartes du site.
"""
import math, random, gzip

L, H = 720, 240
MG, MD, MH, MB = 44, 12, 14, 26


def courbe(valeurs, lacunes=()):
    """valeurs : liste de (etiquette, valeur ou None)."""
    reels = [v for _, v in valeurs if v is not None]
    bas, haut = min(reels), max(reels)
    marge = (haut - bas) * 0.08 or 1
    bas, haut = bas - marge, haut + marge
    n = len(valeurs)

    def x(i): return MG + (L - MG - MD) * i / max(n - 1, 1)
    def y(v): return MH + (H - MH - MB) * (haut - v) / (haut - bas)

    # Les segments s'interrompent sur une lacune : un trou est une
    # information, on ne l'interpole pas.
    segments, courant = [], []
    for i, (_, v) in enumerate(valeurs):
        if v is None:
            if len(courant) > 1: segments.append(courant)
            courant = []
        else:
            courant.append(f"{x(i):.1f},{y(v):.1f}")
    if len(courant) > 1: segments.append(courant)

    traces = "".join(f'<polyline points="{" ".join(s)}"/>' for s in segments)

    # Graduations : cinq lignes horizontales, une étiquette sur cinq ans.
    grille = "".join(
        f'<line x1="{MG}" y1="{MH+(H-MH-MB)*k/4:.1f}" x2="{L-MD}" '
        f'y2="{MH+(H-MH-MB)*k/4:.1f}"/>' for k in range(5))
    etiq = "".join(
        f'<text x="{x(i):.0f}" y="{H-8}">{valeurs[i][0]}</text>'
        for i in range(0, n, max(n // 6, 1)))
    return (f'<svg viewBox="0 0 {L} {H}" class="chr" role="img">'
            f'<g class="chr-grille">{grille}</g>'
            f'<g class="chr-trace">{traces}</g>'
            f'<g class="chr-x">{etiq}</g></svg>')


def serie(n, debut=1969, mensuel=True, trous=0.03):
    random.seed(1)
    out = []
    for i in range(n):
        an = debut + i // (12 if mensuel else 1)
        v = None if random.random() < trous else round(
            100 + 40 * math.sin(i / 6) + random.gauss(0, 12) + i * 0.03, 1)
        out.append((str(an), v))
    return out


cas = [
    ("Débit mensuel, Isère à Saint-Gervais, 1969-2026", serie(687)),
    ("Température mensuelle, Chatte, 1988-2026", serie(452, 1988)),
    ("Jours ≥ 30 °C par an, Chatte, 1988-2026", serie(38, 1988, False)),
    ("Nappe, moyenne mensuelle, 2005-2026", serie(252, 2005)),
]
print(f"{'graphique':<52}{'points':>7}{'SVG':>9}{'gzip':>8}")
for titre, s in cas:
    svg = courbe(s)
    b = svg.encode("utf-8")
    print(f"{titre:<52}{len(s):>7}{len(b):>8} o{len(gzip.compress(b)):>7} o")
