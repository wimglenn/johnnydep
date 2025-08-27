"""Tests for size tracking functionality."""
import pytest
from johnnydep.lib import JohnnyDist, CircularMarker, _format_size


def test_format_size():
    """Test the _format_size function with various inputs."""
    assert _format_size(0) == "0 B"
    assert _format_size(512) == "512 B"
    assert _format_size(1024) == "1.0 KB"
    assert _format_size(1536) == "1.5 KB"
    assert _format_size(1024 * 1024) == "1.0 MB"
    assert _format_size(1024 * 1024 * 1024) == "1.0 GB"
    assert _format_size(1024 * 1024 * 1024 * 1024) == "1.0 TB"
    assert _format_size(1024 * 1024 * 1024 * 1024 * 1024) == "1024.0 TB"
    assert _format_size(2048) == "2.0 KB"
    assert _format_size(1024 * 512) == "512.0 KB"
    assert _format_size(1024 * 1024 * 10) == "10.0 MB"


def test_size_properties(make_dist):
    """Test size and formatted_size properties."""
    # Create a test distribution
    dist_path = make_dist(name="sizetest", version="1.0.0")
    dist = JohnnyDist("sizetest")
    
    # Test that size is populated
    assert dist.size is not None
    assert dist.size > 0
    
    # Test formatted_size
    assert dist.formatted_size != ""
    assert "B" in dist.formatted_size or "KB" in dist.formatted_size


def test_installed_size_properties(make_dist):
    """Test installed_size and formatted_installed_size properties."""
    # Create a test distribution
    dist_path = make_dist(name="installedsizetest", version="1.0.0")
    dist = JohnnyDist("installedsizetest")
    
    # Test that installed_size is populated
    assert dist.installed_size is not None
    assert dist.installed_size > 0
    
    # Test formatted_installed_size
    assert dist.formatted_installed_size != ""
    assert "B" in dist.formatted_installed_size or "KB" in dist.formatted_installed_size


def test_tree_size_with_dependencies(make_dist):
    """Test tree_size calculation with dependencies."""
    # Create distributions with dependencies
    make_dist(name="dep1", version="1.0.0")
    make_dist(name="dep2", version="1.0.0")
    make_dist(name="main", version="1.0.0", install_requires=["dep1", "dep2"])
    
    dist = JohnnyDist("main")
    
    # Test tree_size includes dependencies
    assert dist.tree_size is not None
    assert dist.tree_size > dist.size
    
    # Test formatted_tree_size
    assert dist.formatted_tree_size != ""
    assert "B" in dist.formatted_tree_size or "KB" in dist.formatted_tree_size


def test_installed_tree_size_with_dependencies(make_dist):
    """Test installed_tree_size calculation with dependencies."""
    # Create distributions with dependencies
    make_dist(name="instdep1", version="1.0.0")
    make_dist(name="instdep2", version="1.0.0")
    make_dist(name="instmain", version="1.0.0", install_requires=["instdep1", "instdep2"])
    
    dist = JohnnyDist("instmain")
    
    # Test installed_tree_size includes dependencies
    assert dist.installed_tree_size is not None
    assert dist.installed_tree_size > dist.installed_size
    
    # Test formatted_installed_tree_size
    assert dist.formatted_installed_tree_size != ""
    assert "B" in dist.formatted_installed_tree_size or "KB" in dist.formatted_installed_tree_size


def test_size_with_circular_dependencies(make_dist):
    """Test size calculations with circular dependencies."""
    # Create circular dependency
    make_dist(name="circ1", version="1.0.0", install_requires=["circ2"])
    make_dist(name="circ2", version="1.0.0", install_requires=["circ1"])
    
    dist = JohnnyDist("circ1")
    
    # Test that circular dependencies are handled
    assert dist.tree_size is not None
    assert dist.installed_tree_size is not None
    assert dist.tree_size > 0
    assert dist.installed_tree_size > 0


def test_size_none_values(make_dist):
    """Test handling of None values for size properties."""
    # Create a mock distribution where we can control the size values
    dist_path = make_dist(name="nonetest", version="1.0.0")
    dist = JohnnyDist("nonetest")
    
    # Temporarily set sizes to None to test formatting
    original_size = dist.size
    original_installed_size = dist.installed_size
    
    dist.size = None
    assert dist.formatted_size == ""
    assert dist.tree_size is None
    assert dist.formatted_tree_size == ""
    
    dist.installed_size = None
    assert dist.formatted_installed_size == ""
    assert dist.installed_tree_size is None
    assert dist.formatted_installed_tree_size == ""
    
    # Restore original values
    dist.size = original_size
    dist.installed_size = original_installed_size


def test_tree_size_excludes_duplicates(make_dist):
    """Test that tree_size doesn't double-count shared dependencies."""
    # Create a diamond dependency structure
    #    main
    #    /  \
    #   A    B
    #    \  /
    #     C
    make_dist(name="shared", version="1.0.0")
    make_dist(name="leftdep", version="1.0.0", install_requires=["shared"])
    make_dist(name="rightdep", version="1.0.0", install_requires=["shared"])
    make_dist(name="diamond", version="1.0.0", install_requires=["leftdep", "rightdep"])
    
    dist = JohnnyDist("diamond")
    
    # Get individual sizes
    shared = JohnnyDist("shared")
    leftdep = JohnnyDist("leftdep")
    rightdep = JohnnyDist("rightdep")
    
    # Tree size should not double-count the shared dependency
    expected_max = dist.size + leftdep.size + rightdep.size + 2 * shared.size
    assert dist.tree_size < expected_max
    
    # Similar check for installed_tree_size
    expected_max_installed = dist.installed_size + leftdep.installed_size + rightdep.installed_size + 2 * shared.installed_size
    assert dist.installed_tree_size < expected_max_installed


def test_size_with_child_none_values(make_dist):
    """Test tree size calculation when some children have None sizes."""
    # This tests the branches where child.size or child.installed_size might be None
    make_dist(name="childwithnone", version="1.0.0")
    make_dist(name="parentofnone", version="1.0.0", install_requires=["childwithnone"])
    
    dist = JohnnyDist("parentofnone")
    
    # Temporarily set child's size to None
    if dist.children:
        original_size = dist.children[0].size
        original_installed_size = dist.children[0].installed_size
        
        # Test with child.size = None
        dist.children[0].size = None
        tree_size = dist.tree_size
        assert tree_size == dist.size  # Should only include parent's size
        
        # Test with child.installed_size = None  
        dist.children[0].size = original_size
        dist.children[0].installed_size = None
        installed_tree_size = dist.installed_tree_size
        assert installed_tree_size == dist.installed_size  # Should only include parent's installed size
        
        # Restore original values
        dist.children[0].installed_size = original_installed_size