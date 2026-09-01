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
import re
import shutil
import sys
import unicodedata
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

.carte-bloc{margin-top:22px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px}
.carte-bloc .dsp{font-size:11px;color:var(--soft);display:block;margin-bottom:10px}
svg.carte{display:block;width:100%;height:auto;max-height:440px}
svg.carte .c-voisine{fill:var(--sunken);stroke:var(--line);stroke-width:.8}
svg.carte .c-ici{fill:var(--accent);stroke:var(--accent);stroke-width:1.2;
  fill-opacity:.85}
.carte-legende{font-size:11px;color:var(--soft);margin-top:8px}

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

  fetch(BASE + '/assets/recherche.json')
    .then(function(r){ return r.json(); })
    .then(function(d){ index = d; })
    .catch(function(){ champ.placeholder = 'Recherche indisponible'; });

  function sansAccents(t){
    return t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  // Deux groupes seulement : ce qui commence par la saisie, puis le reste.
  // À l'intérieur de chaque groupe, l'ordre alphabétique s'applique.
  function score(t, v){
    var nom = sansAccents(t.nom);
    if(nom.indexOf(v) === 0) return 0;
    if(nom.indexOf(v) !== -1) return 1;
    if(t.code.indexOf(v) === 0) return 1;
    var cp = (t.codes_postaux || []).some(function(c){ return c.indexOf(v) === 0; });
    if(cp) return 1;
    return -1;
  }

  var LIMITE = 20;

  champ.addEventListener('input', function(){
    var v = sansAccents(champ.value.trim());
    if(!v || !index){ boite.className = 'hits'; return; }

    var trouves = [];
    for(var i = 0; i < index.length; i++){
      var s = score(index[i], v);
      if(s >= 0) trouves.push({ t: index[i], s: s });
    }

    // Les noms commençant par la saisie remontent en tête ;
    // à l'intérieur de chaque groupe, ordre alphabétique.
    trouves.sort(function(a, b){
      if(a.s !== b.s) return a.s - b.s;
      return a.t.nom.localeCompare(b.t.nom, 'fr');
    });

    if(!trouves.length){
      boite.innerHTML = '<p class="vide">Aucun territoire ne correspond</p>';
      boite.className = 'hits on';
      return;
    }

    var total = trouves.length;
    var html = trouves.slice(0, LIMITE).map(function(x){
      var t = x.t;
      var repere = (t.codes_postaux || [])[0] || t.code;
      return '<a href="' + BASE + '/' + t.url + '">'
        + '<span class="tag">' + t.niveau + '</span>'
        + '<span class="nm">' + t.nom + '</span>'
        + '<span class="cd">' + repere + '</span></a>';
    }).join('');

    if(total > LIMITE){
      html += '<p class="vide">' + total + ' territoires correspondent, '
            + LIMITE + ' affichés. Précisez votre recherche.</p>';
    }
    boite.innerHTML = html;
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

def slug(nom):
    """Transforme un nom de commune en fragment d'adresse lisible.

    « Saint-Antoine-l'Abbaye » devient « saint-antoine-l-abbaye ».
    Le code INSEE reste en tête de l'adresse : c'est lui qui identifie
    le territoire de façon stable, le nom n'est là que pour la lisibilité.
    """
    texte = unicodedata.normalize("NFD", nom.lower())
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = re.sub(r"[^a-z0-9]+", "-", texte)
    return texte.strip("-")


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


def lien(r, base, adresses):
    cible = adresses.get((r["niveau"], r["code"]))
    if not cible:
        return f'<span class="chip">{escape(r["nom"])}</span>'
    return f'<a class="chip" href="{base}/{cible}">{escape(r["nom"])}</a>' 


def bloc_rattachements(d, base, adresses):
    t, r = d["territoire"], d["rattachements"]
    lignes = []

    dessus = [x for x in r.get("au_dessus", [])
              if x["niveau"] in ("canton", "epci", "departement")]
    connus = [x for x in dessus if x["niveau"] != "departement"]
    if connus:
        lignes.append(f"""      <div class="rung"><span class="lvl">Au-dessus</span>
        <div class="chips">{''.join(lien(x, base, adresses) for x in connus)}</div></div>""")

    lignes.append(f"""      <div class="rung ici"><span class="lvl">Ici</span>
        <div class="chips"><span class="chip now">{escape(t['nom'])}</span></div></div>""")

    dessous = r.get("en_dessous", [])
    if dessous:
        lignes.append(f"""      <div class="rung"><span class="lvl">Communes</span>
        <div class="chips">{''.join(lien(x, base, adresses) for x in dessous)}</div></div>""")

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


def bloc_carte(t):
    """Insère la carte du territoire si elle a été produite par 05_cartes.py.

    Le SVG est intégré dans la page plutôt qu'appelé en image : il hérite
    ainsi des couleurs du thème, et reste donc pilotable depuis style.css.
    """
    fichier = RACINE / "assets" / "cartes" / t["niveau"] / f"{t['code']}.svg"
    if not fichier.exists():
        return ""
    svg = fichier.read_text(encoding="utf-8")
    legende = ("Situation dans le territoire" if t["niveau"] == "commune"
               else "Communes membres")
    return f"""    <section class="carte-bloc">
      <span class="dsp">Carte</span>
      {svg}
      <p class="carte-legende">{legende}</p>
    </section>"""


def page(d, base, canonique, adresses, accueil=False):
    t = d["territoire"]
    niveau = LIBELLE.get(t["niveau"], t["niveau"])

    mesures = {k: v for k, v in d["mesures"].items() if v["valeur"] is not None}
    resume = ", ".join(f"{m['nom'].lower()} {nombre(m['valeur'])} {m['unite']}"
                       for m in list(mesures.values())[:3])
    description = (f"{t['nom']} ({niveau}) : {resume}. "
                   f"Données publiques INSEE et IGN.")

    codes = t.get("codes_postaux") or []
    if codes:
        libelle_cp = "Codes postaux" if len(codes) > 1 else "Code postal"
        sous_titre = (f"<strong>{libelle_cp} {escape(', '.join(codes))}</strong>"
                      f" · Code INSEE {escape(t['code'])}")
    elif t.get("nombre_communes"):
        sous_titre = (f"{t['nombre_communes']} communes"
                      f" · Code {escape(t['code'])}")
    else:
        sous_titre = f"Code INSEE {escape(t['code'])}"

    if codes:
        description = (f"{t['nom']} ({codes[0]}) : {resume}. "
                       f"Données publiques INSEE et IGN.")

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
    <input id="q" type="text" placeholder="Commune, code postal…"
           autocomplete="off" aria-label="Rechercher un territoire">
    <div class="hits" id="hits"></div>
  </div>
</div></div>

<div class="terr"><div class="wrap">
  <div class="kind dsp">{escape(niveau)}</div>
  <h1>{escape(t['nom'])}</h1>
  <div class="sub">{sous_titre}</div>
</div></div>

<main><div class="wrap">
    <div class="cards">
{chr(10).join(carte(k, v) for k, v in mesures.items())}
    </div>
{bloc_carte(t)}
{bloc_rattachements(d, base, adresses)}
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
    # Les cartes sont produites par 05_cartes.py : on les préserve.
    cartes = ASSETS / "cartes"
    garde = None
    if cartes.exists():
        garde = RACINE / ".cartes-tmp"
        if garde.exists():
            shutil.rmtree(garde)
        shutil.move(str(cartes), str(garde))

    for sous in ("commune", "canton", "epci", "assets"):
        if (RACINE / sous).exists():
            shutil.rmtree(RACINE / sous)

    ASSETS.mkdir(parents=True, exist_ok=True)
    if garde:
        shutil.move(str(garde), str(cartes))
    (ASSETS / "style.css").write_text(CSS.strip(), encoding="utf-8")
    (ASSETS / "recherche.js").write_text(JS.strip(), encoding="utf-8")

    # ── premier passage : table des adresses ─────────────────────
    # Le nom porté par un territoire dans ses propres données fait foi.
    # Les rattachements peuvent l'abréger, d'où cette table de référence.
    fiches, adresses = {}, {}
    for t in index["territoires"]:
        fichier = PUBLIE / t["niveau"] / f"{t['code']}.json"
        if not fichier.exists():
            print(f"  [ignoré] {fichier} absent")
            continue
        d = json.loads(fichier.read_text(encoding="utf-8"))
        cle = (t["niveau"], t["code"])
        fiches[cle] = d
        adresses[cle] = f"{t['niveau']}/{t['code']}-{slug(d['territoire']['nom'])}/"

    if not fiches:
        print("\n[BLOCAGE] Aucune fiche exploitable.")
        sys.exit(1)

    # ── second passage : écriture des pages ──────────────────────
    liens_site, recherche, redirections = [], [], []

    for (niveau, code), d in fiches.items():
        t = d["territoire"]
        chemin = adresses[(niveau, code)]
        dossier = RACINE / chemin
        dossier.mkdir(parents=True, exist_ok=True)
        url = f"{SITE}/{chemin}"

        dossier.joinpath("index.html").write_text(
            page(d, "..\u002f..", url, adresses), encoding="utf-8")
        liens_site.append(url)

        recherche.append({
            "nom": t["nom"],
            "niveau": niveau,
            "code": code,
            "codes_postaux": t.get("codes_postaux", []),
            "population": (d["mesures"].get("POP-01") or {}).get("valeur"),
            "url": chemin,
        })

        # ancienne adresse sans le nom : redirigée, jamais cassée
        redirections.append((f"/{niveau}/{code}", f"/{chemin}"))

        if (niveau, code) == ACCUEIL:
            (RACINE / "index.html").write_text(
                page(d, ".", SITE + "/", adresses, accueil=True), encoding="utf-8")
            liens_site.append(SITE + "/")

    # ── contrôle d'exhaustivité de la recherche ──────────────────
    # Toute commune du référentiel doit être atteignable depuis la barre
    # de recherche. Une commune absente serait invisible sur le site.
    referentiel = RACINE / "data" / "referentiel-communes.json"
    if referentiel.exists():
        attendues = {c["code"]: c["nom"] for c in json.loads(
            referentiel.read_text(encoding="utf-8"))["communes"]}
        presentes = {r["code"] for r in recherche if r["niveau"] == "commune"}
        manquantes = sorted(set(attendues) - presentes)
        if manquantes:
            print(f"\n[BLOCAGE] {len(manquantes)} commune(s) absente(s) "
                  f"de la recherche :")
            for code in manquantes[:20]:
                print(f"  · {code}  {attendues[code]}")
            print("\n  Ces communes seraient introuvables sur le site.")
            sys.exit(1)
        print(f"  Recherche : {len(presentes)}/{len(attendues)} communes "
              f"joignables.")

    sans_cp = [r["nom"] for r in recherche
               if r["niveau"] == "commune" and not r["codes_postaux"]]
    if sans_cp:
        print(f"  [attention] {len(sans_cp)} commune(s) sans code postal : "
              f"{', '.join(sans_cp[:5])}")

    doublons_url = [r["url"] for r in recherche]
    if len(set(doublons_url)) != len(doublons_url):
        print("\n[BLOCAGE] Deux territoires produisent la même adresse.")
        sys.exit(1)

    # index de recherche : propre à l'affichage, distinct du contrat v1
    recherche.sort(key=lambda x: (x["niveau"] != "commune", x["nom"]))
    (ASSETS / "recherche.json").write_text(
        json.dumps(recherche, ensure_ascii=False), encoding="utf-8")

    # redirections des anciennes adresses
    lignes = "\n".join(f"Redirect 301 {a} {b}" for a, b in sorted(redirections))
    (RACINE / ".htaccess").write_text(
        "# Fichier généré par 04_generation.py — ne pas modifier à la main.\n"
        "# Redirige les anciennes adresses sans nom vers les nouvelles.\n"
        f"{lignes}\n", encoding="utf-8")

    # plan du site
    aujourdhui = date.today().isoformat()
    entrees = "\n".join(
        f"  <url><loc>{u}</loc><lastmod>{aujourdhui}</lastmod></url>"
        for u in sorted(set(liens_site)))
    (RACINE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entrees}\n</urlset>\n", encoding="utf-8")

    (RACINE / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n",
        encoding="utf-8")

    produites = len(fiches)
    print(f"\n  Pages produites : {produites}")
    print(f"  Accueil         : index.html ({ACCUEIL[0]} {ACCUEIL[1]})")
    print(f"  Thème           : assets/style.css")
    print(f"  Redirections    : .htaccess ({len(redirections)} anciennes adresses)")
    print(f"  Plan du site    : sitemap.xml ({len(set(liens_site))} adresses)")
    print(f"\n  Exemples d'adresses :")
    for u in list(sorted(set(liens_site)))[:3]:
        print(f"    {u}")
    print()


if __name__ == "__main__":
    main()
