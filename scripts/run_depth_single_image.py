#!/usr/bin/env python3
"""
Run DepthAnything3 on a single image and save depth.
Usage:
  python scripts/run_depth_single_image.py --input path/to/image.jpg --output path/to/depth.png
  python scripts/run_depth_single_image.py -i image.jpg -o depth.png --raw depth.npy
"""
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
from depth_anything_3.api import DepthAnything3


def main():
    parser = argparse.ArgumentParser(description="Run depth estimation on a single image")
    parser.add_argument("--input", "-i", required=True, help="Path to input image")
    parser.add_argument("--output", "-o", required=True, help="Path for output depth (PNG colormap)")
    parser.add_argument(
        "--raw",
        metavar="PATH",
        default=None,
        help="If set, also save raw float32 depth as .npy to this path",
    )
    parser.add_argument(
        "--models-dir",
        default=None,
        help="Directory containing DA3Metric-Large (default: workspace models/)",
    )
    parser.add_argument(
        "--focal",
        type=float,
        default=341.93,
        help="Focal length for metric depth",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    if not input_path.exists():
        print(f"Error: input image not found: {input_path}", file=sys.stderr)
        return 1

    # Resolve models dir
    if args.models_dir:
        models_dir = Path(args.models_dir)
    else:
        # Assume script is in repo/scripts/
        workspace = Path(__file__).resolve().parent.parent
        models_dir = workspace / "models"
    da3_path = models_dir / "DA3Metric-Large"
    if not da3_path.exists():
        print(
            f"Error: model not found at {da3_path}. Run: python3 scripts/download_models.py",
            file=sys.stderr,
        )
        return 1

    # Load image
    img = cv2.imread(str(input_path))
    if img is None:
        print(f"Error: could not load image: {input_path}", file=sys.stderr)
        return 1
    orig_h, orig_w = img.shape[:2]

    # Load model and run inference (same as da3_node.py)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading DepthAnything3 from {da3_path}...")
    model = DepthAnything3.from_pretrained(str(da3_path)).to(device)
    print("Running inference...")
    pred = model.inference([img])
    depth = pred.depth[0]
    metric_depth = (args.focal * depth) / 300.0
    depth = metric_depth
    if depth.shape[0] != orig_h or depth.shape[1] != orig_w:
        depth = cv2.resize(depth, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
    depth = depth.astype(np.float32)

    # Save raw depth if requested
    if args.raw:
        raw_path = Path(args.raw)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(str(raw_path), depth)
        print(f"Saved raw depth to {raw_path}")

    # Colored depth for visualization (same colormap as node)
    depth_vis = np.clip(depth, 0, 10.0)
    depth_vis = (depth_vis / 10.0 * 255).astype(np.uint8)
    depth_colored = cv2.applyColorMap(depth_vis, cv2.COLORMAP_JET)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), depth_colored)
    print(f"Saved depth visualization to {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
