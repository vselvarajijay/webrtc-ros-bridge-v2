#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, Shutdown
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('optical_flow_nav')
    config_path = os.path.join(pkg_share, 'config', 'default.yaml')
    if not os.path.isfile(config_path):
        # Fallback when run from workspace (e.g. install not yet done or path mismatch)
        cwd = os.getcwd()
        fallback = os.path.join(cwd, 'src', 'optical_flow_nav', 'config', 'default.yaml')
        if os.path.isfile(fallback):
            config_path = fallback

    declare_debug = DeclareLaunchArgument(
        'debug',
        default_value='false',
        description='Enable debug topic publishing (flow image, mask). Set params in YAML for now.'
    )
    declare_video_path = DeclareLaunchArgument(
        'video_path',
        default_value='',
        description='Path to a video file (e.g. .mp4). If set, test_video_publisher_node will publish frames to /camera/image_raw.'
    )
    declare_video_loop = DeclareLaunchArgument(
        'video_loop',
        default_value='false',
        description='If true, loop the video when it ends (test_video_publisher_node).'
    )
    declare_record_overlay = DeclareLaunchArgument(
        'record_overlay',
        default_value='false',
        description='If true, record a video with /navigation_state overlaid (video_overlay_recorder_node).'
    )
    declare_overlay_output_path = DeclareLaunchArgument(
        'overlay_output_path',
        default_value='',
        description='Output path for overlay video. Empty means derive from video_path (e.g. test_overlay.mp4).'
    )

    video_path = LaunchConfiguration('video_path')
    video_loop = LaunchConfiguration('video_loop')
    record_overlay = LaunchConfiguration('record_overlay')
    overlay_output_path = LaunchConfiguration('overlay_output_path')
    has_video = IfCondition(PythonExpression(["'", video_path, "' != ''"]))
    has_video_and_overlay = IfCondition(
        PythonExpression(["'", video_path, "' != '' and '", record_overlay, "' == 'true'"])
    )

    optical_flow_node = Node(
        package='optical_flow_nav',
        executable='optical_flow_node',
        name='optical_flow_node',
        output='screen',
        parameters=[config_path],
    )

    # When video publisher exits (e.g. clip ends with loop=false), shut down the whole launch.
    test_video_publisher_node = Node(
        package='optical_flow_nav',
        executable='test_video_publisher_node',
        name='test_video_publisher_node',
        output='screen',
        parameters=[{'video_path': video_path, 'loop': video_loop}],
        on_exit=[Shutdown(reason='video publisher finished')],
    )
    test_video_publisher = GroupAction(
        condition=has_video,
        actions=[test_video_publisher_node],
    )

    video_overlay_recorder_node = Node(
        package='optical_flow_nav',
        executable='video_overlay_recorder_node',
        name='video_overlay_recorder_node',
        output='screen',
        condition=has_video_and_overlay,
        parameters=[{
            'video_path': video_path,
            'overlay_output_path': overlay_output_path,
            'fps': 10.0,
        }],
    )

    return LaunchDescription([
        declare_debug,
        declare_video_path,
        declare_video_loop,
        declare_record_overlay,
        declare_overlay_output_path,
        optical_flow_node,
        test_video_publisher,
        video_overlay_recorder_node,
    ])
