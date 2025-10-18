from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="funz-fz",
    version="0.9.0",
    description="Parametric scientific computing framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Yann Richet, Claude Sonnet",
    author_email="yann.richet@asnr.fr",
    url="https://github.com/Funz/fz",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "paramiko>=2.7.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov",
            "black",
            "flake8",
        ],
        "pandas": [
            "pandas>=1.0.0",
        ],
        "r": [
            "rpy2>=3.4.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "fz=fz.cli:main",
            "fzi=fz.cli:fzi_main",
            "fzc=fz.cli:fzc_main",
            "fzo=fz.cli:fzo_main",
            "fzr=fz.cli:fzr_main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering",
        "Topic :: System :: Distributed Computing",
    ],
    keywords="parametric computing simulation scientific hpc ssh parallel interrupt",
    project_urls={
        "Bug Reports": "https://github.com/Funz/fz/issues",
        "Source": "https://github.com/Funz/fz",
        "Documentation": "https://fz.github.io",
    },
)