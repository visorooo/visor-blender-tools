bl_info = {
    "name": "BlenderBlendMtl",
    "author": "Victor Octavio",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "Shader Editor > Add > BlenderBlendMtl",
    "description": (
        "A layered Base + up to 9 Coat shader node with per-layer Blend "
        "Amount masks and Over/Additive blend modes, for Cycles and EEVEE."
    ),
    "category": "Node",
}

from . import nodes, operators, menu

_modules = (nodes, operators, menu)


def register():
    for module in _modules:
        module.register()


def unregister():
    for module in reversed(_modules):
        module.unregister()
