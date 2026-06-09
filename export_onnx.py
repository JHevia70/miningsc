"""
One-time script: convert digit_cnn.pt → digit_cnn.onnx
Run from the project root: python export_onnx.py
"""
import torch
from src.digit_cnn import DigitCNN
from pathlib import Path

pt_path   = Path("data/digit_cnn.pt")
onnx_path = Path("data/digit_cnn.onnx")

model = DigitCNN()
model.load_state_dict(torch.load(pt_path, map_location="cpu"))
model.eval()

dummy = torch.zeros(1, 1, 16, 16)
torch.onnx.export(
    model, dummy, str(onnx_path),
    input_names=["input"], output_names=["logits"],
    dynamic_axes={"input": {0: "batch"}},
    opset_version=17,
)
print(f"Exported: {onnx_path} ({onnx_path.stat().st_size // 1024} KB)")
