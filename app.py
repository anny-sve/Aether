import io
import json
import math
import os
import re
import shutil
import socket
import subprocess
import time
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import (Flask, jsonify, redirect, render_template, request,
                   send_file, send_from_directory, session, url_for)
from google import genai
from google.genai import types
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, Image, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MEDIA_DIR = BASE_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)

G = 9.81
MODELO = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
MODELOS_RESPALDO = ["gemini-3.6-flash", "gemini-2.5-flash"]
MAX_FOTOGRAMAS = 2400
ANCHO_PROCESO = 640
EXTENSIONES_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".3gp"}

CATEGORIAS = ["Cinemática", "Dinámica", "Leyes de Newton", "Trabajo y Energía"]
ICONOS_CATEGORIA = {
    "Cinemática": "🚀",
    "Dinámica": "⚙️",
    "Leyes de Newton": "🍎",
    "Trabajo y Energía": "⚡",
}
EXPERIMENTOS = {
    "caida": "Caída libre",
    "pendulo": "Péndulo",
    "parabolico": "Tiro parabólico",
}
COLORES = ["rojo", "naranja", "amarillo", "verde", "azul", "rosa", "blanco"]
RANGOS_COLOR = {
    "rojo": [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (180, 255, 255))],
    "naranja": [((10, 120, 100), (22, 255, 255))],
    "amarillo": [((22, 100, 100), (35, 255, 255))],
    "verde": [((36, 70, 60), (85, 255, 255))],
    "azul": [((90, 100, 50), (130, 255, 255))],
    "rosa": [((140, 60, 100), (169, 255, 255))],
    "blanco": [((0, 0, 200), (180, 50, 255))],
}

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "aether-clave-local-cambiala")
app.config["MAX_CONTENT_LENGTH"] = 4096 * 1024 * 1024

SOLUCIONES = {}
RESULTADOS = {}
FUENTE_PDF = {}

PROMPT_TUTOR = """Eres Aether, un tutor de física de nivel universitario, riguroso, claro y didáctico. Respondes siempre en español.

Recibirás una categoría, un enunciado de texto y, opcionalmente, una imagen con el problema. Si el enunciado está en la imagen, léelo con cuidado antes de resolver.

Estructura tu respuesta EXACTAMENTE con estos cuatro encabezados de nivel 2, en este orden y con este texto, sin añadir nada antes ni después:

## 📌 Datos identificados e Incógnitas
## 📐 Fórmulas y Principios Físicos Aplicados
## 💡 Procedimiento paso a paso
## 🎯 Resultado final

Reglas obligatorias:
- Escribe todas las ecuaciones en LaTeX: en línea con $...$ y en bloque con $$...$$. No uses \\[ \\] ni \\( \\).
- En "Datos identificados e Incógnitas" lista cada dato con su símbolo, valor y unidad, y cada incógnita. Si asumes un valor (por ejemplo g = 9.81 m/s²) indícalo.
- En "Fórmulas y Principios Físicos Aplicados" nombra cada principio o ley y escribe su ecuación en bloque.
- En "Procedimiento paso a paso" numera los pasos, explica el razonamiento conceptual de cada uno y sustituye los valores con sus unidades.
- En "Resultado final" da la respuesta en negrita con unidades del Sistema Internacional (SI) y cifras significativas coherentes. Añade una verificación breve de coherencia física.
- No uses bloques de código ni tablas. Si el contenido no es un problema de física, dilo brevemente en la primera sección y explica qué información falta."""

PROMPT_AUDITOR = """Eres el Auditor de Errores de Aether, un físico experimental que redacta informes científicos en español.

Recibirás los datos extraídos con visión artificial (OpenCV) de un video de un experimento real y la predicción teórica ideal calculada con las mismas condiciones iniciales. Debes explicar con rigor por qué la realidad difiere de la teoría del pizarrón.

Estructura el informe con estos encabezados de nivel 2:

## Resumen ejecutivo
## Comparación cuantitativa
## Causas físicas de la discrepancia
## Incertidumbres de medición
## Recomendaciones para mejorar el experimento
## Conclusión

Reglas:
- Usa LaTeX con $...$ en línea y $$...$$ en bloque.
- Cita únicamente cifras presentes en los datos recibidos y no inventes mediciones.
- En las causas físicas considera según corresponda: resistencia aerodinámica (arrastre proporcional a v o a v²), fricción en el pivote, disipación de energía en forma de calor y sonido, deformación inelástica, rotación del objeto, variación de la aceleración efectiva por perspectiva, y flotabilidad del aire.
- En incertidumbres considera: resolución en píxeles, calibración de escala, distorsión de lente, paralaje por profundidad, desenfoque de movimiento, obturador rodante, fotogramas por segundo y ruido del seguimiento.
- Relaciona cada causa con el comportamiento observado en las métricas.
- Sé conciso, científico y específico. Máximo 600 palabras."""


def obtener_cliente():
    clave = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not clave or clave.startswith("tu_clave"):
        raise RuntimeError("Falta la clave de Gemini. Abre el archivo .env y coloca tu clave en GEMINI_API_KEY.")
    return genai.Client(api_key=clave)


def consultar_gemini(contenido, sistema, temperatura=0.3):
    cliente = obtener_cliente()
    configuracion = types.GenerateContentConfig(system_instruction=sistema, temperature=temperatura)
    modelos = [MODELO] + [m for m in MODELOS_RESPALDO if m != MODELO]
    ultimo_error = None
    for modelo in modelos:
        try:
            respuesta = cliente.models.generate_content(model=modelo, contents=contenido, config=configuracion)
        except Exception as error:
            ultimo_error = error
            texto_error = str(error)
            if "404" in texto_error or "NOT_FOUND" in texto_error:
                continue
            raise
        texto = (respuesta.text or "").strip()
        if not texto:
            raise RuntimeError("Gemini no devolvió contenido. Intenta reformular el enunciado.")
        return texto
    raise ultimo_error


def mensaje_error(error):
    texto = str(error).strip()
    if isinstance(error, RuntimeError):
        return texto
    if "API key" in texto or "API_KEY" in texto or "401" in texto or "403" in texto:
        return "Gemini rechazó la clave de API. Revisa GEMINI_API_KEY en el archivo .env."
    if "429" in texto or "RESOURCE_EXHAUSTED" in texto:
        return "Se alcanzó el límite de uso de Gemini. Espera un momento e inténtalo de nuevo."
    if "404" in texto or "NOT_FOUND" in texto:
        return "El modelo configurado en GEMINI_MODEL no está disponible para tu clave. Prueba con otro modelo."
    return "No se pudo completar la consulta a Gemini: " + texto[:300]


def quitar_emojis(texto):
    return re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\uFE0F\u200D]", "", texto)


def normalizar_texto(texto):
    texto = texto.strip()
    texto = re.sub(r"^```(?:markdown|md)?\s*\n", "", texto)
    texto = re.sub(r"\n```\s*$", "", texto)
    texto = re.sub(r"\\\[(.+?)\\\]", lambda m: "$$" + m.group(1) + "$$", texto, flags=re.S)
    texto = re.sub(r"\\\((.+?)\\\)", lambda m: "$" + m.group(1) + "$", texto, flags=re.S)
    return texto


TITULOS_SECCION = [
    "Datos identificados e Incógnitas",
    "Fórmulas y Principios Físicos Aplicados",
    "Procedimiento paso a paso",
    "Resultado final",
]
ICONOS_SECCION = ["📌", "📐", "💡", "🎯"]


def dividir_secciones(texto):
    bloques = re.split(r"(?m)^##\s+", texto)
    partes = []
    for bloque in bloques[1:]:
        lineas = bloque.split("\n", 1)
        titulo = quitar_emojis(lineas[0]).strip().strip("*# ").strip()
        cuerpo = lineas[1].strip() if len(lineas) > 1 else ""
        partes.append({"titulo": titulo, "cuerpo": cuerpo})
    if not partes:
        return [{"icono": "💡", "titulo": "Solución", "cuerpo": texto}]
    for posicion, parte in enumerate(partes):
        parte["icono"] = ICONOS_SECCION[posicion % 4]
        if len(partes) == 4:
            parte["titulo"] = TITULOS_SECCION[posicion]
    return partes


def identificador():
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    return session["sid"]


def render_inicio(error=None, valores=None):
    return render_template(
        "index.html",
        categorias=CATEGORIAS,
        iconos=ICONOS_CATEGORIA,
        error=error,
        valores=valores or {},
    )


@app.route("/")
def index():
    return render_inicio()


@app.route("/resolver", methods=["POST"])
def resolver():
    enunciado = request.form.get("enunciado", "").strip()
    categoria = request.form.get("categoria", CATEGORIAS[0])
    if categoria not in CATEGORIAS:
        categoria = CATEGORIAS[0]
    valores = {"enunciado": enunciado, "categoria": categoria}
    archivo = request.files.get("imagen")
    imagen = None
    mime = None
    if archivo and archivo.filename:
        mime = archivo.mimetype or ""
        if not mime.startswith("image/"):
            return render_inicio("El archivo adjunto debe ser una imagen (JPG, PNG o WEBP).", valores)
        imagen = archivo.read()
        if len(imagen) > 15 * 1024 * 1024:
            return render_inicio("La imagen supera los 15 MB. Usa una más ligera.", valores)
    if not enunciado and not imagen:
        return render_inicio("Escribe el enunciado o adjunta una imagen del problema.", valores)
    texto_usuario = "Categoría: %s\n\nEnunciado:\n%s" % (
        categoria,
        enunciado or "(El enunciado está en la imagen adjunta.)",
    )
    contenido = [texto_usuario]
    if imagen:
        contenido.append(types.Part.from_bytes(data=imagen, mime_type=mime))
    try:
        crudo = consultar_gemini(contenido, PROMPT_TUTOR, 0.3)
    except Exception as error:
        return render_inicio(mensaje_error(error), valores)
    markdown = normalizar_texto(crudo)
    SOLUCIONES[identificador()] = {
        "categoria": categoria,
        "enunciado": enunciado or "(Enunciado proporcionado como imagen)",
        "markdown": markdown,
        "secciones": dividir_secciones(markdown),
        "imagen": imagen,
        "mime": mime,
        "fecha": datetime.now(),
    }
    return redirect(url_for("resultado"))


@app.route("/resultado")
def resultado():
    solucion = SOLUCIONES.get(session.get("sid"))
    if not solucion:
        return redirect(url_for("index"))
    return render_template(
        "resultado.html",
        solucion=solucion,
        iconos=ICONOS_CATEGORIA,
        fecha=solucion["fecha"].strftime("%d/%m/%Y %H:%M"),
    )


@app.route("/imagen-problema")
def imagen_problema():
    solucion = SOLUCIONES.get(session.get("sid"))
    if not solucion or not solucion.get("imagen"):
        return ("", 404)
    return send_file(io.BytesIO(solucion["imagen"]), mimetype=solucion["mime"])


SIMBOLOS = {
    "alpha": ("α", "alfa"), "beta": ("β", "beta"), "gamma": ("γ", "gamma"),
    "delta": ("δ", "delta"), "Delta": ("Δ", "Delta"), "epsilon": ("ε", "epsilon"),
    "varepsilon": ("ε", "epsilon"), "theta": ("θ", "theta"), "Theta": ("Θ", "Theta"),
    "lambda": ("λ", "lambda"), "mu": ("μ", "mu"), "nu": ("ν", "nu"),
    "pi": ("π", "pi"), "rho": ("ρ", "rho"), "sigma": ("σ", "sigma"),
    "Sigma": ("Σ", "Sigma"), "tau": ("τ", "tau"), "phi": ("φ", "phi"),
    "varphi": ("φ", "phi"), "Phi": ("Φ", "Phi"), "omega": ("ω", "omega"),
    "Omega": ("Ω", "Omega"), "cdot": ("·", "*"), "times": ("×", "x"),
    "approx": ("≈", "~"), "neq": ("≠", "!="), "leq": ("≤", "<="),
    "geq": ("≥", ">="), "le": ("≤", "<="), "ge": ("≥", ">="),
    "pm": ("±", "+/-"), "to": ("→", "->"), "rightarrow": ("→", "->"),
    "Rightarrow": ("⇒", "=>"), "infty": ("∞", "inf"), "degree": ("°", " grados"),
    "sum": ("∑", "suma"), "partial": ("∂", "d"), "nabla": ("∇", "nabla"),
    "ldots": ("…", "..."), "dots": ("…", "..."), "propto": ("∝", "~"),
    "perp": ("⊥", "perp"), "parallel": ("∥", "||"), "hbar": ("ħ", "h"),
}


def preparar_fuentes():
    if FUENTE_PDF:
        return FUENTE_PDF["nombre"], FUENTE_PDF["unicode"]
    windir = os.environ.get("WINDIR", "C:/Windows")
    candidatos = [
        tuple(os.path.join(windir, "Fonts", n) for n in ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf")),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf",
         "/Library/Fonts/Arial Italic.ttf", "/Library/Fonts/Arial Bold Italic.ttf"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
         "/System/Library/Fonts/Supplemental/Arial Italic.ttf", "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
        ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf", "/usr/share/fonts/dejavu/DejaVuSans-BoldOblique.ttf"),
    ]
    for normal, negrita, cursiva, negrita_cursiva in candidatos:
        if all(Path(ruta).exists() for ruta in (normal, negrita, cursiva, negrita_cursiva)):
            try:
                pdfmetrics.registerFont(TTFont("AetherSans", normal))
                pdfmetrics.registerFont(TTFont("AetherSans-Bold", negrita))
                pdfmetrics.registerFont(TTFont("AetherSans-Italic", cursiva))
                pdfmetrics.registerFont(TTFont("AetherSans-BoldItalic", negrita_cursiva))
                registerFontFamily("AetherSans", normal="AetherSans", bold="AetherSans-Bold",
                                   italic="AetherSans-Italic", boldItalic="AetherSans-BoldItalic")
                FUENTE_PDF.update({"nombre": "AetherSans", "unicode": True})
                return "AetherSans", True
            except Exception:
                continue
    FUENTE_PDF.update({"nombre": "Helvetica", "unicode": False})
    return "Helvetica", False


def es_simple(texto):
    return re.fullmatch(r"[\w.°]+(<(super|sub)>[^<]*</(super|sub)>)*", texto) is not None


def envolver(texto):
    texto = texto.strip()
    return texto if es_simple(texto) else "(" + texto + ")"


def latex_a_texto(expresion, usar_unicode):
    s = expresion.strip()
    s = re.sub(r"\\(?:begin|end)\{[^}]*\}", "", s)
    s = s.replace("&amp;", " ").replace("\\\\", " ")
    s = re.sub(r"\\(?:left|right|big|Big|bigg|Bigg)\b", "", s)
    s = re.sub(r"\\[,;:!]", " ", s)
    s = s.replace("\\ ", " ").replace("\\%", "%")
    s = re.sub(r"\^\s*\{?\s*\\circ\s*\}?", "°", s)
    for _ in range(8):
        anterior = s
        s = re.sub(r"\\(?:text|textbf|textit|mathrm|mathbf|mathit|operatorname|mbox)\{([^{}]*)\}", r"\1", s)
        s = re.sub(r"\\(?:vec|overrightarrow)\{([^{}]*)\}", r"<b>\1</b>", s)
        s = re.sub(r"\\(?:hat|bar|tilde|dot|ddot)\{([^{}]*)\}", r"\1", s)
        s = re.sub(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}",
                   lambda m: envolver(m.group(1)) + "/" + envolver(m.group(2)), s)
        s = re.sub(r"\\sqrt\{([^{}]*)\}", lambda m: "√" + envolver(m.group(1)) if usar_unicode
                   else "sqrt" + envolver(m.group(1)), s)
        s = re.sub(r"\^\{([^{}]*)\}", r"<super>\1</super>", s)
        s = re.sub(r"_\{([^{}]*)\}", r"<sub>\1</sub>", s)
        if s == anterior:
            break

    def reemplazar_simbolo(coincidencia):
        nombre = coincidencia.group(1)
        if nombre in SIMBOLOS:
            return SIMBOLOS[nombre][0] if usar_unicode else SIMBOLOS[nombre][1]
        return nombre

    s = re.sub(r"\\([A-Za-z]+)", reemplazar_simbolo, s)
    s = re.sub(r"\^([+-]?[A-Za-z0-9])", r"<super>\1</super>", s)
    s = re.sub(r"_([+-]?[A-Za-z0-9])", r"<sub>\1</sub>", s)
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", s).strip()


def inline_a_marcado(texto, usar_unicode):
    bloques = []

    def guardar(coincidencia):
        bloques.append(latex_a_texto(coincidencia.group(1), usar_unicode))
        return "\x00%d\x00" % (len(bloques) - 1)

    texto = re.sub(r"\$\$(.+?)\$\$", guardar, texto, flags=re.S)
    texto = re.sub(r"\$([^$\n]+?)\$", guardar, texto)
    texto = texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", texto)
    texto = re.sub(r"(?<![*\w])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", texto)
    texto = texto.replace("`", "")
    texto = re.sub(r"\x00(\d+)\x00", lambda m: bloques[int(m.group(1))], texto)
    if not usar_unicode:
        texto = quitar_emojis(texto)
    return texto


def markdown_a_flowables(cuerpo, estilos, usar_unicode):
    ecuaciones = []

    def guardar_ecuacion(coincidencia):
        ecuaciones.append(coincidencia.group(1))
        return "\n@@ECU%d@@\n" % (len(ecuaciones) - 1)

    cuerpo = re.sub(r"\$\$(.+?)\$\$", guardar_ecuacion, cuerpo, flags=re.S)
    flujo = []
    parrafo = []

    def cerrar_parrafo():
        if parrafo:
            flujo.append(Paragraph(inline_a_marcado(" ".join(parrafo), usar_unicode), estilos["cuerpo"]))
            parrafo.clear()

    for linea in cuerpo.split("\n"):
        recorte = linea.strip()
        if not recorte:
            cerrar_parrafo()
            continue
        marca = re.fullmatch(r"@@ECU(\d+)@@", recorte)
        if marca:
            cerrar_parrafo()
            texto_ecuacion = latex_a_texto(ecuaciones[int(marca.group(1))], usar_unicode)
            texto_ecuacion = texto_ecuacion.replace("&", "&amp;")
            flujo.append(Paragraph(texto_ecuacion, estilos["ecuacion"]))
            continue
        if recorte.startswith("#"):
            cerrar_parrafo()
            titulo = recorte.lstrip("#").strip()
            flujo.append(Paragraph("<b>%s</b>" % inline_a_marcado(titulo, usar_unicode), estilos["subtitulo"]))
            continue
        viñeta = re.match(r"^(\s*)[-*•]\s+(.*)$", linea)
        numerada = re.match(r"^(\s*)(\d+)[.)]\s+(.*)$", linea)
        if viñeta or numerada:
            cerrar_parrafo()
            coincidencia = viñeta or numerada
            nivel = len(coincidencia.group(1).replace("\t", "    ")) // 2
            texto = viñeta.group(2) if viñeta else numerada.group(3)
            marca_lista = "•" if viñeta else numerada.group(2) + "."
            if not usar_unicode and viñeta:
                marca_lista = "-"
            estilo = ParagraphStyle("lista%d" % nivel, parent=estilos["cuerpo"],
                                    leftIndent=16 + 12 * nivel, bulletIndent=4 + 12 * nivel, spaceAfter=3)
            flujo.append(Paragraph(inline_a_marcado(texto, usar_unicode), estilo, bulletText=marca_lista))
            continue
        parrafo.append(recorte)
    cerrar_parrafo()
    return flujo


def nombre_seguro(texto):
    normal = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", normal).strip("_") or "Reporte"


def construir_pdf(solucion):
    fuente, usar_unicode = preparar_fuentes()
    dorado_oscuro = colors.HexColor("#8a6d1a")
    dorado = colors.HexColor("#d4af37")
    noche = colors.HexColor("#0a0f1d")
    estilos = {
        "marca": ParagraphStyle("marca", fontName=fuente, fontSize=26, leading=30, textColor=noche, alignment=TA_LEFT),
        "subtitulo_marca": ParagraphStyle("submarca", fontName=fuente, fontSize=10, leading=14, textColor=dorado_oscuro),
        "cuerpo": ParagraphStyle("cuerpo", fontName=fuente, fontSize=10.5, leading=15.5, textColor=colors.HexColor("#1b2233"), spaceAfter=5),
        "ecuacion": ParagraphStyle("ecuacion", fontName=fuente, fontSize=12, leading=18, textColor=dorado_oscuro,
                                   alignment=TA_CENTER, spaceBefore=4, spaceAfter=8),
        "subtitulo": ParagraphStyle("subtitulo", fontName=fuente, fontSize=11, leading=15, textColor=noche, spaceBefore=6, spaceAfter=3),
        "seccion": ParagraphStyle("seccion", fontName=fuente, fontSize=14, leading=18, textColor=dorado_oscuro, spaceBefore=14, spaceAfter=2),
        "etiqueta": ParagraphStyle("etiqueta", fontName=fuente, fontSize=9, leading=12, textColor=colors.HexColor("#5b6478")),
        "valor": ParagraphStyle("valor", fontName=fuente, fontSize=10, leading=13, textColor=noche),
    }
    buffer = io.BytesIO()

    def decorar(lienzo, documento):
        ancho, alto = A4
        lienzo.saveState()
        lienzo.setFillColor(noche)
        lienzo.rect(0, alto - 1.1 * cm, ancho, 1.1 * cm, stroke=0, fill=1)
        lienzo.setFillColor(dorado)
        lienzo.rect(0, alto - 1.18 * cm, ancho, 0.08 * cm, stroke=0, fill=1)
        lienzo.setFont(fuente, 9)
        lienzo.setFillColor(colors.HexColor("#f5d77a"))
        lienzo.drawString(2 * cm, alto - 0.72 * cm, "AETHER  |  Plataforma de Física Avanzada")
        lienzo.setFillColor(colors.HexColor("#c9cfdd"))
        lienzo.drawRightString(ancho - 2 * cm, alto - 0.72 * cm, "Reporte de resolución")
        lienzo.setFillColor(colors.HexColor("#5b6478"))
        lienzo.setFont(fuente, 8)
        lienzo.drawCentredString(ancho / 2, 1 * cm, "Página %d" % documento.page)
        lienzo.restoreState()

    documento = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=1.8 * cm,
        title="Aether - " + solucion["categoria"], author="Aether",
    )
    historia = [
        Paragraph("Aether", estilos["marca"]),
        Paragraph("Reporte formal de problema de física", estilos["subtitulo_marca"]),
        Spacer(1, 10),
    ]
    metadatos = Table(
        [
            [Paragraph("Categoría", estilos["etiqueta"]), Paragraph(quitar_emojis(solucion["categoria"]), estilos["valor"])],
            [Paragraph("Fecha", estilos["etiqueta"]), Paragraph(solucion["fecha"].strftime("%d/%m/%Y %H:%M"), estilos["valor"])],
            [Paragraph("Sistema de unidades", estilos["etiqueta"]), Paragraph("Sistema Internacional (SI)", estilos["valor"])],
        ],
        colWidths=[4 * cm, 13 * cm],
    )
    metadatos.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e3dfd0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.append(metadatos)
    historia.append(Paragraph("Enunciado", estilos["seccion"]))
    historia.append(HRFlowable(width="100%", thickness=1, color=dorado, spaceAfter=6))
    historia.append(Paragraph(inline_a_marcado(solucion["enunciado"].replace("\n", "<br/>"), usar_unicode)
                              .replace("&lt;br/&gt;", "<br/>"), estilos["cuerpo"]))
    if solucion.get("imagen"):
        try:
            lector_bytes = io.BytesIO(solucion["imagen"])
            imagen = Image(lector_bytes)
            ancho_max, alto_max = 12 * cm, 8 * cm
            proporcion = min(ancho_max / imagen.imageWidth, alto_max / imagen.imageHeight, 1.0)
            imagen.drawWidth = imagen.imageWidth * proporcion
            imagen.drawHeight = imagen.imageHeight * proporcion
            imagen.hAlign = "CENTER"
            historia.append(Spacer(1, 6))
            historia.append(imagen)
        except Exception:
            pass
    secciones = solucion["secciones"]
    for posicion, seccion in enumerate(secciones):
        titulo = "%d. %s" % (posicion + 1, seccion["titulo"])
        historia.append(Paragraph(titulo, estilos["seccion"]))
        historia.append(HRFlowable(width="100%", thickness=1, color=dorado, spaceAfter=6))
        flujo = markdown_a_flowables(seccion["cuerpo"], estilos, usar_unicode)
        if posicion == len(secciones) - 1 and len(secciones) > 1 and flujo:
            caja = Table([[flujo]], colWidths=[17 * cm])
            caja.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdf6dd")),
                ("BOX", (0, 0), (-1, -1), 1.2, dorado),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            historia.append(caja)
        else:
            historia.extend(flujo)
    documento.build(historia, onFirstPage=decorar, onLaterPages=decorar)
    buffer.seek(0)
    return buffer


@app.route("/descargar-pdf")
def descargar_pdf():
    solucion = SOLUCIONES.get(session.get("sid"))
    if not solucion:
        return redirect(url_for("index"))
    buffer = construir_pdf(solucion)
    nombre = "Aether_%s_%s.pdf" % (nombre_seguro(solucion["categoria"]), solucion["fecha"].strftime("%Y%m%d_%H%M"))
    return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=nombre)


def detectar_objeto(fotograma, modo, sustractor, nucleo, indice):
    alto_f, ancho_f = fotograma.shape[:2]
    area_total = alto_f * ancho_f
    suave = cv2.GaussianBlur(fotograma, (7, 7), 0)
    if modo == "auto":
        primer_plano = sustractor.apply(suave)
        if indice < 6:
            return None
        mascara = cv2.threshold(primer_plano, 200, 255, cv2.THRESH_BINARY)[1]
    else:
        hsv = cv2.cvtColor(suave, cv2.COLOR_BGR2HSV)
        mascara = np.zeros(hsv.shape[:2], np.uint8)
        for bajo, alto_hsv in RANGOS_COLOR[modo]:
            mascara |= cv2.inRange(hsv, np.array(bajo, np.uint8), np.array(alto_hsv, np.uint8))
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, nucleo)
    mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, nucleo)
    contornos = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2]
    mejor = None
    area_mejor = 0.0
    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area_mejor < area < 0.4 * area_total:
            mejor, area_mejor = contorno, area
    if mejor is None or area_mejor < max(25.0, area_total * 0.00015):
        return None
    momentos = cv2.moments(mejor)
    if momentos["m00"] == 0:
        return None
    cx = momentos["m10"] / momentos["m00"]
    cy = momentos["m01"] / momentos["m00"]
    return (cx, cy, math.sqrt(area_mejor / math.pi))


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
    ajuste_inicio = np.polyfit(ejes, valores[:ventana], orden)
    ajuste_final = np.polyfit(ejes, valores[-ventana:], orden)
    salida[:mitad] = np.polyval(ajuste_inicio, ejes[:mitad])
    salida[-mitad:] = np.polyval(ajuste_final, ejes[ventana - mitad:])
    return salida


def periodo_fft(desviacion, paso, duracion):
    n = len(desviacion)
    señal = (desviacion - desviacion.mean()) * np.hanning(n)
    tamano = 1 << (int(math.ceil(math.log2(max(n, 2)))) + 3)
    espectro = np.abs(np.fft.rfft(señal, tamano))
    frecuencias = np.fft.rfftfreq(tamano, paso)
    minimo = max(0.15, 0.75 / max(duracion, 1e-6))
    mascara = (frecuencias >= minimo) & (frecuencias <= 5.0)
    if not mascara.any():
        return 1.0
    posicion = int(np.argmax(np.where(mascara, espectro, 0.0)))
    return 1.0 / frecuencias[posicion]


def lista(valores, decimales=4):
    salida = []
    for valor in np.asarray(valores, dtype=float):
        salida.append(round(float(valor), decimales) if np.isfinite(valor) else None)
    return salida


def formatear(valor, decimales=2):
    return ("%." + str(decimales) + "f") % valor


def analizar(detecciones, fps, alto_px, alto_escena, experimento, longitud):
    indices = np.array([i for i, d in enumerate(detecciones) if d is not None])
    i0, i1 = int(indices[0]), int(indices[-1])
    cuadros = np.arange(i0, i1 + 1)
    xs = np.interp(cuadros, indices, [detecciones[i][0] for i in indices])
    ys = np.interp(cuadros, indices, [detecciones[i][1] for i in indices])
    radios = [detecciones[i][2] for i in indices]
    xs_s = suavizar(xs, 5)
    ys_s = suavizar(ys, 5)
    mpp = alto_escena / alto_px
    t = (cuadros - i0) / fps
    x = (xs_s - xs_s[0]) * mpp
    referencia = ys.max()
    h = (referencia - ys_s) * mpp
    h_crudo = (referencia - ys) * mpp
    vx = suavizar(np.gradient(x, t), 5)
    vh = suavizar(np.gradient(h, t), 5)
    corte = len(t)
    if experimento != "pendulo":
        pico = int(np.argmax(h))
        bajos = np.where(h[pico:] <= 0.04 * max(h.max(), 1e-9))[0]
        fin = pico + int(bajos[0]) if len(bajos) else len(t) - 1
        corte = max(fin, min(len(t) - 1, 7)) + 1
    vx_g = suavizar(np.gradient(x[:corte], t[:corte]), 5)
    vh_g = suavizar(np.gradient(h[:corte], t[:corte]), 5)
    v = np.hypot(vx_g, vh_g)
    energia = suavizar(0.5 * (vx_g ** 2 + vh_g ** 2) + G * h[:corte], 7)

    n0 = int(max(5, min(len(t) // 4, 15)))
    n0 = min(n0, len(t))
    tt = t[:n0]
    matriz = np.column_stack([np.ones(n0), tt])
    metricas = []
    x_teo = h_teo = v_teo = None
    perdida = None

    if experimento != "pendulo":
        a_h, b_h = np.linalg.lstsq(matriz, h[:n0] + 0.5 * G * tt ** 2, rcond=None)[0]
        if experimento == "caida":
            a_x, b_x = float(np.mean(x[:n0])), 0.0
        else:
            a_x, b_x = np.linalg.lstsq(matriz, x[:n0], rcond=None)[0]
        h_teo = a_h + b_h * t - 0.5 * G * t ** 2
        x_teo = a_x + b_x * t
        v_teo = np.hypot(b_x, b_h - G * t)
        e_teo = 0.5 * (b_x ** 2 + b_h ** 2) + G * a_h
        limite = -0.04 * max(h.max(), 1e-9)
        valido = h_teo >= limite
        valido = np.cumprod(valido).astype(bool)
        h_teo = np.where(valido, h_teo, np.nan)
        x_teo = np.where(valido, x_teo, np.nan)
        v_teo = np.where(valido, v_teo, np.nan)
        if corte >= 6:
            coef = np.polyfit(t[:corte], h[:corte], 2)
            g_est = -2.0 * coef[0]
            error_g = abs(g_est - G) / G * 100.0
            metricas.append({"etiqueta": "Gravedad estimada", "valor": formatear(g_est, 2), "unidad": "m/s²",
                             "nota": "Ajuste cuadrático a los datos reales"})
            metricas.append({"etiqueta": "Desviación respecto a g", "valor": formatear(error_g, 1), "unidad": "%",
                             "nota": "Frente a 9.81 m/s²"})
        metricas.append({"etiqueta": "Altura máxima", "valor": formatear(h[:corte].max(), 2), "unidad": "m", "nota": ""})
        metricas.append({"etiqueta": "Tiempo de vuelo", "valor": formatear(t[corte - 1], 2), "unidad": "s", "nota": ""})
        if experimento == "parabolico":
            metricas.append({"etiqueta": "Alcance horizontal", "valor": formatear(abs(x[corte - 1] - x[0]), 2),
                             "unidad": "m", "nota": ""})
        final = max(3, corte // 10)
        e_final = float(np.mean(energia[corte - final:corte]))
        perdida = max(0.0, (e_teo - e_final) / e_teo * 100.0) if e_teo > 1e-9 else 0.0
    else:
        duracion = float(t[-1])
        t_real = periodo_fft(x, 1.0 / fps, duracion)
        ciclos = int(duracion // t_real)
        muestras = int(round(ciclos * t_real * fps)) if ciclos >= 1 else len(x)
        xc = float(np.mean(x[:max(muestras, 3)]))
        d = x - xc
        t_teo = 2.0 * math.pi * math.sqrt(longitud / G) if longitud else t_real
        w = 2.0 * math.pi / t_teo
        ventana = max(3, min(len(d), int(round(t_teo / 2.0 * fps)) + 1))
        amplitud0 = max(float(np.max(np.abs(d[:ventana]))), 1e-9)
        fase0 = math.acos(max(-1.0, min(1.0, d[0] / amplitud0)))
        paso = d[min(3, len(d) - 1)] - d[0]
        fase = -fase0 if paso >= 0 else fase0
        x_teo = xc + amplitud0 * np.cos(w * t + fase)
        v_teo = np.abs(amplitud0 * w * np.sin(w * t + fase))
        v = np.abs(vx_g)
        e_teo = float(np.median(energia[:5]))
        ventana_final = max(3, int(round(t_real / 2.0 * fps)) + 1)
        amplitud_final = float(np.max(np.abs(d[-ventana_final:])))
        relacion = min(amplitud_final / amplitud0, 1.0)
        perdida = (1.0 - relacion ** 2) * 100.0
        metricas.append({"etiqueta": "Periodo medido", "valor": formatear(t_real, 3), "unidad": "s", "nota": "Mediante FFT"})
        if longitud:
            metricas.append({"etiqueta": "Periodo teórico", "valor": formatear(t_teo, 3), "unidad": "s",
                             "nota": "T = 2π√(L/g)"})
        metricas.append({"etiqueta": "Amplitud inicial", "valor": formatear(amplitud0 * 100, 1), "unidad": "cm", "nota": ""})
        metricas.append({"etiqueta": "Amplitud final", "valor": formatear(amplitud_final * 100, 1), "unidad": "cm",
                         "nota": "Amortiguamiento observado"})
    if perdida is not None:
        metricas.insert(0, {"etiqueta": "Pérdida de energía estimada", "valor": formatear(min(perdida, 100.0), 1),
                            "unidad": "%", "nota": "Respecto a la energía ideal conservada"})
    metricas.append({"etiqueta": "Rapidez máxima", "valor": formatear(float(np.max(np.hypot(vx_g, vh_g))), 2),
                     "unidad": "m/s", "nota": ""})
    metricas.append({"etiqueta": "Fotogramas con objeto", "valor": "%d / %d" % (len(indices), i1 - i0 + 1), "unidad": "",
                     "nota": "FPS usados: %s" % formatear(fps, 1)})
    metricas.append({"etiqueta": "Escala", "valor": formatear(mpp * 1000, 2), "unidad": "mm/px", "nota": ""})

    recorte = slice(0, corte)
    grafica = {
        "t": lista(t[recorte]),
        "x": lista(x[recorte]),
        "x_teo": lista(x_teo[recorte]) if x_teo is not None else None,
        "h": lista(h[recorte]),
        "h_crudo": lista(h_crudo[recorte]),
        "h_teo": lista(h_teo[recorte]) if h_teo is not None else None,
        "v": lista(v[recorte]),
        "v_teo": lista(v_teo[recorte]) if v_teo is not None else None,
        "e": lista(energia[recorte]),
        "e_teo": round(float(e_teo), 4),
    }
    serie = {
        "t0": i0 / fps,
        "t": lista(t),
        "x": lista(x),
        "h": lista(h),
        "v": lista(np.hypot(vx, vh)),
    }
    return {
        "i0": i0, "i1": i1, "xs": xs_s, "ys": ys_s, "t": t, "x": x, "h": h, "vx": vx, "vh": vh,
        "mpp": mpp, "radio": float(np.median(radios)), "metricas": metricas,
        "grafica": grafica, "serie": serie,
    }


def abrir_escritor(destino, fps, tamano, codecs):
    for codec in codecs:
        escritor = cv2.VideoWriter(str(destino), cv2.VideoWriter_fourcc(*codec), fps, tamano)
        if escritor.isOpened():
            return escritor, codec
        escritor.release()
    raise RuntimeError("No se pudo crear el video de salida en este equipo.")


def dibujar_estela(fotograma, puntos, dorado, escala):
    total = len(puntos)
    for j in range(1, total):
        fuerza = j / total
        color = tuple(int(c * (0.25 + 0.75 * fuerza)) for c in dorado)
        grosor = max(1, int(round((1 + 3 * fuerza) * escala)))
        p1 = (int(puntos[j - 1][0]), int(puntos[j - 1][1]))
        p2 = (int(puntos[j][0]), int(puntos[j][1]))
        cv2.line(fotograma, p1, p2, color, grosor, cv2.LINE_AA)


def dibujar_panel(fotograma, lineas, escala, dorado):
    alto_linea = int(22 * escala)
    ancho_panel = int(215 * escala)
    alto_panel = alto_linea * len(lineas) + int(10 * escala)
    alto_f, ancho_f = fotograma.shape[:2]
    y2 = min(alto_f, 8 + alto_panel)
    x2 = min(ancho_f, 8 + ancho_panel)
    zona = fotograma[8:y2, 8:x2]
    if zona.size == 0:
        return
    oscuro = np.full_like(zona, (22, 10, 5))
    zona[:] = cv2.addWeighted(zona, 0.3, oscuro, 0.7, 0)
    cv2.rectangle(fotograma, (8, 8), (x2 - 1, y2 - 1), dorado, 1, cv2.LINE_AA)
    grosor = 1 if escala < 1.4 else 2
    for posicion, (texto, color) in enumerate(lineas):
        origen = (8 + int(8 * escala), 8 + int(17 * escala) + posicion * alto_linea)
        cv2.putText(fotograma, texto, origen, cv2.FONT_HERSHEY_SIMPLEX, 0.5 * escala, color, grosor, cv2.LINE_AA)


def renderizar_video(ruta, destino, fps, tamano, analisis, total, codecs):
    captura = cv2.VideoCapture(str(ruta))
    escritor, codec = abrir_escritor(destino, fps, tamano, codecs)
    escala = tamano[0] / 640.0
    dorado = (55, 175, 212)
    blanco = (255, 255, 255)
    i0, i1 = analisis["i0"], analisis["i1"]
    radio = max(8, int(analisis["radio"] * 1.3))
    historial = []
    indice = 0
    while indice < total:
        correcto, fotograma = captura.read()
        if not correcto:
            break
        fotograma = cv2.resize(fotograma, tamano, interpolation=cv2.INTER_AREA)
        if i0 <= indice <= i1:
            k = indice - i0
            centro = (int(analisis["xs"][k]), int(analisis["ys"][k]))
            historial.append((analisis["xs"][k], analisis["ys"][k]))
            dibujar_estela(fotograma, historial[-60:], dorado, escala)
            cv2.circle(fotograma, centro, radio, dorado, max(1, int(2 * escala)), cv2.LINE_AA)
            cv2.circle(fotograma, centro, max(2, int(3 * escala)), blanco, -1, cv2.LINE_AA)
            vx_px = analisis["vx"][k] / analisis["mpp"]
            vy_px = -analisis["vh"][k] / analisis["mpp"]
            longitud = math.hypot(vx_px, vy_px) * 0.1
            if longitud > 4:
                reduccion = min(1.0, 90 * escala / longitud)
                fin = (int(centro[0] + vx_px * 0.1 * reduccion), int(centro[1] + vy_px * 0.1 * reduccion))
                cv2.arrowedLine(fotograma, centro, fin, blanco, max(1, int(2 * escala)), cv2.LINE_AA, tipLength=0.28)
            rapidez = math.hypot(analisis["vx"][k], analisis["vh"][k])
            dibujar_panel(fotograma, [
                ("t = %.2f s" % analisis["t"][k], blanco),
                ("x = %.2f m   h = %.2f m" % (analisis["x"][k], analisis["h"][k]), dorado),
                ("v = %.2f m/s" % rapidez, blanco),
            ], escala, dorado)
        escritor.write(fotograma)
        indice += 1
    captura.release()
    escritor.release()
    return codec


def localizar_ffmpeg():
    ruta = shutil.which("ffmpeg")
    if ruta:
        return ruta
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def transcodificar(entrada, salida):
    ejecutable = localizar_ffmpeg()
    if not ejecutable:
        return False
    orden = [ejecutable, "-y", "-i", str(entrada), "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(salida)]
    try:
        proceso = subprocess.run(orden, capture_output=True, timeout=600)
    except Exception:
        return False
    return proceso.returncode == 0 and Path(salida).exists() and Path(salida).stat().st_size > 0


def procesar_video(ruta, trabajo, experimento, modo, alto_escena, longitud, fps_forzado):
    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        raise ValueError("No se pudo abrir el video. Prueba con un archivo MP4 grabado con la cámara.")
    fps = captura.get(cv2.CAP_PROP_FPS)
    if fps_forzado:
        fps = fps_forzado
    if not fps or math.isnan(fps) or fps < 1 or fps > 480:
        fps = 30.0
    ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if ancho <= 0 or alto <= 0:
        raise ValueError("El video no tiene dimensiones válidas.")
    factor = min(1.0, ANCHO_PROCESO / ancho)
    tamano = (max(2, int(round(ancho * factor)) // 2 * 2), max(2, int(round(alto * factor)) // 2 * 2))
    sustractor = None
    if modo == "auto":
        sustractor = cv2.createBackgroundSubtractorMOG2(history=150, varThreshold=40, detectShadows=True)
    nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    detecciones = []
    while len(detecciones) < MAX_FOTOGRAMAS:
        correcto, fotograma = captura.read()
        if not correcto:
            break
        fotograma = cv2.resize(fotograma, tamano, interpolation=cv2.INTER_AREA)
        detecciones.append(detectar_objeto(fotograma, modo, sustractor, nucleo, len(detecciones)))
    captura.release()
    encontrados = sum(1 for d in detecciones if d is not None)
    if encontrados < 8:
        raise ValueError(
            "No se detectó el objeto en suficientes fotogramas. Usa un objeto de color vivo sobre un fondo "
            "contrastante, elige ese color en la lista y mantén la cámara fija."
        )
    analisis = analizar(detecciones, fps, tamano[1], alto_escena, experimento, longitud)
    crudo = MEDIA_DIR / ("%s_crudo.mp4" % trabajo)
    final = MEDIA_DIR / ("%s_trazado.mp4" % trabajo)
    codecs = ("mp4v",) if localizar_ffmpeg() else ("avc1", "mp4v")
    codec = renderizar_video(ruta, crudo, fps, tamano, analisis, len(detecciones), codecs)
    video_ok = True
    if codec == "avc1":
        crudo.replace(final)
    elif transcodificar(crudo, final):
        crudo.unlink()
    else:
        crudo.replace(final)
        video_ok = False
    grafica = analisis["grafica"]
    paso = max(1, len(grafica["t"]) // 30)
    muestra = []
    for i in range(0, len(grafica["t"]), paso):
        fila = {"t": grafica["t"][i], "x": grafica["x"][i], "h": grafica["h"][i], "e": grafica["e"][i]}
        if grafica["h_teo"]:
            fila["h_teo"] = grafica["h_teo"][i]
        if grafica["x_teo"]:
            fila["x_teo"] = grafica["x_teo"][i]
        muestra.append(fila)
    RESULTADOS[trabajo] = {
        "experimento": EXPERIMENTOS[experimento],
        "modo_deteccion": modo,
        "alto_escena_m": alto_escena,
        "longitud_pendulo_m": longitud,
        "fps": fps,
        "duracion_analizada_s": grafica["t"][-1],
        "energia_ideal_J_por_kg": grafica["e_teo"],
        "metricas": [
            {"nombre": m["etiqueta"], "valor": m["valor"], "unidad": m["unidad"], "nota": m["nota"]}
            for m in analisis["metricas"]
        ],
        "muestra_serie": muestra,
        "creado": time.time(),
    }
    return {
        "ok": True,
        "job": trabajo,
        "video_url": url_for("media", nombre=final.name),
        "video_ok": video_ok,
        "experimento": experimento,
        "fps": fps,
        "metricas": analisis["metricas"],
        "serie": analisis["serie"],
        "grafica": grafica,
    }


def limpiar_media():
    limite = time.time() - 3 * 3600
    for archivo in MEDIA_DIR.iterdir():
        try:
            if archivo.is_file() and archivo.stat().st_mtime < limite:
                archivo.unlink()
        except OSError:
            continue
    if len(RESULTADOS) > 40:
        for clave in sorted(RESULTADOS, key=lambda k: RESULTADOS[k]["creado"])[:-40]:
            RESULTADOS.pop(clave, None)


def leer_numero(valor, defecto, minimo, maximo):
    try:
        numero = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return defecto
    if not math.isfinite(numero) or numero < minimo or numero > maximo:
        return defecto
    return numero


@app.route("/codigo")
def codigo():
    archivo = BASE_DIR / "aether_grafica.py"
    texto = archivo.read_text(encoding="utf-8") if archivo.exists() else ""
    return render_template("codigo.html", codigo=texto, lineas=texto.count("\n") + 1)


@app.route("/codigo/descargar")
def codigo_descargar():
    return send_from_directory(BASE_DIR, "aether_grafica.py", as_attachment=True)


@app.route("/tracker")
def tracker():
    return render_template("tracker.html", experimentos=EXPERIMENTOS, colores=COLORES)


@app.route("/media/<nombre>")
def media(nombre):
    return send_from_directory(MEDIA_DIR, nombre, conditional=True)


@app.route("/api/tracker/procesar", methods=["POST"])
def api_procesar():
    limpiar_media()
    archivo = request.files.get("video")
    if not archivo or not archivo.filename:
        return jsonify(ok=False, error="Adjunta o graba un video para analizar."), 400
    experimento = request.form.get("experimento", "caida")
    if experimento not in EXPERIMENTOS:
        experimento = "caida"
    modo = request.form.get("modo", "auto")
    if modo != "auto" and modo not in RANGOS_COLOR:
        modo = "auto"
    alto_escena = leer_numero(request.form.get("alto_escena"), 2.0, 0.05, 500.0)
    longitud = leer_numero(request.form.get("longitud"), None, 0.05, 100.0) if experimento == "pendulo" else None
    fps_forzado = leer_numero(request.form.get("fps"), None, 1.0, 1000.0)
    trabajo = uuid.uuid4().hex[:12]
    extension = Path(archivo.filename).suffix.lower()
    if extension not in EXTENSIONES_VIDEO:
        extension = ".mp4"
    ruta_entrada = MEDIA_DIR / ("%s_entrada%s" % (trabajo, extension))
    archivo.save(ruta_entrada)
    try:
        respuesta = procesar_video(ruta_entrada, trabajo, experimento, modo, alto_escena, longitud, fps_forzado)
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 422
    except Exception as error:
        return jsonify(ok=False, error="Error al procesar el video: %s" % str(error)[:300]), 500
    finally:
        try:
            ruta_entrada.unlink()
        except OSError:
            pass
    return jsonify(respuesta)


@app.route("/api/tracker/auditar", methods=["POST"])
def api_auditar():
    datos = request.get_json(silent=True) or {}
    registro = RESULTADOS.get(datos.get("job"))
    if not registro:
        return jsonify(ok=False, error="No se encontró el análisis. Procesa el video de nuevo."), 404
    if registro.get("reporte"):
        return jsonify(ok=True, reporte=registro["reporte"])
    contenido = (
        "Datos del experimento analizado con OpenCV (JSON):\n"
        + json.dumps({k: v for k, v in registro.items() if k not in ("creado", "reporte")}, ensure_ascii=False)
    )
    try:
        texto = consultar_gemini(contenido, PROMPT_AUDITOR, 0.4)
    except Exception as error:
        return jsonify(ok=False, error=mensaje_error(error)), 502
    registro["reporte"] = normalizar_texto(texto)
    return jsonify(ok=True, reporte=registro["reporte"])


def obtener_ip_local():
    try:
        sonda = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sonda.connect(("8.8.8.8", 80))
        direccion = sonda.getsockname()[0]
        sonda.close()
        return direccion
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    puerto = int(os.getenv("PORT", "5000"))
    print("\n  Aether en marcha")
    print("  En esta laptop:   http://127.0.0.1:%d" % puerto)
    print("  Desde tu teléfono (misma red Wi-Fi):   http://%s:%d\n" % (obtener_ip_local(), puerto))
    app.run(host="0.0.0.0", port=puerto, debug=False, threaded=True)
