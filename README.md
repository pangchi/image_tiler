# Image Tiler

A simple drag-and-drop desktop tool for combining multiple JPG/PNG images
into a single tiled image (grid layout).

## Features

- **Drag & drop** multiple JPG/PNG files (or whole folders) into the window,
  or add them via the "Add Files..." dialog
- **Reorder** images in the tile grid (Move Up / Move Down, multi-select)
- **Remove** individual images or clear the whole list
- **Grid controls**
  - Columns (0 = auto, arranges into a roughly square grid)
  - Cell size (px) — auto-suggested from the loaded images' dimensions
    (median of each image's smaller side), and re-suggested whenever
    images are added or removed. Manually editing the field turns
    auto-suggest off; re-check "Auto-suggest from image sizes" to
    turn it back on and recalculate.
  - Spacing between cells (px)
- **Fit modes** per image:
  - `contain` — scales image to fit inside its cell, letterboxed (no cropping)
  - `cover` — scales and crops image to fill its cell completely
  - `stretch` — stretches image to exactly fill its cell (may distort aspect ratio)
- **Background color** picker for the letterbox/padding areas
- **Live preview** that updates as you change any option
- **Save** the tiled result as a single `.png` or `.jpg` file

## Requirements

- Python 3
- `tkinterdnd2` and `pillow` — installed automatically on first run if missing

## Usage

```
python image_tiler.pyw
```

1. Drag image files (or a folder of images) into the drop area, or click
   "Add Files...".
2. Reorder with Move Up / Move Down if needed.
3. Adjust Columns, Cell size, Spacing, Fit mode, and Background color to taste
   — the preview updates live.
4. Click "Save Tiled Image..." and choose a destination and filename.

## Notes

- Supported input formats: `.jpg`, `.jpeg`, `.png`
- Output is a single flattened RGB image (PNG or JPEG)
- Dropping a folder adds all supported images inside it (non-recursive)

## Version History

- **v1.1** — Cell size is now auto-detected from the dimensions of the loaded
  images (median of each image's smaller side) and auto-updates as images
  are added/removed. Toggle via the "Auto-suggest from image sizes" checkbox;
  manually editing the cell size field disables it.
- **v1.0** — Initial release: drag-and-drop input, grid tiling, contain/cover/stretch
  fit modes, adjustable spacing/cell size/columns, background color picker,
  live preview, PNG/JPG export.
