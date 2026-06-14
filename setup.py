from setuptools import setup, find_packages


def read_requirements(file):
    with open(file, "r") as f:
        return f.read().splitlines()


setup(
    name="snopyrator",
    version="0.5",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "snopyrator = snopyrator.snopyrator:main",
        ],
    },
    package_data={"snopyrator": ["snes_sfc_roms_info.json"]},
    install_requires=read_requirements("requirements.txt"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.7",
    url="https://github.com/bozothegeek/snopyrator",
)
