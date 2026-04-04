import os
import re
import logging
from typing import Dict, List, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class AutoConfigService:
    """
    Intelligent Schema Inference Engine.
    Analyzes raw file data to automatically suggest mappings and validation rules.
    """

    @classmethod
    def analyze_file(
        cls, file_obj, original_filename: str, sample_size: int = 100
    ) -> Dict[str, Any]:
        """
        Reads a sample of the file and returns an inferred configuration.
        """
        from import_engine.parsing.csv_adapter import CSVAdapter
        from import_engine.parsing.excel_adapter import ExcelAdapter

        ext = os.path.splitext(original_filename)[1].lower()
        adapter = None

        try:
            if ext == ".csv":
                adapter = CSVAdapter(file_obj)
            elif ext in [".xlsx", ".xls"]:
                adapter = ExcelAdapter(file_obj)
            else:
                return {"error": f"Unsupported extension: {ext}"}

            headers = adapter.get_headers()
            if not headers:
                return {"error": "No headers found in file."}


            sample_rows = []
            for _, row_dict in adapter.iter_rows(start_row=1, end_row=sample_size):
                sample_rows.append(row_dict)

            inferred_fields = {}
            for header in headers:
                if not header:
                    continue


                values = [
                    row.get(header)
                    for row in sample_rows
                    if row.get(header) is not None
                ]
                field_type, suggestions = cls._infer_field_metadata(header, values)

                inferred_fields[header] = {
                    "label": str(header),
                    "type": field_type,
                    "rules": suggestions,
                    "is_pii": cls._is_likely_pii(header),
                }

            return {
                "inferred_fields": inferred_fields,
                "total_samples": len(sample_rows),
                "suggested_model_name": cls._suggest_model_name(original_filename),
            }

        except Exception as e:
            logger.exception(f"AutoConfig Inference failed: {e}")
            return {"error": str(e)}
        finally:
            if adapter:
                adapter.close()

    @classmethod
    def _infer_field_metadata(
        cls, header: str, values: List[Any]
    ) -> Tuple[str, List[str]]:
        """Infers the data type and potential DSL rules for a field."""
        if not values:
            return "String", []


        if all(re.match(r"[^@]+@[^@]+\.[^@]+", str(v)) for v in values):
            return "Email", ["email", "required"]


        date_matches = 0
        for v in values:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    datetime.strptime(str(v), fmt)
                    date_matches += 1
                    break
                except ValueError:
                    continue
        if values and date_matches / len(values) > 0.8:
            return "Date", ["date"]


        try:
            [float(v) for v in values]
            if all(str(v).isdigit() for v in values):
                return "Integer", []
            return "Float", []
        except ValueError:
            pass


        unique_vals = set(str(v).lower() for v in values)
        if len(unique_vals) <= 5:
            return "Select", [f"in:{','.join(unique_vals)}"]

        return "String", []

    @classmethod
    def _is_likely_pii(cls, header: str) -> bool:
        """Heuristic to detect sensitive PII fields by name."""
        pii_keywords = {
            "email",
            "phone",
            "mobile",
            "address",
            "ssn",
            "passport",
            "salary",
            "birth",
        }
        header_lower = str(header).lower()
        return any(k in header_lower for k in pii_keywords)

    @classmethod
    def _suggest_model_name(cls, filename: str) -> str:
        """Suggests a model name based on the filename."""
        name = os.path.splitext(filename)[0]

        name = re.sub(r"[_\-][0-9a-fA-F]{32}", "", name)
        name = re.sub(r"[_\-]\d{8}", "", name)
        return name.split("_")[0].split("-")[0].capitalize()
