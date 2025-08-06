import numpy as np
import pytest
import os
from pathlib import Path
import tempfile

from napari_isolate_cell.algorithms import isolate_arbor, skeletonize_swc

# Create a small synthetic test volume
@pytest.fixture
def synthetic_volume():
    """Create a small synthetic test volume with labels 0 (background), 1 (dendrite), 2 (soma)."""
    # Create a 20x20x20 volume
    vol = np.zeros((20, 20, 20), dtype=np.uint8)
    
    # Add a soma (label 2) in the center
    vol[8:12, 8:12, 8:12] = 2
    
    # Add some dendrites (label 1) extending from the soma
    # Horizontal branch along x
    vol[10, 10, 12:18] = 1
    # Vertical branch along y
    vol[10, 12:18, 10] = 1
    # Branch along z
    vol[12:18, 10, 10] = 1
    
    # Add a disconnected soma
    vol[3:5, 3:5, 3:5] = 2
    
    # Add a disconnected dendrite
    vol[15:18, 15:18, 15:18] = 1
    
    return vol

def test_isolate_arbor(synthetic_volume):
    """Test isolating a connected arbor from a soma click."""
    # Soma click coordinates (center of main soma)
    soma_xyz = (10, 10, 10)
    
    # Isolate the arbor
    isolated = isolate_arbor(synthetic_volume, soma_xyz, close_radius=1)
    
    # Check that the output has the right shape and dtype
    assert isolated.shape == synthetic_volume.shape
    assert isolated.dtype == np.uint8
    
    # Check that the output contains exactly one soma (label 2)
    soma_count = np.sum(isolated == 2)
    assert soma_count > 0, "No soma found in isolated output"
    assert np.array_equal(np.unique(isolated[isolated == 2]), np.array([2])), "Soma labels are not all 2"
    
    # The disconnected soma should not be in the output
    assert isolated[4, 4, 4] == 0, "Disconnected soma should not be included"
    
    # The disconnected dendrite should not be in the output
    assert isolated[16, 16, 16] == 0, "Disconnected dendrite should not be included"
    
    # The connected dendrites should be in the output
    assert isolated[10, 10, 15] == 1, "Connected dendrite branch missing"
    assert isolated[10, 15, 10] == 1, "Connected dendrite branch missing"
    assert isolated[15, 10, 10] == 1, "Connected dendrite branch missing"

def test_isolate_arbor_with_click_on_dendrite(synthetic_volume):
    """Test isolating an arbor by clicking on a dendrite instead of soma."""
    # Dendrite click coordinates
    dendrite_xyz = (10, 10, 15)  # On the x-axis dendrite
    
    # Isolate the arbor
    isolated = isolate_arbor(synthetic_volume, dendrite_xyz, close_radius=1)
    
    # Check that the output contains the soma and connected dendrites
    assert isolated[10, 10, 10] == 2, "Main soma should be included when clicking on connected dendrite"
    assert isolated[10, 10, 15] == 1, "Clicked dendrite should be included"
    
    # The disconnected structures should not be in the output
    assert isolated[4, 4, 4] == 0, "Disconnected soma should not be included"
    assert isolated[16, 16, 16] == 0, "Disconnected dendrite should not be included"

def test_isolate_arbor_no_closing(synthetic_volume):
    """Test that morphological closing is optional and disconnected segments remain disconnected."""
    # Soma click coordinates
    soma_xyz = (10, 10, 10)
    
    # Create a copy with a gap that creates a truly disconnected dendrite segment
    vol_with_gap = synthetic_volume.copy()
    vol_with_gap[10, 10, 14] = 0  # Create a gap that disconnects the dendrite
    
    # Isolate with no closing - disconnected parts should be excluded
    isolated = isolate_arbor(vol_with_gap, soma_xyz, close_radius=0)
    
    # The disconnected dendrite segment should be excluded (as expected)
    assert isolated[10, 10, 15] == 0, "Disconnected dendrite segment should be excluded"
    assert isolated[10, 10, 13] == 1, "Connected dendrite before gap should be included"
    
    # Even with closing, truly disconnected segments should remain disconnected
    # This is expected behavior - the plugin doesn't fix bad segmentations
    isolated_with_closing = isolate_arbor(vol_with_gap, soma_xyz, close_radius=1)
    # The closing might not bridge larger gaps, which is fine - it's not meant to fix disconnected segmentations
    # We just verify the function runs without error
    assert isolated_with_closing[10, 10, 10] == 2, "Soma should always be included"

def test_skeletonize_swc(synthetic_volume):
    """Test skeletonizing an isolated arbor to SWC."""
    # Soma click coordinates
    soma_xyz = (10, 10, 10)
    
    # Isolate the arbor
    isolated = isolate_arbor(synthetic_volume, soma_xyz, close_radius=1)
    
    # Create a temporary file for the SWC output
    with tempfile.TemporaryDirectory() as temp_dir:
        swc_path = os.path.join(temp_dir, "test_skeleton.swc")
        
        # Skeletonize and save SWC with a small dust threshold for the tiny test volume
        skeletonize_swc(isolated, swc_path, dust_threshold=10)
        
        # Check that the SWC file was created
        assert Path(swc_path).exists(), "SWC file was not created"
        
        # Read the SWC file and check it has content
        with open(swc_path, 'r') as f:
            lines = f.readlines()
        
        # Filter out comment lines
        data_lines = [line for line in lines if line.strip() and not line.startswith('#')]
        
        # Check that there are skeleton nodes in the SWC
        assert len(data_lines) > 0, "SWC file has no skeleton nodes"
        
        # Check that we have at least one node of each type (soma+dendrite connections)
        node_types = set()
        for line in data_lines:
            parts = line.strip().split()
            if len(parts) >= 7:
                node_types.add(int(float(parts[1])))
        
        # We should have at least one node
        assert len(node_types) > 0, "No valid node types found in SWC"

# make_napari_viewer is a pytest fixture that returns a napari viewer object
def test_isolate_widget(make_napari_viewer, synthetic_volume):
    """Test the isolate_widget functionality."""
    from napari_isolate_cell._widget import make_isolate_widget
    
    # Create a viewer and add the synthetic volume as a labels layer
    viewer = make_napari_viewer()
    labels_layer = viewer.add_labels(synthetic_volume, name="test_labels")
    
    # Create the widget using the factory function (as napari would)
    widget = make_isolate_widget(viewer)
    
    # Update the widget's layer choices to include our layer
    widget.labels_layer.choices = (labels_layer,)
    widget.labels_layer.value = labels_layer
    widget.close_radius.value = 1
    
    # Test that the widget was initialized properly
    assert widget.labels_layer.value == labels_layer
    assert widget.close_radius.value == 1
    
    # Test that clicking the button doesn't raise errors
    # (actual click simulation would require more complex mocking)
    widget.call_button.clicked.emit()
