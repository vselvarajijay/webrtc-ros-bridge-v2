import os
from setuptools import find_packages, setup

package_name = 'connectx_simulation'

# Colcon ament_python may copy package.xml before setuptools runs; ensure share dir exists
# (path from src/connectx_simulation to ros2_ws/install/connectx_simulation/share/connectx_simulation)
_this_dir = os.path.dirname(os.path.abspath(__file__))
_install_share = os.path.join(_this_dir, '..', '..', 'install', package_name, 'share', package_name)
_ros2_ws = os.path.normpath(os.path.join(_this_dir, '..', '..'))
if os.path.basename(_ros2_ws) == 'ros2_ws' and os.path.isdir(_ros2_ws):
    os.makedirs(_install_share, exist_ok=True)

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    entry_points={
        'console_scripts': [
            'robot_description_publisher = connectx_simulation.nodes.robot_description_publisher:main',
            'pose_to_tf = connectx_simulation.nodes.pose_to_tf:main',
            'room_walls = connectx_simulation.nodes.room_walls:main',
        ],
    },
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        # Install into subdirs first so share/connectx_simulation exists before package.xml
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
        ('share/' + package_name, ['package.xml']),
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
