from __future__ import annotations

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from third.workflow.v1_contract import WorkflowResponseV1, WorkflowSnapshotV1


FIXTURE_DIR = Path(__file__).resolve().parents[2] / "contracts" / "third-workflow" / "v1"


class WorkflowV1ContractTests(unittest.TestCase):
    def test_all_shared_fixtures_match_the_python_contract(self) -> None:
        workflow_files = sorted(FIXTURE_DIR.glob("workflow-*.json"))
        snapshot_files = sorted(FIXTURE_DIR.glob("snapshot-*.json"))

        self.assertGreaterEqual(len(workflow_files), 6)
        self.assertGreaterEqual(len(snapshot_files), 4)
        for path in workflow_files:
            WorkflowResponseV1.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for path in snapshot_files:
            WorkflowSnapshotV1.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def test_waiting_snapshot_without_confirmation_is_rejected(self) -> None:
        payload = json.loads((FIXTURE_DIR / "snapshot-confirmation.json").read_text(encoding="utf-8"))
        payload["confirmation"] = None

        with self.assertRaises(ValidationError):
            WorkflowSnapshotV1.model_validate(payload)

    def test_renamed_confirmation_id_is_rejected(self) -> None:
        payload = json.loads((FIXTURE_DIR / "snapshot-confirmation.json").read_text(encoding="utf-8"))
        payload["confirmation"]["confirmation_id"] = payload["confirmation"].pop("confirmationId")

        with self.assertRaises(ValidationError):
            WorkflowSnapshotV1.model_validate(payload)

    def test_unknown_status_is_rejected(self) -> None:
        payload = json.loads((FIXTURE_DIR / "workflow-running.json").read_text(encoding="utf-8"))
        payload["status"] = "almost_done"

        with self.assertRaises(ValidationError):
            WorkflowResponseV1.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
