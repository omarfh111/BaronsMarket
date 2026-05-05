"""
Monkey patch GELU to fix compatibility issues
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

# Patch the forward method of existing GELU instances
def patched_gelu_forward(self, input):
    return F.gelu(input)

# Save original
_original_gelu_forward = nn.GELU.forward

# Apply patch
nn.GELU.forward = patched_gelu_forward

# Also create a new GELU class
class PatchedGELU(nn.Module):
    def __init__(self, approximate='none'):
        super().__init__()
        
    def forward(self, input):
        return F.gelu(input)
        
    def __getattr__(self, name):
        if name == 'approximate':
            return 'none'
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

# Replace the class too
nn.GELU = PatchedGELU

print("GELU patched for compatibility")