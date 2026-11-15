(function () {
  function ticks(minimo, maximo, objetivo) {
    var rango = maximo - minimo || 1;
    var bruto = rango / objetivo;
    var magnitud = Math.pow(10, Math.floor(Math.log10(bruto)));
    var norm = bruto / magnitud;
    var paso = norm < 1.5 ? 1 : norm < 3 ? 2 : norm < 7 ? 5 : 10;
    paso *= magnitud;
    var inicio = Math.ceil(minimo / paso) * paso;
    var valores = [];
    for (var v = inicio; v <= maximo + paso * 1e-6; v += paso) valores.push(Math.round(v / paso) * paso);
    return { valores: valores, paso: paso };
  }

  function formatear(valor, paso) {
    var decimales = Math.max(0, -Math.floor(Math.log10(paso)));
    return valor.toFixed(Math.min(decimales, 4));
  }

  function rectRedondeado(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function Grafica(lienzo) {
    this.lienzo = lienzo;
    this.ctx = lienzo.getContext("2d");
    this.cfg = null;
    this.progreso = 1;
    this.marca = null;
    this.indiceHover = null;
    this.anim = null;
    var self = this;
    lienzo.addEventListener("pointermove", function (e) { self.mover(e); });
    lienzo.addEventListener("pointerdown", function (e) { self.mover(e); });
    lienzo.addEventListener("pointerleave", function () {
      self.indiceHover = null;
      self.dibujar();
    });
    if (window.ResizeObserver) {
      new ResizeObserver(function () { self.dibujar(); }).observe(lienzo.parentElement);
    } else {
      window.addEventListener("resize", function () { self.dibujar(); });
    }
  }

  Grafica.prototype.configurar = function (cfg, animar) {
    var self = this;
    this.cfg = cfg;
    this.indiceHover = null;
    cancelAnimationFrame(this.anim);
    if (animar === false || (window.Aether && window.Aether.reducido)) {
      this.progreso = 1;
      this.dibujar();
      return;
    }
    this.progreso = 0;
    var inicio = performance.now();
    function paso(ahora) {
      var avance = Math.min(1, (ahora - inicio) / 1100);
      self.progreso = 1 - Math.pow(1 - avance, 3);
      self.dibujar();
      if (avance < 1) self.anim = requestAnimationFrame(paso);
    }
    this.anim = requestAnimationFrame(paso);
  };

  Grafica.prototype.ponerMarca = function (valor) {
    this.marca = valor;
    if (this.cfg && this.cfg.marcador) this.dibujar();
  };

  Grafica.prototype.limites = function () {
    var c = this.cfg;
    var xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
    c.series.forEach(function (s) {
      var xs = s.x || c.x;
      for (var i = 0; i < s.y.length; i++) {
        var y = s.y[i];
        var x = xs[i];
        if (y === null || y === undefined || x === null || x === undefined) continue;
        if (x < xmin) xmin = x;
        if (x > xmax) xmax = x;
        if (y < ymin) ymin = y;
        if (y > ymax) ymax = y;
      }
    });
    if (c.banda) {
      for (var j = 0; j < c.banda.sup.length; j++) {
        var a = c.banda.sup[j], b = c.banda.inf[j];
        if (a !== null && a > ymax) ymax = a;
        if (b !== null && b < ymin) ymin = b;
      }
    }
    if (!isFinite(xmin)) { xmin = 0; xmax = 1; ymin = 0; ymax = 1; }
    if (xmax === xmin) xmax = xmin + 1;
    if (ymax === ymin) ymax = ymin + 1;
    var relleno = (ymax - ymin) * 0.08;
    var rellenoX = c.ajustarX ? (xmax - xmin) * 0.05 : 0;
    return { xmin: xmin - rellenoX, xmax: xmax + rellenoX, ymin: ymin - relleno, ymax: ymax + relleno };
  };

  Grafica.prototype.geometria = function () {
    var rect = this.lienzo.getBoundingClientRect();
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var ancho = Math.max(1, Math.floor(rect.width * dpr));
    var alto = Math.max(1, Math.floor(rect.height * dpr));
    if (this.lienzo.width !== ancho || this.lienzo.height !== alto) {
      this.lienzo.width = ancho;
      this.lienzo.height = alto;
    }
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { w: rect.width, h: rect.height };
  };

  Grafica.prototype.mover = function (e) {
    var c = this.cfg;
    if (!c) return;
    var rect = this.lienzo.getBoundingClientRect();
    var px = e.clientX - rect.left;
    var g = this.disposicion;
    if (!g) return;
    var base = c.series[0];
    var xs = base.x || c.x;
    var objetivo = g.xmin + ((px - g.izq) / g.ancho) * (g.xmax - g.xmin);
    var mejor = null, distancia = Infinity;
    for (var i = 0; i < xs.length; i++) {
      if (xs[i] === null || base.y[i] === null) continue;
      var d = Math.abs(xs[i] - objetivo);
      if (d < distancia) { distancia = d; mejor = i; }
    }
    this.indiceHover = mejor;
    this.dibujar();
  };

  Grafica.prototype.dibujar = function () {
    var c = this.cfg;
    if (!c) return;
    var ctx = this.ctx;
    var tam = this.geometria();
    var w = tam.w, h = tam.h;
    ctx.clearRect(0, 0, w, h);
    ctx.font = "11px Sora, system-ui, sans-serif";

    var filasLeyenda = 1;
    var xLey = 0;
    var anchoMax = w - 24;
    c.series.concat(c.banda ? [c.banda] : []).forEach(function (s) {
      var an = ctx.measureText(s.nombre).width + 30;
      if (xLey + an > anchoMax) { filasLeyenda += 1; xLey = 0; }
      xLey += an;
    });

    var izq = 52, der = 14, sup = 14 + filasLeyenda * 18, inf = 38;
    var ancho = w - izq - der;
    var alto = h - sup - inf;
    var lim = this.limites();
    this.disposicion = { izq: izq, ancho: ancho, xmin: lim.xmin, xmax: lim.xmax };

    function px(x) { return izq + ((x - lim.xmin) / (lim.xmax - lim.xmin)) * ancho; }
    function py(y) { return sup + alto - ((y - lim.ymin) / (lim.ymax - lim.ymin)) * alto; }

    var ty = ticks(lim.ymin, lim.ymax, 5);
    var tx = ticks(lim.xmin, lim.xmax, Math.max(3, Math.floor(ancho / 80)));

    ctx.lineWidth = 1;
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.fillStyle = "rgba(200,208,228,0.7)";
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ty.valores.forEach(function (v) {
      var y = Math.round(py(v)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(izq, y);
      ctx.lineTo(izq + ancho, y);
      ctx.stroke();
      ctx.fillText(formatear(v, ty.paso), izq - 8, y);
    });
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    tx.valores.forEach(function (v) {
      var x = Math.round(px(v)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(x, sup);
      ctx.lineTo(x, sup + alto);
      ctx.stroke();
      ctx.fillText(formatear(v, tx.paso), x, sup + alto + 6);
    });

    ctx.fillStyle = "rgba(245,215,122,0.85)";
    ctx.textAlign = "center";
    ctx.fillText(c.ejeX || "", izq + ancho / 2, h - 16);
    ctx.save();
    ctx.translate(13, sup + alto / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.textBaseline = "middle";
    ctx.fillText(c.ejeY || "", 0, 0);
    ctx.restore();

    ctx.strokeStyle = "rgba(245,215,122,0.35)";
    ctx.beginPath();
    ctx.moveTo(izq, sup);
    ctx.lineTo(izq, sup + alto);
    ctx.lineTo(izq + ancho, sup + alto);
    ctx.stroke();

    ctx.save();
    ctx.beginPath();
    ctx.rect(izq, sup - 4, ancho * this.progreso + 1, alto + 8);
    ctx.clip();

    if (c.banda) {
      var xsb = c.x;
      ctx.fillStyle = c.banda.color || "rgba(255,122,107,0.25)";
      var abierto = false;
      var arranque = 0;
      var cerrar = function (fin) {
        for (var k = fin; k >= arranque; k--) ctx.lineTo(px(xsb[k]), py(c.banda.inf[k]));
        ctx.closePath();
        ctx.fill();
        abierto = false;
      };
      for (var i = 0; i < xsb.length; i++) {
        var sv = c.banda.sup[i], iv = c.banda.inf[i];
        var valido = sv !== null && iv !== null && xsb[i] !== null;
        if (valido) {
          if (!abierto) {
            ctx.beginPath();
            ctx.moveTo(px(xsb[i]), py(sv));
            abierto = true;
            arranque = i;
          } else {
            ctx.lineTo(px(xsb[i]), py(sv));
          }
        } else if (abierto) {
          cerrar(i - 1);
        }
      }
      if (abierto) cerrar(xsb.length - 1);
    }

    c.series.forEach(function (s) {
      var xs = s.x || c.x;
      if (s.puntos) {
        ctx.fillStyle = s.color;
        for (var i = 0; i < s.y.length; i += s.cada || 1) {
          if (s.y[i] === null || xs[i] === null) continue;
          ctx.globalAlpha = 0.55;
          ctx.beginPath();
          ctx.arc(px(xs[i]), py(s.y[i]), 2.2, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
        return;
      }
      ctx.strokeStyle = s.color;
      ctx.lineWidth = s.ancho || 2;
      ctx.lineJoin = "round";
      ctx.setLineDash(s.guion || []);
      ctx.shadowColor = s.brillo ? s.color : "transparent";
      ctx.shadowBlur = s.brillo ? 10 : 0;
      ctx.beginPath();
      var trazando = false;
      for (var j = 0; j < s.y.length; j++) {
        if (s.y[j] === null || xs[j] === null) { trazando = false; continue; }
        if (!trazando) { ctx.moveTo(px(xs[j]), py(s.y[j])); trazando = true; }
        else ctx.lineTo(px(xs[j]), py(s.y[j]));
      }
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.shadowBlur = 0;
    });
    ctx.restore();

    if (c.marcador && this.marca !== null && this.marca >= lim.xmin && this.marca <= lim.xmax) {
      var xm = px(this.marca);
      ctx.strokeStyle = "rgba(255,253,245,0.8)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(xm, sup);
      ctx.lineTo(xm, sup + alto);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    var lx = 12, ly = 12;
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    var elementosLey = c.series.filter(function (s) { return !s.oculta; }).concat(c.banda ? [c.banda] : []);
    elementosLey.forEach(function (s) {
      var an = ctx.measureText(s.nombre).width + 30;
      if (lx + an > anchoMax + 12) { lx = 12; ly += 18; }
      ctx.fillStyle = s === c.banda ? (c.banda.color || "rgba(255,122,107,0.5)") : s.color;
      if (s.puntos) {
        ctx.beginPath();
        ctx.arc(lx + 8, ly, 3, 0, Math.PI * 2);
        ctx.fill();
      } else if (s === c.banda) {
        ctx.fillRect(lx, ly - 5, 16, 10);
      } else {
        ctx.strokeStyle = s.color;
        ctx.lineWidth = 2;
        ctx.setLineDash(s.guion || []);
        ctx.beginPath();
        ctx.moveTo(lx, ly);
        ctx.lineTo(lx + 16, ly);
        ctx.stroke();
        ctx.setLineDash([]);
      }
      ctx.fillStyle = "rgba(232,236,247,0.9)";
      ctx.fillText(s.nombre, lx + 22, ly);
      lx += an;
    });

    if (this.indiceHover !== null) this.dibujarTooltip(px, py, sup, alto, izq, ancho, w);
  };

  Grafica.prototype.dibujarTooltip = function (px, py, sup, alto, izq, ancho, w) {
    var c = this.cfg;
    var ctx = this.ctx;
    var i = this.indiceHover;
    var base = c.series[0];
    var xs = base.x || c.x;
    var xv = xs[i];
    if (xv === null || xv === undefined) return;
    var xp = px(xv);
    ctx.strokeStyle = "rgba(245,215,122,0.55)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(xp, sup);
    ctx.lineTo(xp, sup + alto);
    ctx.stroke();

    var filas = [(c.etiquetaX || c.ejeX.split(" ")[0]) + " = " + xv.toFixed(3)];
    c.series.forEach(function (s) {
      if (s.puntos || s.oculta) return;
      var valor = s.y[i];
      if (valor === null || valor === undefined) return;
      var sx = (s.x || c.x)[i];
      if (sx !== null && sx !== undefined) {
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(px(sx), py(valor), 4, 0, Math.PI * 2);
        ctx.fill();
      }
      filas.push(s.nombre + ": " + valor.toFixed(3));
    });

    ctx.font = "11px Sora, system-ui, sans-serif";
    var anchoCaja = 0;
    filas.forEach(function (f) { anchoCaja = Math.max(anchoCaja, ctx.measureText(f).width); });
    anchoCaja += 20;
    var altoCaja = filas.length * 17 + 12;
    var x0 = xp + 14;
    if (x0 + anchoCaja > w - 4) x0 = xp - anchoCaja - 14;
    if (x0 < 4) x0 = 4;
    var y0 = sup + 6;
    ctx.fillStyle = "rgba(10,15,29,0.92)";
    ctx.strokeStyle = "rgba(212,175,55,0.55)";
    rectRedondeado(ctx, x0, y0, anchoCaja, altoCaja, 10);
    ctx.fill();
    ctx.stroke();
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    filas.forEach(function (f, k) {
      ctx.fillStyle = k === 0 ? "#f5d77a" : "rgba(232,236,247,0.95)";
      ctx.fillText(f, x0 + 10, y0 + 15 + k * 17);
    });
  };

  window.AetherGrafica = Grafica;
})();
