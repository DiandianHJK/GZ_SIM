# Draft GitHub issue for ros-controls/gz_ros2_control

> How to file: open https://github.com/ros-controls/gz_ros2_control/issues/new
> and paste everything below the horizontal rule. Keep the title as-is.
> Related existing issue: #848 (same crash, reported from Rolling CI, closed as stale).

---

**Title:** Segfault in `GazeboSimROS2ControlPlugin::Configure()` with binary package 3.0.9 (Lyrical): `ns` string data pointer is NULL when building `"__ns:=" + ns` (follow-up to #848)

## Environment

- OS: Ubuntu 26.04 LTS (amd64)
- ROS 2 Lyrical, binary packages from packages.ros.org (resolute/main)
- `ros-lyrical-gz-ros2-control` **3.0.9-1resolute.20260930.014209**
- `ros-lyrical-gz-sim-vendor` 0.4.6 → **gz-sim 10.5.0** (vendored)
- `ros-lyrical-sdformat-vendor` 0.3.4, `ros-lyrical-gz-math-vendor` 0.4.3
- `ros-lyrical-ros-gz-sim` 3.0.10, `controller_manager` 6.10.1

## Description

Deterministic SIGSEGV in the gz sim server process, right after the plugin logs
`Loading controller_manager`. The simulation dies as soon as a robot carrying the
plugin is spawned, so only the world ever shows up. 100% reproducible with
different robot models.

```
[gazebo-2] [INFO] [...] [gz_ros_control]: Loading controller_manager
[gazebo-2] Stack trace (most recent call last):
...
[gazebo-2] #1    ... in gz_ros2_control::GazeboSimROS2ControlPlugin::Configure(...)
[gazebo-2] #0    ... in /opt/ros/lyrical/lib/libgz_ros2_control-system.so (anonymous)
[gazebo-2] Segmentation fault (Address not mapped to object [(nil)])
```

## How to reproduce (headless, no GUI required)

```bash
# terminal 1
gz sim -s -r <any_world>.world
# terminal 2 (any URDF containing the <gazebo><plugin filename="libgz_ros2_control-system.so" ...> block)
ros2 run ros_gz_sim create -file robot.urdf -name fishbot -z 0.05
```

Also reproduces through the standard `ros_gz_sim` launch flow.
This is the same crash as #848 (reported on Rolling with vendored gz-sim 10.1.1);
it is still present with vendored gz-sim 10.5.0 on Lyrical, so it has survived
several vendor package updates.

## gdb backtrace (gz-sim-main, SIGSEGV)

```
#0  0x00007fffb0d64744 in ??? () at /opt/ros/lyrical/lib/libgz_ros2_control-system.so
#1  gz_ros2_control::GazeboSimROS2ControlPlugin::Configure(
      unsigned long const&, std::shared_ptr<sdf::v16::Element const> const&,
      gz::sim::v10::EntityComponentManager&, gz::sim::v10::EventManager&)
    at /opt/ros/lyrical/lib/libgz_ros2_control-system.so
#2  gz::sim::v10::SystemManager::AddSystemImpl(...)
#3  gz::sim::v10::SystemManager::LoadPlugin(...)
#4  gz::sim::v10::SimulationRunner::LoadPlugins(...)
#6  gz::sim::v10::SdfEntityCreator::LoadModelPlugins()
#7  gz::sim::v10::SdfEntityCreator::CreateEntities(sdf::v16::Model const*)
#8-9 libgz-sim-user-commands-system.so (spawn handling)
#10 gz::sim::v10::SimulationRunner::UpdateSystems()
#12 gz::sim::v10::SimulationRunner::Run(unsigned long)
```

Register state at the fault: `rax = 0x0`, fault address (`si_addr`) = `0x0`.

## Binary-level forensics (3.0.9 shipped lib, symbols stripped)

Mapping runtime addresses to file vaddrs via `info proc mappings`
(`r-xp` segment base `0x7fffb0d57000` ↔ file offset `0x12000`):

- Crash PC `0x...d64744` → **file vaddr `0x1F744`**: instruction `movzbl (%rax),%eax`
  with `rax = 0` — a one-byte read from a NULL pointer.
- Frame #1 return address `0x...d6c46a` → **`Configure + 0x1CEA`** (file vaddr
  `0x2746A`). The preceding instruction is `call 0x1f4f0` with
  `%rsi = "__ns:="` (string literal at `.rodata 0x42bf8`) and `%rdx = &rhs`.
- The local function at `0x1f4f0` is the inlined
  `operator+(const char*, const std::string&)`: it loads `rhs._M_p` and
  `rhs.size()`, calls `strlen(lhs)`, builds the result string, and — at the
  crash point — copies `rhs._M_p[0]` into the result right after the
  `"__ns:="` prefix.
- Therefore the crash is exactly at (source, lyrical branch @ e5cab21d, line 445):

  ```cpp
  arguments.push_back("__ns:=" + ns);   // ns._M_p == NULL here
  ```

  although `ns` was initialized as `std::string ns = "/";` earlier in the same
  function. The `ns` string object's internal data pointer is **zeroed** somewhere
  between its initialization and this concatenation.

## What does NOT change the outcome (all tested)

- Adding `<ros><namespace>/</namespace></ros>` to the plugin SDF: `ns` is
  reassigned early in `Configure` (line ~331) and the crash still occurs at the
  same file offset → the corruption happens **after** that reassignment,
  i.e. in the second half of `Configure` (between ~line 336 and ~line 445:
  `rclcpp::init`, node creation, executor thread start, `GetEnabledJoints()`,
  `declare_parameter`, `GZResourceManager` construction).
- Different hardware plugin / yaml layout / robot model (also reproduced in #848
  with a completely different robot).
- No duplicate Gazebo installations: with the ROS environment sourced, every
  dependency of `libgz_ros2_control-system.so` resolves to
  `/opt/ros/lyrical/opt/gz_sim_vendor/lib` or `/opt/ros/lyrical/lib`.

Note: the rolling branch (4.0.2) refactors this file but still contains
`arguments.push_back("__ns:=" + ns);`, so 4.x may be affected as well
(untested — I only have Lyrical at hand).

## Offer

I am happy to help narrow this down further: run a locally built debug version
of the plugin under gdb with a hardware watchpoint on `ns` to catch the writer,
or test candidate patches on this system.
