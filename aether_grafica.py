import argparse
import sys

import cv2
import matplotlib.pyplot as plt
import numpy as np

G = 9.81

RANGOS = {
    "rojo": [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (180, 255, 255))],
    "naranja": [((10, 120, 100), (22, 255, 255))],
    "amarillo": [((22, 100, 100), (35, 255, 255))],
    "verde": [((36, 70, 60), (85, 255, 255))],
    "azul": [((90, 100, 50), (130, 255, 255))],
    "rosa": [((140, 60, 100), (169, 255, 255))],
    "blanco": [((0, 0, 200), (180, 50, 255))],
}

FONDO = "#050814"
PANEL = "#0a0f1d"
ORO = "#f5d77a"
ORO_OSCURO = "#d4af37"
BLANCO = "#fffdf5"
AZUL = "#6fb7ff"


def suavizar(valores, ventana=5, orden=2):
    valores = np.asarray(valores, dtype=float)
    n = len(valores)
    if ventana > n:
        ventana = n if n % 2 == 1 else n - 1
    if ventana <= orden + 1:
        return valores.copy()
    mitad = ventana // 2
    posiciones = np.arange(-mitad, mitad + 1)
    pesos = np.linalg.pinv(np.vander(posiciones, orden + 1, increasing=True))[0]
    salida = np.convolve(valores, pesos[::-1], mode="same")
    ejes = np.arange(ventana)
    salida[:mitad] = np.polyval(np.polyfit(ejes, valores[:ventana], orden), ejes[:mitad])
    salida[-mitad:] = np.polyval(np.polyfit(ejes, valores[-ventana:], orden), ejes[ventana - mitad:])
    return salida


def seguir_objeto(ruta, color):
    captura = cv2.VideoCapture(ruta)
    if not captura.isOpened():
        sys.exit("No se pudo abrir el video: " + ruta)
    fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
    nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    sustractor = cv2.createBackgroundSubtractorMOG2(history=150, varThreshold=36, detectShadows=True)
    puntos = []
    alto = None
    previo = None
    while True:
        correcto, cuadro = captura.read()
        if not correcto:
            break
        if cuadro.shape[0] > 720:
            factor = 720 / cuadro.shape[0]
            cuadro = cv2.resize(cuadro, None, fx=factor, fy=factor, interpolation=cv2.INTER_AREA)
        alto = cuadro.shape[0]
        borroso = cv2.GaussianBlur(cuadro, (7, 7), 0)
        if color == "auto":
            mascara = sustractor.apply(borroso)
            mascara = cv2.threshold(mascara, 200, 255, cv2.THRESH_BINARY)[1]
        else:
            hsv = cv2.cvtColor(borroso, cv2.COLOR_BGR2HSV)
            mascara = np.zeros(hsv.shape[:2], np.uint8)
            for bajo, alto_hsv in RANGOS[color]:
                mascara |= cv2.inRange(hsv, np.array(bajo), np.array(alto_hsv))
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, nucleo)
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, nucleo, iterations=2)
        contornos, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidatos = []
        for contorno in contornos:
            area = cv2.contourArea(contorno)
            momentos = cv2.moments(contorno)
            if area >= 30 and momentos["m00"] > 0:
                candidatos.append((area, momentos["m10"] / momentos["m00"], momentos["m01"] / momentos["m00"]))
        if not candidatos:
            puntos.append(None)
            continue
        mayor = max(c[0] for c in candidatos)
        validos = [c for c in candidatos if c[0] >= 0.35 * mayor]
        if previo is not None:
            elegido = min(validos, key=lambda c: (c[1] - previo[0]) ** 2 + (c[2] - previo[1]) ** 2)
        else:
            elegido = max(validos)
        previo = (elegido[1], elegido[2])
        puntos.append(previo)
    captura.release()
    return fps, puntos, alto


def preparar_desde_video(ruta, color, alto_escena, factor_lento):
    fps, puntos, alto_px = seguir_objeto(ruta, color)
    indices = np.array([i for i, p in enumerate(puntos) if p is not None])
    if len(indices) < 8:
        sys.exit("Se detectó el objeto en muy pocos fotogramas. Prueba otro color o mejor iluminación.")
    cuadros = np.arange(indices[0], indices[-1] + 1)
    xs = np.interp(cuadros, indices, [puntos[i][0] for i in indices])
    ys = np.interp(cuadros, indices, [puntos[i][1] for i in indices])
    xs = suavizar(xs)
    ys = suavizar(ys)
    desplazamiento = np.hypot(xs - np.median(xs[:3]), ys - np.median(ys[:3]))
    if desplazamiento.max() < 5:
        sys.exit("No se detectó movimiento del objeto.")
    umbral = max(3.0, 0.04 * desplazamiento.max())
    movimiento = np.where(desplazamiento > umbral)[0]
    inicio = max(0, movimiento[0] - 1)
    final_px = np.hypot(xs - xs[-1], ys - ys[-1])
    reposo = np.where(final_px > umbral)[0]
    fin = min(len(xs) - 1, reposo[-1] + 1) if reposo.size else len(xs) - 1
    xs, ys = xs[inicio:fin + 1], ys[inicio:fin + 1]
    mpp = alto_escena / alto_px
    t = np.arange(len(xs)) / (fps * factor_lento)
    x = (xs - xs[0]) * mpp
    h = (ys.max() - ys) * mpp
    return t, x, h


def datos_demo(tipo):
    rng = np.random.default_rng(7)
    paso = 1 / 60
    if tipo == "pendulo":
        t = np.arange(0, 8, paso)
        L, a0, gamma = 0.9, 0.30, 0.15
        w = np.sqrt(G / L)
        angulo = a0 * np.exp(-gamma * t) * np.cos(w * t)
        x = L * np.sin(angulo) + rng.normal(0, 0.002, t.size)
        h = L * (1 - np.cos(angulo)) + rng.normal(0, 0.002, t.size)
        return t, x, h
    vx, vh, h0 = (0.0, 0.0, 2.0) if tipo == "caida" else (2.2, 3.4, 0.4)
    k = 0.18
    t, xs, hs = [0.0], [0.0], [h0]
    x, h, ux, uh = 0.0, h0, vx, vh
    while h > 0 and len(t) < 600:
        rapidez = np.hypot(ux, uh)
        ux += -k * rapidez * ux * paso
        uh += (-G - k * rapidez * uh) * paso
        x += ux * paso
        h += uh * paso
        t.append(t[-1] + paso)
        xs.append(x)
        hs.append(h)
    t = np.array(t)
    return t, np.array(xs) + rng.normal(0, 0.003, t.size), np.array(hs) + rng.normal(0, 0.003, t.size)


def modelo_proyectil(t, x, h, parabolico):
    k = int(np.clip(round(0.15 * len(t)), 4, 12))
    tk = t[:k]
    matriz = np.vstack([np.ones(k), tk]).T
    h0, v0 = np.linalg.lstsq(matriz, h[:k] + 0.5 * G * tk ** 2, rcond=None)[0]
    if parabolico:
        x0, vx = np.linalg.lstsq(matriz, x[:k], rcond=None)[0]
    else:
        x0, vx = float(np.mean(x[:k])), 0.0
    return x0 + vx * t, h0 + v0 * t - 0.5 * G * t ** 2


def modelo_pendulo(t, x):
    n = len(t)
    paso = t[1] - t[0]
    duracion = t[-1]
    senal = (x - x.mean()) * np.hanning(n)
    tamano = 1 << (int(np.ceil(np.log2(n))) + 4)
    espectro = np.abs(np.fft.rfft(senal, tamano))
    frecuencias = np.fft.rfftfreq(tamano, paso)
    banda = (frecuencias >= max(0.15, 0.75 / duracion)) & (frecuencias <= 5.0)
    if not banda.any():
        sys.exit("El video debe cubrir al menos un periodo del péndulo.")
    w0 = 2 * np.pi * frecuencias[int(np.argmax(np.where(banda, espectro, 0)))]
    mejor = None
    for w in np.linspace(0.92 * w0, 1.08 * w0, 41):
        for gamma in np.linspace(0, 3.0 / duracion, 25):
            envolvente = np.exp(-gamma * t)
            matriz = np.vstack([np.ones(n), envolvente * np.cos(w * t), envolvente * np.sin(w * t)]).T
            solucion = np.linalg.lstsq(matriz, x, rcond=None)[0]
            error = np.sum((matriz @ solucion - x) ** 2)
            if mejor is None or error < mejor[0]:
                mejor = (error, w, gamma, solucion)
    _, w, gamma, (centro, a, b) = mejor
    ideal = centro + a * np.cos(w * t) + b * np.sin(w * t)
    return ideal, w, gamma, np.hypot(a, b)


def analizar(tipo, t, x, h):
    t = np.asarray(t, float)
    x = suavizar(x)
    h = suavizar(h)
    vx = suavizar(np.gradient(x, t))
    vh = suavizar(np.gradient(h, t))
    energia = suavizar(0.5 * (vx ** 2 + vh ** 2) + G * h, 7)
    k = int(np.clip(round(0.15 * len(t)), 4, 12))
    e0 = float(np.mean(energia[:k]))
    resultado = {"t": t, "energia": energia, "e0": e0, "tipo": tipo}
    perdida = (e0 - float(np.mean(energia[-k:]))) / e0 * 100 if e0 > 0 else 0.0
    resultado["perdida"] = perdida
    if tipo == "pendulo":
        ideal, w, gamma, amplitud = modelo_pendulo(t, x)
        centro = float(np.mean(ideal))
        resultado.update(
            y_real=x - centro, y_teo=ideal - centro, x_real=x - centro, x_teo=ideal - centro,
            h_real=h, etiqueta_y="Desplazamiento horizontal (m)",
            resumen="Periodo %.3f s | amplitud %.1f cm -> %.1f cm | pérdida de energía %.1f %%"
            % (2 * np.pi / w, amplitud * 100, amplitud * 100 * np.exp(-gamma * t[-1]), perdida),
        )
        longitud = G / (w ** 2 + gamma ** 2)
        u = np.clip(ideal - centro, -0.999 * longitud, 0.999 * longitud)
        resultado["h_teo"] = longitud - np.sqrt(longitud ** 2 - u ** 2)
        return resultado
    x_teo, h_teo = modelo_proyectil(t, x, h, tipo == "parabolico")
    g_est = -2 * np.polyfit(t, h, 2)[0]
    resultado.update(
        y_real=h, y_teo=h_teo, x_real=x, x_teo=x_teo, h_real=h, h_teo=h_teo, etiqueta_y="Altura (m)",
        resumen="g estimada %.2f m/s² (error %.1f %%) | pérdida de energía %.1f %%"
        % (g_est, abs(g_est - G) / G * 100, perdida),
    )
    return resultado


def estilizar(eje, titulo, etiqueta_x, etiqueta_y):
    eje.set_facecolor(PANEL)
    eje.set_title(titulo, color=ORO, fontsize=12, pad=10)
    eje.set_xlabel(etiqueta_x, color=BLANCO)
    eje.set_ylabel(etiqueta_y, color=BLANCO)
    eje.tick_params(colors="#9aa3b8")
    eje.grid(color="#ffffff", alpha=0.07)
    for lado in eje.spines.values():
        lado.set_color("#2b3350")


def dibujar(r, nombre_experimento, guardar):
    figura, ejes = plt.subplots(1, 3, figsize=(17, 5.2), facecolor=FONDO)
    figura.suptitle("AETHER · %s" % nombre_experimento, color=ORO, fontsize=16, fontweight="bold")
    t = r["t"]

    ax = ejes[0]
    estilizar(ax, "Teoría vs realidad", "t (s)", r["etiqueta_y"])
    ax.fill_between(t, r["y_real"], r["y_teo"], color=ORO_OSCURO, alpha=0.25, label="Desviación")
    ax.plot(t, r["y_teo"], "--", color=BLANCO, lw=2, label="Teoría ideal")
    ax.plot(t, r["y_real"], color=ORO, lw=2.4, label="Datos reales")
    ax.legend(facecolor=PANEL, edgecolor="#2b3350", labelcolor=BLANCO)

    ax = ejes[1]
    estilizar(ax, "Trayectoria", "x (m)", "h (m)")
    ax.plot(r["x_teo"], r["h_teo"], "--", color=BLANCO, lw=2, label="Teoría ideal")
    ax.plot(r["x_real"], r["h_real"], color=AZUL, lw=2.4, label="Datos reales")
    minimo = min(np.min(r["x_real"]), np.min(r["x_teo"]))
    maximo = max(np.max(r["x_real"]), np.max(r["x_teo"]))
    if maximo - minimo < 0.4:
        centro = (maximo + minimo) / 2
        ax.set_xlim(centro - 0.2, centro + 0.2)
    ax.legend(facecolor=PANEL, edgecolor="#2b3350", labelcolor=BLANCO)

    ax = ejes[2]
    estilizar(ax, "Energía mecánica específica", "t (s)", "e (J/kg)")
    ax.fill_between(t, r["energia"], r["e0"], where=r["energia"] < r["e0"], color="#ff6b6b", alpha=0.3, label="Pérdida energética")
    ax.axhline(r["e0"], ls="--", color=BLANCO, lw=2, label="Energía ideal")
    ax.plot(t, r["energia"], color=ORO, lw=2.4, label="Energía real")
    ax.legend(facecolor=PANEL, edgecolor="#2b3350", labelcolor=BLANCO)

    figura.text(0.5, 0.01, r["resumen"], ha="center", color=BLANCO, fontsize=11)
    figura.tight_layout(rect=(0, 0.05, 1, 0.94))
    if guardar:
        figura.savefig(guardar, dpi=150, facecolor=FONDO)
        print("Gráfica guardada en", guardar)
    return figura


def main():
    analizador = argparse.ArgumentParser(description="Gráfica teoría vs realidad de un experimento de física")
    analizador.add_argument("video", nargs="?", help="Ruta del video. Si se omite, se usa un ejemplo simulado.")
    analizador.add_argument("--experimento", choices=["caida", "parabolico", "pendulo"], default="caida")
    analizador.add_argument("--color", choices=["auto"] + list(RANGOS), default="rojo")
    analizador.add_argument("--alto", type=float, default=2.0, help="Alto real que abarca el video, en metros")
    analizador.add_argument("--lento", type=float, default=1.0, help="Factor de cámara lenta del video")
    analizador.add_argument("--guardar", default="grafica_aether.png")
    argumentos = analizador.parse_args()

    if argumentos.video:
        t, x, h = preparar_desde_video(argumentos.video, argumentos.color, argumentos.alto, argumentos.lento)
    else:
        t, x, h = datos_demo(argumentos.experimento)
    nombres = {"caida": "Caída libre", "parabolico": "Tiro parabólico", "pendulo": "Péndulo simple"}
    resultado = analizar(argumentos.experimento, t, x, h)
    dibujar(resultado, nombres[argumentos.experimento], argumentos.guardar)
    print(resultado["resumen"])
    plt.show()


if __name__ == "__main__":
    main()
