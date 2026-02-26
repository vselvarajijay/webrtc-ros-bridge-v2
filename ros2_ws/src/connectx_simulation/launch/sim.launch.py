from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import ExecuteProcess, SetEnvironmentVariable
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg = get_package_share_directory('connectx_simulation')
    world = os.path.join(pkg, 'worlds', 'box_car_world.sdf')
    bridge_config = os.path.join(pkg, 'config', 'bridge_params.yaml')
    models_dir = os.path.join(pkg, 'models')
    urdf_path = os.path.join(pkg, 'urdf', 'box_car.urdf')

    with open(urdf_path, 'r') as f:
        robot_description = f.read()

    return LaunchDescription([
        SetEnvironmentVariable('GZ_SIM_RESOURCE_PATH', models_dir),

        ExecuteProcess(
            cmd=['gz', 'sim', '-s', '-r', '--headless-rendering', world],
            output='screen',
        ),

        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            parameters=[{'config_file': bridge_config}],
            output='screen',
        ),

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[{'robot_description': robot_description}],
            output='screen',
        ),
        # Publish /robot_description with transient_local so Foxglove 3D gets URDF when connecting late
        Node(
            package='connectx_simulation',
            executable='robot_description_publisher',
            parameters=[{'robot_description': robot_description}],
            output='screen',
        ),
        # Dynamic world -> chassis TF from Gazebo model pose (Foxglove 3D shows robot moving)
        Node(
            package='connectx_simulation',
            executable='pose_to_tf',
            output='screen',
        ),
        # Room walls as PointCloud2 for Foxglove 3D (add Point cloud layer, topic /room_walls; avoids Marker schema issues)
        Node(
            package='connectx_simulation',
            executable='room_walls',
            output='screen',
        ),
    ])
