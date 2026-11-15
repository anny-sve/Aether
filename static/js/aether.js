(function () {
  var reducido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function iniciarCampo() {
    var lienzo = document.getElementById("campo");
    if (!lienzo) return;
    var ctx = lienzo.getContext("2d");
    var w = 0, h = 0, dpr = 1;
    var particulas = [];
    var estrellas = [];
    var anillos = [];
    var puntero = { x: -9999, y: -9999, activo: false };
    var tiempo = 0;
    var corriendo = true;

    function campo(x, y, t) {
      return (
        Math.sin(x * 0.0042 + t * 0.00045) * 1.7 +
        Math.cos(y * 0.0051 - t * 0.00035) * 1.7 +
        Math.sin((x + y) * 0.0021 + t * 0.0002) * 1.2
      );
    }

    function nueva() {
      return {
        x: Math.random() * w,
        y: Math.random() * h,
        vida: 80 + Math.random() * 220,
        vel: 0.6 + Math.random() * 1.1,
        alfa: 0.12 + Math.random() * 0.4,
        blanca: Math.random() < 0.12
      };
    }

    function crear() {
      var cantidad = Math.min(170, Math.floor((w * h) / 9500));
      particulas = [];
      for (var i = 0; i < cantidad; i++) particulas.push(nueva());
      estrellas = [];
      var total = Math.floor((w * h) / 9000);
      for (var j = 0; j < total; j++) {
        estrellas.push({
          x: Math.random() * w,
          y: Math.random() * h,
          r: Math.random() * 1.1 + 0.2,
          fase: Math.random() * Math.PI * 2,
          ritmo: 0.0006 + Math.random() * 0.0016
        });
      }
    }

    function ajustar() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      lienzo.width = Math.floor(w * dpr);
      lienzo.height = Math.floor(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      crear();
    }

    function dibujarEstrellas() {
      for (var i = 0; i < estrellas.length; i++) {
        var e = estrellas[i];
        var brillo = reducido ? 0.5 : 0.35 + 0.65 * Math.abs(Math.sin(e.fase + tiempo * e.ritmo));
        ctx.globalAlpha = brillo * 0.75;
        ctx.fillStyle = "#fffdf5";
        ctx.beginPath();
        ctx.arc(e.x, e.y, e.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    }

    function paso(ahora) {
      if (!corriendo) return;
      tiempo = ahora || 0;
      ctx.globalCompositeOperation = "destination-out";
      ctx.fillStyle = "rgba(0,0,0,0.085)";
      ctx.fillRect(0, 0, w, h);
      ctx.globalCompositeOperation = "source-over";
      dibujarEstrellas();
      ctx.lineCap = "round";
      for (var i = 0; i < particulas.length; i++) {
        var p = particulas[i];
        var angulo = campo(p.x, p.y, tiempo) ;
        if (puntero.activo) {
          var dx = p.x - puntero.x;
          var dy = p.y - puntero.y;
          var d = Math.sqrt(dx * dx + dy * dy);
          if (d < 190) {
            var fuerza = 1 - d / 190;
            var tangente = Math.atan2(dy, dx) + Math.PI / 2;
            angulo = angulo * (1 - fuerza) + tangente * fuerza;
          }
        }
        var nx = p.x + Math.cos(angulo) * p.vel;
        var ny = p.y + Math.sin(angulo) * p.vel;
        ctx.strokeStyle = p.blanca ? "rgba(255,253,245," + p.alfa + ")" : "rgba(245,215,122," + p.alfa + ")";
        ctx.lineWidth = p.blanca ? 1.1 : 1.3;
        ctx.beginPath();
        ctx.moveTo(p.x, p.y);
        ctx.lineTo(nx, ny);
        ctx.stroke();
        p.x = nx;
        p.y = ny;
        p.vida -= 1;
        if (p.vida <= 0 || nx < -20 || nx > w + 20 || ny < -20 || ny > h + 20) {
          particulas[i] = nueva();
        }
      }
      for (var k = anillos.length - 1; k >= 0; k--) {
        var a = anillos[k];
        a.r += 3.2;
        a.alfa *= 0.955;
        if (a.alfa < 0.02) {
          anillos.splice(k, 1);
          continue;
        }
        ctx.strokeStyle = "rgba(255,240,180," + a.alfa + ")";
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2);
        ctx.stroke();
      }
      requestAnimationFrame(paso);
    }

    window.addEventListener("resize", ajustar);
    window.addEventListener("pointermove", function (e) {
      puntero.x = e.clientX;
      puntero.y = e.clientY;
      puntero.activo = true;
    }, { passive: true });
    window.addEventListener("pointerdown", function (e) {
      puntero.x = e.clientX;
      puntero.y = e.clientY;
      puntero.activo = true;
      anillos.push({ x: e.clientX, y: e.clientY, r: 4, alfa: 0.7 });
    }, { passive: true });
    window.addEventListener("pointerup", function (e) {
      if (e.pointerType !== "mouse") puntero.activo = false;
    }, { passive: true });
    document.addEventListener("mouseleave", function () { puntero.activo = false; });
    document.addEventListener("visibilitychange", function () {
      corriendo = !document.hidden;
      if (corriendo) requestAnimationFrame(paso);
    });

    ajustar();
    if (reducido) {
      dibujarEstrellas();
    } else {
      requestAnimationFrame(paso);
    }
  }

  function iniciarOndas() {
    var lienzos = document.querySelectorAll("canvas[data-onda]");
    if (!lienzos.length) return;
    var visibles = new Set();
    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (en) {
        if (en.isIntersecting) visibles.add(en.target);
        else visibles.delete(en.target);
      });
    });
    lienzos.forEach(function (l) { observador.observe(l); });

    function pintar(l, t) {
      var rect = l.getBoundingClientRect();
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      var ancho = Math.max(1, Math.floor(rect.width * dpr));
      var alto = Math.max(1, Math.floor(rect.height * dpr));
      if (l.width !== ancho || l.height !== alto) {
        l.width = ancho;
        l.height = alto;
      }
      var ctx = l.getContext("2d");
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, rect.width, rect.height);
      var fuerte = l.hasAttribute("data-onda-fuerte");
      var capas = fuerte ? 4 : 3;
      for (var c = 0; c < capas; c++) {
        var amp = (fuerte ? 26 : 16) * (1 - c * 0.18);
        var frec = 0.012 + c * 0.006;
        var vel = 0.0011 + c * 0.0005;
        var fase = c * 1.7;
        ctx.beginPath();
        for (var x = 0; x <= rect.width; x += 3) {
          var envolvente = Math.sin((x / rect.width) * Math.PI);
          var y = rect.height / 2 + Math.sin(x * frec + t * vel + fase) * amp * (0.35 + 0.65 * envolvente) * Math.cos(x * 0.004 - t * 0.0004);
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        var alfa = 0.75 - c * 0.17;
        ctx.strokeStyle = c === 0 ? "rgba(255,253,245," + alfa + ")" : "rgba(245,215,122," + alfa + ")";
        ctx.lineWidth = c === 0 ? 1.6 : 1.2;
        ctx.shadowColor = "rgba(245,215,122,0.8)";
        ctx.shadowBlur = 10;
        ctx.stroke();
        ctx.shadowBlur = 0;
      }
    }

    function ciclo(t) {
      visibles.forEach(function (l) { pintar(l, reducido ? 0 : t); });
      if (!reducido) requestAnimationFrame(ciclo);
    }
    requestAnimationFrame(ciclo);
    if (reducido) {
      window.addEventListener("resize", function () { visibles.forEach(function (l) { pintar(l, 0); }); });
    }
  }

  function iniciarRipple() {
    document.addEventListener("pointerdown", function (e) {
      var objetivo = e.target.closest(".ripple");
      if (!objetivo || objetivo.disabled) return;
      var rect = objetivo.getBoundingClientRect();
      var lado = Math.max(rect.width, rect.height);
      var onda = document.createElement("span");
      onda.className = "onda-click";
      onda.style.width = onda.style.height = lado + "px";
      onda.style.left = e.clientX - rect.left - lado / 2 + "px";
      onda.style.top = e.clientY - rect.top - lado / 2 + "px";
      objetivo.appendChild(onda);
      setTimeout(function () { onda.remove(); }, 750);
    });
  }

  function iniciarTilt() {
    if (reducido || !window.matchMedia("(pointer: fine)").matches) return;
    document.querySelectorAll("[data-tilt]").forEach(function (el) {
      el.addEventListener("pointermove", function (e) {
        var r = el.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width - 0.5;
        var py = (e.clientY - r.top) / r.height - 0.5;
        el.style.transform = "perspective(900px) rotateY(" + px * 3 + "deg) rotateX(" + -py * 3 + "deg)";
      });
      el.addEventListener("pointerleave", function () {
        el.style.transform = "";
      });
    });
  }

  function iniciarReveal() {
    var elementos = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      elementos.forEach(function (el) { el.classList.add("visible"); });
      return;
    }
    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("visible");
          observador.unobserve(en.target);
        }
      });
    }, { threshold: 0.08 });
    elementos.forEach(function (el, i) {
      el.style.transitionDelay = Math.min(i * 70, 350) + "ms";
      observador.observe(el);
    });
  }

  var temporizadorCarga = null;

  function mostrarCarga(mensajes) {
    var capa = document.getElementById("cargando");
    var texto = document.getElementById("cargandoTexto");
    if (!capa) return;
    var lista = mensajes && mensajes.length ? mensajes : ["Procesando…"];
    var i = 0;
    texto.textContent = lista[0];
    capa.classList.add("activo");
    clearInterval(temporizadorCarga);
    if (lista.length > 1) {
      temporizadorCarga = setInterval(function () {
        i = (i + 1) % lista.length;
        texto.textContent = lista[i];
      }, 2600);
    }
  }

  function ocultarCarga() {
    clearInterval(temporizadorCarga);
    var capa = document.getElementById("cargando");
    if (capa) capa.classList.remove("activo");
  }

  function iniciarFormularios() {
    document.querySelectorAll("form[data-cargando]").forEach(function (form) {
      form.addEventListener("submit", function () {
        mostrarCarga(form.getAttribute("data-cargando").split("|"));
      });
    });
    window.addEventListener("pageshow", ocultarCarga);
  }

  function iniciarImagen() {
    var entrada = document.getElementById("imagen");
    if (!entrada) return;
    var vacia = document.getElementById("zonaVacia");
    var previa = document.getElementById("zonaPrevia");
    var img = document.getElementById("imagenPrevia");
    var nombre = document.getElementById("nombreImagen");
    var quitar = document.getElementById("quitarImagen");
    var url = null;

    function limpiar() {
      entrada.value = "";
      if (url) URL.revokeObjectURL(url);
      url = null;
      previa.hidden = true;
      vacia.hidden = false;
    }

    entrada.addEventListener("change", function () {
      var archivo = entrada.files && entrada.files[0];
      if (!archivo) {
        limpiar();
        return;
      }
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(archivo);
      img.src = url;
      nombre.textContent = archivo.name;
      vacia.hidden = true;
      previa.hidden = false;
    });

    quitar.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      limpiar();
    });
  }

  window.Aether = { mostrarCarga: mostrarCarga, ocultarCarga: ocultarCarga, reducido: reducido };

  document.addEventListener("DOMContentLoaded", function () {
    iniciarCampo();
    iniciarOndas();
    iniciarRipple();
    iniciarTilt();
    iniciarReveal();
    iniciarFormularios();
    iniciarImagen();
  });
})();
