# แหล่งอ้างอิงสำหรับผู้เขียนบทความ Phish Radar

รายการตั้งต้นสำหรับเขียนทฤษฎีและงานวิจัยที่เกี่ยวข้อง ตรวจข้อมูลกับแหล่งต้นทางวันที่ 17 ตุลาคม 2026 รหัส R1 ถึง R5 เป็นรหัสทำงานในคู่มือนี้ ให้เปลี่ยนเป็นเลขอ้างอิงหรือรูปแบบที่อาจารย์กำหนดเมื่อจัดบทความ

บรรณานุกรมนี้สนับสนุนหลักการและวิธีประเมิน ผลของงานอ้างอิงต้องแยกจากผลวัดของโครงงาน ผู้เขียนควรอ่านส่วนที่นำมาใช้ก่อนอ้างจริง

สำหรับที่มาของข้อมูล ให้ใช้ [แหล่ง dataset D1 ถึง D7](DATASET_SOURCES_TH.md) ประกอบหัวข้อข้อมูลและวิธีดำเนินงาน ซึ่งแยกข้อมูลพัฒนา ชุดยืนยัน ผลย้อนหลัง และ URL อ้างอิงที่ทีมเก็บเอง พร้อมข้อมูลบรรณานุกรมของแต่ละชุด

## R1 Random Forest

L. Breiman, “Random Forests,” *Machine Learning*, vol. 45, pp. 5–32, 2001. DOI: 10.1023/A:1010933404324.

[หน้าบทความของผู้ตีพิมพ์](https://link.springer.com/article/10.1023/A:1010933404324)

ใช้ในหัวข้อ 2.2 เพื่ออธิบายหลักการ Random Forest และเชื่อมกับการเลือกอัลกอริทึมในหัวข้อ 3 แหล่งนี้ไม่ใช่ผลทดสอบฟิชชิงของโครงงาน

## R2 Probability calibration

A. Niculescu-Mizil and R. Caruana, “Predicting Good Probabilities with Supervised Learning,” in *Proceedings of the 22nd International Conference on Machine Learning*, pp. 625–632, 2005. DOI: 10.1145/1102351.1102430.

[ฉบับเต็มจาก ICML](https://icml.cc/Conferences/2005/proceedings/papers/079_GoodProbabilities_NiculescuMizilCaruana.pdf) · [DOI](https://doi.org/10.1145/1102351.1102430)

ใช้ในหัวข้อ 2.3 เรื่องการปรับความน่าจะเป็นและการแยกข้อมูลสำหรับ calibration ต้องตรวจวิธีที่ artifact ของโครงงานใช้จริงด้วย รุ่นที่ตรวจมีการใช้ mapping เดิมกับ posterior ที่ปรับ จึงต้องกล่าวถึงข้อจำกัดของ calibration หลังการแก้โมเดลด้วย ไม่อ้างว่าการคูณ 100 หรือเกณฑ์ 60 และ 80 มาจากบทความนี้

## R3 การตรวจฟิชชิงจาก URL

O. K. Sahingoz, E. Buber, O. Demir, and B. Diri, “Machine learning based phishing detection from URLs,” *Expert Systems with Applications*, vol. 117, pp. 345–357, 2019. DOI: 10.1016/j.eswa.2018.09.029.

[หน้าบทความของผู้ตีพิมพ์](https://www.sciencedirect.com/science/article/abs/pii/S0957417418306067)

ใช้ในหัวข้อ 2.1 และ 2.5 เพื่อเปรียบเทียบแนวทาง URL-based ML อธิบายให้ชัดว่าชุดคุณลักษณะ ชุดข้อมูล และวิธีทดสอบต่างจากโครงงาน ห้ามยกความแม่นยำที่บทความรายงานมาเป็นค่าของ Phish Radar

## R4 คุณภาพข้อมูลและการประเมินฟิชชิง

T. Dalton, H. Gowda, G. Rao, S. Pargi, A. Hadj Khodabakhshi, J. Rombs, S. Jou, and M. Marwah, “PhreshPhish: A Real-World, High-Quality, Large-Scale Phishing Website Dataset and Benchmark,” *arXiv preprint*, arXiv:2507.10854, 2025, version 2 revised February 11, 2026.

[บทความและประวัติรุ่น](https://arxiv.org/abs/2507.10854) · [ฉบับเต็มรุ่น 2](https://arxiv.org/html/2507.10854v2) · [ชุดข้อมูลของผู้จัดทำ](https://huggingface.co/datasets/phreshphish/phreshphish)

ใช้ในหัวข้อ 2.4 เรื่องคุณภาพข้อมูล การรั่วของข้อมูลระหว่างชุด และสัดส่วน class ระบุสถานะ preprint เมื่อกล่าวถึงงานนี้ หากใช้เป็นแหล่งข้อมูลของการทดลอง ต้องตรวจ recovery manifest ว่าใช้รุ่นใด split ใดและคอลัมน์ใดจริง ไม่ถือว่าการมีบทความนี้ในบรรณานุกรมพิสูจน์ว่าโมเดลฝึกจากข้อมูลทั้งหมดของผู้จัดทำ

## R5 การประเมินข้อมูลไม่สมดุล

T. Saito and M. Rehmsmeier, “The Precision-Recall Plot Is More Informative than the ROC Plot When Evaluating Binary Classifiers on Imbalanced Datasets,” *PLOS ONE*, vol. 10, no. 3, e0118432, 2015. DOI: 10.1371/journal.pone.0118432.

[บทความฉบับเต็มของผู้ตีพิมพ์](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0118432)

ใช้ในหัวข้อ 2.4 และการวิเคราะห์ผลส่วนที่ 4 เพื่อให้รายงาน Precision และ Recall ควบคู่กับ FPR และ confusion matrix ระบุสัดส่วน phishing ในชุดที่ประเมินด้วย ไม่สรุปความสามารถของโมเดลจาก Accuracy หรือ ROC-AUC เพียงค่าเดียว

## จัดเอกสารอ้างอิงควบคู่กับหัวข้อ 2

1. เลือกประเด็นที่จะอธิบาย แล้วอ่านแหล่งต้นทางที่สนับสนุนประเด็นนั้น
2. จดข้อความสรุปด้วยภาษาของตนเอง พร้อมตำแหน่งหน้า หัวข้อ หรือรูปที่อ่าน
3. ใส่การอ้างอิงในย่อหน้าที่ใช้แนวคิดนั้นทันที
4. แยกว่ารายการใดเป็นทฤษฎี งานที่เกี่ยวข้อง แหล่ง dataset หรือเอกสารเทคนิค
5. เทียบการอ้างในเนื้อหากับท้ายบทความให้ครบทั้งสองทาง ลบรายการที่ไม่ได้ใช้

| ประเด็นในบทความ | รายการตั้งต้น | สิ่งที่ผู้เขียนต้องยืนยันเพิ่ม |
|---|---|---|
| Random Forest | R1 | รุ่นและพารามิเตอร์ของ artifact ที่รายงาน |
| Calibration | R2 | calibrator ที่ใช้และข้อจำกัดหลังปรับโมเดล |
| URL-based detection | R3 | ความต่างของคุณลักษณะและข้อมูล |
| Dataset quality และ leakage | R4 | แหล่งข้อมูลและ split ของโครงงานจริง |
| Metrics ของข้อมูลไม่สมดุล | R5 | confusion matrix และสัดส่วน class ของแต่ละชุด |

## หลักฐานภายในโครงงาน

ใช้ [PROJECT_FACTS_TH.md](PROJECT_FACTS_TH.md) และไฟล์ใน [evidence](evidence/) เพื่อตรวจรุ่นและผลที่บันทึกไว้ หลักฐานภายในมีไว้รับรองสิ่งที่โครงงานทำและวัด ไม่ใช้แทนบทความวิชาการสำหรับอธิบายทฤษฎี

วันที่เปิดตรวจบทความในเอกสารนี้ไม่ใช่วันที่เก็บข้อมูลของโครงงาน วันที่ฝึกโมเดล หรือวันที่ทดสอบระบบ หากจะอ้างช่วงปีของ dataset ให้แยกวันเก็บ วันเผยแพร่ วันดาวน์โหลด และช่วงเวลาที่ metadata ของข้อมูลรองรับ
