"""Synthetic documents for the 2026-10-02 pipeline run (BLK-5).

Invented people, invented employer, clinic and lab. Nothing here copies an
official design: the ID card is a plain data card with no emblem, issuer
branding or security features. No "ficticio" stamp either - the 2026-09-13 run
showed the extraction agent treats one as tampering and blocks scoring.

Each PDF is signed and stamped by whoever issued it. On 2026-11-03 Sonnet 5.5
flagged the constancia's blank signature line ("no se observa firma ni sello de
la empresa"), which made it stop counting as a required document. The stamps
carry the invented issuer's own name, never a real body's.
"""
import math
import random
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parent

# Same bytes on every run: no creation date or random document id in the PDFs,
# so regenerating changes a file only when what it shows changes.
rl_config.invariant = 1
FONTS = Path(r"C:\Windows\Fonts")


def dui(base8: str) -> str:
    """Salvadoran DUI: 8 digits, weights 9..2, check = (10 - sum % 10) % 10."""
    total = sum(int(d) * w for d, w in zip(base8, range(9, 1, -1)))
    return f"{base8}-{(10 - total % 10) % 10}"


KARLA = {
    "apellidos": "HERNÁNDEZ QUINTANILLA",
    "nombres": "KARLA BEATRIZ",
    "full": "Karla Beatriz Hernández Quintanilla",
    "dob": date(1989, 7, 23),
    "birthplace": "SANTA TECLA, LA LIBERTAD",
    "sex": "F",
    "dui": dui("05392718"),
    "issued": date(2022, 5, 17),
    "expires": date(2030, 5, 16),
    "address": "RESIDENCIAL LAS MARGARITAS, PASAJE 4, CASA 17",
    "municipio": "SANTA TECLA",
    "departamento": "LA LIBERTAD",
    "estado_familiar": "SOLTERA",
    "profesion": "LICENCIADA EN ADMINISTRACIÓN DE EMPRESAS",
}
JOSE = {
    "apellidos": "MENJÍVAR PORTILLO",
    "nombres": "JOSÉ ALBERTO",
    "full": "José Alberto Menjívar Portillo",
    "dob": date(1984, 11, 2),
    "birthplace": "SAN MIGUEL, SAN MIGUEL",
    "sex": "M",
    "dui": dui("03871264"),
    "issued": date(2023, 2, 8),
    "expires": date(2031, 2, 7),
    "address": "COLONIA CIUDAD JARDÍN, CALLE LOS ALMENDROS, CASA 9",
    "municipio": "SAN MIGUEL",
    "departamento": "SAN MIGUEL",
    "estado_familiar": "CASADO",
    "profesion": "TÉCNICO EN MANTENIMIENTO INDUSTRIAL",
}

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def long_date(d: date) -> str:
    return f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"


def card_date(d: date) -> str:
    return f"{d.day:02d} {MONTHS[d.month - 1][:3].upper()} {d.year}"


# --------------------------------------------------------------------------
# ID cards (PNG, CR80 proportions at ~300 dpi)
# --------------------------------------------------------------------------
def id_card(person: dict, path: Path) -> None:
    w, h = 1012, 638
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, w - 5, h - 5], radius=36, fill="#eef3f7", outline="#9db3c6", width=3)
    d.rectangle([4, 96, w - 5, 100], fill="#2f5f8a")

    bold = ImageFont.truetype(str(FONTS / "arialbd.ttf"), 34)
    label = ImageFont.truetype(str(FONTS / "arial.ttf"), 19)
    value = ImageFont.truetype(str(FONTS / "arialbd.ttf"), 27)
    d.text((w // 2, 52), "DOCUMENTO ÚNICO DE IDENTIDAD", font=bold, fill="#1f3f5f", anchor="mm")

    # Photo placeholder: a plain silhouette, no likeness of anyone.
    px, py = 48, 130
    d.rounded_rectangle([px, py, px + 250, py + 320], radius=12, fill="#cfd8e0", outline="#9db3c6", width=2)
    d.ellipse([px + 75, py + 50, px + 175, py + 160], fill="#8fa3b5")
    d.pieslice([px + 30, py + 170, px + 220, py + 400], 180, 360, fill="#8fa3b5")

    rows = [
        ("APELLIDOS", person["apellidos"]),
        ("NOMBRES", person["nombres"]),
        ("FECHA DE NACIMIENTO", card_date(person["dob"])),
        ("LUGAR DE NACIMIENTO", person["birthplace"]),
        ("SEXO", person["sex"]),
    ]
    x, y = 330, 128
    for k, v in rows:
        d.text((x, y), k, font=label, fill="#4a6278")
        d.text((x, y + 22), v, font=value, fill="#111111")
        y += 64

    d.text((48, 478), "NÚMERO DE DUI", font=label, fill="#4a6278")
    d.text((48, 500), person["dui"], font=ImageFont.truetype(str(FONTS / "arialbd.ttf"), 40), fill="#111111")
    d.text((490, 478), "FECHA DE EXPEDICIÓN", font=label, fill="#4a6278")
    d.text((490, 500), card_date(person["issued"]), font=value, fill="#111111")
    d.text((735, 478), "FECHA DE VENCIMIENTO", font=label, fill="#4a6278")
    d.text((735, 500), card_date(person["expires"]), font=value, fill="#111111")
    d.line([330, 590, 700, 590], fill="#4a6278", width=2)
    d.text((330, 596), "FIRMA DEL TITULAR", font=ImageFont.truetype(str(FONTS / "arial.ttf"), 16), fill="#4a6278")
    img.save(path)


def id_card_back(person: dict, path: Path) -> None:
    """The reverso: where the person lives, and their estado familiar and
    profession. Same plain card as the front, no emblem or security features."""
    w, h = 1012, 638
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, w - 5, h - 5], radius=36, fill="#eef3f7", outline="#9db3c6", width=3)
    d.rectangle([4, 96, w - 5, 100], fill="#2f5f8a")

    bold = ImageFont.truetype(str(FONTS / "arialbd.ttf"), 30)
    label = ImageFont.truetype(str(FONTS / "arial.ttf"), 19)
    value = ImageFont.truetype(str(FONTS / "arialbd.ttf"), 26)
    d.text((w // 2, 52), "DOCUMENTO ÚNICO DE IDENTIDAD · REVERSO", font=bold, fill="#1f3f5f", anchor="mm")

    rows = [
        ("DIRECCIÓN DE RESIDENCIA", person["address"]),
        ("MUNICIPIO", person["municipio"]),
        ("DEPARTAMENTO", person["departamento"]),
        ("ESTADO FAMILIAR", person["estado_familiar"]),
        ("PROFESIÓN U OFICIO", person["profesion"]),
    ]
    x, y = 48, 128
    for k, v in rows:
        d.text((x, y), k, font=label, fill="#4a6278")
        d.text((x, y + 22), v, font=value, fill="#111111")
        y += 70

    d.text((48, 500), "NÚMERO DE DUI", font=label, fill="#4a6278")
    d.text((48, 522), person["dui"], font=ImageFont.truetype(str(FONTS / "arialbd.ttf"), 34), fill="#111111")
    img.save(path)


# --------------------------------------------------------------------------
# PDFs
# --------------------------------------------------------------------------
styles = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=11, leading=16, alignment=TA_JUSTIFY)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=9, leading=12, textColor=colors.HexColor("#444444"))
RIGHT = ParagraphStyle("right", parent=BODY, alignment=TA_RIGHT)
HEAD = ParagraphStyle("head", parent=BODY, fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.HexColor("#1f3f5f"))
TITLE = ParagraphStyle("title", parent=BODY, fontName="Helvetica-Bold", fontSize=13, leading=18, alignment=1, spaceBefore=6, spaceAfter=6)
LABEL = ParagraphStyle("label", parent=BODY, fontName="Helvetica-Bold", fontSize=10.5, leading=14)


def build(path: Path, story: list) -> None:
    SimpleDocTemplate(str(path), pagesize=letter, leftMargin=2.5 * cm, rightMargin=2.5 * cm,
                      topMargin=2 * cm, bottomMargin=2 * cm, title=path.stem, author="").build(story)


def rule() -> Table:
    t = Table([[""]], colWidths=[16.5 * cm], rowHeights=[2])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.2, colors.HexColor("#2f5f8a"))]))
    return t


class SignedAndStamped(Flowable):
    """A handwritten-looking signature on the line, and the issuer's round stamp beside it.

    The signature is loops of Bezier curves from a seed, so each signer's is
    the same on every run. The stamp is two rings with the issuer's name around
    them and a word in the middle, in stamp-pad violet, a little crooked.
    """

    INK = colors.HexColor("#1b2a6b")
    STAMP = colors.HexColor("#4b3fa0")

    def __init__(self, seed: str, ring: str, centre: str):
        super().__init__()
        self.seed, self.ring, self.centre = seed, ring, centre
        self.width, self.height = 16.5 * cm, 3.2 * cm

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        c = self.canv
        line_y = 0.55 * cm
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.6)
        c.line(0, line_y, 6.2 * cm, line_y)
        self._signature(c, x0=0.4 * cm, y0=line_y + 0.35 * cm)
        self._stamp(c, cx=8.0 * cm, cy=1.65 * cm, radius=1.35 * cm)

    def _signature(self, c, x0: float, y0: float):
        rng = random.Random(self.seed)
        c.saveState()
        c.translate(x0, y0)
        # Handwriting leans right.
        c.transform(1, 0, 0.32, 1, 0, 0)
        c.setStrokeColor(self.INK)
        c.setLineWidth(1.1)
        c.setLineCap(1)
        c.setLineJoin(1)
        path = c.beginPath()
        # A tall initial, then lower letters of uneven height and width, the
        # way a name trails off when it is signed fast.
        path.moveTo(0, 0.15 * cm)
        path.curveTo(0.1 * cm, 1.9 * cm, 0.7 * cm, 1.9 * cm, 0.45 * cm, 0.1 * cm)
        x, y = 0.45 * cm, 0.1 * cm
        for i in range(rng.randint(5, 7)):
            dx = rng.uniform(0.22, 0.5) * cm
            rise = rng.uniform(0.35, 0.95) * cm * (1 - i * 0.07)
            path.curveTo(x + dx * 0.1, y + rise, x + dx * 0.8, y + rise * rng.uniform(0.6, 1.0), x + dx * 0.5, y + 0.05 * cm)
            path.curveTo(x + dx * 0.35, y - 0.12 * cm, x + dx * 0.9, y - 0.1 * cm, x + dx, y + rng.uniform(-0.06, 0.1) * cm)
            x, y = x + dx, y + rng.uniform(-0.05, 0.05) * cm
        # The stroke back across the name, and off the end.
        path.curveTo(x + 0.5 * cm, y + 0.3 * cm, x * 0.55, 0.55 * cm, -0.15 * cm, 0.35 * cm)
        c.drawPath(path, stroke=1, fill=0)
        c.restoreState()

    def _stamp(self, c, cx: float, cy: float, radius: float):
        c.saveState()
        c.translate(cx, cy)
        c.rotate(-11)
        c.setStrokeColor(self.STAMP)
        c.setFillColor(self.STAMP)
        c.setStrokeAlpha(0.85)
        c.setFillAlpha(0.85)
        c.setLineWidth(1.6)
        c.circle(0, 0, radius, stroke=1, fill=0)
        c.setLineWidth(0.7)
        c.circle(0, 0, radius * 0.66, stroke=1, fill=0)
        self._ring_text(c, self.ring.upper(), radius * 0.83, "Helvetica-Bold", 6)
        # The middle word or words, one per line, inside the inner ring.
        size, lines = 6.4, self.centre.upper().split()
        c.setFont("Helvetica-Bold", size)
        top = (len(lines) - 1) * size * 1.15 / 2
        for i, line in enumerate(lines):
            c.drawCentredString(0, top - i * size * 1.15 - size / 3, line)
        c.restoreState()

    @staticmethod
    def _ring_text(c, text: str, radius: float, font: str, size: float):
        """Characters around the circle, clockwise, centred on the top."""
        c.setFont(font, size)
        widths = [stringWidth(ch, font, size) for ch in text]
        angle = math.pi / 2 + sum(widths) / radius / 2
        for ch, w in zip(text, widths):
            angle -= w / 2 / radius
            c.saveState()
            c.translate(radius * math.cos(angle), radius * math.sin(angle))
            c.rotate(math.degrees(angle) - 90)
            c.drawCentredString(0, -size / 3, ch)
            c.restoreState()
            angle -= w / 2 / radius


def salary_certificate(path: Path) -> None:
    issued = date(2026, 9, 28)
    story = [
        Paragraph("Grupo Comercial Nubeluna, S.A. de C.V.", HEAD),
        Paragraph("Calle La Reforma N.º 418, Colonia San Benito, San Salvador, El Salvador", SMALL),
        Paragraph("recursoshumanos@nubeluna.com.sv", SMALL),
        Spacer(1, 4), rule(), Spacer(1, 18),
        Paragraph(f"San Salvador, {long_date(issued)}", RIGHT),
        Spacer(1, 22),
        Paragraph("CONSTANCIA DE SALARIO", TITLE),
        Spacer(1, 14),
        Paragraph("A quien interese:", BODY),
        Spacer(1, 10),
        Paragraph(
            f"Por medio de la presente, Grupo Comercial Nubeluna, S.A. de C.V. hace constar que la señora "
            f"<b>{KARLA['full']}</b>, con Documento Único de Identidad número <b>{KARLA['dui']}</b>, labora "
            f"en esta empresa desde el 4 de marzo de 2019, desempeñando el cargo de <b>Analista de Compras</b> "
            f"en el Departamento de Abastecimiento, con contrato por tiempo indefinido.", BODY),
        Spacer(1, 10),
        Paragraph(
            "Su salario nominal mensual es de <b>US$ 2,400.00</b> (dos mil cuatrocientos dólares de los "
            "Estados Unidos de América), sobre el cual se efectúan los descuentos de ley.", BODY),
        Spacer(1, 10),
        Paragraph(
            "Se extiende la presente a solicitud de la interesada, para los usos que estime convenientes, en la "
            "ciudad de San Salvador, a los veintiocho días del mes de septiembre de dos mil veintiséis.", BODY),
        Spacer(1, 14),
        SignedAndStamped("Marta Elisa Rivas Durán", "Grupo Comercial Nubeluna, S.A. de C.V.", "Recursos Humanos"),
        Paragraph("Lcda. Marta Elisa Rivas Durán", LABEL),
        Paragraph("Gerente de Recursos Humanos", BODY),
        Paragraph("Grupo Comercial Nubeluna, S.A. de C.V.", BODY),
    ]
    build(path, story)


def lab_results(path: Path) -> None:
    sampled, issued = date(2026, 9, 22), date(2026, 9, 23)
    patient = Table([
        [Paragraph("<b>Paciente:</b> " + JOSE["full"], BODY), Paragraph("<b>Edad:</b> 41 años", BODY)],
        [Paragraph("<b>DUI:</b> " + JOSE["dui"], BODY), Paragraph("<b>Sexo:</b> Masculino", BODY)],
        [Paragraph("<b>Toma de muestra:</b> " + long_date(sampled), BODY), Paragraph("<b>Emisión:</b> " + long_date(issued), BODY)],
        [Paragraph("<b>Médico solicitante:</b> Dr. Ricardo Ernesto Alfaro Mejía", BODY), Paragraph("<b>Orden:</b> VS-2026-08841", BODY)],
    ], colWidths=[9 * cm, 7.5 * cm])
    patient.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))

    rows = [["Prueba", "Resultado", "Unidades", "Valores de referencia"],
            ["Glucosa en ayunas", "98", "mg/dL", "70 – 100"],
            ["Hemoglobina glicosilada (HbA1c)", "5.4", "%", "4.0 – 5.6"],
            ["Colesterol total", "186", "mg/dL", "Menor de 200"],
            ["Colesterol HDL", "48", "mg/dL", "Mayor de 40"],
            ["Colesterol LDL", "112", "mg/dL", "Menor de 130"],
            ["Triglicéridos", "131", "mg/dL", "Menor de 150"],
            ["Creatinina", "0.9", "mg/dL", "0.7 – 1.3"]]
    results = Table(rows, colWidths=[6.6 * cm, 2.6 * cm, 2.4 * cm, 4.9 * cm])
    results.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10.5),
        ("FONT", (0, 1), (-1, -1), "Helvetica", 10.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3ecf3")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#2f5f8a")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor("#c8d3dc")),
        ("ALIGN", (1, 1), (2, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story = [
        Paragraph("Laboratorio Clínico Valle Sereno", HEAD),
        Paragraph("Avenida Masferrer Norte N.º 233, San Salvador, El Salvador", SMALL),
        Spacer(1, 4), rule(), Spacer(1, 12),
        Paragraph("INFORME DE RESULTADOS — QUÍMICA SANGUÍNEA", TITLE),
        Spacer(1, 8), patient, Spacer(1, 16), results, Spacer(1, 14),
        Paragraph("Muestra de sangre venosa tomada tras ayuno de 10 horas.", SMALL),
        Spacer(1, 6),
        SignedAndStamped("Sofía Margarita Chávez Ayala", "Laboratorio Clínico Valle Sereno", "Validado"),
        Paragraph("Lic. Sofía Margarita Chávez Ayala", LABEL),
        Paragraph("Química Clínica — Responsable de validación", BODY),
    ]
    build(path, story)


def medical_report(path: Path) -> None:
    issued = date(2026, 8, 30)
    story = [
        Paragraph("Consultorio de Medicina Interna", HEAD),
        Paragraph("Dr. Ricardo Ernesto Alfaro Mejía — Calle El Mirador N.º 52, Colonia Escalón, San Salvador", SMALL),
        Spacer(1, 4), rule(), Spacer(1, 14),
        Paragraph(f"San Salvador, {long_date(issued)}", RIGHT),
        Spacer(1, 12),
        Paragraph("INFORME MÉDICO", TITLE),
        Spacer(1, 10),
        Paragraph(f"<b>Paciente:</b> {JOSE['full']} &nbsp;&nbsp; <b>Edad:</b> 41 años &nbsp;&nbsp; <b>DUI:</b> {JOSE['dui']}", BODY),
        Spacer(1, 12),
        Paragraph("Antecedentes personales patológicos", LABEL),
        Paragraph("Hipertensión arterial esencial diagnosticada en 2021, en tratamiento con losartán 50 mg cada día, "
                  "con buen control en los últimos doce meses. Sin otros antecedentes patológicos de importancia.", BODY),
        Spacer(1, 8),
        Paragraph("Hábitos", LABEL),
        Paragraph("No fuma. Consumo ocasional de alcohol. Actividad física moderada tres veces por semana.", BODY),
        Spacer(1, 8),
        Paragraph("Examen físico", LABEL),
        Paragraph("Presión arterial 128/82 mmHg, frecuencia cardiaca 72 lpm. Peso 84 kg, talla 1.75 m, "
                  "índice de masa corporal 27.4 kg/m<super>2</super>. Examen cardiopulmonar sin hallazgos patológicos.", BODY),
        Spacer(1, 8),
        Paragraph("Diagnósticos", LABEL),
        Paragraph("1. Hipertensión arterial esencial, controlada.", BODY),
        Spacer(1, 8),
        Paragraph("Total de condiciones crónicas activas: 1.", BODY),
        Spacer(1, 10),
        SignedAndStamped("Ricardo Ernesto Alfaro Mejía", "Consultorio Dr. R. E. Alfaro Mejía", "Medicina Interna"),
        Paragraph("Dr. Ricardo Ernesto Alfaro Mejía", LABEL),
        Paragraph("Medicina Interna", BODY),
    ]
    build(path, story)


if __name__ == "__main__":
    (OUT / "seguros").mkdir(parents=True, exist_ok=True)
    (OUT / "medico").mkdir(parents=True, exist_ok=True)
    id_card(KARLA, OUT / "seguros" / "dui-karla-hernandez.png")
    id_card_back(KARLA, OUT / "seguros" / "dui-karla-hernandez-reverso.png")
    salary_certificate(OUT / "seguros" / "constancia-salario-karla-hernandez.pdf")
    id_card(JOSE, OUT / "medico" / "dui-jose-menjivar.png")
    id_card_back(JOSE, OUT / "medico" / "dui-jose-menjivar-reverso.png")
    lab_results(OUT / "medico" / "resultados-laboratorio-jose-menjivar.pdf")
    medical_report(OUT / "medico" / "informe-medico-jose-menjivar.pdf")
    print("Karla DUI", KARLA["dui"], "| José DUI", JOSE["dui"])
    for p in sorted(OUT.rglob("*.*")):
        print(p.relative_to(OUT), p.stat().st_size, "bytes")
