import logging
from typing import Dict, List, Any
from thefuzz import process

logger = logging.getLogger(__name__)


def generate_fuzzy_mapping(
    raw_headers: List[str], config_fields: Dict[str, Any]
) -> Dict[str, str]:
    """Resolves raw headers to model fields via fuzzy matching."""
    mapping = {}
    expected_field_names = list(config_fields.keys())
    unmapped_expected = set(expected_field_names)

    # 1. Exact Name/Label Match
    unmapped_raw = []
    for raw in raw_headers:
        if not raw:
            continue
        cleaned_raw = str(raw).strip().lower()
        matched = False

        for field_name, field_cfg in config_fields.items():
            if field_name not in unmapped_expected:
                continue

            label = (
                field_cfg.get("label", "").lower()
                if isinstance(field_cfg, dict)
                else ""
            )
            if field_name.lower() == cleaned_raw or label == cleaned_raw:
                mapping[raw] = field_name
                unmapped_expected.remove(field_name)
                matched = True
                break

        if not matched:
            unmapped_raw.append(raw)

    # 2. Fuzzy Match for remaining
    for raw in unmapped_raw:
        if not unmapped_expected:
            break

        # Use a high threshold for fuzzy matching to avoid incorrect auto-mapping
        best_match, score = process.extractOne(str(raw), list(unmapped_expected))
        if score >= 85:
            mapping[raw] = best_match
            unmapped_expected.remove(best_match)
            logger.info(
                f"Fuzzy Mapper: Mapped '{raw}' to '{best_match}' (score: {score})"
            )

    return mapping


def apply_mapping(
    row_dict: Dict[str, Any], field_mapping: Dict[str, str], config: Any
) -> Dict[str, Any]:
    """Applies a field mapping to a raw row dictionary."""
    if field_mapping:
        return {field_mapping[k]: v for k, v in row_dict.items() if k in field_mapping}

    # Fallback to label-based mapping if no explicit mapping exists
    label_to_field = {
        (f_cfg.get("label") if isinstance(f_cfg, dict) else f_name): f_name
        for f_name, f_cfg in config.fields.items()
    }
    return {label_to_field.get(k, k): v for k, v in row_dict.items()}
