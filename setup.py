from setuptools import setup, find_packages

setup(
    name="nlp-package-hallucination",
    version="0.1.0",
    description="Verifying Package Claims in LLM-Generated Code — Final Year NLP Project",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
)
