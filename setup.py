from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        name="src.core",
        sources=[
            "src/core.pyx"
        ],
        language="c",
        include_dirs=["./include"],
        extra_compile_args=['-pthread'],
        extra_link_args=['-pthread']
    ),
    Extension(
        name="src.multi_dirs_chunker",  
        sources=["src/multi_dirs_chunker.pyx"],
        language="c",
        include_dirs=["./include"],
        extra_compile_args=['-pthread'],
        extra_link_args=['-pthread']
    ),
    Extension(
        name="src.gitignore",
        sources=["src/gitignore.pyx"],
        language="c"
    )
]

setup(
    name="komodo",
    packages=["src"],
    ext_modules=cythonize(extensions, language_level="3"),
    zip_safe=False,
    install_requires=[
        'pathspec', 
    ],
)