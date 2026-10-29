from __future__ import annotations

import json
import unittest

from safeops.tools import (
    delete_volume,
    get_incident,
    get_logs,
    get_metrics,
    get_resource,
    list_alarms,
    list_incidents,
    reboot_instance,
    terminate_instance,
)


class ToolTests(unittest.TestCase):
    def test_list_incidents_returns_synthetic_rows(self) -> None:
        rows = json.loads(list_incidents())
        self.assertIsInstance(rows, list)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["incident_id"], "INC-001")

    def test_get_incident_found(self) -> None:
        incident = json.loads(get_incident("INC-001"))
        self.assertEqual(incident["incident_id"], "INC-001")
        self.assertIn("synthetic", incident["summary"].lower())

    def test_get_incident_missing(self) -> None:
        result = json.loads(get_incident("INC-999"))
        self.assertIn("error", result)
        self.assertIn("unknown incident_id", result["error"])

    def test_get_resource_by_name_and_id(self) -> None:
        by_name = json.loads(get_resource("web-api-prod"))
        self.assertEqual(by_name["name"], "web-api-prod")
        self.assertEqual(by_name["resource_id"], "i-0safeops01")

        by_id = json.loads(get_resource("i-0safeops01"))
        self.assertEqual(by_id["name"], "web-api-prod")

    def test_get_resource_missing(self) -> None:
        result = json.loads(get_resource("non-existent-vm"))
        self.assertIn("error", result)

    def test_get_logs_found_and_missing(self) -> None:
        logs = json.loads(get_logs("web-api-prod"))
        self.assertEqual(logs["resource"], "web-api-prod")
        self.assertTrue(len(logs["lines"]) > 0)

        missing = json.loads(get_logs("ghost-service"))
        self.assertIn("error", missing)

    def test_get_metrics_found_and_missing(self) -> None:
        metrics = json.loads(get_metrics("web-api-prod"))
        self.assertEqual(metrics["resource"], "web-api-prod")
        self.assertIn("p99_latency_ms", metrics["metrics"])

        missing = json.loads(get_metrics("ghost-service"))
        self.assertIn("error", missing)

    def test_list_alarms(self) -> None:
        alarms = json.loads(list_alarms())
        self.assertIsInstance(alarms, list)
        self.assertGreaterEqual(len(alarms), 1)
        self.assertEqual(alarms[0]["alarm_id"], "ALM-401")

    def test_destructive_stubs_raise_runtime_error(self) -> None:
        with self.assertRaises(RuntimeError):
            reboot_instance("i-01")
        with self.assertRaises(RuntimeError):
            terminate_instance("i-01")
        with self.assertRaises(RuntimeError):
            delete_volume("vol-01")


if __name__ == "__main__":
    unittest.main()
