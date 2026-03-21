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
    
    ref_ws = wb.create_sheet(title="Reference Data")
    ref_ws.sheet_state = 'hidden'
    
    col_idx = 1
    ref_col_idx = 1
    
    for f_name, f_config in config.fields.items():
        cell = ws.cell(row=1, column=col_idx, value=f_name)
        cell.font = header_font
        
        if isinstance(f_config, list):
            rules = f_config
            label = f_name
        else:
            rules = f_config.get('rules', [])
            label = f_config.get('label', f_name)
            
        is_required = ('required' in rules) or (isinstance(f_config, dict) and f_config.get('required'))
        cell.fill = required_fill if is_required else optional_fill
        
        tips = [f"Field: {label}"]
        tips.append("Required" if is_required else "Optional")
        if isinstance(f_config, dict) and f_config.get('type') == 'fk':
            tips.append(f"Foreign Key: lookups automatically resolved via {f_config.get('lookup', 'name')}.")
            
        cell.comment = Comment('\n'.join(tips), "ImportEngine")
        
        if isinstance(f_config, dict) and f_config.get('type') == 'choice':
            choices = f_config.get('choices', [])
            if choices:
                ref_ws.cell(row=1, column=ref_col_idx, value=f"{f_name}_choices")
                for r_idx, c_val in enumerate(choices, start=2):
                    val = c_val[0] if isinstance(c_val, (list, tuple)) else c_val
                    ref_ws.cell(row=r_idx, column=ref_col_idx, value=str(val))
                    
                col_letter = ref_ws.cell(row=1, column=ref_col_idx).column_letter
                formula = f"='Reference Data'!${col_letter}$2:${col_letter}${len(choices)+1}"
                
                dv = DataValidation(type="list", formula1=formula, allow_blank=not is_required)
                ws.add_data_validation(dv)
                
                target_col_letter = ws.cell(row=1, column=col_idx).column_letter
                dv.add(f"{target_col_letter}2:{target_col_letter}1048576")
                
                ref_col_idx += 1
                
        ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max(len(label) + 5, 15)
        col_idx += 1
        
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output
