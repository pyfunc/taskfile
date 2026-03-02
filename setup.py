from setuptools import setup, find_packages

setup(
    name='taskfile',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'pyyaml',
    ],
    entry_points={
        'console_scripts': [
            'taskfile=taskfile.taskfile:main',
        ],
    },
    author='Your Name',
    author_email='your.email@example.com',
    description='Python package for running taskfile with deployment options',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/pyfunc/taskfile',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)