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

import hashlib
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
TITRE_SITE = "Sud Grésiv'"
SOUS_TITRE = "Données publiques du territoire"

RACINE = Path(".")
PUBLIE = RACINE / "data" / "publie" / "v1"
ASSETS = RACINE / "assets"
ACCUEIL = ("canton", "3823")

# Empreinte du thème et du script : ajoutée aux adresses des ressources
# pour que les navigateurs rechargent d'eux-mêmes après chaque génération.
EMPREINTE = ""

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
  --attention:#B4610E; --attention-soft:#FBF0E4;
  --alerte:#A32C1B; --alerte-soft:#FBEAE7;
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
.top .wrap{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;
  gap:18px;min-height:60px;padding:8px 20px}
.logo{font-family:var(--font-display);font-weight:600;font-size:19px;
  white-space:nowrap;justify-self:start}
.find-groupe{display:flex;align-items:center;gap:10px;justify-self:center}
.find-label{font-family:var(--font-display);font-weight:600;
  text-transform:uppercase;letter-spacing:.09em;font-size:11px;
  color:var(--soft);white-space:nowrap;cursor:pointer}
.find{position:relative;width:340px;max-width:44vw}
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

.terr{background:var(--surface);border-bottom:1px solid var(--line);
  position:sticky;top:var(--h-top,61px);z-index:19}
.terr .wrap{padding:24px 20px;transition:padding .16s ease}
.terr h1{transition:font-size .16s ease}
.terr.compact .wrap{padding-top:5px;padding-bottom:6px}
.terr.compact h1{font-size:20px}
.terr.compact .kind{font-size:10px}
.terr.compact .sub{margin-top:1px;font-size:12px}
.terr .kind{font-size:11px;color:var(--soft)}
.terr h1{font-family:var(--font-display);font-size:34px;line-height:1.05;
  text-transform:none;letter-spacing:.01em;font-weight:600}
.terr .sub{font-size:13px;color:var(--soft);margin-top:4px}

.nav{background:var(--paper);border-bottom:1px solid var(--line)}
.nav .wrap{display:flex;gap:2px;padding:0 20px;overflow-x:auto;
  scrollbar-width:thin}
.nav-item{display:inline-block;white-space:nowrap;padding:11px 15px;
  font-size:14px;color:var(--soft);border-bottom:2px solid transparent;
  transition:color .12s,border-color .12s,background .12s}
a.nav-item:hover{color:var(--accent);background:var(--accent-soft)}
.nav-item.actif{color:var(--accent);border-bottom-color:var(--accent);
  font-weight:600}
.nav-item.vide{color:var(--dim);cursor:default}

main .wrap{padding:26px 20px 48px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.card{background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px;display:flex;flex-direction:column;gap:8px}
.card .id{font-family:var(--font-data);font-size:10px;color:var(--dim)}
.card h2{font-size:15px;font-weight:600;line-height:1.25}
.card .v{font-family:var(--font-data);font-size:28px;color:var(--accent);line-height:1}
.card .u{font-size:12px;color:var(--soft)}
.card footer{margin-top:auto;border-top:1px solid var(--line);padding-top:8px;
  display:flex;gap:6px;flex-wrap:wrap;font-size:10px;color:var(--soft)}
.card.pleine{grid-column:1/-1}
.card.pleine .v{font-size:34px}
.card.ton-attention{background:var(--attention-soft);border-color:var(--attention)}
.card.ton-attention .v{color:var(--attention)}
.card.ton-alerte{background:var(--alerte-soft);border-color:var(--alerte);
  border-width:2px}
.card.ton-alerte .v{color:var(--alerte)}
.card-repere{font-size:11px;color:var(--ink);font-family:var(--font-data);
  background:var(--sunken);border:1px solid var(--line);border-radius:var(--radius);
  padding:3px 8px;align-self:flex-start;line-height:1.4}
.card.ton-attention .card-repere{background:var(--surface);border-color:var(--attention)}
.card.ton-alerte .card-repere{background:var(--surface);border-color:var(--alerte)}
.card-expl{font-size:12px;color:var(--soft);line-height:1.45}
.card-lien{display:inline-block;font-size:12px;color:var(--link);
  border-bottom:1px solid currentColor;align-self:flex-start}
.card-lien:hover{color:var(--accent)}
.card.ton-alerte .card-lien{color:var(--alerte)}
.card.ton-attention .card-lien{color:var(--attention)}
.bloc{scroll-margin-top:calc(var(--h-top,61px) + 84px)}
.pill{border:1px solid var(--line);border-radius:var(--radius);padding:1px 6px}

.carte-bloc{margin-top:22px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:16px}
.carte-bloc .dsp{font-family:var(--font-body);font-size:15px;font-weight:600;
  text-transform:none;letter-spacing:0;color:var(--ink);display:block;
  margin-bottom:12px}
svg.carte{display:block;width:100%;height:auto;max-height:440px}
svg.carte a{cursor:pointer}
svg.carte .c-voisine{fill:var(--sunken);stroke:var(--line);stroke-width:.8;
  transition:fill .12s,stroke .12s}
svg.carte a:hover .c-voisine,svg.carte a:focus .c-voisine{
  fill:var(--accent-soft);stroke:var(--accent);stroke-width:1.4}
svg.carte a:focus{outline:none}
svg.carte .c-ici{fill:var(--accent);stroke:var(--accent);stroke-width:1.2;
  fill-opacity:.85}
.carte-legende{font-size:14px;color:var(--soft);margin-top:10px;line-height:1.45}
.carte-bulle{position:fixed;z-index:50;display:none;pointer-events:none;
  background:var(--ink);color:var(--surface);font-size:12px;line-height:1.3;
  padding:4px 9px;border-radius:var(--radius);white-space:nowrap;
  box-shadow:0 4px 14px rgba(0,0,0,.22)}
.carte-bulle.on{display:block}
.carte-bulle b{display:block;font-size:13px}
.carte-bulle i{font-style:normal;color:var(--accent-soft)}

.carte-grille{display:grid;grid-template-columns:172px 1fr;gap:16px;align-items:start}
.carte-menu{display:flex;flex-direction:column;gap:2px;border:1px solid var(--line);
  border-radius:var(--radius);padding:6px;background:var(--sunken)}
.carte-menu .opt{display:flex;align-items:center;gap:8px;padding:7px 9px;
  font-size:13px;border-radius:var(--radius);cursor:pointer}
.carte-menu .opt:hover{background:var(--surface)}
.carte-menu .opt input{accent-color:var(--accent);margin:0}
.carte-menu .opt:has(input:checked){background:var(--accent);color:var(--surface);
  font-weight:600}

.carte-echelle{display:flex;align-items:center;gap:3px;margin-top:10px;
  font-size:11px;color:var(--soft)}
.carte-echelle .pal{width:26px;height:11px;border:1px solid var(--line);
  background:var(--accent)}
.carte-echelle .unite{margin-left:auto;font-family:var(--font-data);
  font-size:18px;font-weight:500;color:var(--ink)}
.carte-echelle .bas{margin-right:4px}
.carte-echelle .haut{margin-left:4px}

svg.carte .n0,.carte-echelle .n0{fill-opacity:.14;opacity:.14}
svg.carte .n1,.carte-echelle .n1{fill-opacity:.32;opacity:.32}
svg.carte .n2,.carte-echelle .n2{fill-opacity:.52;opacity:.52}
svg.carte .n3,.carte-echelle .n3{fill-opacity:.74;opacity:.74}
svg.carte .n4,.carte-echelle .n4{fill-opacity:1;opacity:1}
svg.carte path.n0,svg.carte path.n1,svg.carte path.n2,
svg.carte path.n3,svg.carte path.n4{fill:var(--accent);stroke:var(--surface);
  stroke-width:.8}
svg.carte path.nd{fill:var(--sunken);stroke:var(--line)}
svg.carte a:hover path[class*="n"],svg.carte a:focus path[class*="n"]{
  stroke:var(--ink);stroke-width:2;fill-opacity:1}

.bloc{margin-top:22px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:18px}
.bloc > .dsp{font-family:var(--font-body);font-size:15px;font-weight:600;
  text-transform:none;letter-spacing:0;color:var(--ink);display:block;
  margin-bottom:12px}
.bl-grille{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.bl-item{border:1px solid var(--line);border-radius:var(--radius);
  padding:13px 14px;background:var(--sunken)}
.bl-item header{display:flex;align-items:flex-start;justify-content:space-between;
  gap:10px;margin-bottom:9px}
.bl-item h3{font-size:14px;font-weight:600;line-height:1.3}
.bl-etat{font-size:10px;font-weight:600;padding:3px 8px;border-radius:var(--radius);
  white-space:nowrap;text-transform:uppercase;letter-spacing:.05em}
.bl-etat.ok{background:var(--accent);color:var(--surface)}
.bl-etat.alerte{background:var(--alerte);color:var(--surface)}
.bl-etat.attention{background:var(--attention);color:var(--surface)}
.bl-etat.neutre{background:var(--line);color:var(--soft)}
.bl-ligne{display:flex;justify-content:space-between;gap:12px;font-size:13px;
  padding:3px 0;border-top:1px solid var(--line)}
.bl-ligne:first-of-type{border-top:none}
.bl-cle{color:var(--soft)}
.bl-val{font-family:var(--font-data);text-align:right}
.bl-texte{font-size:12px;color:var(--soft);margin-top:9px;line-height:1.45}
.bl-lien{display:inline-block;margin-top:9px;font-size:12px;color:var(--link);
  border-bottom:1px solid currentColor}
.bl-lien:hover{color:var(--accent)}
.bl-note{font-size:12px;color:var(--soft);margin-top:12px;
  border-left:2px solid var(--mark);padding:6px 11px;background:var(--sunken);
  border-radius:var(--radius)}

.ratt{margin-top:30px;background:var(--surface);border:1px solid var(--line);
  border-radius:var(--radius);padding:20px}
.ratt > .dsp{font-family:var(--font-body);font-size:15px;font-weight:600;
  text-transform:none;letter-spacing:0;color:var(--ink);display:block;
  margin-bottom:14px}
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
a.chip{transition:background .12s,color .12s,border-color .12s}
a.chip:hover,a.chip:focus-visible{background:var(--accent);color:var(--surface);
  border-color:var(--accent);font-weight:600}
.chip.now{background:var(--accent-soft);border-color:var(--accent);
  color:var(--accent);font-weight:600}
.note{margin-top:14px;border-left:2px solid var(--mark);padding:8px 12px;
  font-size:12px;color:var(--soft);background:var(--sunken);border-radius:var(--radius)}

footer.site{border-top:1px solid var(--line);background:var(--surface);
  padding:18px 0;font-size:11px;color:var(--soft)}
footer.site a{color:var(--link)}

@media(max-width:820px){.cards{grid-template-columns:repeat(2,1fr)}}
@media(max-width:700px){
  .carte-grille{grid-template-columns:1fr}
  .carte-menu{flex-direction:row;flex-wrap:wrap}
  .carte-menu .opt{font-size:12px;padding:6px 8px}
}
@media(max-width:640px){
  .nav .wrap{padding:0 12px}
  .nav-item{padding:10px 11px;font-size:13px}
  .top .wrap{grid-template-columns:1fr;gap:8px;justify-items:stretch}
  .logo{justify-self:center}
  .find-groupe{justify-self:stretch}
  .find{width:auto;max-width:none;flex:1}
  .top-fin{display:none}
}
@media(max-width:560px){
  .bl-grille{grid-template-columns:1fr}
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

// ── Bandeau du territoire : collant, et compressé au défilement ────
// La hauteur de la barre du haut est mesurée plutôt que devinée :
// elle varie selon la largeur d'écran et la longueur du nom du site.
(function(){
  var haut = document.querySelector('.top');
  var terr = document.querySelector('.terr');
  if(!haut || !terr) return;

  function caler(){
    document.documentElement.style.setProperty(
      '--h-top', haut.offsetHeight + 'px');
  }

  var enCours = false;
  function defiler(){
    if(enCours) return;
    enCours = true;
    window.requestAnimationFrame(function(){
      terr.classList.toggle('compact', window.scrollY > 40);
      enCours = false;
    });
  }

  caler();
  window.addEventListener('resize', caler, {passive:true});
  window.addEventListener('scroll', defiler, {passive:true});
  defiler();
})();

// ── Infobulle des cartes ────────────────────────────────────────────
// L'infobulle native du SVG n'est pas fiable quand la forme est placée
// dans un lien. On l'affiche donc nous-mêmes. Le <title> reste présent
// dans le document : il sert de secours et aux lecteurs d'écran.
(function(){
  var carte = document.querySelector('svg.carte');
  if(!carte) return;

  var bulle = document.createElement('div');
  bulle.className = 'carte-bulle';
  bulle.setAttribute('aria-hidden', 'true');
  document.body.appendChild(bulle);

  var couches = null, active = null;
  try{
    var bloc = document.getElementById('carte-donnees');
    if(bloc){
      couches = JSON.parse(bloc.textContent);
      active = couches.defaut;
    }
  }catch(err){ couches = null; }

  function formeDe(cible){
    return cible.closest ? cible.closest('path') : null;
  }

  function contenu(forme){
    var nom = forme.getAttribute('data-nom') || '';
    if(!couches || !active) return '<b>' + nom + '</b>';
    var code = forme.getAttribute('data-code');
    var c = couches.couches[active];
    var valeur = c.libelles[code] || 'non disponible';
    return '<b>' + nom + '</b><i>' + c.nom + ' : ' + valeur + '</i>';
  }

  // Change la donnée représentée : recolore les formes et met à jour l'unité.
  function appliquer(ident){
    if(!couches || !couches.couches[ident]) return;
    active = ident;
    var c = couches.couches[ident];
    var formes = carte.querySelectorAll('path[data-code]');
    for(var i = 0; i < formes.length; i++){
      var f = formes[i];
      var code = f.getAttribute('data-code');
      // classList fonctionne sur les éléments SVG ;
      // className y est en lecture seule, contrairement au HTML.
      f.classList.remove('n0', 'n1', 'n2', 'n3', 'n4', 'nd');
      f.classList.add(c.classes[code] || 'nd');
    }
    var u = document.getElementById('carte-unite');
    if(u) u.textContent = c.unite;
  }

  var choix = document.querySelectorAll('.carte-menu input[name="donnee"]');
  for(var k = 0; k < choix.length; k++){
    choix[k].addEventListener('change', function(){ appliquer(this.value); });
  }

  carte.addEventListener('mousemove', function(e){
    var forme = formeDe(e.target);
    if(!forme){ bulle.className = 'carte-bulle'; return; }
    bulle.innerHTML = contenu(forme);
    bulle.className = 'carte-bulle on';
    var x = e.clientX + 14, y = e.clientY + 16;
    var large = bulle.offsetWidth;
    if(x + large > window.innerWidth - 8) x = e.clientX - large - 14;
    bulle.style.left = x + 'px';
    bulle.style.top = y + 'px';
  });

  carte.addEventListener('mouseleave', function(){
    bulle.className = 'carte-bulle';
  });

  // au clavier, le nom s'affiche aussi lors du parcours par tabulation
  carte.addEventListener('focusin', function(e){
    var lien = e.target.closest('a');
    if(!lien) return;
    var forme = lien.querySelector('path');
    if(!forme) return;
    var r = lien.getBoundingClientRect();
    bulle.innerHTML = contenu(forme);
    bulle.className = 'carte-bulle on';
    bulle.style.left = (r.left + window.scrollX) + 'px';
    bulle.style.top = (r.bottom + window.scrollY + 6) + 'px';
  });
  carte.addEventListener('focusout', function(){
    bulle.className = 'carte-bulle';
  });

  // en dernier : une erreur ici ne doit plus empêcher le survol de fonctionner
  if(active) appliquer(active);
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
    if isinstance(v, str):
        return v
    if not isinstance(v, (int, float)):
        return "—"
    if isinstance(v, float) and not v.is_integer():
        entier, _, decimales = f"{v:,.1f}".partition(".")
        return entier.replace(",", "\u202f") + "," + decimales
    return f"{int(v):,}".replace(",", "\u202f")


def carte(ident, m, ancres=frozenset()):
    """Rend une carte d'indicateur.

    Trois habillages facultatifs, pilotés par la donnée elle-même :
      · mise_en_avant → la carte occupe toute la largeur, en tête de grille
      · ton           → « attention » ou « alerte » colore la carte
      · ancre         → un lien mène au bloc détaillé plus bas dans la page

    Le lien n'est posé que si le bloc visé existe réellement sur cette
    page. Un collecteur peut annoncer une ancre alors que le bloc n'a
    pas été produit — commune sans réseau connu, sans prélèvement — et
    le lien mènerait alors dans le vide.
    """
    classes = ["card"]
    if m.get("mise_en_avant"):
        classes.append("pleine")
    if m.get("ton") in ("attention", "alerte"):
        classes.append("ton-" + m["ton"])

    lien = (f'<a class="card-lien" href="#{escape(m["ancre"])}">Voir le détail</a>'
            if m.get("ancre") in ancres else "")
    repere = (f'<p class="card-repere">{escape(m["repere"])}</p>'
              if m.get("repere") else "")
    explication = (f'<p class="card-expl">{escape(m["explication"])}</p>'
                   if m.get("explication") else "")
    unite = (f' <span class="u">{escape(m["unite"])}</span>'
             if m.get("unite") else "")

    return f"""      <article class="{' '.join(classes)}">
        <span class="id">{escape(ident)}</span>
        <h2>{escape(m['nom'])}</h2>
        <div><span class="v">{nombre(m['valeur'])}</span>{unite}</div>
        {repere}
        {explication}
        {lien}
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


MOTIF_FORME = re.compile(
    r'<path class="(c-voisine|c-ici)" data-code="([^"]+)" '
    r'd="([^"]*)"><title>([^<]*)</title></path>')

# Ordre de présentation des données proposées sur la carte.
# Les identifiants absents des fiches sont simplement ignorés :
# ajouter les élections plus tard ne demandera rien d'autre ici.
ORDRE_CARTE = ["POP-01", "GEO-13", "POP-10"]

# ══════════════════════════════════════════════════════════════════
# RUBRIQUES
#
# Chaque rubrique regroupe les indicateurs dont l'identifiant commence
# par l'un de ses préfixes. « prevue » signale une rubrique affichée
# dans la navigation même si elle est encore vide : le visiteur voit
# ce qui existe et ce qui vient, plutôt qu'un menu qui s'allonge sans
# prévenir. Ajouter une rubrique se fait ici, et nulle part ailleurs.
# ══════════════════════════════════════════════════════════════════

RUBRIQUES = [
    {"id": "",              "nom": "Aperçu",        "prefixes": None, "prevue": True},
    {"id": "population",    "nom": "Population",    "prefixes": ["POP"], "prevue": True},
    {"id": "geographie",    "nom": "Géographie",    "prefixes": ["GEO"], "prevue": True},
    {"id": "urbanisme",     "nom": "Urbanisme",     "prefixes": ["URB"], "prevue": True},
    {"id": "environnement", "nom": "Environnement", "prefixes": ["ENV", "EAU", "MET"], "prevue": True},
    {"id": "transports",    "nom": "Transports",    "prefixes": ["TRA"], "prevue": True},
    {"id": "elections",     "nom": "Élections",     "prefixes": ["POL"], "prevue": True},
]


def indicateurs_de(rubrique, mesures):
    """Sélectionne les mesures relevant d'une rubrique."""
    if rubrique["prefixes"] is None:
        return dict(mesures)
    return {k: v for k, v in mesures.items()
            if any(k.startswith(pref) for pref in rubrique["prefixes"])}


def rubriques_actives(mesures):
    """Rubriques disposant d'au moins une valeur pour ce territoire."""
    actives = set()
    for r in RUBRIQUES:
        contenu = indicateurs_de(r, mesures)
        if any(m.get("valeur") is not None for m in contenu.values()):
            actives.add(r["id"])
    return actives


def nav_rubriques(base, chemin_territoire, actives, courante):
    liens = []
    for r in RUBRIQUES:
        libelle = escape(r["nom"])
        if r["id"] == courante:
            liens.append(f'<span class="nav-item actif" '
                         f'aria-current="page">{libelle}</span>')
        elif r["id"] in actives:
            suffixe = f"{r['id']}/" if r["id"] else ""
            liens.append(f'<a class="nav-item" '
                         f'href="{base}/{chemin_territoire}{suffixe}">{libelle}</a>')
        elif r["prevue"]:
            liens.append(f'<span class="nav-item vide" '
                         f'title="Données à venir">{libelle}</span>')
    return ('<nav class="nav" aria-label="Rubriques"><div class="wrap">'
            + "".join(liens) + "</div></nav>")

NB_CLASSES = 5


def quantiles(valeurs, nb=NB_CLASSES):
    """Découpe en classes d'effectifs comparables.

    Les distributions territoriales sont très déséquilibrées : une commune
    de 7 700 habitants voisine avec des villages de 200. Un découpage à
    intervalles réguliers produirait une carte presque uniforme, avec une
    seule commune détachée. Les quantiles répartissent les nuances.
    """
    tri = sorted(set(valeurs))
    if len(tri) < 2:
        return []
    nb = min(nb, len(tri))
    return [tri[round(i * (len(tri) - 1) / nb)] for i in range(1, nb)]


def classe(valeur, seuils):
    if valeur is None:
        return "nd"
    if not seuils:                      # valeurs toutes identiques
        return f"n{NB_CLASSES // 2}"
    for i, seuil in enumerate(seuils):
        if valeur < seuil:
            return f"n{i}"
    return f"n{len(seuils)}"


def format_valeur(v, unite):
    """Espace normale avant un mot, espace fine avant un symbole.

    « 7 700 habitants » se lit mieux avec une vraie espace ;
    « 12,4 km² » ou « 76,9 hab./km² » avec une espace fine.
    Une unité entièrement alphabétique est traitée comme un mot.
    """
    if v is None:
        return "non disponible"
    separateur = "\u00a0" if unite.isalpha() else "\u202f"
    return f"{nombre(v)}{separateur}{unite}"


def donnees_carte(membres, fiches, rubrique):
    """Prépare les données de coloration pour les communes membres."""
    dispo = {}
    for m in membres:
        f = fiches.get(("commune", m["code"]))
        if not f:
            continue
        for ident, mesure in indicateurs_de(rubrique, f["mesures"]).items():
            if isinstance(mesure.get("valeur"), (int, float)):
                dispo.setdefault(ident, {"nom": mesure["nom"],
                                         "unite": mesure["unite"],
                                         "valeurs": {}})
                dispo[ident]["valeurs"][m["code"]] = mesure["valeur"]

    idents = ([i for i in ORDRE_CARTE if i in dispo]
              + sorted(i for i in dispo if i not in ORDRE_CARTE))
    if not idents:
        return None

    couches = {}
    for ident in idents:
        d = dispo[ident]
        seuils = quantiles(list(d["valeurs"].values()))
        couches[ident] = {
            "nom": d["nom"],
            "unite": d["unite"],
            "seuils": seuils,
            "classes": {code: classe(v, seuils)
                        for code, v in d["valeurs"].items()},
            "libelles": {code: format_valeur(v, d["unite"])
                         for code, v in d["valeurs"].items()},
            "bornes": [nombre(s) for s in seuils],
        }
    return {"defaut": idents[0], "ordre": idents, "couches": couches}


def menu_carte(carte):
    """Sélecteur vertical des données affichables."""
    boutons = []
    for i, ident in enumerate(carte["ordre"]):
        c = carte["couches"][ident]
        coche = " checked" if ident == carte["defaut"] else ""
        boutons.append(
            f'<label class="opt"><input type="radio" name="donnee" '
            f'value="{ident}"{coche}> <span>{escape(c["nom"])}</span></label>')
    return ('<div class="carte-menu" role="group" '
            'aria-label="Donnée représentée">'
            + "".join(boutons) + '</div>')


def legende_carte(carte):
    paliers = "".join(f'<span class="pal n{i}"></span>'
                      for i in range(NB_CLASSES))
    return (f'<div class="carte-echelle"><span class="bas">moins</span>'
            f'{paliers}<span class="haut">plus</span>'
            f'<span class="unite" id="carte-unite"></span></div>')


def bloc_carte(t, base, adresses, fiches, membres, rubrique):
    """Insère la carte du territoire si elle a été produite par 05_cartes.py.

    Le SVG est intégré dans la page plutôt qu'appelé en image : il hérite
    ainsi des couleurs du thème, ses formes deviennent des liens, et elles
    peuvent être colorées selon la donnée choisie.
    """
    fichier = RACINE / "assets" / "cartes" / t["niveau"] / f"{t['code']}.svg"
    if not fichier.exists():
        return ""

    carte = donnees_carte(membres, fiches, rubrique) if membres else None
    defaut = carte["couches"][carte["defaut"]]["classes"] if carte else {}

    def relier(m):
        cl, code, trace, nom = m.groups()
        teinte = f" {defaut.get(code, 'nd')}" if carte else ""
        # Le nom est porté par un attribut plutôt que par une balise <title> :
        # celle-ci déclencherait l'infobulle native du navigateur, qui se
        # superposerait à la nôtre. L'accessibilité passe par aria-label.
        forme = (f'<path class="{cl}{teinte}" data-code="{code}" '
                 f'data-nom="{nom}" d="{trace}"/>')
        cible = adresses.get(("commune", code))
        if not cible or code == t["code"]:
            return f'<g role="img" aria-label="{nom}">{forme}</g>'
        return f'<a href="{base}/{cible}" aria-label="{nom}">{forme}</a>' 

    svg = MOTIF_FORME.sub(relier, fichier.read_text(encoding="utf-8"))

    if not carte:
        legende = ("Situation dans le territoire — cliquez une commune "
                   "pour ouvrir sa fiche")
        return f"""    <section class="carte-bloc">
      <span class="dsp">Carte</span>
      {svg}
      <p class="carte-legende">{legende}</p>
    </section>"""

    charge = json.dumps({
        "defaut": carte["defaut"],
        "couches": {i: {"nom": c["nom"], "unite": c["unite"],
                        "classes": c["classes"], "libelles": c["libelles"]}
                    for i, c in carte["couches"].items()},
    }, ensure_ascii=False)

    return f"""    <section class="carte-bloc">
      <span class="dsp">Carte</span>
      <div class="carte-grille">
        {menu_carte(carte)}
        <div class="carte-zone">
          {svg}
          {legende_carte(carte)}
        </div>
      </div>
      <p class="carte-legende">Survolez une commune pour lire sa valeur,
         cliquez pour ouvrir sa fiche. Les nuances sont réparties en cinq
         groupes d'effectifs comparables.</p>
      <script type="application/json" id="carte-donnees">{charge}</script>
    </section>"""


def bloc_liste(d, rubrique):
    """Rend les blocs détaillés attachés à une rubrique.

    Certaines données ne se réduisent pas à un chiffre : les réseaux
    d'eau qui desservent une commune forment une liste d'objets, chacun
    avec ses propres caractéristiques. Ils ont donc leur propre gabarit,
    distinct des cartes d'indicateurs.
    """
    blocs = [b for b in (d.get("blocs") or [])
             if b.get("rubrique") == rubrique["id"]]
    if not blocs:
        return ""

    sorties = []
    for b in blocs:
        entrees = []
        for item in b["items"]:
            lignes = "".join(
                f'<div class="bl-ligne"><span class="bl-cle">{escape(k)}</span>'
                f'<span class="bl-val">{escape(str(v))}</span></div>'
                for k, v in item.get("details", {}).items())
            etat = item.get("etat")
            pastille = (f'<span class="bl-etat {escape(etat[1])}">'
                        f'{escape(etat[0])}</span>') if etat else ""
            texte = (f'<p class="bl-texte">{escape(item["texte"])}</p>'
                     if item.get("texte") else "")
            lien = item.get("lien")
            ancre = (f'<a class="bl-lien" href="{escape(lien["url"])}" '
                     f'target="_blank" rel="noopener">{escape(lien["libelle"])}</a>'
                     if lien else "")
            entrees.append(
                f'<article class="bl-item"><header><h3>{escape(item["titre"])}</h3>'
                f'{pastille}</header>{lignes}{texte}{ancre}</article>')
        note = (f'<p class="bl-note">{escape(b["note"])}</p>'
                if b.get("note") else "")
        ancre = f' id="{escape(b["id"])}"' if b.get("id") else ""
        sorties.append(
            f'    <section class="bloc"{ancre}>'
            f'<span class="dsp">{escape(b["titre"])}</span>'
            f'<div class="bl-grille">{"".join(entrees)}</div>{note}</section>')
    return "\n".join(sorties)


def page(d, base, canonique, adresses, fiches, rubrique,
         chemin_territoire, actives, accueil=False):
    t = d["territoire"]
    niveau = LIBELLE.get(t["niveau"], t["niveau"])

    toutes = indicateurs_de(rubrique, d["mesures"])
    mesures = {k: v for k, v in toutes.items() if v["valeur"] is not None}
    # les indicateurs mis en avant passent en tête de grille
    mesures = dict(sorted(mesures.items(),
                          key=lambda kv: (not kv[1].get("mise_en_avant"), kv[0])))

    # ancres réellement disponibles sur cette page
    ancres = {b["id"] for b in (d.get("blocs") or [])
              if b.get("rubrique") == rubrique["id"] and b.get("id")}
    resume = ", ".join(f"{m['nom'].lower()} {nombre(m['valeur'])} {m['unite']}"
                       for m in list(mesures.values())[:3])
    description = (f"{t['nom']} ({niveau}) : {resume}. "
                   f"Données publiques INSEE et IGN.")

    # Le code d'un EPCI est un numéro SIREN, pas un code INSEE :
    # les nommer pareil serait une erreur de fond.
    ref = ("Code SIREN Intercommunalité" if t["niveau"] == "epci"
           else f"Code INSEE {niveau}")
    codes = t.get("codes_postaux") or []
    if codes:
        libelle_cp = "Codes postaux" if len(codes) > 1 else "Code postal"
        sous_titre = (f"<strong>{libelle_cp} {escape(', '.join(codes))}</strong>"
                      f" · {ref} {escape(t['code'])}")
    elif t.get("nombre_communes"):
        sous_titre = (f"{t['nombre_communes']} communes"
                      f" · {ref} {escape(t['code'])}")
    else:
        sous_titre = f"{ref} {escape(t['code'])}"

    if codes:
        description = (f"{t['nom']} ({codes[0]}) : {resume}. "
                       f"Données publiques INSEE et IGN.")

    suffixe_titre = rubrique["nom"] if rubrique["id"] else niveau

    maj = date.fromisoformat(d["genere_le"]).strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(t['nom'])} — {escape(suffixe_titre)} | {escape(TITRE_SITE)}</title>
<meta name="description" content="{escape(description)}">
<link rel="canonical" href="{canonique}">
<meta property="og:title" content="{escape(t['nom'])} — {escape(TITRE_SITE)}">
<meta property="og:description" content="{escape(description)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonique}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}/assets/style.css?v={EMPREINTE}">
</head>
<body>

<div class="top"><div class="wrap">
  <a class="logo" href="{base}/">{escape(TITRE_SITE)}</a>
  <div class="find-groupe">
    <label class="find-label" for="q">Recherche</label>
    <div class="find">
      <input id="q" type="text" placeholder="Commune, code postal…"
             autocomplete="off">
      <div class="hits" id="hits"></div>
    </div>
  </div>
  <div class="top-fin"></div>
</div></div>

<div class="terr"><div class="wrap">
  <div class="kind dsp">{escape(niveau)}</div>
  <h1>{escape(t['nom'])}</h1>
  <div class="sub">{sous_titre}</div>
</div></div>

{nav_rubriques(base, chemin_territoire, actives, rubrique["id"])}

<main><div class="wrap">
    <div class="cards">
{chr(10).join(carte(k, v, ancres) for k, v in mesures.items())}
    </div>
{bloc_liste(d, rubrique)}
{bloc_rattachements(d, base, adresses)}
{bloc_carte(t, base, adresses, fiches, d["rattachements"].get("en_dessous"), rubrique)}
</div></main>

<footer class="site"><div class="wrap">
  {escape(SOUS_TITRE)} — Licence Ouverte 2.0 · Contrat v{d['version_contrat']}
  · Mise à jour du {maj}
  · <a href="{base}/data/publie/v1/{t['niveau']}/{t['code']}.json">données brutes</a>
</div></footer>

<script>var BASE="{base}";</script>
<script src="{base}/assets/recherche.js?v={EMPREINTE}"></script>
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

    global EMPREINTE
    EMPREINTE = hashlib.sha1(
        (CSS + JS).encode("utf-8")).hexdigest()[:8]
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
        actives = rubriques_actives(d["mesures"])

        for r in RUBRIQUES:
            if r["id"] and r["id"] not in actives:
                continue
            suffixe = f"{r['id']}/" if r["id"] else ""
            dossier = RACINE / chemin / r["id"] if r["id"] else RACINE / chemin
            dossier.mkdir(parents=True, exist_ok=True)
            url = f"{SITE}/{chemin}{suffixe}"
            profondeur = "../" * (2 + (1 if r["id"] else 0))

            dossier.joinpath("index.html").write_text(
                page(d, profondeur.rstrip("/"), url, adresses, fiches,
                     r, chemin, actives),
                encoding="utf-8")
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
                page(d, ".", SITE + "/", adresses, fiches,
                     RUBRIQUES[0], chemin, actives, accueil=True),
                encoding="utf-8")
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

    produites = len(set(liens_site))
    par_rubrique = {}
    for r in RUBRIQUES:
        n = sum(1 for d in fiches.values()
                if r["id"] in rubriques_actives(d["mesures"]) or not r["id"])
        if n:
            par_rubrique[r["nom"]] = n
    print(f"\n  Territoires     : {len(fiches)}")
    print(f"  Pages produites : {produites}")
    print(f"  Rubriques       : "
          + ", ".join(f"{k} ({v})" for k, v in par_rubrique.items()))
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
