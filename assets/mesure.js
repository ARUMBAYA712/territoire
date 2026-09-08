// Mesure d'audience — chargée seulement après acceptation.
//
// Rien de Google n'est demandé tant que le visiteur n'a pas répondu.
// Son choix est conservé localement pour ne pas le lui redemander ; ce
// stockage-là est dispensé de consentement puisqu'il ne sert qu'à
// respecter sa décision.
(function () {
  var CLE = "sg-mesure";
  var ID = "G-ER3H1G7XSP";

  function memoire(action, valeur) {
    try {
      if (action === "lire") { return localStorage.getItem(CLE); }
      localStorage.setItem(CLE, valeur);
    } catch (e) { return null; }   // navigation privée, stockage refusé
  }

  function charger() {
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + ID;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    gtag("js", new Date());
    // Mesure d'audience seule : aucun signal publicitaire.
    gtag("config", ID, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
  }

  function repondre(choix) {
    memoire("ecrire", choix);
    var b = document.getElementById("mesure-bandeau");
    if (b) { b.hidden = true; }
    if (choix === "oui") { charger(); }
  }

  var choix = memoire("lire");
  if (choix === "oui") { charger(); }

  document.addEventListener("DOMContentLoaded", function () {
    var bandeau = document.getElementById("mesure-bandeau");
    if (!bandeau) { return; }
    if (!choix) { bandeau.hidden = false; }
    var oui = document.getElementById("mesure-oui");
    var non = document.getElementById("mesure-non");
    if (oui) { oui.addEventListener("click", function () { repondre("oui"); }); }
    if (non) { non.addEventListener("click", function () { repondre("non"); }); }

    // Bouton présent sur les mentions légales : permet de revenir sur
    // son choix, dans un sens comme dans l'autre.
    var revenir = document.getElementById("mesure-revenir");
    if (revenir) {
      revenir.hidden = false;
      revenir.addEventListener("click", function () {
        try { localStorage.removeItem(CLE); } catch (e) {}
        location.reload();
      });
    }
  });
})();