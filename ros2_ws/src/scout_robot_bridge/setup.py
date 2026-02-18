import os
from setuptools import find_packages, setup

package_name = 'scout_robot_bridge'

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
        'scout_robot_bridge': [
            'robot_sdk/earth_rovers_sdk/*.py',
        ],
    },
    install_requires=[
        'setuptools',
        'requests',
        'pyppeteer',
        'python-dotenv',
        'aiohttp',
        'keyboard',  # For key release event detection
        # webrtc_node (optional at runtime):
        'aiortc',
        'av',
        'numpy',
        'opencv-python-headless',
        'websockets',
        # Note: pynput removed - not needed for direct robot control
        # Terminal input works fine without X11 dependencies
    ],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'bridge_node = scout_robot_bridge.nodes.bridge_node:main',
            'teleop_node = scout_robot_bridge.nodes.teleop_node:main',
            'webrtc_node = scout_robot_bridge.nodes.webrtc_node:main',
        ],
    },
)
