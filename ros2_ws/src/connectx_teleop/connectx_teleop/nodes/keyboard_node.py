#!/usr/bin/env python3
"""
Keyboard connection node: reads arrow keys and speed mode 1-5, publishes target
Twist to /teleop/velocity_target. Run manual_controller (connectx_controller) for
ramping and safety; this node is connection-only.
"""

import sys
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

import termios
import tty
import select

from connectx_teleop.constants import TELEOP_VELOCITY_TARGET_TOPIC

try:
    import keyboard as kb
    HAS_KEYBOARD_LIB = True
except ImportError:
    HAS_KEYBOARD_LIB = False
    kb = None

# Tuning (same scale as original teleop; manual_controller does ramping)
LINEAR_MAX = 0.3   # m/s (mode 5)
ANGULAR_MAX = 0.6  # rad/s (mode 5)
CONTROL_HZ = 50
SPEED_MODE_MIN = 1
SPEED_MODE_MAX = 5
SPEED_MODE_DEFAULT = 3


class KeyboardNode(Node):
    """Publishes target velocities to /teleop/velocity_target from keyboard input."""

    def __init__(self):
        super().__init__("keyboard_node")
        self.pub = self.create_publisher(Twist, TELEOP_VELOCITY_TARGET_TOPIC, 10)
        self._lock = threading.Lock()
        self._held: set[str] = set()
        self._quit = threading.Event()
        self._speed_mode = SPEED_MODE_DEFAULT
        self.create_timer(1.0 / CONTROL_HZ, self._control_tick)

    def _get_speed_limits(self) -> tuple[float, float]:
        scale = self._speed_mode / float(SPEED_MODE_MAX)
        return (LINEAR_MAX * scale, ANGULAR_MAX * scale)

    def _control_tick(self) -> None:
        if self._quit.is_set():
            return
        with self._lock:
            held = set(self._held)
        linear_max_i, angular_max_i = self._get_speed_limits()
        target_linear = 0.0
        target_angular = 0.0
        if "up" in held:
            target_linear += linear_max_i
        if "down" in held:
            target_linear -= linear_max_i
        if "right" in held:
            target_angular -= angular_max_i
        if "left" in held:
            target_angular += angular_max_i
        if abs(target_linear) > 0.01 and abs(target_angular) > 0.01:
            factor = 1.0 / (2.0 ** 0.5)
            target_linear *= factor
            target_angular *= factor
        msg = Twist()
        msg.linear.x = float(target_linear)
        msg.angular.z = float(target_angular)
        self.pub.publish(msg)

    def run_keyboard_listener(self) -> None:
        if HAS_KEYBOARD_LIB:
            try:
                self._run_keyboard_lib_listener()
                return
            except Exception as e:
                self.get_logger().warning("keyboard library failed: %s, falling back to terminal", e)
        self._run_terminal_key_reader()

    def _run_keyboard_lib_listener(self) -> None:
        key_map = {"up": "up", "down": "down", "left": "left", "right": "right"}

        def on_key_event(event):
            if event.event_type == kb.KEY_DOWN:
                key_name = event.name.lower()
                if key_name in ("1", "2", "3", "4", "5"):
                    with self._lock:
                        self._speed_mode = int(key_name)
                    return
                if key_name in key_map:
                    with self._lock:
                        self._held.add(key_map[key_name])
            elif event.event_type == kb.KEY_UP:
                key_name = event.name.lower()
                if key_name in key_map:
                    with self._lock:
                        self._held.discard(key_map[key_name])

        kb.hook(on_key_event)
        while not self._quit.is_set():
            time.sleep(0.1)
        kb.unhook_all()

    def _run_terminal_key_reader(self) -> None:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        HELD_TIMEOUT = 0.3
        last_seen: dict[str, float] = {}
        arrow_map = {"A": "up", "B": "down", "C": "right", "D": "left"}
        try:
            tty.setraw(fd)
            while not self._quit.is_set():
                try:
                    ready = select.select([sys.stdin], [], [], 0.001)[0]
                    if not ready:
                        now = time.monotonic()
                        with self._lock:
                            expired = [k for k, t in last_seen.items() if now - t > HELD_TIMEOUT]
                            for k in expired:
                                self._held.discard(k)
                                del last_seen[k]
                        continue
                    ch = sys.stdin.read(1)
                except Exception as e:
                    self.get_logger().error("Key reader error: %s", e)
                    time.sleep(0.01)
                    continue
                if ch in ("\x03", "\x04"):
                    self._quit.set()
                    break
                if ch in (" ", "s", "S"):
                    with self._lock:
                        self._held.clear()
                    last_seen.clear()
                    continue
                if ch in ("1", "2", "3", "4", "5"):
                    with self._lock:
                        self._speed_mode = int(ch)
                    continue
                if ch == "\x1b":
                    try:
                        remaining = sys.stdin.read(2)
                        if len(remaining) >= 2 and remaining[0] == "[":
                            key = arrow_map.get(remaining[1])
                            if key:
                                now = time.monotonic()
                                with self._lock:
                                    opposite = {"up": "down", "down": "up", "left": "right", "right": "left"}.get(key)
                                    if opposite and opposite in self._held:
                                        self._held.discard(opposite)
                                        if opposite in last_seen:
                                            del last_seen[opposite]
                                    for h in list(self._held):
                                        last_seen[h] = now
                                    self._held.add(key)
                                    last_seen[key] = now
                    except Exception:
                        pass
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass
            with self._lock:
                self._held.clear()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = KeyboardNode()
    if not sys.stdin.isatty():
        node.get_logger().error("stdin is not a TTY – run in a real terminal")
        rclpy.shutdown()
        return
    node.get_logger().info(
        "Keyboard node: publishing to %s. Run manual_controller for ramping/safety.",
        TELEOP_VELOCITY_TARGET_TOPIC,
    )
    node.get_logger().info(
        "Arrow keys to move, 1-5 speed mode, Space/s to stop, Ctrl+C to quit."
    )
    keyboard_thread = threading.Thread(target=node.run_keyboard_listener, daemon=True)
    keyboard_thread.start()
    time.sleep(0.1)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node._quit.set()
        msg = Twist()
        node.pub.publish(msg)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
