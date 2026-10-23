import os
import subprocess
from pathlib import Path
from markdown_it import MarkdownIt

BASE_DIR = Path(__file__).resolve().parent.parent
MD_PATH = BASE_DIR / "approach_document.md"
HTML_PATH = BASE_DIR / "approach_document_print.html"
PDF_PATH = BASE_DIR / "approach_document.pdf"
DOWNLOADS_PDF = Path("C:/Users/honey/Downloads/CardioTrack_CT200_Approach_Document_Harini_P.pdf")

def generate_pdf():
    with open(MD_PATH, "r", encoding="utf-8") as f:
        md_text = f.read()

    md = MarkdownIt()
    html_content = md.render(md_text)

    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CardioTrack CT-200 Engineering Approach Document</title>
<style>
    @page {{
        size: A4;
        margin: 20mm 18mm 20mm 18mm;
    }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        line-height: 1.6;
        font-size: 11pt;
    }}
    h1 {{
        color: #0f172a;
        font-size: 20pt;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 8px;
        margin-top: 0;
        margin-bottom: 12px;
    }}
    h2 {{
        color: #1e3a8a;
        font-size: 14pt;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 4px;
        margin-top: 22px;
        margin-bottom: 10px;
        page-break-after: avoid;
    }}
    h3 {{
        color: #334155;
        font-size: 12pt;
        margin-top: 16px;
        margin-bottom: 6px;
        page-break-after: avoid;
    }}
    p, li {{
        font-size: 10.5pt;
        color: #334155;
    }}
    ul, ol {{
        margin-top: 4px;
        margin-bottom: 10px;
        padding-left: 24px;
    }}
    li {{
        margin-bottom: 3px;
    }}
    code {{
        background-color: #f1f5f9;
        color: #0f172a;
        font-family: "Cascadia Code", Consolas, Monaco, monospace;
        padding: 2px 5px;
        border-radius: 4px;
        font-size: 9.5pt;
    }}
    pre {{
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #3b82f6;
        padding: 12px;
        border-radius: 6px;
        overflow-x: auto;
        page-break-inside: avoid;
    }}
    pre code {{
        background: transparent;
        padding: 0;
        font-size: 9pt;
        color: #1e293b;
    }}
    hr {{
        border: none;
        border-top: 1px solid #e2e8f0;
        margin: 20px 0;
    }}
    blockquote {{
        border-left: 4px solid #94a3b8;
        padding-left: 12px;
        color: #64748b;
        margin: 10px 0;
    }}
</style>
</head>
<body>
{html_content}
</body>
</html>
"""
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(full_html)

    edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    cmd = [
        edge_exe,
        "--headless",
        "--disable-gpu",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={PDF_PATH}",
        str(HTML_PATH)
    ]
    print(f"Generating PDF via headless Edge to {PDF_PATH}...")
    subprocess.run(cmd, check=True)
    print("PDF generated successfully.")

    # Copy to Downloads
    import shutil
    shutil.copyfile(PDF_PATH, DOWNLOADS_PDF)
    print(f"Copied to user Downloads folder: {DOWNLOADS_PDF}")

if __name__ == "__main__":
    generate_pdf()
