# ComfyUI-PepeUtils

Small utility nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI).

Currently included:

- **Load Image Cropped** - loads an image and returns a cropped image + mask, with an interactive crop preview in the ComfyUI frontend.
- **Stride Scale Size** - computes width/height snapped to a chosen stride after scaling.

## Installation

### Option 1: Git clone

Clone this repository into your `ComfyUI/custom_nodes` directory:

```bash
git clone https://github.com/Pepehoschi/ComfyUI-PepeUtils.git
```

### Option 2: Download ZIP

Download this repository as a ZIP, extract it, and place the folder here:

```text
ComfyUI/custom_nodes/ComfyUI-PepeUtils
```

Then restart ComfyUI.

## Requirements

No extra setup is currently documented beyond a normal ComfyUI installation.

This node relies on libraries that are typically already present in ComfyUI environments:

- `torch`
- `numpy`
- `Pillow`

## Included Nodes

### Load Image Cropped

Category: `image`

Inputs:

- `image`
- `x1`, `y1`, `x2`, `y2`

Outputs:

- `image`
- `mask`
- `width`
- `height`

What it does:

- Loads an input image from ComfyUI.
- Lets you define a crop rectangle.
- Returns the cropped image and cropped mask.
- Also returns the crop width and height as integers.

Frontend behavior:

- Includes an interactive crop preview.
- Hidden crop widgets are updated from the preview.
- Supports dragging a file onto the node to upload/select an image.
- Includes a **Clear Crop** context-menu action.

Notes:

- If the crop is invalid or empty, it falls back to the full image.
- Crop coordinates are clamped to the image bounds.

### Stride Scale Size

Category: `utils/math`

Inputs:

- `image_width`
- `image_height`
- `rescale_by`
- `stride`
- `mode` (`down`, `up`, `nearest`)
- `side_selector` (`shortest`, `longest`)
- `clamp_rescale_min_1`

Outputs:

- `scaled_width`
- `scaled_height`
- `chosen_side`

What it does:

- Scales an input size.
- Snaps the result to a stride.
- Returns the scaled width, height, and either the shortest or longest side.

## Folder Structure

```text
ComfyUI-PepeUtils/
├─ LICENSE
├─ __init__.py
├─ LoadImageCropped.py
├─ StrideScaleSize.py
├─ examples/
│  └─ minimal_workflow.json
└─ web/
   └─ load_image_cropped.js
```

## Example Workflow

A minimal example workflow is included at:

- [`examples/minimal_workflow.json`](examples/minimal_workflow.json)

It places both included PepeUtils nodes into a small ComfyUI workflow:

- `LoadImageCropped`
- `StrideScaleSize`

Notes:

- Set the image filename in the workflow to a file that exists in your ComfyUI input folder.
- The two nodes are intentionally shown as simple standalone examples; `StrideScaleSize` uses numeric widget values rather than being wired from another node.

## Publish Status / Missing Nice-to-Haves

Before public GitHub release, these would improve the project:

- screenshots or GIFs for the crop UI
- release/version metadata
- optional tests

## Development Notes

Files that should not be published as source artifacts are ignored in `.gitignore`, including:

- `__pycache__/`
- `*.pyc`
- `.omx/`

## License

This project now includes a `LICENSE` file using **GNU GPL v3**.

Recommendation: GPL v3 is the safest default here because this custom node appears to reuse and adapt ComfyUI-style node implementation patterns, and it keeps the project aligned with the broader ComfyUI licensing model.
