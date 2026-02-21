from setuptools import find_packages, setup
import os

package_name = 'connectx_boot'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), 
            ['connectx_boot/launch/connectx.launch.py']),
    ],
    package_data={'': ['py.typed']},
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ConnectX',
    maintainer_email='connectx@example.com',
    description='ConnectX unified launch: perception, planner, and optional controller/bridge.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
        ],
    },
)