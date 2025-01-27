from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        name="src.core",
        sources=["src/core.pyx", "src/thread_pool.c"],
        language="c",
        include_dirs=["./include"],
        extra_compile_args=['-pthread'],
        extra_link_args=['-pthread']
    )
]

setup(
    name="komodo",
    packages=["src"],
    ext_modules=cythonize(extensions, language_level="3"),
    zip_safe=False,
)
