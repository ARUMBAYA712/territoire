(function(){
  var champ = document.getElementById('q');
  var boite = document.getElementById('hits');
  if(!champ) return;
  var index = null;

  fetch(BASE + '/assets/recherche.json')
    .then(function(r){ return r.json(); })
    .then(function(d){ index = d; })
    .catch(function(){ champ.placeholder = 'Recherche indisponible'; });

  function correspond(t, v){
    if(t.nom.toLowerCase().indexOf(v) !== -1) return true;
    if(t.code.indexOf(v) === 0) return true;
    return (t.codes_postaux || []).some(function(cp){
      return cp.indexOf(v) === 0;
    });
  }

  champ.addEventListener('input', function(){
    var v = champ.value.trim().toLowerCase();
    if(!v || !index){ boite.className = 'hits'; return; }
    var hits = index.filter(function(t){ return correspond(t, v); }).slice(0, 8);
    boite.innerHTML = hits.length
      ? hits.map(function(t){
          var cp = (t.codes_postaux || [])[0] || t.code;
          return '<a href="' + BASE + '/' + t.url + '">'
            + '<span class="tag">' + t.niveau + '</span>'
            + '<span class="nm">' + t.nom + '</span>'
            + '<span class="cd">' + cp + '</span></a>';
        }).join('')
      : '<p class="vide">Aucun territoire ne correspond</p>';
    boite.className = 'hits on';
  });

  document.addEventListener('click', function(e){
    if(!e.target.closest('.find')) boite.className = 'hits';
  });
})();