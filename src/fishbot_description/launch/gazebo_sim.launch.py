import launch
import launch_ros
from ament_index_python.packages import get_package_share_directory
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

def generate_launch_description():
    robot_name_in_model = "fishbot"
    urdf_tutorial_path = get_package_share_directory('fishbot_description')
    default_model_path = urdf_tutorial_path + '/urdf/fishbot/fishbot.urdf.xacro'
    default_world_path = urdf_tutorial_path + '/world/custom_room.world'

    action_declare_arg_mode_path=launch.actions.DeclareLaunchArgument(
        name='model', default_value=str(default_model_path),        
        description='The absolute path of URDF'
    )

    robot_description=launch_ros.parameter_descriptions.ParameterValue(
        launch.substitutions.Command(
            ['xacro ', launch.substitutions.LaunchConfiguration('model')]
        ), value_type=str)

    robot_state_publisher_node=launch_ros.actions.Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description, 'use_sim_time': True}],
        output='screen'
    )

    launch_gazebo=launch.actions.IncludeLaunchDescription(
        PythonLaunchDescriptionSource([get_package_share_directory('ros_gz_sim'), '/launch', '/gz_sim.launch.py']), 
        launch_arguments={
            #'gz_args': f'-r {default_world_path}'
            # 黑屏就换成下面这行
             'gz_args': f'-r {default_world_path} --render-engine ogre'
        }.items()
    )
    
    spawn_entity_node=launch_ros.actions.Node(
        package='ros_gz_sim',
        executable='create',
        arguments=['-topic', 'robot_description', '-name', robot_name_in_model, ]
    )
    delay_spawn = launch.actions.TimerAction(
        period=5.0,
        actions=[spawn_entity_node]
    )
    from launch_ros.actions import Node

    controller_manager_node = Node(
        package="controller_manager",
        executable="ros2_control_node",
        parameters=[
            # 控制器yaml
            urdf_tutorial_path + '/config/fishbot_ros2_controller.yaml',
            # 把robot_description传给controller_manager
            {'robot_description': robot_description},
            {'use_sim_time': True},
    
        ],
        output="screen"
    )

    ros_gz_bridge_node = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        arguments=[
            "/clock@rosgraph_msgs/msg/Clock@gz.msgs.Clock",
            # "/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist",
            # "/odom@nav_msgs/msg/Odometry@gz.msgs.Odometry",
            # "/joint_states@sensor_msgs/msg/JointState@gz.msgs.Model",
            # "/tf@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V",
            "/lidar@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan",
            "/imu@sensor_msgs/msg/Imu@gz.msgs.IMU",
            "/camera/points@sensor_msgs/msg/PointCloud2@gz.msgs.PointCloudPacked",
            "/camera/image@sensor_msgs/msg/Image@gz.msgs.Image",
            "/camera/depth_image@sensor_msgs/msg/Image@gz.msgs.Image",
            "/camera/camera_info@sensor_msgs/msg/CameraInfo@gz.msgs.CameraInfo",

        ],
        output="screen"
    )
    spawn_controllers = launch.actions.TimerAction(
        period=10.0,
        actions=[
            launch_ros.actions.Node(
                package="controller_manager",
                executable="spawner",
                arguments=["joint_state_broadcaster"],
                output="screen"
            ),
            launch_ros.actions.Node(
                package="controller_manager",
                executable="spawner",
                arguments=["diff_drive_controller"],
                output="screen"
            ),
        ]
    )
    # spawn_controllers = launch.actions.TimerAction(
    # period=8.0,
    # actions=[
    #     launch_ros.actions.Node(
    #         package="controller_manager",
    #         executable="spawner",
    #         arguments=[
    #             "joint_state_broadcaster",
    #             "--activate",
    #             "--controller-manager", "/controller_manager",
    #             "--param-file", urdf_tutorial_path + '/config/fishbot_ros2_controller.yaml'
    #         ],
    #         output="screen"
    #     ),
    #     launch_ros.actions.Node(
    #         package="controller_manager",
    #         executable="spawner",
    #         arguments=[
    #             "diffbot_base_controller", # 【重点！和yaml顶层名字完全一致】
    #             "--activate",
    #             "--controller-manager", "/controller_manager",
    #             "--param-file", urdf_tutorial_path + '/config/fishbot_ros2_controller.yaml'
    #         ],
    #         output="screen"
    #     ),
    # ]
    # )

    return launch.LaunchDescription([
        action_declare_arg_mode_path,
        robot_state_publisher_node,
        launch_gazebo,
        #spawn_entity_node,
        delay_spawn,
        ros_gz_bridge_node,
        spawn_controllers,
        controller_manager_node
    ])