from setuptools import setup

setup(
    name='symbol-treasury-analysis',
    version='1.0',
    packages=['treasury'],
    package_data={
        '': ['*.json', '*.csv'],
        'treasury': ['treasury/*']
    },
    install_requires=[
        'requests',
        'dash',
        'dash-bootstrap-components',
        'numpy',
        'pandas',
        'tqdm',
    ]
)
