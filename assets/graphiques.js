// Survol des graphiques — un confort, jamais une dépendance.
document.querySelectorAll('.chr-fig[data-serie]').forEach(function (fig) {
  var s;
  try { s = JSON.parse(fig.dataset.serie); } catch (e) { return; }
  var svg = fig.querySelector('svg');
  var info = fig.querySelector('.chr-info');
  var cadre = fig.querySelector('.chr-cadre');
  if (!svg || !info || !cadre || !s.x || !s.x.length) return;

  var viseur = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  viseur.setAttribute('class', 'chr-viseur');
  viseur.setAttribute('y1', s.y1);
  viseur.setAttribute('y2', s.y2);
  viseur.style.display = 'none';
  svg.appendChild(viseur);

  function place(e) {
    var r = svg.getBoundingClientRect();
    if (!r.width) return;
    var u = (e.clientX - r.left) / r.width * s.large;
    // Point le plus proche : la zone sensible vaut la moitié de
    // l'écart aux voisins, jamais un pixel à viser.
    var i = 0, ecart = Infinity;
    for (var k = 0; k < s.x.length; k++) {
      var d = Math.abs(s.x[k] - u);
      if (d < ecart) { ecart = d; i = k; }
    }
    viseur.style.display = '';
    viseur.setAttribute('x1', s.x[i]);
    viseur.setAttribute('x2', s.x[i]);
    info.hidden = false;
    info.textContent = s.l[i] + ' · ' + s.v[i];
    info.style.left = (s.x[i] / s.large * 100) + '%';
    info.style.top = (s.y[i] / s.hautTotal * 100) + '%';
  }
  function partir() {
    info.hidden = true;
    viseur.style.display = 'none';
  }
  cadre.addEventListener('pointermove', place);
  cadre.addEventListener('pointerleave', partir);
  cadre.addEventListener('pointercancel', partir);
});