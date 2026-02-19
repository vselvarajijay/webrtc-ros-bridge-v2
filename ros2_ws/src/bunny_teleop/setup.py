import os
from setuptools import find_packages, setup

package_name = 'bunny_teleop'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    package_data={'': ['py.typed']},
    install_requires=[
        'setuptools',
        'numpy',
        'av',
        'aiortc',
        'opencv-python-headless',
        'websockets',
    ],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='Teleop connection layer: WebRTC and keyboard nodes that route to controllers.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'webrtc_node = bunny_teleop.nodes.webrtc_node:main',
            'keyboard_node = bunny_teleop.nodes.keyboard_node:main',
        ],
    },
)
