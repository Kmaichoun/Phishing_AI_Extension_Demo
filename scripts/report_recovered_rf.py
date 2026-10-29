"""Write a Thai comparison report from measured experiment results."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('experiment',type=Path)
parser.add_argument('--output',type=Path,default=ROOT/'output/retrained-rf-20261005/report_TH.md')
args=parser.parse_args()
experiment=args.experiment.resolve()
r=json.loads((experiment/'evaluation.json').read_text(encoding='utf-8'))
new=r['candidate_holdout']; old=r['baseline_same_holdout']
percent=lambda value:'ไม่มีข้อมูล' if value is None else f'{100*value:.2f}%'
rows=[]
for stage,label in [('warning','เตือน'),('blocking','บล็อก')]:
    for model,metrics in [('โมเดลปัจจุบัน',old),('โมเดลที่ฝึกใหม่',new)]:
        m=metrics[stage]
        rows.append(f"| {label} | {model} | {100*m['threshold']:.2f} | {m['false_positive']:,} | {percent(m['false_positive_rate'])} | {percent(m['false_positive_rate_upper_95'])} | {percent(m['recall'])} | {m['false_negative']:,} |")
gate='ผ่านเงื่อนไขตัวเลขที่ตั้งไว้บนชุดนี้' if r['statistical_gate_passed'] else 'ยังไม่ผ่านเงื่อนไขตัวเลขครบ โดยต้องตรวจทั้งขอบบน FPR และ Recall เทียบโมเดลปัจจุบัน'
regression_path=experiment/'regression.json'
regression=json.loads(regression_path.read_text(encoding='utf-8')) if regression_path.exists() else None
lines=[
    '# ผลฝึก Random Forest เพื่อลด False Positive — 5 ตุลาคม 2026','',
    f"ฝึกสองรูปแบบแล้ว เลือกรุ่น `{r['selected']}` จาก Validation ก่อนเปิด Holdout สูตรคือ **{r['risk_formula']}**",'',
    'ผลนี้เป็นการวัดบนชุดข้อมูลของรอบทดลอง ประวัติการใช้ข้อมูลของโมเดลเก่าบางส่วนยังตรวจไม่ได้ จึงยังไม่ใช่หลักฐานกับทุกเว็บไซต์หรือทุกโรงเรียนไทย และยังไม่ได้แทนที่โมเดลที่ใช้งาน','',
    '## เปรียบเทียบบน URL ชุดเดียวกัน','',
    '| เกณฑ์ | รุ่น | คะแนนจุดตัด | เตือนผิด FP | FPR | ขอบบน FPR 95% | จับฟิชชิง Recall | พลาดฟิชชิง FN |',
    '|---|---|---:|---:|---:|---:|---:|---:|',*rows,'',
    f"{gate} เป้าหมายขอบบน FPR: เตือนไม่เกิน 1%, บล็อกไม่เกิน 0.1%; Recall ที่เกณฑ์เตือนต้องไม่ต่ำกว่าโมเดลปัจจุบัน",'',
    'เกณฑ์บล็อกโมเดลปัจจุบันอยู่ที่ 100 และไม่ถึงจากตัว Calibrate เดิม จึงมี Recall สำหรับบล็อกเป็นศูนย์ ต้องอ่านผลเตือนควบคู่กัน','',
    '## การแบ่งข้อมูล','',
    '| ชุด | URL | กลุ่มโดเมน | ปกติ | ฟิชชิง |','|---|---:|---:|---:|---:|',
]
for name,counts in r['split_counts'].items():
    lines.append(f"| {name} | {counts['rows']:,} | {counts['domains']:,} | {int(counts['labels'].get('0',0)):,} | {int(counts['labels'].get('1',0)):,} |")
lines += ['', 'โดเมนไม่ซ้ำข้ามชุดในรอบนี้ เลือกพารามิเตอร์และเกณฑ์จาก Validation ไม่ refit หรือปรับเกณฑ์จาก Holdout', '',
          '## กลุ่มเว็บการศึกษาและ URL มี query','',
          '| กลุ่ม | URL | FP เดิม | FP ใหม่ | FPR เดิม | FPR ใหม่ | Recall เดิม | Recall ใหม่ |',
          '|---|---:|---:|---:|---:|---:|---:|---:|']
for name,group in r['subgroups'].items():
    a,b=group['baseline'],group['candidate']
    lines.append(f"| {name} | {group['rows']:,} | {a['false_positive']:,} | {b['false_positive']:,} | {percent(a.get('false_positive_rate'))} | {percent(b.get('false_positive_rate'))} | {percent(a.get('recall'))} | {percent(b.get('recall'))} |")
lines += ['', 'กลุ่มการศึกษาคัดจากรูปแบบชื่อโดเมน ไม่ใช่ whitelist หรือชุดตัวแทนโรงเรียนไทยทั้งหมด หากกลุ่มมีเพียงฉลากเดียว ค่าที่ต้องใช้ฉลากอีกฝั่งแสดงว่าไม่มีข้อมูล', '',
          '## ตัวอย่างเว็บปกติที่ตรวจซ้ำ','']
if regression:
    lines += ['| URL | คะแนนใหม่ | ผล |','|---|---:|---|']
    for item in regression['results']:
        lines.append(f"| `{item['url']}` | {item['final_score']} | {item['decision']} |")
    lines += ['',f"ผ่านตัวอย่างทั้งหมด: {regression['all_allow']} ตัวอย่างเหล่านี้เป็น regression ที่รู้จักแล้ว จึงไม่ใช่การวัด FPR อิสระ"]
else:lines.append('ยังไม่มีผล regression ในไฟล์รอบนี้')
lines += ['', '## ที่มาและข้อจำกัด','',
          '- ข้อมูลพัฒนา: PhreshPhish train และ URL-Phish v1 ที่มีฉลากผู้เผยแพร่; ไม่ใช้ CSV seed หรือ URL สังเคราะห์ในการฝึก',
          '- ชุดทดสอบ: PhreshPhish publisher test ที่ตัดโดเมนร่วมกับข้อมูลพัฒนาและ URL ซ้ำแล้ว',
          '- รุ่น hard_negative เพิ่มน้ำหนัก 4 เท่าเฉพาะข้อมูลฝึกที่ฉลากเป็นเว็บปกติแต่โมเดลเดิมเตือน ไม่ใช้ฉลากชุดทดสอบปรับน้ำหนัก',
          '- ปรับ features เป็น url-v4-public-suffix เพื่อแยกโดเมนอย่าง .ac.th ได้ถูกต้อง และฝึกใหม่ให้ตรงกับความหมาย features',
          '- PhreshPhish ตัด query ของเว็บปกติในขั้นตอนเตรียมข้อมูล จึงอาจทำให้โมเดล URL-only เรียนรู้อคติ และทำให้กลุ่ม query ขาดตัวอย่างปกติ',
          '- ช่วง Wilson คำนวณจากจำนวน URL ไม่รวมความสัมพันธ์ของหลาย URL ในโดเมนเดียวกัน',
          '- ประวัติชุดข้อมูลฝึกเดิมที่หายไปยังตรวจไม่ครบ ไม่ข้ามเงื่อนไขเปิดใช้โมเดลด้วยการสร้างไฟล์เดิมขึ้นใหม่','',
          f"โมเดลทดลอง: `{experiment/'candidate.pkl'}`",f"ผลตัวเลข: `{experiment/'evaluation.json'}`",f"คะแนนราย URL: `{experiment/'holdout-scores.csv'}`",'']
if r.get('augmentation'):
    a=r['augmentation']
    lines += ['## ข้อมูลเพิ่มเติมในรอบต่อเนื่อง','',
        f"แหล่ง [Web page phishing detection v3]({a['source']}) โดย {a['attribution']}; {a['license']}",
        f"ข้อมูลที่เพิ่มและรายการที่ตัดออก: `{json.dumps(a['counts'],ensure_ascii=False)}`",'',
        'ชุดตรวจสอบ 70,085 URL นี้เคยถูกประเมินในรอบแรกแล้ว รอบต่อเนื่องจึงเป็นผลบน benchmark ที่ใช้ซ้ำ ไม่อ้างว่าเป็นชุดทดสอบที่ไม่เคยเห็นมาก่อน พารามิเตอร์และจุดตัดยังเลือกจาก Development Validation ของรอบนี้ ไม่ใช้คะแนน benchmark เลือกเกณฑ์','']
out=args.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
out.write_text('\n'.join(lines),encoding='utf-8')
print(str(out))
