import os
from setuptools import find_packages, setup

package_name = 'connectx_robot_bridge'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), ['config/frodobot_params.yaml']),
    ],
    package_data={
        '': ['py.typed'],
        'connectx_robot_bridge': [
            'robot_sdk/earth_rovers_sdk/*.py',
        ],
    },
    install_requires=[
        'setuptools',
        'requests',
        'pyppeteer',
        'python-dotenv',
        'aiohttp',
        'opencv-python',
        'numpy',
        'PyYAML',
    ],
    zip_safe=True,
    maintainer='ConnectX',
    maintainer_email='connectx@example.com',
    description='ROS2 bridge for ConnectX robot: cmd_vel to robot control, camera feed, telemetry. Teleop/WebRTC nodes live in connectx_teleop.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bridge_node = connectx_robot_bridge.nodes.bridge_node:main',
            'calibration_node = connectx_robot_bridge.nodes.calibration_node:main',
        ],
    },
)
