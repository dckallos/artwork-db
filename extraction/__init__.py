"""
Top-level extraction package.

Regular (non-namespace) package marker so `extraction.met.*` resolves the same
way whether the project is run via `python -m extraction.met.run` from the repo
root or ever pip-installed (classic setuptools find_packages skips dirs without
this file). Sibling source packages carry their own __init__.py.
"""
