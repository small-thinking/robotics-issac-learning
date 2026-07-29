from __future__ import annotations

import ast
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_DIR / "tools/capture_dofbot_camera.py"


class DofbotCameraRunnerBindingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
        cls.functions = {
            node.name: node
            for node in cls.module.body
            if isinstance(node, ast.FunctionDef)
        }

    def _calls_named(self, function_name: str, called_name: str) -> list[ast.Call]:
        function = self.functions[function_name]
        return [
            node
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
            and (
                isinstance(node.func, ast.Name)
                and node.func.id == called_name
                or isinstance(node.func, ast.Attribute)
                and node.func.attr == called_name
            )
        ]

    def test_binding_uses_public_camera_world_pose_api_in_opengl_convention(
        self,
    ) -> None:
        calls = self._calls_named("_apply_camera_binding", "set_world_poses")
        self.assertEqual(len(calls), 1)
        convention = next(
            keyword.value
            for keyword in calls[0].keywords
            if keyword.arg == "convention"
        )
        self.assertIsInstance(convention, ast.Constant)
        self.assertEqual(convention.value, "opengl")

    def test_isaac_pose_inputs_cross_explicit_xyzw_boundary(self) -> None:
        self.assertEqual(
            len(
                self._calls_named(
                    "_camera_world_transform",
                    "from_xyzw",
                )
            ),
            1,
        )
        self.assertEqual(
            len(
                self._calls_named(
                    "_link4_world_transform",
                    "from_xyzw",
                )
            ),
            1,
        )

    def test_static_capture_and_looping_viewer_both_use_bound_step(self) -> None:
        self.assertGreaterEqual(
            len(self._calls_named("main", "_step_with_camera_binding")),
            1,
        )
        self.assertGreaterEqual(
            len(
                self._calls_named(
                    "_run_viewer_motion",
                    "_step_with_camera_binding",
                )
            ),
            1,
        )
        self.assertEqual(
            len(
                self._calls_named(
                    "_step_with_camera_binding",
                    "_apply_camera_binding",
                )
            ),
            1,
        )

    def test_bound_step_updates_physics_then_binds_then_renders(self) -> None:
        physics_steps = self._calls_named("_step_with_camera_binding", "step")
        binding_calls = self._calls_named(
            "_step_with_camera_binding",
            "_apply_camera_binding",
        )
        render_calls = self._calls_named(
            "_step_with_camera_binding",
            "render",
        )
        self.assertEqual(
            (len(physics_steps), len(binding_calls), len(render_calls)),
            (1, 1, 1),
        )
        render_keyword = next(
            keyword.value
            for keyword in physics_steps[0].keywords
            if keyword.arg == "render"
        )
        self.assertIsInstance(render_keyword, ast.Constant)
        self.assertIs(render_keyword.value, False)
        self.assertLess(physics_steps[0].lineno, binding_calls[0].lineno)
        self.assertLess(binding_calls[0].lineno, render_calls[0].lineno)

    def test_runner_calibrates_extrinsic_once_from_official_pose(self) -> None:
        self.assertEqual(
            len(self._calls_named("main", "calibrate")),
            1,
        )


if __name__ == "__main__":
    unittest.main()
