from setuptools import setup

setup(
    name='symbol-treasury-analysis',
    version='1.0',
    packages=['treasury'],
    package_data={
        '': ['*.json', '*.csv'],
        'treasury': ['treasury/*']
    },
    # scripts=[
    #     'block/extractor/extract',
    #     'block/harvester/get_block_stats',
    #     'block/delegates/find_delegates'
    # ],
    install_requires=[
        'requests',
        'dash',
        'jupyter-dash',
        'msgpack-python',
        'numpy',
        'pandas',
        'tensorflow',
        'tensorflow-probability',
        'tqdm',
        'networkx',
    ]
)
