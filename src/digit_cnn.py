import numpy as np
from PIL import Image
from pathlib import Path

CHARS = ".%0123456789"
IDX_TO_CHAR = {i: c for i, c in enumerate(CHARS)}

INPUT_W = 16
INPUT_H = 16

_session = None


def _base_dir() -> Path:
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


MODEL_PATH = _base_dir() / "data" / "digit_cnn.onnx"


def load_model():
    global _session
    if _session is not None:
        return _session
    if not MODEL_PATH.exists():
        return None
    import onnxruntime as ort
    _session = ort.InferenceSession(
        str(MODEL_PATH),
        providers=["CPUExecutionProvider"],
    )
    return _session


def glyph_to_input(glyph: np.ndarray) -> np.ndarray:
    img = Image.fromarray(glyph).resize((INPUT_W, INPUT_H), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    return arr[np.newaxis, np.newaxis, :, :]  # (1, 1, H, W)


def predict_glyph(glyph: np.ndarray) -> tuple[str, float]:
    session = load_model()
    if session is None:
        return "?", 0.0
    inp = glyph_to_input(glyph)
    logits = session.run(None, {"input": inp})[0]  # (1, 12)
    # softmax
    e = np.exp(logits - logits.max())
    probs = e / e.sum()
    idx = int(probs.argmax())
    return IDX_TO_CHAR[idx], float(probs[0, idx])
