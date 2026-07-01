"""Extração de texto de material (PDF/imagem) — issue #33.

Primeiro passo das funcionalidades pedagógicas: receber um PDF/imagem e extrair
o texto (base de resumo, questão e card). Duas estratégias:

- **PDF nativo** → PyMuPDF (texto direto, rápido).
- **PDF escaneado / imagem** → OCR, atrás da interface ``OcrEngine``
  (Tesseract local ↔ AWS Textract, trocáveis por configuração).

O texto extraído **nunca volta cru ao chat**: vira artefato recuperável e entra
no contexto apenas como resumo, dentro da cota do contrato de ferramentas
(``fit_to_budget``, issue #32). A decisão entre nativo e OCR é heurística: se o
texto nativo é esparso demais (poucos chars por página), assume-se escaneado.

⚠️ Licença: PyMuPDF é AGPL — reavaliar ``pypdf``/``pdfplumber`` se o produto for
fechado/SaaS. OCR é ~1000× mais lento que a extração nativa → idealmente roda em
job assíncrono.
"""

from __future__ import annotations

import io
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger("thinkai.extraction")


@dataclass
class ExtractionResult:
    """Resultado da extração de um material."""

    text: str
    page_count: int
    engine: str  # "pymupdf" | "tesseract" | "textract"
    ocr_used: bool


# ---------------------------------------------------------------------------
# OCR — interface + implementações intercambiáveis por configuração
# ---------------------------------------------------------------------------


class OcrEngine(ABC):
    """Contrato de OCR: recebe uma imagem (PNG) e devolve texto.

    As implementações fazem *import tardio* das dependências pesadas para que o
    módulo carregue mesmo sem o binário/serviço presentes.
    """

    name: str = "base"

    @abstractmethod
    def image_to_text(self, image_png: bytes) -> str: ...


class TesseractOcr(OcrEngine):
    """OCR local via Tesseract (grátis; exige o binário ``tesseract`` no host)."""

    name = "tesseract"

    def __init__(self, language: str = "por+eng") -> None:
        self.language = language

    def image_to_text(self, image_png: bytes) -> str:
        import pytesseract
        from PIL import Image

        with Image.open(io.BytesIO(image_png)) as img:
            return pytesseract.image_to_string(img, lang=self.language)


class TextractOcr(OcrEngine):
    """OCR gerenciado via AWS Textract (maior acurácia; usa a IAM Role da EC2)."""

    name = "textract"

    def __init__(self, region: str) -> None:
        self.region = region
        self._client = None

    def image_to_text(self, image_png: bytes) -> str:
        import boto3

        if self._client is None:
            self._client = boto3.client("textract", region_name=self.region)
        resp = self._client.detect_document_text(Document={"Bytes": image_png})
        lines = [b["Text"] for b in resp.get("Blocks", []) if b.get("BlockType") == "LINE"]
        return "\n".join(lines)


def get_ocr_engine(settings) -> OcrEngine:
    """Seleciona o engine de OCR por configuração — troca sem alterar chamadas."""
    if settings.ocr_engine.lower() == "textract":
        return TextractOcr(settings.s3_region)
    return TesseractOcr(settings.ocr_language)


# ---------------------------------------------------------------------------
# Extração de PDF
# ---------------------------------------------------------------------------


def extract_pdf(
    data: bytes,
    *,
    ocr: OcrEngine | None = None,
    ocr_min_chars_per_page: int = 100,
    ocr_dpi: int = 200,
) -> ExtractionResult:
    """Extrai o texto de um PDF: nativo (PyMuPDF) com *fallback* para OCR.

    Se o texto nativo tiver menos que ``ocr_min_chars_per_page`` por página e um
    ``ocr`` for fornecido, renderiza cada página como imagem e roda o OCR; o
    resultado com mais texto vence. Sem ``ocr``, devolve sempre o texto nativo.
    """
    import fitz  # PyMuPDF (import tardio: dependência pesada)

    with fitz.open(stream=data, filetype="pdf") as doc:
        page_count = doc.page_count
        native_text = "\n".join(page.get_text() for page in doc).strip()

        needs_ocr = ocr is not None and len(native_text) < ocr_min_chars_per_page * max(1, page_count)
        if not needs_ocr:
            return ExtractionResult(
                text=native_text, page_count=page_count, engine="pymupdf", ocr_used=False
            )

        logger.info(
            "Texto nativo esparso (%d chars, %d págs) — acionando OCR %s",
            len(native_text),
            page_count,
            ocr.name,
        )
        ocr_parts: list[str] = []
        for page in doc:
            pix = page.get_pixmap(dpi=ocr_dpi)
            ocr_parts.append(ocr.image_to_text(pix.tobytes("png")))
        ocr_text = "\n".join(ocr_parts).strip()

    if len(ocr_text) > len(native_text):
        return ExtractionResult(
            text=ocr_text, page_count=page_count, engine=ocr.name, ocr_used=True
        )
    # OCR não rendeu mais que o nativo: fica com o nativo (evita piorar).
    return ExtractionResult(
        text=native_text, page_count=page_count, engine="pymupdf", ocr_used=False
    )
