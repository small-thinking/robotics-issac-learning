from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from tools.dofbot_contact_report import (
    maximum_monitored_contact_force_n,
    normalized_contact_pair,
    resolve_monitored_path,
)


class DofbotContactReportTest(unittest.TestCase):
    def test_reduces_contact_point_impulses_to_force(self) -> None:
        headers = [
            SimpleNamespace(
                actor0=1,
                actor1=2,
                contact_data_offset=0,
                num_contact_data=2,
            )
        ]
        contacts = [
            SimpleNamespace(impulse=(0.03, 0.0, 0.0)),
            SimpleNamespace(impulse=(0.01, 0.03, 0.0)),
        ]
        force = maximum_monitored_contact_force_n(
            headers=headers,
            contact_data=contacts,
            critical_paths=frozenset({"/critical"}),
            physics_dt=0.01,
            decode_path={1: "/critical", 2: "/other"}.__getitem__,
        )
        self.assertTrue(math.isclose(force, 5.0))

    def test_ignores_unmonitored_actors_and_validates_dt(self) -> None:
        header = SimpleNamespace(
            actor0=1,
            actor1=2,
            contact_data_offset=0,
            num_contact_data=1,
        )
        contact = SimpleNamespace(impulse=(10.0, 0.0, 0.0))
        kwargs = {
            "headers": [header],
            "contact_data": [contact],
            "critical_paths": frozenset({"/critical"}),
            "decode_path": {1: "/other-a", 2: "/other-b"}.__getitem__,
        }
        self.assertEqual(
            maximum_monitored_contact_force_n(physics_dt=0.01, **kwargs),
            0.0,
        )
        with self.assertRaisesRegex(ValueError, "finite and positive"):
            maximum_monitored_contact_force_n(physics_dt=0.0, **kwargs)

    def test_descendant_collision_shape_resolves_to_rigid_body_owner(self) -> None:
        monitored = frozenset(
            {
                "/World/Dofbot/link4",
                "/World/Dofbot/link5/Finger_Left_03",
            }
        )
        shape = "/World/Dofbot/link5/Finger_Left_03/collisions/mesh"
        self.assertEqual(
            resolve_monitored_path(shape, monitored),
            "/World/Dofbot/link5/Finger_Left_03",
        )
        self.assertEqual(
            normalized_contact_pair(shape, "/World/Table/geometry", monitored),
            ("/World/Dofbot/link5/Finger_Left_03", None),
        )
        header = SimpleNamespace(
            actor0=1,
            actor1=2,
            contact_data_offset=0,
            num_contact_data=1,
        )
        force = maximum_monitored_contact_force_n(
            headers=[header],
            contact_data=[SimpleNamespace(impulse=(0.02, 0.0, 0.0))],
            critical_paths=monitored,
            physics_dt=0.01,
            decode_path={1: shape, 2: "/World/Table/geometry"}.__getitem__,
        )
        self.assertTrue(math.isclose(force, 2.0))

    def test_path_prefix_requires_a_complete_component(self) -> None:
        monitored = frozenset({"/World/Dofbot/link4"})
        self.assertIsNone(
            resolve_monitored_path("/World/Dofbot/link40/collider", monitored)
        )


if __name__ == "__main__":
    unittest.main()
