import os
from setuptools import find_packages, setup

package_name = 'connectx_simulation'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    entry_points={
        'console_scripts': [
            'robot_description_publisher = connectx_simulation.nodes.robot_description_publisher:main',
        ],
    },
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), [
            'launch/sim.launch.py',
        ]),
        (os.path.join('share', package_name, 'config'), [
            'config/bridge_params.yaml',
        ]),
        (os.path.join('share', package_name, 'urdf'), [
            'urdf/box_car.urdf',
        ]),
        (os.path.join('share', package_name, 'models', 'box_car'), [
            'models/box_car/model.config',
            'models/box_car/model.sdf',
        ]),
        (os.path.join('share', package_name, 'worlds'), [
            'worlds/box_car_world.sdf',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ConnectX',
    maintainer_email='connectx@example.com',
    description='ConnectX Gazebo simulation: box car, world, bridge, launch.',
    license='Apache-2.0',
    extras_require={
        'test': ['pytest'],
    },
)
