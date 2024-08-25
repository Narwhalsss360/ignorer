from pathlib import Path
from setuptools import setup

npycli_path: str = (Path(__file__).parent / "extern" / "npycli").as_uri()

setup(
    install_requires=[
        f"npycli @ {npycli_path}",
        "requests"
    ]
)
