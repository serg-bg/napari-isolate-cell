"""
This module contains the napari widget for isolating cell arbors from segmentation volumes.
"""
from typing import TYPE_CHECKING

from magicgui import magicgui
from magicgui.widgets import SpinBox
import napari
from pathlib import Path
from tifffile import imread, imwrite
import numpy as np

if TYPE_CHECKING:
    import napari

# Define default anisotropy - adjust if needed based on typical data
DEFAULT_ANISOTROPY = (1.0, 1.0, 1.0)
DEFAULT_DUST_THRESHOLD = 100 # Default from plan

# Use relative import for algorithms within the same package
from .algorithms import isolate_arbor, skeletonize_swc

@magicgui(
    call_button="Activate Click Isolation", # Changed button text for clarity
    layout="vertical",
    labels_layer={"label": "Input Labels Layer"},
    close_radius={"widget_type": SpinBox, "label": "Morphological Closing Radius (voxels)", "min": 0, "max": 10, "value": 1},
    anisotropy_z={"label": "Anisotropy (Z)", "min": 0.1, "max": 100.0, "value": DEFAULT_ANISOTROPY[0], "step": 0.1},
    anisotropy_y={"label": "Anisotropy (Y)", "min": 0.1, "max": 100.0, "value": DEFAULT_ANISOTROPY[1], "step": 0.1},
    anisotropy_x={"label": "Anisotropy (X)", "min": 0.1, "max": 100.0, "value": DEFAULT_ANISOTROPY[2], "step": 0.1},
    dust_threshold={"label": "Skeleton Dust Threshold (voxels)", "min": 0, "max": 10000, "value": DEFAULT_DUST_THRESHOLD}
)
def isolate_widget(
    viewer: napari.Viewer,
    labels_layer: napari.layers.Labels,
    close_radius: int = 1,
    anisotropy_z: float = DEFAULT_ANISOTROPY[0],
    anisotropy_y: float = DEFAULT_ANISOTROPY[1],
    anisotropy_x: float = DEFAULT_ANISOTROPY[2],
    dust_threshold: int = DEFAULT_DUST_THRESHOLD
):
    """Widget to isolate a cell based on a click and export results."""
    
    # --- State --- 
    # Use a dictionary to store state associated with this widget instance
    # This helps manage callbacks if multiple widgets are opened
    widget_state = {"click_callback": None, "bound_layer": None}
    
    def _cleanup_callback(state):
        """Removes the click callback if it exists and layer is valid."""
        active_callback = state.get("click_callback")
        bound_layer = state.get("bound_layer")
        
        if bound_layer and active_callback and hasattr(bound_layer, 'mouse_drag_callbacks') and active_callback in bound_layer.mouse_drag_callbacks:
            try:
                bound_layer.mouse_drag_callbacks.remove(active_callback)
                print(f"Click callback removed from layer '{bound_layer.name}'.")
            except ValueError:
                print("Callback already removed.")
        state["click_callback"] = None
        state["bound_layer"] = None # Clear bound layer on cleanup

    def _on_click(layer, event):
        """Handles the mouse click event on the layer."""
        
        # Check if the callback is still supposed to be active
        active_callback = widget_state.get("click_callback")
        if not active_callback or event.type != "mouse_press":
            return
        
        # --- One-time click logic: Immediately cleanup --- 
        print("Click detected, processing...")
        _cleanup_callback(widget_state) 
        # --- 

        # Ensure the click was on the layer bound by this widget instance
        if layer != labels_layer: # Compare with the labels_layer at the time of widget creation
            print(f"Ignoring click on unexpected layer '{layer.name}'.")
            return

        try:
            xyz_float = layer.world_to_data(event.position)
            xyz_int = tuple(int(round(c)) for c in xyz_float)
            print(f"Clicked position (data): {xyz_int}")

            if not hasattr(layer, 'data') or layer.data is None:
                raise ValueError("Selected layer has no data.")
            
            print(f"Isolating arbor (closing radius={close_radius})...")
            isolated_label_volume = isolate_arbor(layer.data, xyz_int, close_radius)

            if np.sum(isolated_label_volume > 0) == 0:
                 print(f"Isolation resulted in an empty volume near {xyz_int}.")
                 from napari.utils.notifications import show_warning
                 show_warning(f"No cell found near {xyz_int}. Isolation empty.")
                 return

            isolated_layer_name = f"isolated_{layer.name}_{xyz_int[0]}_{xyz_int[1]}_{xyz_int[2]}"
            if viewer is None or viewer.window is None:
                 print("Error: Napari viewer is not available.")
                 return
            viewer.add_labels(isolated_label_volume, name=isolated_layer_name)
            print(f"Added isolated cell layer: '{isolated_layer_name}'")

            # --- File Saving --- 
            if hasattr(layer, 'source') and layer.source and layer.source.path:
                 in_path = Path(layer.source.path)
                 base_name = in_path.stem
                 output_dir = in_path.parent
            else:
                 base_name = f"{layer.name}_isolated_at_{xyz_int[0]}_{xyz_int[1]}_{xyz_int[2]}"
                 output_dir = Path.cwd()

            output_tif_path = output_dir / f"{base_name}_isolated.tif"
            output_swc_path = output_dir / f"{base_name}_isolated.swc"
            
            print(f"Saving volume to: {output_tif_path}")
            imwrite(output_tif_path, isolated_label_volume, imagej=True, metadata={'axes': 'ZYX'})

            anisotropy = (anisotropy_z, anisotropy_y, anisotropy_x)
            print(f"Skeletonizing (dust={dust_threshold}) and saving SWC to: {output_swc_path}")
            skeletonize_swc(isolated_label_volume, str(output_swc_path), anisotropy=anisotropy, dust_threshold=dust_threshold)
            
            print("Processing complete.")
            from napari.utils.notifications import show_info
            show_info(f"Saved: {output_tif_path.name} and {output_swc_path.name}")

        except ValueError as e:
            print(f"Error during isolation: {e}")
            from napari.utils.notifications import show_error
            show_error(f"Isolation Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
            from napari.utils.notifications import show_error
            show_error(f"Unexpected Error: {e}")

    # --- Callback Activation Logic --- 
    # This function runs when the magicgui button is clicked.
    def activate_click_mode():
        # Cleanup any previous callback from this widget instance first
        _cleanup_callback(widget_state)
        
        # Check if the currently selected layer in the widget is valid
        current_layer = labels_layer # From the magicgui args
        if not isinstance(current_layer, napari.layers.Labels):
            err_msg = "Please select a valid Labels layer first."
            print(f"Error: {err_msg}")
            from napari.utils.notifications import show_warning
            show_warning(err_msg)
            return
        
        # Bind the callback to the currently selected layer
        print(f"Activating click mode for layer '{current_layer.name}'. Click once on the target soma.")
        current_layer.mouse_drag_callbacks.append(_on_click)
        widget_state["click_callback"] = _on_click
        widget_state["bound_layer"] = current_layer # Store which layer this callback is for
        
        from napari.utils.notifications import show_info
        show_info(f"Click mode active for '{current_layer.name}'")

        # --- Auto-cleanup listeners --- 
        # Clean up if the bound layer is removed from the viewer.
        def _handle_layer_removal(event):
            removed_layer = event.value
            bound_layer = widget_state.get("bound_layer")
            if removed_layer == bound_layer:
                print(f"Bound layer '{bound_layer.name}' removed, cleaning up callback.")
                _cleanup_callback(widget_state)
                # Disconnect listener to prevent memory leaks if widget persists
                viewer.layers.events.removed.disconnect(_handle_layer_removal)
                
        # Connect only if not already connected (simple check)
        try: 
             viewer.layers.events.removed.disconnect(_handle_layer_removal)
        except (TypeError, RuntimeError): # Already disconnected or never connected
             pass
        viewer.layers.events.removed.connect(_handle_layer_removal)
        
    # --- On Button Click --- 
    activate_click_mode() # Call the activation logic directly

# No return value needed if magicgui handles the widget lifecycle.
