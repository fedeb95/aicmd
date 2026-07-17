# aicmd/paths.py

import os
import sys


def app_path(*parts):
    if getattr(sys, "frozen", False):
        # directory dell'eseguibile
        base = os.path.dirname(sys.executable)
    else:
        # root progetto
        base = os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

    return os.path.join(base, *parts)
