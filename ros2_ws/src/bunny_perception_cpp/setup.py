from setuptools import find_packages, setup

package_name = 'bunny_perception_cpp'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='root',
    maintainer_email='root@todo.todo',
    description='Perception nodes for depth estimation and semantic segmentation',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'da3_node = bunny_perception_cpp.nodes.da3_node:main',
            'optical_flow_node = bunny_perception_cpp.nodes.optical_flow_node:main',
            'floor_mask_node = bunny_perception_cpp.nodes.floor_mask_node:main',
        ],
    },
)
