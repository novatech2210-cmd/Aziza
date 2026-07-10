import json
import os
import glob
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def load_json(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Failed to load {filepath}: {e}")
        return None

def build_pdf(report_data, filename="Aziza_Benchmark_Report_Leon.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        textColor=colors.HexColor("#1e3a8a"),
        alignment=1
    )
    
    subtitle_style = ParagraphStyle(
        'SubtitleStyle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        textColor=colors.HexColor("#3b82f6")
    )
    
    normal_style = styles['Normal']
    
    elements = []
    
    # Title
    elements.append(Paragraph("AZIZA Milestone 2 - Benchmark Report", title_style))
    elements.append(Paragraph(f"Prepared for: Leon", subtitle_style))
    elements.append(Paragraph(f"Date: {report_data.get('timestamp', 'N/A')}", normal_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Executive Summary
    elements.append(Paragraph("Executive Summary", styles['Heading2']))
    
    summary = report_data.get('summary', {})
    total = summary.get('total_benchmarks', 0)
    passed = summary.get('passed_benchmarks', 0)
    failed = summary.get('failed_benchmarks', 0)
    
    summary_data = [
        ["Total Benchmarks", str(total)],
        ["Passed", str(passed)],
        ["Failed", str(failed)]
    ]
    
    t = Table(summary_data, colWidths=[2.5*inch, 2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#eff6ff")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#1e3a8a")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.25*inch))
    
    # Results Breakdown
    elements.append(Paragraph("Detailed Results", styles['Heading2']))
    
    for bm_key, bm_result in report_data.get('benchmark_results', {}).items():
        if bm_result.get('status') == 'MISSING':
            continue
            
        elements.append(Paragraph(bm_result.get('test_name', bm_key.replace('_', ' ').title()), styles['Heading3']))
        status = bm_result.get('status', 'UNKNOWN')
        status_color = "#16a34a" if status == "PASS" else "#dc2626"
        status_para = Paragraph(f"<b>Status:</b> <font color='{status_color}'>{status}</font>", normal_style)
        elements.append(status_para)
        
        target = bm_result.get('target_median_ms') or bm_result.get('target_s')
        if target:
            elements.append(Paragraph(f"<b>Target:</b> {target}", normal_style))
            
        summary_info = bm_result.get('summary', {})
        if summary_info:
            elements.append(Spacer(1, 0.1*inch))
            stats_data = [["Metric", "Value"]]
            for k, v in summary_info.items():
                stats_data.append([k.replace('_', ' ').title(), str(v)])
                
            t_stats = Table(stats_data, colWidths=[2.5*inch, 2*inch])
            t_stats.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            elements.append(t_stats)
            
        elements.append(Spacer(1, 0.2*inch))
        
    doc.build(elements)
    print(f"PDF generated successfully at {filename}")

if __name__ == '__main__':
    report = load_json('benchmarks/reports/final_report.json')
    if report:
        build_pdf(report, 'Aziza_Benchmark_Report_Leon.pdf')
    else:
        print("Report not found.")
