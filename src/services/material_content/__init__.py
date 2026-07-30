"""Compiled content-material services.

Import concrete contracts from their owning submodules.  Keeping this package
initializer side-effect free prevents persistence, compilation, composition,
and attachment execution from becoming one circular dependency graph.
"""

__all__: list[str] = []
