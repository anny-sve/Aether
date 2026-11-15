window.AetherRender = (function () {
  function escapar(texto) {
    return String(texto)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function extraerMatematicas(texto) {
    var bloques = [];
    texto = texto.replace(/\$\$([\s\S]+?)\$\$/g, function (coincidencia, expresion) {
      bloques.push({ expresion: expresion, display: true });
      return "@@M" + (bloques.length - 1) + "@@";
    });
    texto = texto.replace(/\$([^$\n]+?)\$/g, function (coincidencia, expresion) {
      bloques.push({ expresion: expresion, display: false });
      return "@@M" + (bloques.length - 1) + "@@";
    });
    return { texto: texto, bloques: bloques };
  }

  function renderizarMatematica(bloque) {
    try {
      return window.katex.renderToString(bloque.expresion, {
        displayMode: bloque.display,
        throwOnError: false,
        strict: "ignore"
      });
    } catch (error) {
      return "<code>" + escapar(bloque.expresion) + "</code>";
    }
  }

  function montar(elemento, markdown) {
    var partes = extraerMatematicas(String(markdown || ""));
    var texto = partes.texto.replace(/</g, "&lt;");
    var html;
    if (window.marked && typeof window.marked.parse === "function") {
      html = window.marked.parse(texto, { gfm: true, breaks: true });
    } else {
      html = "<p>" + escapar(texto).replace(/\n\n/g, "</p><p>").replace(/\n/g, "<br>") + "</p>";
    }
    html = html.replace(/@@M(\d+)@@/g, function (coincidencia, indice) {
      var bloque = partes.bloques[parseInt(indice, 10)];
      return bloque ? renderizarMatematica(bloque) : "";
    });
    elemento.innerHTML = html;
  }

  return { montar: montar, escapar: escapar };
})();
