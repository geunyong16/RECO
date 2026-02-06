"""Setup configuration for bid-crawler package."""
from setuptools import setup, find_packages

setup(
    name="bid-crawler",
    version="1.0.0",
    description="누리장터(나라장터) 입찰공고 크롤러 - 동적 웹페이지 크롤링 및 데이터 수집",
    author="Your Name",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "playwright>=1.40.0",
        "pydantic>=2.0",
        "aiohttp>=3.9.0",
        "schedule>=1.2.0",
        "apscheduler>=3.10.0",
        "click>=8.1.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=4.1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "bid-crawler=bid_crawler.main:main",
        ]
    },
)
