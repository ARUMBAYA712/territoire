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