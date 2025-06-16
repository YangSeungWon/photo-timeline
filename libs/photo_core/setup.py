from setuptools import setup, find_packages

setup(
    name="photo_core",
    version="0.1.0",
    description="Core EXIF and photo clustering utilities for Photo-Timeline",
    packages=find_packages(),
    install_requires=[
        "Pillow>=9.0",
        "piexif>=1.1",
    ],
    python_requires=">=3.8",
)
