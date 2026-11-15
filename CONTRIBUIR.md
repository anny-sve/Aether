# Guía para contribuir

Este proyecto lo desarrolla un equipo universitario. Para trabajar en conjunto sin pisarse el código:

## Flujo de trabajo

1. Clona el repositorio y crea tu entorno (ver [README](README.md)).
2. Antes de empezar, actualiza `main`:
   ```bash
   git checkout main
   git pull
   ```
3. Crea una rama por cada tarea:
   ```bash
   git checkout -b feature/nombre-corto
   ```
4. Haz commits pequeños con mensajes claros en español:
   ```
   Agrega selector de color en el laboratorio
   Corrige el cálculo del periodo del péndulo
   ```
5. Sube tu rama y abre un *Pull Request* hacia `main`. Otro integrante debe revisarlo antes de unirlo.

## Reglas del proyecto

- **No subir secretos.** El archivo `.env` y las claves de API nunca van al repositorio. Si una clave se sube por error, revócala en Google AI Studio y crea otra.
- **Código sin comentarios.** El equipo decidió mantener el código fuente (Python, JS, CSS y HTML) sin comentarios; la explicación va en `docs/`.
- **Probar antes de unir.** Ejecuta `python app.py` y verifica el tutor, el laboratorio y la descarga del PDF.
- No subir videos pesados ni la carpeta `media/` (está en `.gitignore`).

## Reporte de errores

Abre un *Issue* con: qué hiciste, qué esperabas, qué pasó, el mensaje de la terminal y, si aplica, el tamaño y la resolución del video.
