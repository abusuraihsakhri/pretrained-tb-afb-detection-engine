from setuptools import setup, find_packages

setup(
    name="tb_afb",
    version="1.1.0.dev0",
    description="Research pipeline for auditable AFB microscopy object detection",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "numpy>=1.24.0",
        "openslide-python>=1.3.0",
        "opencv-python-headless>=4.10.0",
        "torch>=2.13.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0.0"
    ],
    python_requires=">=3.10",
)
