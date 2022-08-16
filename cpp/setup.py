from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext

ext_modules = [
    Pybind11Extension(
        "EU4cpplib._cpplib",
        ["EU4cpplib.cpp"]
    )
]
setup(cmdclass={"build_ext": build_ext}, ext_modules=ext_modules,
      name="EU4cpplib", 
      packages=["EU4cpplib"],
      package_dir={"EU4cpplib": "wrapper"},
      package_data={"EU4cpplib": ["*.pyi", "py.typed"]},
      include_package_data=True
)