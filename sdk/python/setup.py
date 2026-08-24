from setuptools import setup, find_packages

setup(
    name="kubemind-sdk",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "httpx>=0.20.0",
    ],
    author="KubeMind team",
    description="Official Python SDK for the KubeMind gateway and governance plane",
    python_requires=">=3.8",
)
