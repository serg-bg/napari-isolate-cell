"""
I/O helper functions for the napari-isolate-cell plugin.
"""
import numpy as np
import os
from pathlib import Path
import tifffile
from typing import Optional, Callable, List, Tuple, Dict, Any

# Define known TIFF resolution units (simplified)
# Based on https://www.loc.gov/preservation/digital/formats/content/tiff_tags.shtml
TIFF_RESOLUTION_UNIT_INCH = 2
TIFF_RESOLUTION_UNIT_CENTIMETER = 3
# Add Micrometer based on some software exporting it
TIFF_RESOLUTION_UNIT_MICROMETER = 10 # Non-standard but sometimes seen

# Define common ways to write micrometers
MICROMETER_UNITS = {'micron', 'microns', 'um', 'µm', '\\u00b5m'}

def _parse_ij_description_string(desc: str) -> Dict[str, str]:
    """Helper to parse ImageJ key=value description string."""
    ij_props = {}
    # Handle potential byte strings decoded with backslashes
    lines = desc.replace('\\\\n', '\\n').split('\\n') 
    for line in lines:
        if '=' in line:
            key, value = line.split('=', 1)
            ij_props[key.strip().lower()] = value.strip() # Use lowercase keys
    return ij_props

def _get_microns_per_unit(unit_code: int, unit_str: Optional[str] = None) -> Optional[float]:
    """Get conversion factor to microns based on TIFF unit code or string."""
    unit_str_lower = unit_str.lower() if unit_str else None

    if unit_code == TIFF_RESOLUTION_UNIT_MICROMETER or unit_str_lower in MICROMETER_UNITS:
        return 1.0
    elif unit_code == TIFF_RESOLUTION_UNIT_INCH:
        return 25400.0  # Microns per inch
    elif unit_code == TIFF_RESOLUTION_UNIT_CENTIMETER:
        return 10000.0  # Microns per cm
    # Add other units if needed (e.g., millimeter=1000.0)
    
    # Fallback: If only unit string is present and known
    if unit_str_lower in MICROMETER_UNITS:
         return 1.0
    
    return None # Unknown or unsupported unit

def _extract_scale_from_metadata(tiff_file: tifffile.TiffFile) -> Optional[Tuple[float, float, float]]:
    """Attempt to extract ZYX scale (in micrometers) from TIF metadata, prioritizing ImageJ tags."""
    page = tiff_file.pages[0]
    tags = page.tags

    scale_zyx = [1.0, 1.0, 1.0]
    scale_known = [False, False, False] # Z, Y, X
    ij_unit = 'micron' # Default unit assumption
    found_ij_unit = False

    # 1. Check ImageJ Metadata (dictionary or description string)
    ij_metadata_dict = tiff_file.imagej_metadata
    ij_props = {}

    if ij_metadata_dict and isinstance(ij_metadata_dict, dict):
        # Use lowercase keys for consistency
        ij_props = {k.lower(): v for k, v in ij_metadata_dict.items()}
        print("Found parsed ImageJ metadata dictionary.")
    elif 'ImageDescription' in tags:
        desc = tags['ImageDescription'].value
        if isinstance(desc, bytes):
            try:
                desc = desc.decode('utf-8')
            except UnicodeDecodeError:
                desc = str(desc) # Fallback
        if isinstance(desc, str) and desc.startswith('ImageJ='):
            print("Parsing ImageJ metadata from ImageDescription string.")
            ij_props = _parse_ij_description_string(desc)
            
    # Extract info from parsed ImageJ properties (if any)
    if ij_props:
        # Get Unit
        temp_unit = ij_props.get('unit')
        if temp_unit:
            ij_unit = temp_unit
            found_ij_unit = True
            print(f"  Found ImageJ Unit: '{ij_unit}'")
            # Normalize common variations
            if ij_unit.lower() in MICROMETER_UNITS:
                ij_unit = 'micron' # Standardize
        
        # Get Z scale (spacing)
        if 'spacing' in ij_props:
            try:
                scale_zyx[0] = float(ij_props['spacing'])
                scale_known[0] = True
                print(f"  Found ImageJ Z Spacing: {scale_zyx[0]}")
            except (ValueError, TypeError): pass
        elif 'finterval' in ij_props: # Check alternative Z spacing key
             try:
                scale_zyx[0] = float(ij_props['finterval'])
                scale_known[0] = True
                print(f"  Found ImageJ Z FInterval: {scale_zyx[0]}")
             except (ValueError, TypeError): pass
             
        # Get explicit X/Y scale if present
        if 'x_scale' in ij_props:
            try:
                scale_zyx[2] = float(ij_props['x_scale'])
                scale_known[2] = True
                print(f"  Found ImageJ X Scale: {scale_zyx[2]}")
            except (ValueError, TypeError): pass
        elif 'pixelwidth' in ij_props: # Check alternative X scale key
            try:
                scale_zyx[2] = float(ij_props['pixelwidth'])
                scale_known[2] = True
                print(f"  Found ImageJ Pixel Width: {scale_zyx[2]}")
            except (ValueError, TypeError): pass

        if 'y_scale' in ij_props:
            try:
                scale_zyx[1] = float(ij_props['y_scale'])
                scale_known[1] = True
                print(f"  Found ImageJ Y Scale: {scale_zyx[1]}")
            except (ValueError, TypeError): pass
        elif 'pixelheight' in ij_props: # Check alternative Y scale key
             try:
                scale_zyx[1] = float(ij_props['pixelheight'])
                scale_known[1] = True
                print(f"  Found ImageJ Pixel Height: {scale_zyx[1]}")
             except (ValueError, TypeError): pass


    # 2. Check standard TIFF Resolution Tags if X or Y scale still unknown
    if not scale_known[2] or not scale_known[1]:
        x_res_tag = tags.get('XResolution')
        y_res_tag = tags.get('YResolution')
        unit_tag = tags.get('ResolutionUnit')
        
        unit_code = unit_tag.value if unit_tag and unit_tag.value else None
        
        # Determine the unit conversion factor (microns per unit)
        # Prioritize standard unit tag, fallback to ImageJ unit string if standard is missing/unknown
        microns_per_unit = _get_microns_per_unit(unit_code, ij_unit if found_ij_unit else None)
        
        if microns_per_unit is None and unit_code is not None:
             print(f"Warning: Unsupported standard TIFF ResolutionUnit code: {unit_code}. Cannot use standard resolution tags.")
        elif microns_per_unit is None and unit_code is None and not found_ij_unit:
             print("Warning: Standard TIFF ResolutionUnit missing and no ImageJ unit found. Cannot determine scale from standard tags.")
             
        if microns_per_unit is not None: # Only proceed if we know the unit
             print(f"Processing standard TIFF tags with unit factor: {microns_per_unit} um/unit (Unit code: {unit_code}, IJ Unit: {ij_unit if found_ij_unit else 'N/A'})")
             if not scale_known[2] and x_res_tag and x_res_tag.value: # Check X
                 try:
                     x_res = x_res_tag.value[0] / x_res_tag.value[1] # Pixels per unit
                     if x_res > 0:
                         scale_zyx[2] = (1.0 / x_res) * microns_per_unit # um per pixel
                         scale_known[2] = True
                         print(f"  Calculated X scale from standard tag: {scale_zyx[2]:.4f} um/pixel")
                 except (AttributeError, IndexError, ZeroDivisionError, TypeError) as e:
                     print(f"  Warning: Could not parse XResolution tag: {e}")

             if not scale_known[1] and y_res_tag and y_res_tag.value: # Check Y
                 try:
                     y_res = y_res_tag.value[0] / y_res_tag.value[1] # Pixels per unit
                     if y_res > 0:
                         scale_zyx[1] = (1.0 / y_res) * microns_per_unit # um per pixel
                         scale_known[1] = True
                         print(f"  Calculated Y scale from standard tag: {scale_zyx[1]:.4f} um/pixel")
                 except (AttributeError, IndexError, ZeroDivisionError, TypeError) as e:
                     print(f"  Warning: Could not parse YResolution tag: {e}")

    # 3. Final checks and unit conversion (if ImageJ unit wasn't micron)
    if found_ij_unit and ij_unit != 'micron':
         # Apply conversion only if scale was determined from ImageJ explicit values (spacing, x_scale, y_scale etc)
         # AND the unit wasn't micron. Scale derived from standard tags is already in microns.
         # This logic might need refinement if complex unit mixing occurs.
         print(f"Warning: ImageJ unit was '{ij_unit}'. Assuming scales derived *directly* from ImageJ tags (spacing, x_scale, etc.) need conversion.")
         # Add conversion factors here if needed. Example for 'mm':
         # if ij_unit == 'mm':
         #    if scale_known[0] and 'spacing' in ij_props: scale_zyx[0] *= 1000.0
         #    if scale_known[1] and ('y_scale' in ij_props or 'pixelheight' in ij_props) : scale_zyx[1] *= 1000.0
         #    if scale_known[2] and ('x_scale' in ij_props or 'pixelwidth' in ij_props) : scale_zyx[2] *= 1000.0
         # For now, just warn:
         print(f"  -> Scale values {scale_zyx} might need manual adjustment if units are not micrometers.")

    # Ensure scale values are positive
    if any(s <= 0 for s in scale_zyx):
        print(f"Warning: Invalid non-positive scale detected {scale_zyx}. Resetting affected axes to 1.0.")
        scale_zyx = [s if s > 0 else 1.0 for s in scale_zyx]

    if not any(scale_known):
        print("Could not determine scale from metadata. Using default (1,1,1).")
        return None # Indicate scale couldn't be found
    
    final_scale = tuple(scale_zyx)
    print(f"Final determined scale (ZYX) in µm: {final_scale}")
    return final_scale


def napari_get_reader(path: str) -> Optional[Callable[[str], List[Tuple[Any, Dict, str]]]]:
    """A basic implementation of the napari_get_reader hook specification.

    Parameters
    ----------
    path : str or list of str
        Path to file, or list of paths.

    Returns
    -------
    function or None
        If the path is a recognized format, return a function that accepts the
        same path or list of paths, and returns a list of layer data tuples.
    """
    if isinstance(path, str) and path.lower().endswith(('.tif', '.tiff')):
        return read_tiff_with_scale
    return None


def read_tiff_with_scale(path: str) -> List[Tuple[Any, Dict, str]]:
    """Reads a TIFF file and extracts scale information for Napari.

    Parameters
    ----------
    path : str or list of str
        Path to file, or list of paths.

    Returns
    -------
    List[Tuple[Any, Dict, str]]
        A list of LayerData tuples, where each tuple contains the data, metadata dict, and layer type.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find TIFF file at {path}")
        
    try:
        with tifffile.TiffFile(path) as tif:
            data = tif.asarray()
            scale = _extract_scale_from_metadata(tif)
            
            metadata = {"name": path.stem}
            if scale:
                metadata["scale"] = scale
            else: 
                # If scale extraction fails, use default 1,1,1 but maybe warn user?
                metadata["scale"] = (1.0, 1.0, 1.0) 
                from napari.utils.notifications import show_warning
                show_warning(f"Could not read scale from {path.name}. Assuming (1,1,1). Please check/set anisotropy manually.")

            # Determine layer type (simple check for now)
            # Could be improved (e.g., check if data looks like labels)
            layer_type = 'image' 
            if data.ndim == 3 and data.dtype in (np.int32, np.uint32, np.int64, np.uint64, np.uint8, np.uint16):
                 # Heuristic: If 3D integer type, assume it's labels for this plugin's purpose
                 unique_vals = np.unique(data)
                 if len(unique_vals) < 256: # Arbitrary threshold for typical label counts
                      layer_type = 'labels'
                 else:
                      print(f"Warning: Integer data type but >256 unique values. Loading as 'image'. Load as 'labels' manually if needed.")

            return [(data, metadata, layer_type)]

    except Exception as e:
        print(f"Error reading TIFF {path}: {e}")
        raise # Re-raise exception for Napari to handle


def save_tiff(volume: np.ndarray, path: str, channel_axis=None, metadata=None):
    """
    Save a 3D numpy array as a TIFF stack with optional metadata.
    
    Parameters
    ----------
    volume : np.ndarray
        The 3D volume to save
    path : str
        Output file path
    channel_axis : int, optional
        The axis that contains channel information, by default None
    metadata : dict, optional
        Additional metadata to include in the TIFF file, by default None
    """
    path = Path(path)
    os.makedirs(path.parent, exist_ok=True)
    
    # Default metadata for better interoperability
    if metadata is None:
        metadata = {}
    
    default_metadata = {'axes': 'ZYX'}
    metadata = {**default_metadata, **metadata}
    
    tifffile.imwrite(
        path, 
        volume, 
        imagej=True, 
        metadata=metadata,
        channel_axis=channel_axis
    )

def load_tiff(path: str) -> np.ndarray:
    """
    Load a TIFF stack as a numpy array.
    
    Parameters
    ----------
    path : str
        Path to the TIFF file
        
    Returns
    -------
    np.ndarray
        The loaded volume
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find TIFF file at {path}")
    
    return tifffile.imread(path)

def read_swc(swc_path: str) -> np.ndarray:
    """
    Read an SWC skeleton file into a numpy array.
    
    Parameters
    ----------
    swc_path : str
        Path to the SWC file
        
    Returns
    -------
    np.ndarray
        Array with shape (n, 7) containing the SWC data:
        [id, type, x, y, z, radius, parent_id]
    """
    path = Path(swc_path)
    if not path.exists():
        raise FileNotFoundError(f"Could not find SWC file at {path}")
    
    # Read SWC format: [id, type, x, y, z, radius, parent]
    with open(swc_path, 'r') as f:
        lines = f.readlines()
    
    # Filter out comment lines and empty lines
    data_lines = [line for line in lines if line.strip() and not line.startswith('#')]
    
    if not data_lines:
        return np.empty((0, 7))
    
    # Parse the SWC data
    swc_data = []
    for line in data_lines:
        parts = line.strip().split()
        if len(parts) >= 7:  # Valid SWC line should have 7 columns
            swc_data.append([float(p) for p in parts[:7]])
    
    return np.array(swc_data) 