import numpy as np
from skimage.measure import label as cc_label
from scipy.ndimage import binary_closing
import kimimaro
from skimage.morphology import ball # Added missing import

def isolate_arbor(vol: np.ndarray, soma_xyz: tuple[int, int, int], close_radius: int = 1) -> np.ndarray:
    """Return uint8 label volume containing only the clicked cell."""
    # Ensure soma_xyz is within bounds
    if not all(0 <= soma_xyz[i] < vol.shape[i] for i in range(3)):
        raise ValueError(f"Clicked coordinates {soma_xyz} are outside the volume dimensions {vol.shape}")

    candidate = (vol == 1) | (vol == 2)
    if close_radius > 0:
        candidate = binary_closing(candidate, structure=ball(close_radius))

    comps = cc_label(candidate, connectivity=3) # Use connectivity=3 for 3D
    
    cid = comps[soma_xyz]
    if cid == 0:
        original_label = vol[soma_xyz]
        if original_label == 1 or original_label == 2:
             print(f"Warning: Clicked voxel {soma_xyz} had label {original_label} but was not found after processing. It might be too small or disconnected after morphological closing.")
             coords_nonzero = np.argwhere(comps > 0)
             if coords_nonzero.size == 0:
                 raise ValueError("No valid components found in the volume after processing.")
             from scipy.spatial.distance import cdist
             distances = cdist([soma_xyz], coords_nonzero)
             nearest_idx = np.argmin(distances)
             nearest_coord = tuple(coords_nonzero[nearest_idx])
             cid = comps[nearest_coord]
             print(f"Using nearest component {cid} at {nearest_coord} instead.")
             if cid == 0:
                  raise ValueError("Clicked voxel isn't soma/dendrite, and failed to find a nearby component!")
        else:
             raise ValueError(f"Clicked voxel {soma_xyz} isn't soma(2) or dendrite(1), it's {original_label}!")

    mask = comps == cid
    out = np.zeros_like(vol, dtype=np.uint8)
    out[mask & (vol == 1)] = 1
    out[mask & (vol == 2)] = 2
    
    if vol[soma_xyz] == 2 and out[soma_xyz] != 2:
       print(f"Warning: Original soma voxel at {soma_xyz} was lost during isolation. Re-adding it.")
       out[soma_xyz] = 2

    return out

def skeletonize_swc(label_vol: np.ndarray, swc_path: str, anisotropy: tuple[float, float, float] = (1.0, 1.0, 1.0), dust_threshold: int = 100):
    """Skeletonise dendrites + soma and write SWC."""
    soma_vox = np.argwhere(label_vol == 2)
    if soma_vox.shape[0] == 0:
        print("Warning: No soma label (2) found in the isolated volume. Using centroid of dendrites (1) as root.")
        soma_vox = np.argwhere(label_vol == 1)
        if soma_vox.shape[0] == 0:
            print("Warning: No dendrite labels (1) either. Cannot skeletonize.")
            with open(swc_path, 'w') as f:
                f.write("# No segments found to skeletonize\n")
            return

    root_zyx = soma_vox.mean(0) 
    volume_to_skeletonize = (label_vol > 0).astype(np.uint8) 
    
    print(f"Skeletonizing volume with shape {volume_to_skeletonize.shape}...")
    print(f"Using root hint (zyx): {root_zyx}")
    print(f"Anisotropy: {anisotropy}")
    print(f"Dust threshold: {dust_threshold}")

    skels = kimimaro.skeletonize(
        label_map={1: volume_to_skeletonize},
        root_hints=[(0, int(root_zyx[0]), int(root_zyx[1]), int(root_zyx[2]))],
        dust_threshold=dust_threshold,
        anisotropy=anisotropy,
        fix_branching=True,
    )
    
    print(f"Skeletonization complete. Found {len(skels.get(1, []))} skeletons.")
    kimimaro.save_skeletons(swcs=skels, path=swc_path, anisotropy=anisotropy)
    print(f"Saved SWC skeleton to {swc_path}") 