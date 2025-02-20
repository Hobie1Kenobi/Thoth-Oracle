from setuptools import setup, find_packages

setup(
    name="thoth-oracle",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "xrpl-py",
        "web3",
        "aiohttp",
        "numpy",
        "pandas",
        "qiskit",
        "pytest",
        "pytest-asyncio",
        "pytest-cov"
    ]
)
