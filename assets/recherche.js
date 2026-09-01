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

  // Score de pertinence : plus il est bas, plus le résultat remonte.
  // Un nom qui commence par la saisie prime sur un nom qui la contient,
  // qui prime sur une correspondance de code postal.
  function score(t, v){
    var nom = sansAccents(t.nom);
    if(nom.indexOf(v) === 0) return 0;
    if(nom.indexOf(v) !== -1) return 1;
    if(t.code.indexOf(v) === 0) return 2;
    var cp = (t.codes_postaux || []).some(function(c){ return c.indexOf(v) === 0; });
    if(cp) return 3;
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

    // à pertinence égale, la commune la plus peuplée d'abord :
    // sur un code postal partagé, c'est presque toujours celle que l'on cherche
    trouves.sort(function(a, b){
      if(a.s !== b.s) return a.s - b.s;
      var pa = a.t.population || 0, pb = b.t.population || 0;
      if(pa !== pb) return pb - pa;
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