import os
from setuptools import find_packages, setup

package_name = 'connectx_planner'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), [
            'config/world_model_params.yaml',
            'config/wander_params.yaml',
        ]),
    ],
    package_data={'': ['py.typed']},
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ConnectX',
    maintainer_email='connectx@example.com',
    description='ConnectX planner: world model and wander behavior from optical flow and telemetry.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'wander_node = connectx_planner.nodes.wander_node:main',
            'world_model_node = connectx_planner.nodes.world_model_node:main',
        ],
    },
)
