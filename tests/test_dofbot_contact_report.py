from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from tools.dofbot_contact_report import maximum_monitored_contact_force_n


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


if __name__ == "__main__":
    unittest.main()
