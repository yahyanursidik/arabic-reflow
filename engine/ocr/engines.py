"""Engine registry and lazy-importing adapters (backlog M5-02, M5-03).

PaddleOCR is the primary engine, Tesseract the optional fallback. Both
adapters import their dependency only when instantiated, so the package
installs and tests run without either present.
"""

from __future__ import annotations

from engine.ocr.base import OcrEngine, OcrEngineUnavailable

_REGISTRY: dict[str, type] = {}


def register(name: str):
    def decorator(cls):
        _REGISTRY[name] = cls
        return cls

    return decorator


def get_engine(name: str, **kwargs) -> OcrEngine:
    """Instantiate a registered engine by name.

    Raises OcrEngineUnavailable with install guidance when the engine's
    dependency is missing.
    """
    if name not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise OcrEngineUnavailable(f"unknown OCR engine {name!r}; known: {known}")
    engine = _REGISTRY[name](**kwargs)
    if engine is None:
        raise OcrEngineUnavailable(f"engine {name!r} could not be constructed")
    return engine


def available_engines() -> list[str]:
    """Installed runtimes, without initializing/downloading heavy OCR models."""
    from engine.ocr.runtime import ocr_capabilities

    return [item["name"] for item in ocr_capabilities()["engines"] if item["available"]]


@register("paddle")
class PaddleOcrEngine:
    """PaddleOCR adapter (M5-02, P0). Requires `pip install .[ocr-paddle]`."""

    name = "paddle"

    def __init__(self, languages: list[str] | None = None, **_) -> None:
        try:
            from paddleocr import PaddleOCR  # noqa: F401
        except ImportError as exc:
            raise OcrEngineUnavailable(
                "PaddleOCR is not installed; install with: pip install \".[ocr-paddle]\""
            ) from exc
        self._languages = languages or ["ar", "id", "en"]
        # PaddleOCR v3 changed initialization and recognition APIs. Supporting
        # both avoids the old v2-only arguments breaking the declared v3 extra.
        from importlib.metadata import version

        self._v3 = int(version("paddleocr").split(".")[0]) >= 3
        if self._v3:
            self._ocr = PaddleOCR(lang="ar", use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=True)
        else:
            self._ocr = PaddleOCR(use_angle_cls=True, lang="ar", show_log=False)

    def recognize(self, image: bytes, languages: list[str] | None = None) -> "OcrPage":
        import numpy
        import pymupdf

        from engine.ocr.base import OcrBox, OcrLine, OcrPage, png_size

        pix = pymupdf.Pixmap(image)
        if pix.colorspace and pix.colorspace.n != 3:
            pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
        pixels = numpy.frombuffer(pix.samples, dtype=numpy.uint8).reshape(pix.height, pix.width, pix.n)
        pixels = pixels[:, :, :3][:, :, ::-1].copy()  # RGB -> BGR image array
        result = list(self._ocr.predict(pixels)) if self._v3 else self._ocr.ocr(pixels, cls=True)
        width, height = png_size(image)

        lines: list[OcrLine] = []
        confidences: list[float] = []
        if self._v3:
            entries = []
            for page_result in result:
                record = page_result.get("res", page_result)
                texts = record.get("rec_texts", [])
                scores = record.get("rec_scores", [])
                boxes = record.get("rec_polys", [])
                for box, text, score in zip(boxes, texts, scores):
                    entries.append((box, (text, score)))
            page_result = entries
        else:
            page_result = result[0] if result else []
        for entry in page_result or []:
            box_points, (text, confidence) = entry[0], entry[1]
            xs = [p[0] for p in box_points]
            ys = [p[1] for p in box_points]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            word = OcrBox(text=text, bbox=bbox, confidence=float(confidence))
            lines.append(OcrLine(bbox=bbox, words=[word]))
            confidences.append(float(confidence))

        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrPage(
            page=0, width=width, height=height, lines=lines,
            engine=self.name, mean_confidence=mean,
        )


@register("tesseract")
class TesseractOcrEngine:
    """Tesseract adapter (M5-03, P2). Requires `pip install ".[ocr-tesseract]"`
    plus the tesseract binary with the desired language packs.

    Optional environment variables:
    - TESSERACT_CMD: full path to the tesseract binary when it is not on PATH;
    - TESSDATA_PREFIX: directory containing *.traineddata when the default
      install location is not writable (the binary reads this itself).
    """

    name = "tesseract"

    def __init__(self, languages: list[str] | None = None, **_) -> None:
        import os

        try:
            import pytesseract  # noqa: F401
        except ImportError as exc:
            raise OcrEngineUnavailable(
                "pytesseract is not installed; install with: pip install \".[ocr-tesseract]\" "
                "and ensure the tesseract binary (with ara/ind language data) is on PATH"
            ) from exc
        from engine.ocr.runtime import language_codes, tesseract_command, tesseract_status

        status = tesseract_status(languages)
        if not status["available"]:
            raise OcrEngineUnavailable(status["message"])
        pytesseract.pytesseract.tesseract_cmd = tesseract_command()
        # pytesseract expects the language pack list as one '+'-joined string.
        self._languages = "+".join(language_codes(languages))

    def recognize(self, image: bytes, languages: list[str] | None = None) -> "OcrPage":
        import io

        import pytesseract
        from PIL import Image

        from engine.ocr.base import OcrBox, OcrLine, OcrPage, png_size

        pil = Image.open(io.BytesIO(image))
        width, height = png_size(image)
        from engine.ocr.runtime import language_codes

        lang = "+".join(language_codes(languages)) if languages else self._languages

        data = pytesseract.image_to_data(
            pil, lang=lang, output_type=pytesseract.Output.DICT, timeout=120
        )
        lines: list[OcrLine] = []
        confidences: list[float] = []
        count = len(data["text"])
        current_key = None
        current_words: list[OcrBox] = []
        for index in range(count):
            text = (data["text"][index] or "").strip()
            confidence = float(data["conf"][index]) / 100.0
            if not text or confidence <= 0:
                continue
            box = (
                float(data["left"][index]),
                float(data["top"][index]),
                float(data["left"][index] + data["width"][index]),
                float(data["top"][index] + data["height"][index]),
            )
            key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
            word = OcrBox(text=text, bbox=box, confidence=confidence)
            if current_key is None or key != current_key:
                if current_words:
                    bbox = (
                        min(w.bbox[0] for w in current_words),
                        min(w.bbox[1] for w in current_words),
                        max(w.bbox[2] for w in current_words),
                        max(w.bbox[3] for w in current_words),
                    )
                    lines.append(OcrLine(bbox=bbox, words=current_words))
                    current_words = []
                current_key = key
            current_words.append(word)
            confidences.append(confidence)
        if current_words:
            bbox = (
                min(w.bbox[0] for w in current_words),
                min(w.bbox[1] for w in current_words),
                max(w.bbox[2] for w in current_words),
                max(w.bbox[3] for w in current_words),
            )
            lines.append(OcrLine(bbox=bbox, words=current_words))

        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrPage(
            page=0, width=width, height=height, lines=lines,
            engine=self.name, mean_confidence=mean,
        )
