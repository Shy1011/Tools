# Tools

[English](README_EN.md) | [中文](README.md)

A lightweight collection of web tools built with plain HTML + CSS + JavaScript. Just download and open them in a browser — no installation or dependencies required, and most tools work fully offline.

## Included Tools

### 1. 32-bit Bit Selector × 6 (`bit-to-hex-x6.html`)

Six independent 32-bit value editors on one page, handy for assembling register values, masks, or configuration words.

Features:

- 32-bit binary toggle switches with bit numbers on top (31 → 0); hover to see the bit weight
- Live display of HEX, unsigned decimal, signed int32 decimal, and binary
- All 6 editors are fully independent, each supporting: clear, all 1s, random, load from HEX input, one-click copy
- Each editor accepts a short note, auto-saved to browser local storage (`localStorage`) — survives refresh
- Responsive layout: 3 columns × 2 rows on wide screens (≥1400px), 2 columns × 3 rows on medium screens, single column on phones; bit buttons wrap into two rows inside each card
- Auto-adapts to light / dark system theme

![Preview](bit-to-hex-x6-preview.png)

### 2. XY Plotter · Simple Edition (`xy-plotter.html`)

A minimal data plotting tool: paste X / Y data into two text boxes, click "Plot" to view the curve; multiple curves are supported.

Features:

- Multiple curves: add any number via "+ New Curve", each with its own X / Y inputs, name, and color; supports deletion and show / hide; when X is left empty it defaults to 0, 1, 2, …; mismatched lengths are drawn against the shorter one
- Title and axis labels: editable text, font, size, and color; draggable directly on the canvas (position auto-saved)
- Axes: linear / log10 scaling (automatically filters and warns about 0 and negative values), grid toggle, polyline / smooth curve
- Point picking: click a data point to add/remove a marker, mark multiple points at once with coordinates listed, one-click "Clear all markers"
- Tick modes: auto pretty numbers (1/2/5×10ⁿ), N equal segments, fixed step, data point positions, custom tick list
- Interaction: click the legend to show/hide curves, hover to show the curve name and exact coordinates, box-select zoom, hold Space or "Pan" to drag, double-click to reset the view
- Data export / import: one-click CSV export (curve name, x, y — opens in Excel), and load same-format CSV / TXT to restore multiple curves
- Auto-save: title, axis label text/font/size/color and positions, axis and tick settings, and curve data are all saved in the current browser and restored on refresh
- PNG export; light / dark theme toggle; fully offline with no external dependencies

![Preview](xy-plotter-preview.png)

## Usage

1. Clone or download this repository;
2. Open the HTML files directly in Chrome / Edge / Firefox or another browser;
3. No server and no dependencies needed.

## File Structure

| File | Description |
| --- | --- |
| `bit-to-hex-x6.html` | 32-bit bit selector × 6 tool page |
| `bit-to-hex-x6-preview.png` | Tool preview screenshot |
| `xy-plotter.html` | XY plotter · simple edition |
| `xy-plotter-preview.png` | Tool preview screenshot |
| `README.md` | Chinese documentation |
| `README_EN.md` | This documentation (English) |

## Technical Notes

- Pure vanilla HTML / CSS / JavaScript, zero third-party dependencies, works offline
- The bit selector computes with 32-bit unsigned integers; when bit 31 is set, the `int32` column shows the two's-complement negative value; notes are saved in browser `localStorage`
- In the plotter, title / axis label positions and curve data are saved locally in the current browser; log axes automatically skip 0 and negative values

## License

This repository does not currently include a license file. Consider adding a LICENSE (e.g. MIT) before public release and updating this documentation accordingly.
