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
    """Engines whose dependencies are actually importable."""
    result = []
    for name, cls in sorted(_REGISTRY.items()):
        try:
            cls()
        except OcrEngineUnavailable:
            continue
        except Exception:
            continue
        result.append(name)
    return result


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
        self._ocr = PaddleOCR(use_angle_cls=True, lang="ar", show_log=False)

    def recognize(self, image: bytes, languages: list[str] | None = None) -> "OcrPage":
        import numpy
        from paddleocr import PaddleOCR as _Engine  # noqa: F401

        from engine.ocr.base import OcrBox, OcrLine, OcrPage, png_size

        pixmap = numpy.frombuffer(image, dtype=numpy.uint8)
        # PaddleOCR accepts image arrays via its own reader; hand it the raw
        # bytes path through its tooling to stay version-tolerant.
        result = self._ocr.ocr(image, cls=True)
        width, height = png_size(image)

        lines: list[OcrLine] = []
        confidences: list[float] = []
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
    """Tesseract adapter (M5-03, P2). Requires `pip install .[ocr-tesseract]`
    plus the tesseract binary with the desired language packs."""

    name = "tesseract"

    def __init__(self, languages: list[str] | None = None, **_) -> None:
        try:
            import pytesseract  # noqa: F401
        except ImportError as exc:
            raise OcrEngineUnavailable(
                "pytesseract is not installed; install with: pip install \".[ocr-tesseract]\" "
                "and ensure the tesseract binary (with ara/ind language data) is on PATH"
            ) from exc
        self._languages = languages or ["ara+ind+eng"]

    def recognize(self, image: bytes, languages: list[str] | None = None) -> "OcrPage":
        import io

        import pytesseract
        from PIL import Image

        from engine.ocr.base import OcrBox, OcrLine, OcrPage, png_size

        pil = Image.open(io.BytesIO(image))
        width, height = png_size(image)
        lang = "+".join(languages) if languages else self._languages

        data = pytesseract.image_to_data(
            pil, lang=lang, output_type=pytesseract.Output.DICT
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
