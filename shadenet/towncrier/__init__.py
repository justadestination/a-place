"""towncrier — continuous local event discovery.

Canonical shadenet.towncrier package (facts, entities, resolve, store,
normalize, discover). Refactored so shadenet.nightcal and the legacy
towncrier/ root re-export it.
"""

from shadenet.towncrier import discover    # noqa: F401
from shadenet.towncrier import entities    # noqa: F401
from shadenet.towncrier import facts       # noqa: F401
from shadenet.towncrier import normalize   # noqa: F401
from shadenet.towncrier import resolve     # noqa: F401
from shadenet.towncrier import store       # noqa: F401
__version__ = "0.1.0"
