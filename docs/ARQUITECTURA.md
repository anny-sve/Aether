# Arquitectura

## Visión general

```
Navegador (móvil o PC)
   │  HTML + Tailwind + JS (fetch)
   ▼
Flask (app.py)
   ├── Tutor ──────────► Gemini (texto + imagen) ──► 4 secciones en Markdown/LaTeX
   ├── PDF ────────────► ReportLab (+ ecuaciones como texto Unicode)
   ├── Laboratorio ────► OpenCV (seguimiento) ──► NumPy (análisis) ──► JSON + video MP4
   └── Auditor ────────► Gemini (métricas del experimento) ──► informe en Markdown/LaTeX
```

El estado de cada usuario (última solución y último análisis) se guarda **en memoria** del servidor y se enlaza con una cookie de sesión. Al reiniciar el servidor se pierde; no hay base de datos.

## Rutas

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Formulario del tutor |
| POST | `/resolver` | Envía el problema a Gemini y redirige a `/resultado` |
| GET | `/resultado` | Solución en cuatro secciones |
| GET | `/imagen-problema` | Imagen adjunta del último problema |
| GET | `/descargar-pdf` | Reporte PDF de la última solución |
| GET | `/tracker` | Interfaz del laboratorio de video |
| POST | `/api/tracker/procesar` | Recibe el video, lo analiza y devuelve métricas, series y gráficas en JSON |
| GET | `/media/<archivo>` | Video de salida con la trayectoria trazada |
| POST | `/api/tracker/auditar` | Genera el informe del Auditor de Errores con Gemini |
| GET | `/codigo` | Muestra el script `aether_grafica.py` con botón de copiar |
| GET | `/codigo/descargar` | Descarga el script |

### Parámetros de `/api/tracker/procesar` (formulario multipart)

| Campo | Descripción |
|---|---|
| `video` | Archivo de video (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`, `.3gp`) |
| `experimento` | `caida`, `pendulo` o `parabolico` |
| `modo` | `auto` (movimiento) o un color (`rojo`, `naranja`, `amarillo`, `verde`, `azul`, `rosa`, `blanco`) |
| `alto_escena` | Alto real visible en el encuadre, en metros |
| `longitud` | Solo péndulo: longitud real del hilo en metros, para calcular el periodo teórico |
| `fps` | Opcional: fuerza los fotogramas por segundo si el video los reporta mal |

## Tubería del laboratorio

1. **Lectura**: se procesan hasta 2400 fotogramas, reescalados a un máximo de 640 px de ancho.
2. **Detección**: por color (máscara HSV + contornos) o por movimiento (sustracción de fondo MOG2). Se toma el centroide del contorno más grande.
3. **Análisis**: se rellenan huecos, se suaviza con un filtro polinomial y se calcula velocidad, energía y el modelo teórico (ver [fundamentos](FUNDAMENTOS_FISICOS.md)).
4. **Salida**: se dibuja la estela, un panel con tiempo, coordenadas y rapidez, y se codifica un MP4 compatible con el navegador mediante `ffmpeg`.
5. **Auditoría** (opcional): las métricas se envían a Gemini para redactar el informe.

## Límites y configuración

- Subida máxima: 4 GB por video.
- Los videos de salida se guardan en `media/` y los antiguos se eliminan automáticamente.
- El servidor escucha en `0.0.0.0` para poder usarse desde el celular en la misma red; no lo expongas a internet.
