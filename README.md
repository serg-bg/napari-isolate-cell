# napari-isolate-cell

[![License BSD-3](https://img.shields.io/pypi/l/napari-isolate-cell.svg?color=green)](https://github.com/serg-bg/napari-isolate-cell/raw/main/LICENSE)
[![Python Version](https://img.shields.io/pypi/pyversions/napari-isolate-cell.svg?color=green)](https://python.org)
[![tests](https://github.com/serg-bg/napari-isolate-cell/workflows/tests/badge.svg)](https://github.com/serg-bg/napari-isolate-cell/actions)
[![codecov](https://codecov.io/gh/serg-bg/napari-isolate-cell/branch/main/graph/badge.svg)](https://codecov.io/gh/serg-bg/napari-isolate-cell)
[![npe2](https://img.shields.io/badge/plugin-npe2-blue?link=https://napari.org/stable/plugins/index.html)](https://napari.org/stable/plugins/index.html)

A [napari] plugin to isolate single cell morphologies (e.g., neurons) from label volumes based on a user click, automatically read image scale, and export the isolated structure as TIFF and correctly scaled SWC files.

![Demo of napari-cell-isolate plugin](images/napari-cell-isolate-demo.gif)

----------------------------------

## Overview

This plugin helps streamline the process of extracting individual cell structures from dense segmentations, such as those produced by deep learning models like nnUNet.

**Key Features:**

*   **Click-Based Isolation:** Simply click on the soma (or any part) of the cell you want to isolate in a Napari Labels layer.
*   **Automatic Scale Detection:** Reads ZYX scale information directly from TIFF metadata (standard tags or ImageJ metadata) and applies it to the loaded Napari layer.
*   **Anisotropy Awareness:** Automatically populates the widget's Anisotropy fields based on the detected image scale.
*   **Outputs:**
    *   Adds the isolated cell as a new Labels layer in Napari, preserving the original scale.
    *   Saves the isolated label volume as a TIFF file.
    *   Saves the skeletonized structure as an SWC file with coordinates reflecting the original image's physical scale (micrometers).
*   **Configurable Parameters:** Adjust morphological closing radius (defaults to 0 for dense segmentations) and skeleton dust threshold.

## Workflow

![Workflow diagram](images/One-click_cell_isolation_RESPAN.png)

## Installation

Currently, installation is primarily from source:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/serg-bg/napari-isolate-cell.git
    cd napari-isolate-cell
    ```

2.  **Create and activate a virtual environment:**
    *   **Using `uv` (Recommended, Fast):**
        ```bash
        # Install uv if you haven't already (see https://github.com/astral-sh/uv#installation)
        uv venv
        source .venv/bin/activate # Linux/macOS
        # OR: .\.venv\Scripts\activate # Windows
        ```
    *   **Using standard `venv`:**
        ```bash
        python -m venv .venv # Or python3
        source .venv/bin/activate # Linux/macOS
        # OR: .\.venv\Scripts\activate # Windows
        ```

3.  **Install the plugin in editable mode:**
    *   **Using `uv`:**
        ```bash
        uv pip install -e .
        # To include testing dependencies:
        # uv pip install -e .[testing]
        ```
    *   **Using `pip`:**
        ```bash
        pip install -e .
        # To include testing dependencies:
        # pip install -e .[testing]
        ```

## Usage

1.  **Launch Napari:** Open Napari. If you installed from source, ensure your virtual environment is activated.
2.  **Open the Widget:** Go to `Plugins` > `napari-isolate-cell` > `Isolate Cell Arbor`.
3.  **Load Data:**
    *   Open your 3D segmentation volume (e.g., a `.tif` file from nnUNet).
    *   The plugin's TIFF reader will attempt to automatically read the ZYX scale from the file's metadata. Check Napari's status bar or layer info to confirm the scale looks correct.
    *   Ensure the data is loaded as a `Labels` layer in Napari. If it loads as an `Image` layer (e.g., due to data type or number of unique values), right-click the layer and select `Convert to Labels`.
4.  **Select Input Layer:** Choose your loaded Labels layer from the `Input Labels Layer` dropdown in the widget.
5.  **Check Anisotropy:** The `Anisotropy (Z/Y/X)` fields should automatically update based on the scale read from the selected layer. Verify these values match your expectations.
6.  **Adjust Parameters (Optional):**
    *   `Morphological Closing Radius (voxels)`: Defaults to `0`, which is often best for separating touching cells in dense segmentations. Increase this (e.g., to `1` or `2`) if individual cells in your segmentation have small internal holes or fragmented parts that need bridging.
    *   `Skeleton Dust Threshold (voxels)`: Sets the minimum size (in voxels) for skeleton branches to be kept. Increase this to remove small, potentially noisy skeleton fragments.
7.  **Activate Isolation:** Click the `Activate Click Isolation` button.
8.  **Click on Target Cell:** In the Napari viewer, click once on the soma (or any part) of the specific cell you want to isolate.
9.  **Outputs:**
    *   A new Labels layer (e.g., `isolated_YourLayerName_Z_Y_X`) will appear in Napari containing only the isolated cell, displayed with the correct scale.
    *   In the same directory as your input TIFF file, a new sub-directory named `isolated_outputs` will be created.
    *   Inside `isolated_outputs`, two files will be saved:
        *   `YourLayerName_isolated.tif`: The isolated cell volume.
        *   `YourLayerName_isolated.swc`: The skeletonized structure. The XYZ coordinates in this file are in physical units (micrometers, based on the detected scale), suitable for direct use in tools like SNT.

10. **Downstream Analysis Note:** When loading the generated SWC file into analysis software like SNT ([ImageJ plugin](https://imagej.net/plugins/snt/)), you might observe a very slight offset (e.g., half a voxel) between the SWC overlay and the original image due to minor differences in coordinate system interpretation (voxel center vs. corner). Such minor adjustments are typically best handled within the dedicated analysis software if needed.

## Requirements

*   Python >= 3.10
*   napari
*   NumPy
*   scikit-image
*   SciPy
*   tifffile
*   magicgui
*   qtpy

(See `pyproject.toml` for specific version constraints)

## Contributing

Contributions are very welcome. Please file an issue to discuss potential changes or features first. Tests can be run with [pytest] (`pip install -e .[testing]` then `pytest`). Please ensure
the coverage at least stays the same before you submit a pull request.

## License

Distributed under the terms of the [BSD-3] license,
"napari-isolate-cell" is free and open source software

## Issues

If you encounter any problems, please [file an issue] along with a detailed description.

[napari]: https://github.com/napari/napari
[napari hub]: https://napari-hub.org/
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
[pytest]: https://docs.pytest.org/
[file an issue]: https://github.com/serg-bg/napari-isolate-cell/issues
