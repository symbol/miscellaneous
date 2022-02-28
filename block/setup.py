from setuptools import setup

setup(
    name='block',
    version='1.0',
    packages=['block'],
    package_data={
        '': ['*.json', '*.pkl', '*.msgpack'],
        'block': ['block/*']
    },
    # scripts=[
    #     'block/extractor/extract',
    #     'block/harvester/get_block_stats',
    #     'block/delegates/find_delegates'
    # ],
    install_requires=[
        'requests',
        'msgpack-python',
        'numpy',
        'pandas',
        'tqdm',
        'networkx',
    ]
)
