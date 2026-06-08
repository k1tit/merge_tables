import pandas as pd
import numpy
import os
import openpyxl
from pathlib import Path

def create_empty_excel(columns: list, filename: str, sheet_name: str = 'Sheet1'):
    df = pd.DataFrame(columns=columns)

    if not os.path.exists('report_files'):
        os.makedirs('report_files')

    filepath = os.path.join('report_files', filename)
    excel_writer = pd.ExcelWriter(filepath, engine='xlsxwriter')
    df.to_excel(excel_writer, index=False, sheet_name=sheet_name, freeze_panes=(1, 0))
    excel_writer._save()

    return filepath