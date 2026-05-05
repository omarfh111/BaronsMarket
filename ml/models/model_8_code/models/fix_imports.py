"""
Simple import compatibility fix for timm
"""
import sys
import torch.nn as nn
try:
    import timm.layers as new_layers
    
    # Create fake modules for backward compatibility
    sys.modules['timm.models.layers.drop'] = new_layers.drop
    sys.modules['timm.models.layers'] = new_layers
    
    # Also ensure the imports work
    from timm.layers import DropPath, trunc_normal_
    
    # Patch DropPath to add missing attribute
    def patched_droppath_init(self, drop_prob=0., scale_by_keep=True):
        super(DropPath, self).__init__()
        self.drop_prob = drop_prob
        self.scale_by_keep = scale_by_keep
        
    # Save original
    _original_droppath_init = DropPath.__init__
    
    # Apply patch
    DropPath.__init__ = patched_droppath_init
    
except ImportError:
    pass

print("Import compatibility fixes applied")