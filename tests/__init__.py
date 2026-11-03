import pathlib
import sys

# The CLI modules live in scripts/; make them importable for every test module.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
