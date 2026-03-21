import io
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Font, PatternFill
from openpyxl.comments import Comment

def generate_template(config) -> io.BytesIO:
    wb = Workbook()
    
    ws = wb.active
    ws.title = "Import Data"
    
    header_font = Font(bold=True, color="FFFFFF")
    required_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
    optional_fill = PatternFill(start_color="FFC000", end_color="FFC000", fill_type="solid")
    
    col_idx = 1

    
    for f_name, f_config in config.fields.items():
        if isinstance(f_config, list):
            rules = f_config
            label = f_name
        else:
            rules = f_config.get('rules', [])
            label = f_config.get('label', f_name)

        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font = header_font
            
        is_required = ('required' in rules) or (isinstance(f_config, dict) and f_config.get('required'))
        cell.fill = required_fill if is_required else optional_fill
        
        tips = [f"Field: {label}"]
        tips.append("Required" if is_required else "Optional")
        if isinstance(f_config, dict) and f_config.get('type') == 'fk':
            tips.append(f"Foreign Key: lookups automatically resolved via {f_config.get('lookup', 'name')}.")
            
        cell.comment = Comment('\n'.join(tips), "ImportEngine")
        
        # Support for Choices
        choices = []
        is_choice_or_fk = False

        if isinstance(f_config, dict):
            if f_config.get('type') == 'choice':
                choices = f_config.get('choices', [])
                is_choice_or_fk = True
            elif f_config.get('fk'):
                from import_engine.domain.config_registry import get_config as get_registry_config
                fk_name = f_config.get('fk')
                fk_config = get_registry_config(fk_name)
                if fk_config:
                    lookup_field = getattr(fk_config, 'lookup_field', f_config.get('lookup', 'name'))
                    # Fetch first 100 choices for the dropdown to avoid huge Excel files
                    choices = list(fk_config.model.objects.all().values_list(lookup_field, flat=True)[:100])
                    is_choice_or_fk = True

        if is_choice_or_fk and choices:
            # Create a custom named reference sheet for this specific field
            # Excel limits sheet names to 31 chars, so we truncate label just in case
            safe_sheet_name = f"{label[:20]} Reference"
            ref_ws = wb.create_sheet(title=safe_sheet_name)
            ref_ws.sheet_state = 'visible'  # visible for debugging, hide later if desired
            
            ref_ws.cell(row=1, column=1, value=f"{label} Choices")
            choice_strs = []
            for r_idx, c_val in enumerate(choices, start=2):
                # Ensure atomic values and convert to string for Excel
                val = str(c_val[0] if isinstance(c_val, (list, tuple)) else c_val)
                choice_strs.append(val)
                ref_ws.cell(row=r_idx, column=1, value=val)
                
            # Use Named Ranges (Defined Names) for bulletproof Google Sheets compatibility
            from openpyxl.workbook.defined_name import DefinedName
            
            # Sheet names with spaces must be quoted in the range string
            range_str = f"'{safe_sheet_name}'!$A$2:$A${len(choices)+1}"
            list_name = f"ChoicesList_{f_name}_{col_idx}"  # Unique name
            
            defined_name = DefinedName(name=list_name, attr_text=range_str)
            wb.defined_names.append(defined_name)
            
            formula = f"={list_name}"
            
            dv = DataValidation(
                type="list", 
                formula1=formula, 
                allow_blank=True,
                showInputMessage=True
            )
            ws.add_data_validation(dv)
            
            target_col_letter = ws.cell(row=1, column=col_idx).column_letter
            # Apply to the entire column below the header
            dv.add(f"{target_col_letter}2:{target_col_letter}1000")
            
            # Auto-adjust column width for the reference sheet
            ref_ws.column_dimensions['A'].width = max(len(label) + 10, 25)
            
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max(len(label) + 5, 15)
        col_idx += 1
        
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
