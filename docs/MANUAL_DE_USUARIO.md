# Manual de usuario

## 1. Resolver un problema (pestaña «Resolver»)

1. Escribe el enunciado o toma una foto del problema con el botón de imagen.
2. Elige la categoría: Cinemática, Dinámica, Leyes de Newton o Trabajo y Energía.
3. Pulsa el botón de resolver y espera unos segundos.
4. Lee la solución en cuatro secciones:
   - **Datos identificados e Incógnitas**
   - **Fórmulas y Principios Físicos Aplicados**
   - **Procedimiento paso a paso**
   - **Resultado final** (en unidades del SI)
5. Pulsa **Descargar reporte PDF** para guardar el reporte en tu dispositivo.

## 2. Analizar un experimento (pestaña «Laboratorio»)

1. Graba un video corto con la cámara del teléfono o sube un archivo.
2. Elige el experimento: caída libre, péndulo o tiro parabólico.
3. Elige cómo detectar el objeto: por **color** (recomendado) o **automático** por movimiento.
4. Escribe el **alto real visible** en metros (mide la altura que abarca el encuadre).
5. En el péndulo puedes indicar la longitud del hilo para comparar con el periodo teórico.
6. Pulsa **Analizar con OpenCV**.
7. Revisa:
   - el video con la estela y los contadores en tiempo real,
   - las métricas (gravedad estimada, pérdida de energía, periodo, alcance…),
   - las gráficas de altura, energía y velocidad: teoría frente a datos reales,
8. Pulsa **Generar informe del auditor** para que la IA explique las diferencias.

## 3. Código (pestaña «Código»)

Muestra el script `aether_grafica.py`. Usa **Copiar código** o **Descargar .py** y ejecútalo en tu computadora (ver [README](../README.md)).

## Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| «Falta la clave de Gemini» | `.env` sin clave | Pega tu clave en `GEMINI_API_KEY` y reinicia |
| «Gemini rechazó la clave» | Clave inválida o revocada | Crea otra en Google AI Studio |
| «Se alcanzó el límite de uso» | Cuota gratuita agotada | Espera unos minutos |
| «No se pudo completar la conexión con el servidor» | El servidor se cerró o el video es enorme | Revisa la terminal y prueba con un video más corto o en 1080p |
| Se detectó el objeto en pocos fotogramas | Poco contraste o mala luz | Usa un color vivo sobre fondo liso o prueba otro color |
| La gravedad estimada sale muy distinta de 9.81 | Escala mal indicada o arrastre del aire | Revisa el alto real del encuadre |
