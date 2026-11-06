"""A file behind every seeded document (audit 2026-11-05, V-15).

db/supabase/seed.sql writes document rows with a storage_path and an
extracted_data, and uploads nothing, so opening a seeded document in the demo
found no file (27 of the 38 documents in production on 2026-11-05). This
generates, for each seeded document row whose Storage object is missing, a
plausible file of the type its path names, showing the same names and values
its extracted_data holds, and uploads it to that path in the `documents`
bucket.

    python upload_demo_files.py                 # dry run: lists what it would upload
    python upload_demo_files.py --out ./preview # dry run, and writes the files here to look at
    python upload_demo_files.py --apply         # uploads

Credentials come from the environment: SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY. The key is sent as a header and never printed.

What it will not do:
  - overwrite an object that exists (x-upsert: false, and it checks first);
  - touch a row that is not in the seed (the seed's fixed document ids);
  - upload for a document still `uploaded` unless --include-unread is given.
    ai-orchestrator's sweep extracts a received document whose file has
    appeared (pipeline_sweep_candidates, kind `extract`), which is a paid model
    call and changes what the demo shows. With --include-unread that is what
    happens next, on purpose.

Same approach as qa/2026-10-02/make_fixtures.py: invented people and issuers,
plain cards with no emblem or security feature, nothing stamped "ficticio" (the
extraction agent reads that as tampering), and the same bytes on every run —
nothing random but what is seeded from the document id, no timestamps.

Needs Pillow (and reportlab only for a .pdf path, which the seed has none of).
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SEED = HERE.parent.parent / "db" / "supabase" / "seed.sql"
BUCKET = "documents"

# --------------------------------------------------------------------------
# The seed's document ids
# --------------------------------------------------------------------------

UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def seeded_document_ids(seed: Path = SEED) -> list[str]:
    """The first id of every row of the seed's `insert into documents` statements."""
    text = seed.read_text(encoding="utf-8")
    ids: list[str] = []
    for statement in re.finditer(r"insert into documents \(.*?;\n", text, re.S):
        ids += re.findall(rf"^\s*\('({UUID})'", statement.group(0), re.M)
    return ids


# --------------------------------------------------------------------------
# Supabase, over plain HTTP (no SDK to install)
# --------------------------------------------------------------------------


class Supabase:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self._key = key

    def _request(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None):
        request = urllib.request.Request(self.url + path, data=body, method=method)
        request.add_header("apikey", self._key)
        request.add_header("Authorization", f"Bearer {self._key}")
        for k, v in (headers or {}).items():
            request.add_header(k, v)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()

    def rows(self, table: str, select: str, ids: list[str]) -> list[dict]:
        query = urllib.parse.urlencode({"select": select, "id": f"in.({','.join(ids)})"})
        status, body = self._request("GET", f"/rest/v1/{table}?{query}")
        if status != 200:
            raise SystemExit(f"reading {table} failed: HTTP {status} {body[:300]!r}")
        return json.loads(body)

    def object_exists(self, path: str) -> bool:
        folder, _, name = path.rpartition("/")
        payload = json.dumps({"prefix": folder, "limit": 1000, "offset": 0, "search": name}).encode()
        status, body = self._request("POST", f"/storage/v1/object/list/{BUCKET}", payload,
                                     {"content-type": "application/json"})
        if status != 200:
            raise SystemExit(f"listing {folder} failed: HTTP {status} {body[:300]!r}")
        return any(entry.get("name") == name for entry in json.loads(body))

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        quoted = urllib.parse.quote(path)
        status, body = self._request("POST", f"/storage/v1/object/{BUCKET}/{quoted}", data,
                                     {"content-type": content_type, "x-upsert": "false"})
        if status not in (200, 201):
            raise RuntimeError(f"HTTP {status} {body[:300]!r}")


# --------------------------------------------------------------------------
# What a document shows
# --------------------------------------------------------------------------

LABELS = {
    "full_name": "Nombre",
    "national_id": "DUI",
    "date_of_birth": "Fecha de nacimiento",
    "employer": "Empresa",
    "monthly_income": "Salario mensual (US$)",
    "issued_on": "Fecha de emisión",
    "issue_date": "Fecha de emisión",
    "condition_count": "Condiciones crónicas activas",
    "blood_pressure": "Presión arterial (mmHg)",
    "last_visit": "Última consulta",
    "glucose_mg_dl": "Glucosa en ayunas (mg/dL)",
    "cholesterol_total": "Colesterol total (mg/dL)",
    "hemoglobin": "Hemoglobina (g/dL)",
    "bmi": "Índice de masa corporal",
    "smoker": "Fumador",
}

TITLES = {
    "national_id": "DOCUMENTO ÚNICO DE IDENTIDAD",
    "proof_of_income": "CONSTANCIA DE SALARIO",
    "medical_report": "INFORME MÉDICO",
    "lab_results": "RESULTADOS DE LABORATORIO",
}

# Invented issuers, one per kind of document. Never a real body's name.
ISSUERS = {
    "medical_report": "Consultorio Médico Los Almendros",
    "lab_results": "Laboratorio Clínico San Rafael",
}

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fields_of(extracted: dict | None) -> dict[str, object]:
    out: dict[str, object] = {}
    for f in (extracted or {}).get("fields") or []:
        if isinstance(f, dict) and isinstance(f.get("key"), str) and f.get("value") is not None:
            out.setdefault(f["key"], f["value"])
    return out


def long_date(iso: str | None) -> str:
    if not iso or not re.match(r"^\d{4}-\d{2}-\d{2}", str(iso)):
        return "—"
    y, m, d = (int(x) for x in str(iso)[:10].split("-"))
    return f"{d} de {MONTHS[m - 1]} de {y}"


def money(value: object) -> str:
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return str(value)


def facts_for(row: dict, client: dict | None) -> dict:
    """Everything a rendering needs, from the row, falling back to the client
    for a document that has not been read yet (extracted_data is {})."""
    extracted = row.get("extracted_data") or {}
    fields = fields_of(extracted)
    client = client or {}
    return {
        "doc_type": row["doc_type"],
        "seed": row["id"],
        "full_name": fields.get("full_name") or client.get("full_name") or "Titular",
        "national_id": fields.get("national_id") or client.get("national_id") or "—",
        "date_of_birth": fields.get("date_of_birth") or client.get("date_of_birth"),
        "issue_date": extracted.get("issue_date") or fields.get("issued_on") or fields.get("issue_date"),
        "expiry_date": extracted.get("expiry_date"),
        "fields": fields,
    }


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

FONT_DIRS = [Path(r"C:\Windows\Fonts"), Path("/usr/share/fonts/truetype/dejavu"), Path("/Library/Fonts")]
FONT_FILES = {"regular": ["arial.ttf", "DejaVuSans.ttf", "Arial.ttf"],
              "bold": ["arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"]}


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for folder in FONT_DIRS:
        for name in FONT_FILES[weight]:
            if (folder / name).exists():
                return ImageFont.truetype(str(folder / name), size)
    return ImageFont.load_default(size=size)


def signature(d: ImageDraw.ImageDraw, x: int, y: int, seed: str, ink: str = "#1b2a6b") -> None:
    """A scribble on the signature line, the same for the same document on every run."""
    rnd = random.Random(seed)
    px, py = x, y
    for _ in range(9):
        nx, ny = px + rnd.randint(18, 34), y + rnd.randint(-22, 10)
        d.line([px, py, nx, ny], fill=ink, width=3)
        px, py = nx, ny


def stamp(d: ImageDraw.ImageDraw, cx: int, cy: int, issuer: str, centre: str) -> None:
    violet = "#4b3fa0"
    d.ellipse([cx - 95, cy - 95, cx + 95, cy + 95], outline=violet, width=4)
    d.ellipse([cx - 70, cy - 70, cx + 70, cy + 70], outline=violet, width=2)
    d.text((cx, cy - 112), issuer.upper()[:34], font=font(16, "bold"), fill=violet, anchor="mm")
    d.text((cx, cy), centre.upper()[:12], font=font(22, "bold"), fill=violet, anchor="mm")


def render_id_card(f: dict) -> Image.Image:
    w, h = 1012, 638
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, w - 5, h - 5], radius=36, fill="#eef3f7", outline="#9db3c6", width=3)
    d.rectangle([4, 96, w - 5, 100], fill="#2f5f8a")
    d.text((w // 2, 52), TITLES["national_id"], font=font(34, "bold"), fill="#1f3f5f", anchor="mm")

    # Photo placeholder: a plain silhouette, no likeness of anyone.
    px, py = 48, 130
    d.rounded_rectangle([px, py, px + 250, py + 320], radius=12, fill="#cfd8e0", outline="#9db3c6", width=2)
    d.ellipse([px + 75, py + 50, px + 175, py + 160], fill="#8fa3b5")
    d.pieslice([px + 30, py + 170, px + 220, py + 400], 180, 360, fill="#8fa3b5")

    words = str(f["full_name"]).upper().split()
    nombres, apellidos = (" ".join(words[:-2]), " ".join(words[-2:])) if len(words) > 2 else (words[0] if words else "", " ".join(words[1:]))
    rows = [("APELLIDOS", apellidos), ("NOMBRES", nombres),
            ("FECHA DE NACIMIENTO", long_date(f["date_of_birth"]).upper())]
    x, y = 330, 128
    for k, v in rows:
        d.text((x, y), k, font=font(19), fill="#4a6278")
        d.text((x, y + 22), v, font=font(27, "bold"), fill="#111111")
        y += 72
    d.text((48, 478), "NÚMERO DE DUI", font=font(19), fill="#4a6278")
    d.text((48, 500), str(f["national_id"]), font=font(40, "bold"), fill="#111111")
    if f["expiry_date"]:
        d.text((560, 478), "FECHA DE VENCIMIENTO", font=font(19), fill="#4a6278")
        d.text((560, 500), long_date(f["expiry_date"]).upper(), font=font(27, "bold"), fill="#111111")
    d.line([330, 590, 700, 590], fill="#4a6278", width=2)
    signature(d, 360, 575, f["seed"])
    d.text((330, 596), "FIRMA DEL TITULAR", font=font(16), fill="#4a6278")
    return img


def render_page(f: dict) -> Image.Image:
    """A letter-size page at 150 dpi: a constancia, an informe or lab results."""
    w, h = 1275, 1650
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    doc_type = f["doc_type"]
    fields = f["fields"]
    issuer = str(fields.get("employer") or ISSUERS.get(doc_type) or "Emisor")

    d.text((120, 110), issuer, font=font(40, "bold"), fill="#1f3f5f")
    d.rectangle([120, 175, w - 120, 179], fill="#2f5f8a")
    d.text((w // 2, 250), TITLES.get(doc_type, doc_type.replace("_", " ").upper()), font=font(34, "bold"),
           fill="#111111", anchor="mm")
    d.text((w - 120, 320), f"San Salvador, {long_date(f['issue_date'])}", font=font(24), fill="#111111", anchor="ra")

    body = font(26)
    y = 400
    if doc_type == "proof_of_income":
        text = (f"Por medio de la presente hacemos constar que {f['full_name']}, con Documento Único de "
                f"Identidad número {f['national_id']}, labora en esta empresa y devenga un salario mensual "
                f"de US$ {money(fields.get('monthly_income', '—'))}. Se extiende la presente a solicitud "
                f"del interesado para los usos que estime convenientes.")
    else:
        text = f"Paciente: {f['full_name']}. DUI {f['national_id']}."
    for line in wrap(d, text, body, w - 240):
        d.text((120, y), line, font=body, fill="#111111")
        y += 40

    shown = [(k, v) for k, v in fields.items() if k not in ("full_name", "national_id", "employer")]
    if doc_type != "proof_of_income" and shown:
        y += 30
        for k, v in shown:
            d.rectangle([120, y, w - 120, y + 56], outline="#9db3c6", width=2)
            d.text((140, y + 14), LABELS.get(k, k.replace("_", " ")), font=font(24), fill="#4a6278")
            d.text((w - 140, y + 14), str(v), font=font(24, "bold"), fill="#111111", anchor="ra")
            y += 56

    d.line([120, 1320, 560, 1320], fill="#4a6278", width=2)
    signature(d, 150, 1300, f["seed"])
    d.text((120, 1332), "Firma y sello", font=font(22), fill="#4a6278")
    stamp(d, 900, 1300, issuer, "RR. HH." if doc_type == "proof_of_income" else "Sello")
    return img


def wrap(d: ImageDraw.ImageDraw, text: str, f, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if d.textlength(candidate, font=f) <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def render(facts: dict, storage_path: str) -> tuple[bytes, str]:
    """The file's bytes and its content type, chosen by the path's extension."""
    ext = storage_path.rsplit(".", 1)[-1].lower()
    image = render_id_card(facts) if facts["doc_type"] == "national_id" else render_page(facts)
    if ext == "pdf":
        return render_pdf(image), "application/pdf"
    buffer = io.BytesIO()
    if ext in ("jpg", "jpeg"):
        image.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue(), "image/jpeg"
    if ext == "png":
        image.save(buffer, format="PNG")
        return buffer.getvalue(), "image/png"
    if ext == "webp":
        image.save(buffer, format="WEBP", quality=90)
        return buffer.getvalue(), "image/webp"
    raise ValueError(f"no renderer for .{ext}")


def render_pdf(image: Image.Image) -> bytes:
    from reportlab import rl_config
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    rl_config.invariant = 1  # no creation date or random id: same bytes every run
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawImage(ImageReader(image), 0, 0, width=letter[0], height=letter[1])
    c.showPage()
    c.save()
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="upload; without it this is a dry run")
    parser.add_argument("--include-unread", action="store_true",
                        help="also upload for documents still `uploaded` (the sweep will then extract them, a paid call)")
    parser.add_argument("--out", type=Path, help="also write each generated file under this folder")
    args = parser.parse_args(argv)

    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.", file=sys.stderr)
        return 2
    api = Supabase(url, key)

    ids = seeded_document_ids()
    rows = api.rows("documents", "id,application_id,doc_type,status,storage_path,extracted_data", ids)
    found = {r["id"] for r in rows}
    apps = api.rows("applications", "id,clients(full_name,national_id,date_of_birth)",
                    sorted({r["application_id"] for r in rows})) if rows else []
    client_of = {a["id"]: a.get("clients") for a in apps}

    print(f"{'DRY RUN — ' if not args.apply else ''}{len(ids)} seeded documents, {len(rows)} in the database")
    counts = {"exists": 0, "upload": 0, "skipped": 0, "missing_row": 0, "failed": 0}
    for doc_id in ids:
        if doc_id not in found:
            print(f"  {doc_id}  no such row — skipped")
            counts["missing_row"] += 1
    for row in sorted(rows, key=lambda r: r["id"]):
        path = row["storage_path"]
        label = f"  {row['id']}  {row['doc_type']:<16} {row['status']:<10}"
        if api.object_exists(path):
            print(f"{label} file present")
            counts["exists"] += 1
            continue
        if row["status"] == "uploaded" and not args.include_unread:
            print(f"{label} missing — skipped (unread; --include-unread to upload)")
            counts["skipped"] += 1
            continue
        data, content_type = render(facts_for(row, client_of.get(row["application_id"])), path)
        if args.out:
            target = args.out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if not args.apply:
            print(f"{label} missing — would upload {len(data):,} bytes ({content_type}) to {path}")
            counts["upload"] += 1
            continue
        try:
            api.upload(path, data, content_type)
            print(f"{label} uploaded {len(data):,} bytes to {path}")
            counts["upload"] += 1
        except RuntimeError as err:
            print(f"{label} FAILED: {err}")
            counts["failed"] += 1

    verb = "uploaded" if args.apply else "to upload"
    print(f"{counts['exists']} present, {counts['upload']} {verb}, {counts['skipped']} skipped, "
          f"{counts['missing_row']} rows not found, {counts['failed']} failed")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
