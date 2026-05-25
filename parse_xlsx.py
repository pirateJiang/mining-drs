import zipfile
import xml.etree.ElementTree as ET

def get_shared_strings(zf):
    strings = []
    try:
        with zf.open('xl/sharedStrings.xml') as f:
            tree = ET.parse(f)
            root = tree.getroot()
            ns = {'ns': root.tag.split('}')[0].strip('{')}
            for si in root.findall('ns:si', ns):
                t = si.find('ns:t', ns)
                if t is not None:
                    strings.append(t.text)
                else:
                    strings.append('')
    except KeyError:
        pass
    return strings

def parse_sheet(zf, sheet_path, shared_strings):
    with zf.open(sheet_path) as f:
        tree = ET.parse(f)
        root = tree.getroot()
        ns = {'ns': root.tag.split('}')[0].strip('{')}
        sheet_data = root.find('ns:sheetData', ns)
        for row in sheet_data.findall('ns:row', ns):
            row_idx = row.get('r')
            row_vals = []
            for c in row.findall('ns:c', ns):
                col_idx = c.get('r')
                v = c.find('ns:v', ns)
                val = v.text if v is not None else ''
                if c.get('t') == 's' and val:
                    val = shared_strings[int(val)]
                row_vals.append(f"{col_idx}:{val}")
            if row_vals:
                print(f"Row {row_idx}: " + " | ".join(row_vals))

with zipfile.ZipFile('examples/MiningSystemDRS_ConfExStrings_v4.xlsx', 'r') as zf:
    shared = get_shared_strings(zf)
    print("Workbook strings:", shared[:20]) # preview
    
    # get sheet names
    with zf.open('xl/workbook.xml') as f:
        tree = ET.parse(f)
        root = tree.getroot()
        ns = {'ns': root.tag.split('}')[0].strip('{')}
        sheets = root.find('ns:sheets', ns)
        for sheet in sheets.findall('ns:sheet', ns):
            name = sheet.get('name')
            sheet_id = sheet.get('sheetId')
            # map to filename
            rel_id = sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            print(f"Sheet: {name} (Id: {sheet_id}, Rel: {rel_id})")

    # In a typical xlsx, sheets are in xl/worksheets/sheet1.xml, etc.
    for i in range(1, 4):
        try:
            print(f"\n--- Sheet {i} ---")
            parse_sheet(zf, f'xl/worksheets/sheet{i}.xml', shared)
        except Exception as e:
            pass

