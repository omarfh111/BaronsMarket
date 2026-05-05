"""
Patch DropPath for compatibility
"""
try:
    from timm.layers import DropPath
    
    # Patch existing instances to add scale_by_keep
    def patched_droppath_getattr(self, name):
        if name == 'scale_by_keep':
            return True
        return object.__getattribute__(self, name)
    
    DropPath.__getattr__ = patched_droppath_getattr
    
    print("DropPath patched for compatibility")
except ImportError:
    pass