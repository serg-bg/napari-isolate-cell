"""
I/O helper functions for the napari-isolate-cell plugin.
"""
import numpy as np
import os
from pathlib import Path
import tifffile

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