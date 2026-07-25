# ComfyUI-PepeUtils

Small utility nodes for [ComfyUI](https://github.com/comfyanonymous/ComfyUI).

Currently included:

- **Anime PromptGen** - generates anime prompt text with the FredZhang7 GPT-2 prompt generator or a compatible local GGUF file through Transformers.
- **Load Image Cropped** - loads an image and returns a cropped image + mask, with an interactive crop preview in the ComfyUI frontend.
- **Pepe Paste Image** - pastes a clipboard image into a selected node and keeps it only in ComfyUI's temporary storage.
- **Pepe Resize Image** - resizes, crops, pads, or pillarboxes images with automatic Lanczos upscale and Pepe Bicubic Sharper downscale selection.
- **Pepe Scale Image By** - scales images with a Photoshop Bicubic Sharper style approximation based on configurable cubic resampling.
- **Stride Scale Size** - computes width/height snapped to a chosen stride after scaling.

## Node Screenshots

![ComfyUI-PepeUtils nodes](assets/nodes.png)

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

The **Anime PromptGen** node also needs:

- `transformers`
- `gguf` when loading `.gguf` files through Transformers

Place local GGUF models in one of these folders:

```text
ComfyUI/models/gguf
ComfyUI/models/llm_gguf
ComfyUI/models/LLM/GGUF
```

After restarting ComfyUI, files in that folder appear in the `gguf_model` dropdown. You can also paste an absolute `.gguf` path into `gguf_file_path`.

## Included Nodes

### Anime PromptGen

Category: `utils/text`

Inputs:

- `prompt`
- `model_id_or_path`
- `tokenizer_id_or_path`
- `gguf_model`
- `gguf_file_path`
- `max_length`
- `num_return_sequences`
- `do_sample`
- `repetition_penalty`
- `temperature`
- `top_k`
- `early_stopping`
- `seed`
- `dtype`
- `device`
- `local_files_only`
- `strip_input_prompt`

Outputs:

- `prompts`
- `first_prompt`

What it does:

- Wraps the Hugging Face text-generation pipeline.
- Exposes the generation arguments from the original `outs = nlp(...)` snippet as node widgets.
- Loads the normal Hugging Face model by default.
- Can load a compatible local `.gguf` model with Transformers using `gguf_file`.

Notes:

- Transformers loads GGUF checkpoints by dequantizing them into PyTorch weights, so memory use is closer to the selected `dtype` than to the GGUF file size.
- For GGUF workflows, the node first tries tokenizer metadata from the GGUF or adjacent files before falling back to `tokenizer_id_or_path`.
- If a custom node changes Hugging Face hub settings and you see requests to mirrors such as `hf-mirror.com`, enable `local_files_only` or set `tokenizer_id_or_path` to a local tokenizer folder.

### Load Image Cropped

Category: `image`

Inputs:

- `image`

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
- Internal crop coordinates are updated from the preview.
- Supports dragging a file onto the node to upload/select an image.
- Includes a **Clear Crop** context-menu action.

Notes:

- If the crop is invalid or empty, it falls back to the full image.
- Crop coordinates are clamped to the image bounds.

### Pepe Paste Image

Category: `image`

Outputs:

- `image`
- `mask`

What it does:

- Select the node and press `Ctrl+V` to paste an image from the system clipboard.
- Alternatively, click **Paste image from clipboard**.
- Shows a preview and the pasted image dimensions.
- Uploads clipboard images only to `ComfyUI/temp/pepeutils/paste-image`.

Notes:

- Pasted files are removed by ComfyUI when it starts and when it shuts down normally.
- A saved workflow retains the temporary filename, not the image itself. Paste the image again after restarting ComfyUI.
- The clipboard button depends on browser clipboard permission. `Ctrl+V` remains available when direct clipboard access is unavailable.
- Exactly one Pepe Paste Image node must be selected for the `Ctrl+V` shortcut.

### Pepe Scale Image By

Category: `utils/image`

Inputs:

- `image`
- `scale_by`
- `snap_to_stride`
- `stride`
- `snap_mode` (`nearest`, `down`, `up`)
- `clamp_intermediate`

Outputs:

- `image`
- `width`
- `height`

What it does:

- Scales a ComfyUI image batch by `scale_by`.
- Uses a NumPy separable resampler approximating Photoshop CS5.1 Bicubic Sharper behavior from Jason Summers' ResampleScope notes.
- For each axis, applies an integrated box prepass when scale is below `0.25`, then a cubic pass with `B=0`, `blur=1.05`, and scale-dependent `C`.
- Processes X first, then Y, and clamps after cubic passes when `clamp_intermediate` is enabled.
- Uses a box blur of `0.33` and source-space phase `0.3999` for the large-downscale prepass.
- Uses cubic filter scale derived from the active cubic pass: direct downscales use `scale`; large downscales below `0.25` prebox to `4x target`, so the final cubic pass uses `0.25`.
- Equivalent cubic filter scale rule: `max(scale, 0.25)`.

Notes:

- This is not guaranteed to be pixel-identical to Photoshop. Boundary handling, rounding, and exact clamping behavior are reverse-engineered approximations.
- Manual ring-pattern tests matched Photoshop closely from scale `0.3` upward with this derived math. Below `0.25`, minor differences remain around Photoshop's exact box prepass/crop behavior.
- Very large images or batches may be slower than ComfyUI's built-in GPU scaling because this node runs the custom resampler on CPU.

### Pepe Resize Image

Category: `utils/image`

Inputs:

- `image`
- `width`
- `height`
- `keep_proportion` (`stretch`, `resize`, `pad`, `pad_edge`, `pad_edge_pixel`, `crop`, `pillarbox_blur`, `total_pixels`)
- `pad_color_r`
- `pad_color_g`
- `pad_color_b`
- `crop_position` (`center`, `top`, `bottom`, `left`, `right`)
- `divisible_by`
- `mask` (optional)

Outputs:

- `image`
- `width`
- `height`
- `mask`

What it does:

- Provides KJNodes-style resize, pad, crop, pillarbox, and total-pixel geometry modes.
- Automatically uses Lanczos when enlarging.
- Automatically uses the existing Pepe Photoshop-style Bicubic Sharper path when reducing.
- Handles mixed-axis `stretch` by shrinking first, then enlarging.
- Applies the same geometry to optional masks with mask-safe bilinear interpolation.
- Aligns final dimensions downward to `divisible_by`.

Notes:

- Width or height may be `0`; missing dimensions are derived from the source aspect ratio.
- `pad_edge` fills padding from average edge colors.
- `pad_edge_pixel` extends actual edge pixels.
- `pillarbox_blur` uses a blurred cover background plus a sharp fitted foreground.

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
├─ AnimePromptGen.py
├─ assets/
│  └─ nodes.png
├─ LoadImageCropped.py
├─ PasteImage.py
├─ PepeResizeImage.py
├─ PepeScaleImageBy.py
├─ StrideScaleSize.py
├─ examples/
│  └─ minimal_workflow.json
└─ web/
   ├─ load_image_cropped.js
   └─ paste_image.js
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

## Development Notes

Files that should not be published as source artifacts are ignored in `.gitignore`, including:

- `__pycache__/`
- `*.pyc`
- `.omx/`

## License

GNU GPL v3
