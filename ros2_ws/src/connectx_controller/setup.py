import os
from setuptools import find_packages, setup

package_name = 'connectx_controller'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), ['config/controller_params.yaml']),
    ],
    package_data={'': ['py.typed']},
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ConnectX',
    maintainer_email='connectx@example.com',
    description='ConnectX controller: autonomy command execution and velocity control.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'controller_node = connectx_controller.nodes.controller_node:main',
            'manual_controller = connectx_controller.nodes.manual_controller:main',
        ],
    },
)
