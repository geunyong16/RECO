from setuptools import setup, find_packages

setup(
    name="weighing-parser",
    version="1.1.0",
    description="Korean vehicle weighing receipt OCR text parser",
    author="Your Name",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "pydantic>=2.0",
        "structlog>=23.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.21.0",
        ],
        "async": [
            "aiofiles>=23.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "weighing-parser=weighing_parser.main:main",
        ],
    },
)
