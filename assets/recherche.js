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
    return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
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

// ── Fond de plan ───────────────────────────────────────────────────
// Les tuiles ne sont téléchargées qu'au moment où le fond est demandé.
// Sans JavaScript, la carte reste affichée en schéma : le contenu ne
// dépend donc jamais de ce script.
(function(){
  var cadre = document.querySelector('.carte-cadre');
  var bloc = document.querySelector('.carte-bloc');
  var choix = document.querySelectorAll('.carte-fonds input[name="fond"]');
  if(!cadre || !choix.length) return;

  function charger(couche){
    var images = couche.querySelectorAll('img[data-src]');
    for(var i = 0; i < images.length; i++){
      images[i].src = images[i].getAttribute('data-src');
      images[i].removeAttribute('data-src');
    }
  }

  function appliquer(id){
    if(id === 'schema'){
      cadre.removeAttribute('data-fond');
      if(bloc) bloc.removeAttribute('data-fond');
      return;
    }
    var couche = cadre.querySelector('.carte-fond[data-fond="' + id + '"]');
    if(couche) charger(couche);
    cadre.setAttribute('data-fond', id);
    if(bloc) bloc.setAttribute('data-fond', id);
  }

  for(var k = 0; k < choix.length; k++){
    choix[k].addEventListener('change', function(){ appliquer(this.value); });
  }
})();