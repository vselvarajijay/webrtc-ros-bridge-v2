#!/usr/bin/env python3
"""Download DepthAnything3 and Mask2Former models locally."""
import os
import sys
from pathlib import Path
from huggingface_hub import snapshot_download

def main():
    # Get workspace root (assuming script is in scripts/)
    workspace_root = Path(__file__).parent.parent
    models_dir = workspace_root / "models"
    models_dir.mkdir(exist_ok=True)
    
    print("Downloading DepthAnything3 model...")
    da3_path = models_dir / "DA3Metric-Large"
    if not da3_path.exists():
        try:
            snapshot_download(
                repo_id="depth-anything/DA3Metric-Large",
                local_dir=str(da3_path),
                local_dir_use_symlinks=False
            )
            print(f"✓ Downloaded to {da3_path}")
        except Exception as e:
            print(f"✗ Error downloading DA3 model: {e}")
            print("Make sure you have huggingface_hub installed: pip install huggingface_hub")
            return 1
    else:
        print(f"✓ Already exists at {da3_path}")
    
    print("\nDownloading Mask2Former model...")
    mask2former_path = models_dir / "mask2former-cityscapes"
    if not mask2former_path.exists():
        try:
            snapshot_download(
                repo_id="facebook/mask2former-swin-large-cityscapes-semantic",
                local_dir=str(mask2former_path),
                local_dir_use_symlinks=False
            )
            print(f"✓ Downloaded to {mask2former_path}")
        except Exception as e:
            print(f"✗ Error downloading Mask2Former model: {e}")
            print("Make sure you have huggingface_hub installed: pip install huggingface_hub")
            return 1
    else:
        print(f"✓ Already exists at {mask2former_path}")
    
    print(f"\n✓ Models ready at: {models_dir}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
