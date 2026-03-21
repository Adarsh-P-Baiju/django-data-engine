from thefuzz import process

def generate_fuzzy_mapping(raw_headers: list[str], config_fields: dict) -> dict:
    """
    Takes raw headers from Excel/CSV and expected config fields,
    returns a mapping dict: {'Raw Header': 'config_field_name'}
    """
    mapping = {}
    expected_field_names = list(config_fields.keys())
    
    unmapped_raw = []
    unmapped_expected = set(expected_field_names)
    
    for raw in raw_headers:
        if not raw:
            continue
        cleaned_raw = str(raw).strip().lower()
        matched = False
        for expected in list(unmapped_expected):
            if expected.lower() == cleaned_raw:
                mapping[raw] = expected
                unmapped_expected.remove(expected)
                matched = True
                break
        
        if not matched:
            unmapped_raw.append(raw)
            
    for raw in unmapped_raw:
        if not unmapped_expected:
            break
            
        best_match, score = process.extractOne(str(raw), list(unmapped_expected))
        if score >= 85:
            mapping[raw] = best_match
            unmapped_expected.remove(best_match)
            
    return mapping
