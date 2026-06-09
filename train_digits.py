"""
Train the digit CNN on real glyphs + synthetic augmentations.
Usage:  python train_digits.py [--glyphs F:/SC_temp/glyphs] [--epochs 200]
"""
import argparse
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from PIL import Image, ImageFilter, ImageEnhance
from pathlib import Path

from src.digit_cnn import DigitCNN, CHAR_TO_IDX, INPUT_W, INPUT_H, MODEL_PATH


# ── Augmentation ─────────────────────────────────────────────────────────────

def augment(arr: np.ndarray) -> np.ndarray:
    """Apply random augmentations to a white-background glyph array."""
    img = Image.fromarray(arr)

    # Slight rotation ±3°
    if random.random() < 0.6:
        angle = random.uniform(-3, 3)
        img = img.rotate(angle, fillcolor=255, expand=False)

    # Slight scale jitter ±10%
    if random.random() < 0.5:
        w, h = img.size
        scale = random.uniform(0.90, 1.10)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        # re-center in original size canvas
        canvas = Image.new('L', (w, h), 255)
        ox = (w - nw) // 2
        oy = (h - nh) // 2
        canvas.paste(img, (ox, oy))
        img = canvas

    # Brightness jitter
    if random.random() < 0.5:
        factor = random.uniform(0.7, 1.3)
        img = ImageEnhance.Brightness(img).enhance(factor)

    # Slight blur
    if random.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    # Pixel noise
    arr2 = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, 8, arr2.shape).astype(np.float32)
    arr2 = np.clip(arr2 + noise, 0, 255).astype(np.uint8)

    return arr2


# ── Dataset ───────────────────────────────────────────────────────────────────

class GlyphDataset(Dataset):
    def __init__(self, glyphs_dir: Path, augment_factor: int = 40):
        self.samples = []   # (arr, label_idx)
        self.augment_factor = augment_factor

        for char_dir in sorted(glyphs_dir.iterdir()):
            if not char_dir.is_dir() or not char_dir.name.startswith('char_'):
                continue
            char = chr(int(char_dir.name.split('_')[1]))
            if char not in CHAR_TO_IDX:
                continue
            label = CHAR_TO_IDX[char]
            for png in char_dir.glob('*.png'):
                arr = np.array(Image.open(png).convert('L'))
                self.samples.append((arr, label))

        if not self.samples:
            raise RuntimeError(f"No glyph images found in {glyphs_dir}")

        print(f"Loaded {len(self.samples)} real glyphs -> "
              f"{len(self.samples) * augment_factor} augmented samples")

    def __len__(self):
        return len(self.samples) * self.augment_factor

    def __getitem__(self, idx):
        arr, label = self.samples[idx % len(self.samples)]
        arr = augment(arr)
        img = Image.fromarray(arr).resize((INPUT_W, INPUT_H), Image.LANCZOS)
        x = torch.tensor(np.array(img, dtype=np.float32) / 255.0).unsqueeze(0)
        return x, label


# ── Training loop ─────────────────────────────────────────────────────────────

def train(glyphs_dir: Path, epochs: int, lr: float, batch: int):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    ds = GlyphDataset(glyphs_dir)

    # Weighted sampler for class balance
    labels = [ds.samples[i % len(ds.samples)][1] for i in range(len(ds))]
    class_counts = np.bincount(labels, minlength=len(CHAR_TO_IDX))
    weights = 1.0 / (class_counts[labels] + 1e-6)
    sampler = WeightedRandomSampler(weights, len(ds))
    loader = DataLoader(ds, batch_size=batch, sampler=sampler, num_workers=0)

    model = DigitCNN().to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    criterion = nn.CrossEntropyLoss()

    best_loss = float('inf')
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, total_correct, total_n = 0.0, 0, 0
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            loss = criterion(model(x), y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(y)
            total_correct += (model(x).argmax(1) == y).sum().item()
            total_n += len(y)
        scheduler.step()

        avg_loss = total_loss / total_n
        acc = total_correct / total_n
        if epoch % 20 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{epochs}  loss={avg_loss:.4f}  acc={acc:.3f}")

        if avg_loss < best_loss:
            best_loss = avg_loss
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), MODEL_PATH)

    print(f"\nBest model saved to {MODEL_PATH}  (loss={best_loss:.4f})")
    return model


def evaluate(glyphs_dir: Path):
    """Quick sanity check on real (non-augmented) glyphs."""
    from src.digit_cnn import load_model, predict_glyph

    # Force reload
    import src.digit_cnn as dcnn
    dcnn._model = None

    model = load_model()
    if model is None:
        print("No model found")
        return

    correct, total = 0, 0
    errors = []
    for char_dir in sorted(glyphs_dir.iterdir()):
        if not char_dir.is_dir() or not char_dir.name.startswith('char_'):
            continue
        char = chr(int(char_dir.name.split('_')[1]))
        for png in char_dir.glob('*.png'):
            arr = np.array(Image.open(png).convert('L'))
            pred, conf = predict_glyph(arr)
            total += 1
            if pred == char:
                correct += 1
            else:
                errors.append(f"  {png.name}: expected '{char}' got '{pred}' ({conf:.2f})")

    print(f"\nEval on real glyphs: {correct}/{total} correct ({correct/total:.1%})")
    if errors:
        print("Errors:")
        for e in errors:
            print(e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--glyphs", default=r"F:\SC_temp\glyphs")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--eval-only", action="store_true")
    args = parser.parse_args()

    glyphs_dir = Path(args.glyphs)

    if not args.eval_only:
        train(glyphs_dir, args.epochs, args.lr, args.batch)

    evaluate(glyphs_dir)
