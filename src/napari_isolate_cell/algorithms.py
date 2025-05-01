import numpy as np
from skimage.measure import label as cc_label
from scipy.ndimage import binary_closing
from skimage.morphology import ball
try:
    # Available in scikit-image >=0.19
    from skimage.morphology import skeletonize_3d
except ImportError:
    # Older versions keep it in a private submodule
    try:
        from skimage.morphology._skeletonize_3d import skeletonize_3d  # type: ignore
    except ImportError:
        # skimage >=0.25 removed skeletonize_3d; use generic skeletonize
        from skimage.morphology import skeletonize as _skel_generic

        def skeletonize_3d(vol):  # type: ignore
            """Wrapper for skimage.morphology.skeletonize compatible with 3‑D volumes."""
            if vol.ndim != 3:
                raise ValueError("Expected 3‑D volume for skeletonization, got shape %s" % (vol.shape,))
            return _skel_generic(vol)
        import warnings

        warnings.warn(
            "scikit‑image >=0.25 removed skeletonize_3d; falling back to skeletonize, "
            "which may be slower for large volumes.",
            RuntimeWarning,
        )
import networkx as nx
from pathlib import Path

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
    """Skeletonise dendrites + soma and write SWC.
    
    Parameters
    ----------
    label_vol : np.ndarray
        The label volume containing the dendrites and soma.
    swc_path : str
        The path to save the SWC file.
    anisotropy : tuple[float, float, float], optional
        The anisotropy of the volume (Z, Y, X scale), by default (1.0, 1.0, 1.0)
    dust_threshold : int, optional
        Minimum voxel count for a skeleton component to be kept, by default 100
    """
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

    # --- New implementation using scikit‑image thinning + NetworkX graph ---
    # 1) centreline extraction via thinning
    skel_mask = skeletonize_3d(volume_to_skeletonize > 0)

    # Remove tiny skeleton fragments ("dust") if requested
    if dust_threshold > 0:
        labeled_skeleton = cc_label(skel_mask, connectivity=3)
        # Compute size of each connected component (component 0 is background)
        comp_sizes = np.bincount(labeled_skeleton.ravel())
        # Identify component ids that are smaller than the threshold (skip background id 0)
        small_ids = np.where((comp_sizes < dust_threshold) & (np.arange(comp_sizes.size) != 0))[0]
        if small_ids.size:
            skel_mask[np.isin(labeled_skeleton, small_ids)] = False
            print(f"Removed {small_ids.size} small skeleton component(s) below {dust_threshold} voxels.")

    if not np.any(skel_mask):
        print("Warning: Skeletonization produced an empty skeleton. Writing empty SWC.")
        with open(swc_path, "w") as f:
            f.write("# Empty skeleton\n")
        return

    # 2) Build graph from skeleton voxels (26‑connectivity)
    g = nx.Graph()
    coords = np.argwhere(skel_mask)
    for idx, (z, y, x) in enumerate(coords):
        g.add_node(idx, z=int(z), y=int(y), x=int(x))

    coord_to_idx = {tuple(c): i for i, c in zip(range(len(coords)), coords)}

    neighbor_shifts = [
        (dz, dy, dx)
        for dz in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
        if not (dz == dy == dx == 0)
    ]

    max_z, max_y, max_x = skel_mask.shape
    for z, y, x in coords:
        src_idx = coord_to_idx[(z, y, x)]
        for dz, dy, dx in neighbor_shifts:
            nz_, ny_, nx_ = z + dz, y + dy, x + dx  # avoid shadowing networkx alias 'nx'
            if 0 <= nz_ < max_z and 0 <= ny_ < max_y and 0 <= nx_ < max_x:
                if skel_mask[nz_, ny_, nx_]:
                    tgt_idx = coord_to_idx[(nz_, ny_, nx_)]
                    g.add_edge(src_idx, tgt_idx)

    # 3) Choose root node (closest voxel to root_zyx)
    root_voxel = tuple(np.round(root_zyx).astype(int))
    if root_voxel in coord_to_idx:
        root_idx = coord_to_idx[root_voxel]
    else:
        # fallback: pick the node closest (euclidean) to root_zyx
        dists = np.linalg.norm(coords - root_zyx, axis=1)
        root_idx = int(np.argmin(dists))

    # 4) Traverse graph (BFS) to assign parent relationships
    parent = {root_idx: -1}
    order = []
    queue = [root_idx]
    visited = set(queue)
    while queue:
        current = queue.pop(0)
        order.append(current)
        for neighbor in g.neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                parent[neighbor] = current
                queue.append(neighbor)

    # 5) Write SWC file
    with open(swc_path, "w") as f:
        f.write("# Generated by napari-isolate-cell skeletonize_swc (skimage)\n")
        for nid in order:
            z, y, x = coords[nid]
            # Convert ZYX voxel coordinates directly to XYZ physical coordinates using anisotropy
            pz = z * anisotropy[0]
            py = y * anisotropy[1]
            px = x * anisotropy[2]
            radius = 1.0  # placeholder radius
            pid = parent.get(nid, -1)
            f.write(f"{nid + 1} 3 {px:.3f} {py:.3f} {pz:.3f} {radius:.3f} {pid + 1 if pid != -1 else -1}\n")

    print(f"Skeletonization complete. Nodes: {len(coords)}. SWC saved to {swc_path}") 