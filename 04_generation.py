"""
04_generation.py — Génération des pages HTML statiques
=======================================================

Transforme les fichiers publiés en v1 en pages HTML complètes, avec les
chiffres écrits dans le code source. Chaque territoire obtient sa propre
adresse, indexable par les moteurs de recherche :

    /                        page d'accueil (canton)
    /commune/38416/          Saint-Marcellin
    /canton/3823/            Le Sud Grésivaudan
    /epci/200070431/         Saint-Marcellin Vercors Isère
    /sitemap.xml             plan du site
    /assets/style.css        thème, fichier unique et remplaçable

Les fichiers JSON restent publiés : ils constituent le service de données
appelable par des sites tiers. Les pages HTML en sont une lecture.

Utilisation :
    python 04_generation.py
"""

import json
import shutil
import sys
from datetime import date
from html import escape
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════

SITE = "https://territoire.sudgresiv.com"
TITRE_SITE = "Sud Grésivaudan"
SOUS_TITRE = "Données publiques du territoire"

RACINE = Path(".")
PUBLIE = RACINE / "data" / "publie" / "v1"
ASSETS = RACINE / "assets"
ACCUEIL = ("canton", "3823")

LIBELLE = {"commune": "Commune", "canton": "Canton",
           "epci": "Intercommunalité", "departement": "Département"}


# ══════════════════════════════════════════════════════════════════
# THÈME — fichier unique. Le remplacer rhabille tout le site.
# ══════════════════════════════════════════════════════════════════

CSS = """
:root{
  --paper:#EDF0EA; --surface:#FFF; --sunken:#F5F7F3;
  --ink:#16211C; --soft:#5D6E64; --dim:#9AA79F; --line:#D5DCD3;
  --accent:#2C6B4C; --accent-soft:#EAF3EE; --link:#2A6F97; --mark:#9C8340;
  --font-display:"Barlow Condensed",sans-serif;
  --font-body:"IBM Plex Sans",system-ui,sans-serif;
  --font-data:"IBM Plex Mono",monospace;
  --radius:3px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--paper);color:var(--ink);font-family:var(--font-body);
  font-size:15px;line-height:1.5}
a{color:inherit;text-decoration:none}
button,input{font:inherit;color:inherit}
button{background:none;border:none;cursor:pointer}
:focus-visible{outline:2px solid var(--link);outline-offset:2px}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px}
.dsp{font-family:var(--font-display);font-weight:600;text-transform:uppercase;
  letter-spacing:.09em}

.top{position:sticky;top:0;z-index:20;background:var(--surface);
  border-bottom:1px solid var(--line)}
.top .wrap{display:flex;align-items:center;gap:18px;min-height:60px;
  flex-wrap:wrap;padding:8px 20px}
.logo{font-family:var(--font-display);font-weight:600;font-size:19px;white-space:nowrap}
.find{position:relative;flex:1;min-width:200px;max-width:400px}
.find input{width:100%;height:36px;padding:0 12px;background:var(--sunken);
  border:1px solid var(--line);border-radius:var(--radius);font-size:14px}
.find input::placeholder{color:var(--dim)}
.find input:focus{border-color:var(--accent);background:var(--surface);outline:none}
.hits{position:absolute;top:40px;left:0;right:0;background:var(--surface);
  border:1px solid var(--line);border-radius:var(--radius);
  box-shadow:0 10px 26px rgba(0,0,0,.13);max-height:300px;overflow:auto;
  display:none;z-index:30}
.hits.on{display:block}
.hits a{display:flex;gap:10px;align-items:center;padding:8px 12px;
  border-bottom:1px solid var(--line)}
.hits a:last-child{border-bottom:none}
.hits a:hover{background:var(--sunken)}
.tag{font-size:10px;padding:2px 6px;border-radius:var(--radius);
  background:var(--accent-soft);color:var(--accent);white-space:nowrap}
.hits .nm{flex:1;font-size:14px}
.hits .cd{font-family:var(--font-data);font-size:11px;color:var(--dim)}
.vide{padding:8px 12px;font-size:13px;color:var(--dim)}

.terr{background:var(--surface);border-bottom:1px solid var(--line)}
.terr .wrap{padding:24px 20px}
.terr .kind{font-size:11px;color:var(--soft)}
.terr h1{font-family:var(--font-display);font-size:34px;line-height:1.05;
  text-transform:none;letter-spacing:.01em;font-weight:600}
.terr .sub{font-size:13px;color:var(--soft);margin-top:4px}

main .wrap{padding:26px 20px 48px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.card{background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px;display:flex;flex-direction:column;gap:8px}
.card .id{font-family:var(--font-data);font-size:10px;color:var(--dim)}
.card h2{font-size:13px;font-weight:600}
.card .v{font-family:var(--font-data);font-size:28px;color:var(--accent);line-height:1}
.card .u{font-size:12px;color:var(--soft)}
.card footer{margin-top:auto;border-top:1px solid var(--line);padding-top:8px;
  display:flex;gap:6px;flex-wrap:wrap;font-size:10px;color:var(--soft)}
.pill{border:1px solid var(--line);border-radius:var(--radius);padding:1px 6px}

.ratt{margin-top:30px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:20px}
.ratt > .dsp{font-size:11px;color:var(--soft);display:block;margin-bottom:14px}
.spine{position:relative;padding-left:30px}
.spine::before{content:"";position:absolute;left:9px;top:8px;bottom:8px;width:1px;
  background:repeating-linear-gradient(to bottom,var(--mark) 0 3px,transparent 3px 7px)}
.rung{position:relative;padding:10px 0;display:flex;flex-wrap:wrap;gap:10px;
  align-items:center}
.rung::before{content:"";position:absolute;left:-21px;top:50%;width:13px;height:1px;
  background:var(--mark)}
.rung::after{content:"";position:absolute;left:-24px;top:calc(50% - 3px);
  width:7px;height:7px;border-radius:50%;background:var(--surface);
  border:1px solid var(--mark)}
.rung.ici::after{background:var(--accent);border-color:var(--accent)}
.rung .lvl{font-family:var(--font-display);text-transform:uppercase;
  letter-spacing:.08em;font-size:11px;color:var(--soft);width:96px;flex-shrink:0}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{border:1px solid var(--line);border-radius:var(--radius);padding:4px 10px;
  font-size:13px;display:inline-block}
a.chip:hover{border-color:var(--link);color:var(--link)}
.chip.now{background:var(--accent-soft);border-color:var(--accent);
  color:var(--accent);font-weight:600}
.note{margin-top:14px;border-left:2px solid var(--mark);padding:8px 12px;
  font-size:12px;color:var(--soft);background:var(--sunken);border-radius:var(--radius)}

footer.site{border-top:1px solid var(--line);background:var(--surface);
  padding:18px 0;font-size:11px;color:var(--soft)}
footer.site a{color:var(--link)}

@media(max-width:820px){.cards{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){
  .cards{grid-template-columns:1fr}
  .terr h1{font-size:27px}
  .rung .lvl{width:100%}
}
"""

# ══════════════════════════════════════════════════════════════════
# RECHERCHE — seul JavaScript de la page. Le contenu existe sans lui.
# ══════════════════════════════════════════════════════════════════

JS = """
(function(){
  var champ = document.getElementById('q');
  var boite = document.getElementById('hits');
  if(!champ) return;
  var index = null;

  fetch(BASE + '/data/publie/v1/index.json')
    .then(function(r){ return r.json(); })
    .then(function(d){ index = d.territoires; })
    .catch(function(){ champ.placeholder = 'Recherche indisponible'; });

  champ.addEventListener('input', function(){
    var v = champ.value.trim().toLowerCase();
    if(!v || !index){ boite.className = 'hits'; return; }
    var hits = index.filter(function(t){
      return t.nom.toLowerCase().indexOf(v) !== -1 || t.code.indexOf(v) === 0;
    }).slice(0, 8);
    boite.innerHTML = hits.length
      ? hits.map(function(t){
          return '<a href="' + BASE + '/' + t.niveau + '/' + t.code + '/">'
            + '<span class="tag">' + t.niveau + '</span>'
            + '<span class="nm">' + t.nom + '</span>'
            + '<span class="cd">' + t.code + '</span></a>';
        }).join('')
      : '<p class="vide">Aucun territoire ne correspond</p>';
    boite.className = 'hits on';
  });

  document.addEventListener('click', function(e){
    if(!e.target.closest('.find')) boite.className = 'hits';
  });
})();
"""


# ══════════════════════════════════════════════════════════════════
# GABARIT
# ══════════════════════════════════════════════════════════════════

def nombre(v):
    """Formatage français : espace fine insécable pour les milliers,
    virgule pour les décimales."""
    if not isinstance(v, (int, float)):
        return "—"
    if isinstance(v, float) and not v.is_integer():
        entier, _, decimales = f"{v:,.1f}".partition(".")
        return entier.replace(",", "\u202f") + "," + decimales
    return f"{int(v):,}".replace(",", "\u202f")


def carte(ident, m):
    return f"""      <article class="card">
        <span class="id">{escape(ident)}</span>
        <h2>{escape(m['nom'])}</h2>
        <div><span class="v">{nombre(m['valeur'])}</span> <span class="u">{escape(m['unite'])}</span></div>
        <footer><span class="pill">{escape(m['source'])}</span><span class="pill">{escape(m['obtention'])}</span></footer>
      </article>"""


def lien(r, base):
    return (f'<a class="chip" href="{base}/{r["niveau"]}/{r["code"]}/">'
            f'{escape(r["nom"])}</a>')


def bloc_rattachements(d, base):
    t, r = d["territoire"], d["rattachements"]
    lignes = []

    dessus = [x for x in r.get("au_dessus", [])
              if x["niveau"] in ("canton", "epci", "departement")]
    connus = [x for x in dessus if x["niveau"] != "departement"]
    if connus:
        lignes.append(f"""      <div class="rung"><span class="lvl">Au-dessus</span>
        <div class="chips">{''.join(lien(x, base) for x in connus)}</div></div>""")

    lignes.append(f"""      <div class="rung ici"><span class="lvl">Ici</span>
        <div class="chips"><span class="chip now">{escape(t['nom'])}</span></div></div>""")

    dessous = r.get("en_dessous", [])
    if dessous:
        lignes.append(f"""      <div class="rung"><span class="lvl">Communes</span>
        <div class="chips">{''.join(lien(x, base) for x in dessous)}</div></div>""")

    note = ""
    if t["niveau"] == "commune":
        note = ("Cette commune relève d'un canton et d'une intercommunalité qui ne "
                "regroupent pas les mêmes communes : les deux périmètres se "
                "recouvrent sans coïncider.")
    elif t["niveau"] == "canton" and t.get("communes_scindees") is False:
        note = (f"Ce canton est composé de {t.get('nombre_communes')} communes "
                "entières. Les valeurs agrégées y sont donc exactes.")

    bloc_note = f'\n      <div class="note">{note}</div>' if note else ""
    return f"""    <section class="ratt"><span class="dsp">Rattachements</span>
      <div class="spine">
{chr(10).join(lignes)}
      </div>{bloc_note}
    </section>"""


def page(d, base, canonique, accueil=False):
    t = d["territoire"]
    niveau = LIBELLE.get(t["niveau"], t["niveau"])

    mesures = {k: v for k, v in d["mesures"].items() if v["valeur"] is not None}
    resume = ", ".join(f"{m['nom'].lower()} {nombre(m['valeur'])} {m['unite']}"
                       for m in list(mesures.values())[:3])
    description = (f"{t['nom']} ({niveau}) : {resume}. "
                   f"Données publiques INSEE et IGN.")

    sous_titre = (f"{t['nombre_communes']} communes · code {t['code']}"
                  if t.get("nombre_communes") else f"Code INSEE {t['code']}")

    maj = date.fromisoformat(d["genere_le"]).strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t['nom'])} — {escape(niveau)} | {escape(TITRE_SITE)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{canonique}">
<meta property="og:title" content="{escape(t['nom'])} — {escape(TITRE_SITE)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonique}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}/assets/style.css">
</head>
<body>

<div class="top"><div class="wrap">
  <a class="logo" href="{base}/">{escape(TITRE_SITE)}</a>
  <div class="find">
    <input id="q" type="text" placeholder="Rechercher une commune…"
           autocomplete="off" aria-label="Rechercher un territoire">
    <div class="hits" id="hits"></div>
  </div>
</div></div>

<div class="terr"><div class="wrap">
  <div class="kind dsp">{escape(niveau)}</div>
  <h1>{escape(t['nom'])}</h1>
  <div class="sub">{escape(sous_titre)}</div>
</div></div>

<main><div class="wrap">
    <div class="cards">
{chr(10).join(carte(k, v) for k, v in mesures.items())}
    </div>
{bloc_rattachements(d, base)}
</div></main>

<footer class="site"><div class="wrap">
  {escape(SOUS_TITRE)} — Licence Ouverte 2.0 · Contrat v{d['version_contrat']}
  · Mise à jour du {maj}
  · <a href="{base}/data/publie/v1/{t['niveau']}/{t['code']}.json">données brutes</a>
</div></footer>

<script>var BASE="{base}";</script>
<script src="{base}/assets/recherche.js"></script>
</body>
</html>
"""


# ══════════════════════════════════════════════════════════════════

def main():
    print("\nGénération des pages statiques")
    print("─" * 46)

    if not (PUBLIE / "index.json").exists():
        print(f"\n[ERREUR] {PUBLIE / 'index.json'} introuvable.")
        print("  Lancez d'abord : python 03_agregation.py")
        sys.exit(1)

    index = json.loads((PUBLIE / "index.json").read_text(encoding="utf-8"))

    # nettoyage des dossiers générés uniquement
    for sous in ("commune", "canton", "epci", "assets"):
        if (RACINE / sous).exists():
            shutil.rmtree(RACINE / sous)

    ASSETS.mkdir(parents=True)
    (ASSETS / "style.css").write_text(CSS.strip(), encoding="utf-8")
    (ASSETS / "recherche.js").write_text(JS.strip(), encoding="utf-8")

    adresses, produites = [], 0

    for t in index["territoires"]:
        fichier = PUBLIE / t["niveau"] / f"{t['code']}.json"
        if not fichier.exists():
            print(f"  [ignoré] {fichier} absent")
            continue
        d = json.loads(fichier.read_text(encoding="utf-8"))

        dossier = RACINE / t["niveau"] / t["code"]
        dossier.mkdir(parents=True, exist_ok=True)
        url = f"{SITE}/{t['niveau']}/{t['code']}/"
        dossier.joinpath("index.html").write_text(
            page(d, "..\u002f..", url), encoding="utf-8")
        adresses.append(url)
        produites += 1

        if (t["niveau"], t["code"]) == ACCUEIL:
            (RACINE / "index.html").write_text(
                page(d, ".", SITE + "/", accueil=True), encoding="utf-8")
            adresses.append(SITE + "/")

    # plan du site
    aujourdhui = date.today().isoformat()
    entrees = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{aujourdhui}</lastmod></url>"
        for u in sorted(set(adresses)))
    (RACINE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entrees}\n</urlset>\n", encoding="utf-8")

    (RACINE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n",
        encoding="utf-8")

    print(f"\n  Pages produites : {produites}")
    print(f"  Accueil         : index.html ({ACCUEIL[0]} {ACCUEIL[1]})")
    print(f"  Thème           : assets/style.css")
    print(f"  Plan du site    : sitemap.xml ({len(set(adresses))} adresses)")
    print(f"\n  Exemples d'adresses :")
    for u in list(sorted(set(adresses)))[:3]:
        print(f"    {u}")
    print()


if __name__ == "__main__":
    main()