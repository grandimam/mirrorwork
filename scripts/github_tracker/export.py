import json
from pathlib import Path

from .types import YearlyReport


def export_json(report: YearlyReport, output_path: Path | str) -> None:
    path = Path(output_path)
    data = report.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2, default=str))


def export_json_string(report: YearlyReport) -> str:
    data = report.model_dump(mode="json")
    return json.dumps(data, indent=2, default=str)
