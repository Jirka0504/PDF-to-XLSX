from .registry import register
from .omnia import create as create_omnia
from .generic import create as create_generic

def bootstrap() -> None:
    # Register all parsers here
    register(create_omnia())
    register(create_generic())
