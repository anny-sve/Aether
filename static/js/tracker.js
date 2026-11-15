(function () {
  var COLOR = {
    real: "#f5d77a",
    teoria: "#fffdf5",
    puntos: "#7fd4ff",
    banda: "rgba(255,122,107,0.28)",
    desviacion: "rgba(127,212,255,0.2)"
  };

  var estado = {
    archivo: null,
    resultado: null,
    pestanas: [],
    activa: 0,
    grafica: null,
    urlPrevia: null,
    temporizador: null,
    animacion: null
  };

  function $(selector) {
    return document.querySelector(selector);
  }

  function escapar(texto) {
    return window.AetherRender.escapar(texto);
  }

  function mostrarError(mensaje) {
    var caja = $("#errorTracker");
    caja.textContent = mensaje;
    caja.hidden = !mensaje;
    if (mensaje) caja.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function elegirArchivo(archivo, origen) {
    if (!archivo) return;
    ["#videoCamara", "#videoArchivo"].forEach(function (id) {
      if (id !== origen) $(id).value = "";
    });
    estado.archivo = archivo;
    if (estado.urlPrevia) URL.revokeObjectURL(estado.urlPrevia);
    estado.urlPrevia = URL.createObjectURL(archivo);
    $("#vistaPrevia").src = estado.urlPrevia;
    $("#nombreArchivo").textContent = archivo.name + " · " + (archivo.size / 1048576).toFixed(1) + " MB";
    $("#previaCaja").hidden = false;
    $("#btnProcesar").disabled = false;
    mostrarError("");
  }

  function experimentoActual() {
    var marcado = document.querySelector("input[name='experimento']:checked");
    return marcado ? marcado.value : "caida";
  }

  function actualizarExperimento() {
    $("#grupoLongitud").hidden = experimentoActual() !== "pendulo";
  }

  function iniciarMensajes() {
    var mensajes = [
      "Subiendo el video…",
      "Leyendo fotograma a fotograma…",
      "Rastreando el objeto con OpenCV…",
      "Calculando velocidades y energía…",
      "Dibujando la estela de trayectoria…",
      "Codificando el video final…"
    ];
    var i = 0;
    $("#mensajeProceso").textContent = mensajes[0];
    clearInterval(estado.temporizador);
    estado.temporizador = setInterval(function () {
      i = Math.min(i + 1, mensajes.length - 1);
      $("#mensajeProceso").textContent = mensajes[i];
    }, 3200);
  }

  function detenerMensajes() {
    clearInterval(estado.temporizador);
    $("#estadoProceso").hidden = true;
  }

  async function enviar(evento) {
    evento.preventDefault();
    if (!estado.archivo) {
      mostrarError("Primero graba o sube un video.");
      return;
    }
    mostrarError("");
    $("#resultados").hidden = true;
    $("#auditoria").hidden = true;
    $("#auditoria").innerHTML = "";
    var boton = $("#btnProcesar");
    boton.disabled = true;
    $("#estadoProceso").hidden = false;
    iniciarMensajes();

    var datos = new FormData();
    datos.append("video", estado.archivo);
    datos.append("experimento", experimentoActual());
    datos.append("modo", $("#modo").value);
    datos.append("alto_escena", $("#altoEscena").value);
    datos.append("longitud", $("#longitud").value);
    datos.append("fps", $("#fps").value);

    try {
      var respuesta = await fetch("/api/tracker/procesar", { method: "POST", body: datos });
      if (respuesta.status === 413) {
        throw new Error("El video es demasiado pesado (máximo 4 GB). Grábalo más corto o en menor resolución.");
      }
      var cuerpo;
      try {
        cuerpo = await respuesta.json();
      } catch (e) {
        throw new Error("El servidor devolvió una respuesta inesperada. Revisa la consola donde corre Flask.");
      }
      if (!cuerpo.ok) throw new Error(cuerpo.error || "No se pudo procesar el video.");
      mostrarResultado(cuerpo);
    } catch (error) {
      var texto = error.message || "Ocurrió un error inesperado.";
      if (error instanceof TypeError || /failed to fetch|networkerror|load failed/i.test(texto)) {
        texto = "No se pudo completar la conexión con el servidor. Revisa que la terminal donde ejecutaste python app.py siga abierta sin errores, y prueba con un video más corto o de menor resolución.";
      }
      mostrarError(texto);
    } finally {
      detenerMensajes();
      boton.disabled = false;
    }
  }

  function renderizarMetricas(metricas) {
    var contenedor = $("#metricas");
    contenedor.innerHTML = "";
    metricas.forEach(function (m, i) {
      var tarjeta = document.createElement("div");
      tarjeta.className = "metrica" + (i === 0 && /energ/i.test(m.etiqueta) ? " destacada" : "");
      tarjeta.style.animationDelay = i * 60 + "ms";
      tarjeta.innerHTML =
        '<span class="et">' + escapar(m.etiqueta) + "</span>" +
        "<b>" + escapar(m.valor) + (m.unidad ? "<small>" + escapar(m.unidad) + "</small>" : "") + "</b>" +
        (m.nota ? '<p class="nota">' + escapar(m.nota) + "</p>" : "");
      contenedor.appendChild(tarjeta);
    });
  }

  function bandaEntre(a, b, nombre, color) {
    var sup = [], inf = [];
    for (var i = 0; i < a.length; i++) {
      if (a[i] === null || b[i] === null) {
        sup.push(null);
        inf.push(null);
      } else {
        sup.push(Math.max(a[i], b[i]));
        inf.push(Math.min(a[i], b[i]));
      }
    }
    return { nombre: nombre, sup: sup, inf: inf, color: color };
  }

  function definirPestanas(r) {
    var g = r.grafica;
    var exp = r.experimento;
    var n = g.t.length;
    var cada = Math.max(1, Math.floor(n / 140));
    var lista = [];

    if (exp === "parabolico") {
      lista.push({
        nombre: "Trayectoria",
        cfg: {
          ejeX: "x (m)", ejeY: "h (m)", etiquetaX: "x", x: g.x, ajustarX: true, marcador: false,
          series: [
            { nombre: "Datos reales (OpenCV)", x: g.x, y: g.h, color: COLOR.real, ancho: 2.6, brillo: true },
            { nombre: "Teoría ideal", x: g.x_teo, y: g.h_teo, color: COLOR.teoria, ancho: 1.8, guion: [7, 5] }
          ]
        }
      });
    }

    if (exp === "pendulo") {
      lista.push({
        nombre: "Posición x(t)",
        cfg: {
          ejeX: "t (s)", ejeY: "x (m)", etiquetaX: "t", x: g.t, marcador: true,
          series: [
            { nombre: "Datos reales (OpenCV)", y: g.x, color: COLOR.real, ancho: 2.4, brillo: true },
            { nombre: "Teoría ideal sin amortiguar", y: g.x_teo, color: COLOR.teoria, ancho: 1.8, guion: [7, 5] }
          ],
          banda: bandaEntre(g.x, g.x_teo, "Desviación", COLOR.desviacion)
        }
      });
    } else {
      lista.push({
        nombre: "Altura h(t)",
        cfg: {
          ejeX: "t (s)", ejeY: "h (m)", etiquetaX: "t", x: g.t, marcador: true,
          series: [
            { nombre: "Puntos detectados", y: g.h_crudo, color: COLOR.puntos, puntos: true, cada: cada, oculta: false },
            { nombre: "Datos reales (suavizados)", y: g.h, color: COLOR.real, ancho: 2.4, brillo: true },
            { nombre: "Teoría ideal", y: g.h_teo, color: COLOR.teoria, ancho: 1.8, guion: [7, 5] }
          ],
          banda: bandaEntre(g.h, g.h_teo, "Desviación", COLOR.desviacion)
        }
      });
    }

    var eTeo = g.t.map(function () { return g.e_teo; });
    var eInf = g.e.map(function (v) { return v === null ? null : Math.min(v, g.e_teo); });
    lista.push({
      nombre: "Energía",
      cfg: {
        ejeX: "t (s)", ejeY: "E específica (J/kg)", etiquetaX: "t", x: g.t, marcador: true,
        series: [
          { nombre: "Energía real", y: g.e, color: COLOR.real, ancho: 2.4, brillo: true },
          { nombre: "Energía ideal conservada", y: eTeo, color: COLOR.teoria, ancho: 1.8, guion: [7, 5] }
        ],
        banda: { nombre: "Pérdida energética", sup: eTeo, inf: eInf, color: COLOR.banda }
      }
    });

    lista.push({
      nombre: "Velocidad",
      cfg: {
        ejeX: "t (s)", ejeY: exp === "pendulo" ? "|vx| (m/s)" : "v (m/s)", etiquetaX: "t", x: g.t, marcador: true,
        series: [
          { nombre: exp === "pendulo" ? "Rapidez horizontal real" : "Rapidez real", y: g.v, color: COLOR.real, ancho: 2.4, brillo: true },
          { nombre: "Teoría ideal", y: g.v_teo, color: COLOR.teoria, ancho: 1.8, guion: [7, 5] }
        ],
        banda: bandaEntre(g.v, g.v_teo, "Desviación", COLOR.desviacion)
      }
    });

    return lista;
  }

  function activarPestana(indice) {
    estado.activa = indice;
    document.querySelectorAll(".pestana").forEach(function (b, i) {
      b.classList.toggle("activa", i === indice);
      b.setAttribute("aria-selected", i === indice ? "true" : "false");
    });
    estado.grafica.configurar(estado.pestanas[indice].cfg, true);
    actualizarContadores();
  }

  function construirPestanas(r) {
    estado.pestanas = definirPestanas(r);
    var contenedor = $("#pestanas");
    contenedor.innerHTML = "";
    estado.pestanas.forEach(function (p, i) {
      var boton = document.createElement("button");
      boton.type = "button";
      boton.className = "pestana ripple";
      boton.setAttribute("role", "tab");
      boton.textContent = p.nombre;
      boton.addEventListener("click", function () { activarPestana(i); });
      contenedor.appendChild(boton);
    });
    if (!estado.grafica) estado.grafica = new window.AetherGrafica($("#grafica"));
    activarPestana(0);
  }

  function buscarIndice(tiempos, t) {
    var bajo = 0, alto = tiempos.length - 1;
    while (bajo < alto) {
      var medio = (bajo + alto + 1) >> 1;
      if (tiempos[medio] <= t) bajo = medio;
      else alto = medio - 1;
    }
    return bajo;
  }

  function actualizarContadores() {
    if (!estado.resultado) return;
    var video = $("#videoSalida");
    var s = estado.resultado.serie;
    var t = video.currentTime - s.t0;
    if (t < 0 || t > s.t[s.t.length - 1] + 0.2) {
      ["#cT", "#cX", "#cH", "#cV"].forEach(function (id) { $(id).textContent = "—"; });
      if (estado.grafica) estado.grafica.ponerMarca(null);
      return;
    }
    var i = buscarIndice(s.t, t);
    $("#cT").textContent = t.toFixed(2);
    $("#cX").textContent = s.x[i].toFixed(2);
    $("#cH").textContent = s.h[i].toFixed(2);
    $("#cV").textContent = s.v[i].toFixed(2);
    if (estado.grafica) estado.grafica.ponerMarca(t);
  }

  function ciclo() {
    actualizarContadores();
    var video = $("#videoSalida");
    if (!video.paused && !video.ended) estado.animacion = requestAnimationFrame(ciclo);
  }

  function iniciarVideo() {
    var video = $("#videoSalida");
    video.addEventListener("play", function () {
      cancelAnimationFrame(estado.animacion);
      estado.animacion = requestAnimationFrame(ciclo);
    });
    ["pause", "seeked", "seeking", "timeupdate", "loadedmetadata", "ended"].forEach(function (nombre) {
      video.addEventListener(nombre, actualizarContadores);
    });
  }

  function mostrarResultado(r) {
    estado.resultado = r;
    var video = $("#videoSalida");
    video.src = r.video_url;
    video.load();
    $("#enlaceVideo").href = r.video_url;
    $("#enlaceVideo").setAttribute("download", "aether_trayectoria.mp4");
    $("#avisoVideo").hidden = r.video_ok;
    renderizarMetricas(r.metricas);
    $("#resultados").hidden = false;
    construirPestanas(r);
    $("#btnAuditar").disabled = false;
    $("#btnAuditar").querySelector("span").textContent = "Generar informe del auditor";
    setTimeout(function () {
      $("#resultados").scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
  }

  async function auditar() {
    if (!estado.resultado) return;
    var boton = $("#btnAuditar");
    var caja = $("#auditoria");
    boton.disabled = true;
    caja.hidden = false;
    caja.innerHTML = '<p class="cargando-texto">El auditor está analizando las diferencias entre teoría y realidad…</p>';
    if (window.Aether) window.Aether.mostrarCarga(["Contrastando teoría y mediciones…", "Evaluando fricción y resistencia del aire…", "Redactando el informe científico…"]);
    try {
      var respuesta = await fetch("/api/tracker/auditar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job: estado.resultado.job })
      });
      var cuerpo = await respuesta.json();
      if (!cuerpo.ok) throw new Error(cuerpo.error || "No se pudo generar el informe.");
      window.AetherRender.montar(caja, cuerpo.reporte);
      boton.querySelector("span").textContent = "Informe generado";
    } catch (error) {
      caja.innerHTML = '<div class="alerta">' + escapar(error.message || "Error inesperado.") + "</div>";
      boton.disabled = false;
    } finally {
      if (window.Aether) window.Aether.ocultarCarga();
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("#videoCamara").addEventListener("change", function (e) {
      elegirArchivo(e.target.files[0], "#videoCamara");
    });
    $("#videoArchivo").addEventListener("change", function (e) {
      elegirArchivo(e.target.files[0], "#videoArchivo");
    });
    document.querySelectorAll("input[name='experimento']").forEach(function (r) {
      r.addEventListener("change", actualizarExperimento);
    });
    $("#formTracker").addEventListener("submit", enviar);
    $("#btnAuditar").addEventListener("click", auditar);
    actualizarExperimento();
    iniciarVideo();
  });
})();
