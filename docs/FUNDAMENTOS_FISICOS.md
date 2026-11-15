# Fundamentos físicos y matemáticos

Convención: la altura $h$ se mide hacia arriba desde el punto más bajo observado, y $g = 9.81\ \mathrm{m/s^2}$.

## Escala

Los píxeles se convierten a metros con

$$\text{mpp} = \frac{\text{alto real de la escena (m)}}{\text{alto del fotograma (px)}}$$

Por eso la gravedad estimada depende directamente de que la medida del encuadre sea correcta.

## Caída libre y tiro parabólico

Con las condiciones iniciales tomadas de los primeros fotogramas del movimiento:

$$h(t) = h_0 + v_{0}\,t - \tfrac{1}{2} g t^2 \qquad x(t) = x_0 + v_x t$$

- El inicio del movimiento se detecta cuando el objeto se desplaza más que un umbral respecto a su posición inicial.
- $h_0$ y $v_0$ se obtienen por mínimos cuadrados sobre los primeros fotogramas, usando $g$ conocida.
- En caída libre se toma $v_x = 0$.

**Gravedad estimada.** Se ajusta un polinomio de segundo grado a los datos reales $h(t) = a t^2 + b t + c$ y se calcula

$$g_{\text{est}} = -2a \qquad \text{error} = \frac{|g_{\text{est}} - g|}{g}\times 100\,\%$$

## Péndulo simple

Para oscilaciones pequeñas con amortiguamiento, el desplazamiento horizontal se modela como

$$x(t) = x_c + e^{-\gamma t}\left(a\cos\omega t + b\sin\omega t\right)$$

Se busca $\omega$ cerca del pico de la transformada de Fourier y se ajustan $\gamma$, $a$ y $b$ por mínimos cuadrados. De allí:

$$T = \frac{2\pi}{\omega} \qquad A_0 = \sqrt{a^2 + b^2} \qquad \omega_0^2 = \omega^2 + \gamma^2 \qquad L = \frac{g}{\omega_0^2}$$

La curva **teórica ideal** es la misma sin amortiguamiento ($\gamma = 0$): amplitud constante. La diferencia entre ambas es la pérdida de amplitud.

## Energía mecánica específica

Por unidad de masa:

$$e(t) = \tfrac{1}{2} v^2 + g\,h$$

La energía ideal $e_0$ es el promedio de los primeros fotogramas y permanece constante en la teoría. La pérdida se estima como

$$\text{pérdida} = \frac{e_0 - \bar e_{\text{final}}}{e_0}\times 100\,\%$$

La región entre $e_0$ y $e(t)$ es el **margen de pérdida energética** que se sombrea en la gráfica.

## Procesamiento de señal

- **Suavizado:** filtro de Savitzky–Golay (polinomio de grado 2). Conserva exactamente las parábolas, incluso en los extremos, lo que evita sesgar la gravedad estimada.
- **Velocidad:** derivada numérica de la posición suavizada.
- **Huecos:** los fotogramas sin detección se interpolan linealmente.

## Fuentes de discrepancia que analiza el auditor

Resistencia aerodinámica (proporcional a $v$ o a $v^2$), fricción en el pivote, disipación como calor y sonido, deformación inelástica, rotación del objeto, perspectiva y paralaje, distorsión de lente, desenfoque de movimiento, resolución en píxeles y fotogramas por segundo.
