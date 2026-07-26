'''
Optional Imports

Include:
    - pandas
'''

def pandas():
    try:
        import pandas as pd
        return pd
    except ImportError as e:
        raise ImportError(
            "Pandas support is optional.\n"
            "Install it with:\n\n"
            "   pip install pandas" 
        ) from e
