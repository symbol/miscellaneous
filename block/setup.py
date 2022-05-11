from setuptools import setup

setup(
    name='block',
    version='1.0',
    packages=['block'],
    package_data={
        '': ['*.json', '*.pkl', '*.msgpack'],
        'block': ['block/*']
    },
    install_requires=[
        'requests',
        'msgpack-python',
        'numpy',
        'pandas',
        'tqdm',
        'networkx',
    ]
)
