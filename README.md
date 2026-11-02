# CPU Simulator V8

ต่อยอดจาก V7 ที่อาจารย์ให้มา โครงสร้างไฟล์และวิธีทำงานเหมือนเดิม คืออ่านโปรแกรมทีละบรรทัดแล้วรันจากข้อความ ไม่มีขั้น compile/assemble และไม่มีการรับ input ส่วนที่เพิ่มคือคำสั่งจำนวนเต็มของ MIPS32 ครบชุด, label, หน้าต่างแอป และโปรแกรม nCk

V8 ตัวแรกที่ทำงานแบบ MARS (มี assembler, `.data` และ syscall) ย้ายไปอยู่ที่ `../cpu_simulator_python-main32V8_mars/`

ต้องใช้ Python 3.10 ขึ้นไปที่มี Tkinter บน macOS ควรใช้ Tk 8.6.13 ขึ้นไป เพราะรุ่นเก่ากว่าอาจรับคลิกปุ่มไม่ครบ แอปจะแจ้งเตือนเมื่อเปิดด้วย Tk รุ่นเก่า ในเครื่องนี้ Python ของ miniconda (`/Users/kawin/miniconda3/bin/python3`) มี Tk 8.6.15

## วิธีรัน

รัน `instructions.txt` แบบ V7 (เหมือนกด F5 ใน IDLE) โดยพิมพ์ทุกบรรทัดของโปรแกรมพร้อม address และ hex แล้วแสดง register และ memory ทุก step ในรูปแบบเดียวกับ V7:

```bash
python3 main.py
```

ถ้าไม่มี `instructions.txt` ในโฟลเดอร์ปัจจุบัน จะใช้ไฟล์ที่อยู่ข้าง `main.py`

รันไฟล์อื่นแบบเดียวกัน:

```bash
python3 main.py examples/ncr_recursive.txt
```

ค่า register แสดงเป็นฐานสิบตามค่าเริ่มต้น (`DISP_FORMAT = "INT"` ใน `cpu.py`) ใส่ `--hex` เพื่อแสดงแบบฐาน 16

เปิดหน้าต่างแอป:

```bash
python3 main.py --gui
```

หรือเปิดไฟล์ `run_gui.py` ใน IDLE แล้วกด F5

ดูเฉพาะผลสุดท้าย:

```bash
python3 main.py -q examples/ncr_iterative.txt
```

## วิดีโอสอน nCk แบบ Recursive

`video/ncr_recursive.mp4` (ประมาณ 7 นาครึ่ง) อธิบาย nCk, กฎของปาสคาล, โครงโปรแกรม, stack frame แล้วไล่การทำงานจริงของ `C(3, 1)` ทีละคำสั่ง ภาพทุกขั้นมาจากการรัน simulator นี้จริง เสียงพากย์เป็นเสียงสังเคราะห์ภาษาไทย (Kanya ของ macOS) ส่วน `video/script.md` คือสคริปต์พร้อมเวลา สำหรับอัดเสียงพากย์เอง

สร้างใหม่ได้ด้วย (ต้องมี Pillow, ffmpeg และ macOS):

```bash
python3 video/make_video.py
```

## ใช้กับ Autolab

`--print` จะพิมพ์ค่าเฉพาะ register ที่ระบุตอนโปรแกรมจบ บรรทัดละตัว โดยไม่มี trace หรือ memory เพื่อให้เทียบกับเฉลยได้ตรง

```bash
python3 main.py --print v0 examples/ncr_recursive.txt
```

```text
$2 = 15
```

```bash
python3 main.py --print 10,11 --hex examples/instructions.txt
```

```text
$10 = 0x0000001f
$11 = 0x00000020
```

| Option | ความหมาย |
|---|---|
| `--print REGS` | register ที่จะพิมพ์ คั่นด้วยจุลภาค เขียนได้ทั้ง `2`, `$2`, `v0` หรือ `$v0` และใช้ `pc`, `hi`, `lo` ได้ |
| `--hex` | พิมพ์เป็นเลขฐาน 16 แบบ 8 หลัก (ค่าเริ่มต้นเป็นฐานสิบแบบมีเครื่องหมาย เช่น `-5`) |
| `--max-steps N` | หยุดเมื่อรันครบ N คำสั่ง (ค่าเริ่มต้น 10,000,000) กันโปรแกรมวนไม่รู้จบ โดย `HALT` ไม่นับเป็นคำสั่ง |

ข้อความ error ทุกอย่างไปที่ stderr ส่วน stdout มีเฉพาะผลลัพธ์

| Exit code | ความหมาย |
|---|---|
| 0 | จบด้วย `HALT` หรือรันพ้นบรรทัดสุดท้าย |
| 1 | โปรแกรมผิด syntax, เปิดไฟล์ไม่ได้ หรือชื่อ register ใน `--print` ผิด |
| 2 | runtime error เช่น overflow หรือ address ไม่ align (บอกเลขบรรทัดใน stderr) |
| 3 | รันครบ `--max-steps` แล้วโปรแกรมยังไม่จบ |

รันเทสต์:

```bash
python3 -m unittest discover tests
```

## เดโม nCk

1. เปิดแอปด้วย `python3 main.py --gui` โปรแกรม `ncr_recursive.txt` จะอยู่ในแท็บ Edit
2. แก้ค่า n และ k ที่บรรทัด `ADDI $4 $0 6` และ `ADDI $5 $0 2`
3. กด **Load** แท็บ Execute จะแสดง address, hex และ source ของทุกบรรทัด
4. กด **Run** คำตอบจะอยู่ใน `$2` (`$v0`) และแสดงในช่องข้อความด้านล่าง
5. กด **Reset** แล้วใช้ **Step** หรือตั้ง Speed เป็น `5 /s` เพื่อดู `$29` (stack) และ `$31` เปลี่ยนระหว่าง recursion กดปุ่ม `$sp` ในส่วน Memory เพื่อดู stack
6. คลิกช่อง Bkpt ของบรรทัดเพื่อตั้ง breakpoint

| ไฟล์ | วิธี | ช่วงที่เหมาะ |
|---|---|---|
| `examples/ncr_recursive.txt` | `C(n,k) = C(n-1,k-1) + C(n-1,k)` ใช้ stack | n ไม่เกินประมาณ 20 |
| `examples/ncr_iterative.txt` | แถวของสามเหลี่ยมปาสคาลใน memory ที่ `0x3000` | ทุกคำตอบที่อยู่ใน signed 32 บิต ถ้าเกินจะได้ `$2 = -1` |
| `examples/instructions.txt` | ไฟล์ตัวอย่างของ V7 | รันได้โดยไม่ต้องแก้ |
| `examples/factorial_mult.txt` | n! ด้วยคำสั่ง `MULT` แล้วเช็ก `HI` ว่าล้นหรือไม่ | 0! ถึง 12! ถ้าเกินจะได้ `$2 = -1` |
| `examples/factorial_nomul.txt` | n! โดยไม่ใช้คำสั่งคูณ เรียก subroutine `MULTIPLY` (shift-and-add) ด้วย `JAL` | 0! ถึง 12! ถ้าเกินจะได้ `$2 = -1` |

ไฟล์ factorial ทั้งสองแบบใส่ n ที่บรรทัด `ADDI $4 $0 5` แล้วดูคำตอบใน `$2` ส่วน n ติดลบจะได้ 0 ค่าสูงสุดคือ 12! = 479001600 เพราะ 13! เกิน signed 32 บิต

```bash
python3 main.py --print v0 examples/factorial_nomul.txt
```

## Syntax

```asm
.ORG 0x2000                 # address เริ่มต้น
        ADDI $4 $0 5        # n
LOOP:   BEQ  $4 $0 DONE     # label ใช้แทนตัวเลขได้
        ADDI $4 $4 -1
        J    LOOP
DONE:   HALT                # หยุดโปรแกรม
```

- เขียนแบบ V7 ได้ทุกอย่าง: ตัวพิมพ์ใหญ่หรือเล็ก, ไม่ต้องใส่จุลภาค, `$9` หรือ `$t1`
- Immediate รับเลขฐานสิบ, `0x` และ `0b`
- `#` ใช้เขียน comment
- Load/Store ใช้ `offset($reg)` เช่น `LW $8 4($29)`
- `BEQ`/`BNE` รับ label หรือตัวเลข offset แบบ V7 (`1` = ข้าม 1 คำสั่ง)
- `J`/`JAL` รับ label หรือ address ตรงๆ แบบ V7 (`J 0x2030`)
- `HALT` หยุดโปรแกรม ถ้าไม่มี `HALT` โปรแกรมจะหยุดเมื่อรันพ้นบรรทัดสุดท้าย
- ไม่มีคำสั่งช่วย (pseudo-instruction) เช่น `LI` หรือ `MOVE` ให้ใช้ `ADDI $8 $0 5` หรือ `ADD $8 $9 $0` แทน

## คำสั่งที่รองรับ

รองรับเฉพาะคำสั่งจำนวนเต็มที่อยู่ใน MIPS Reference Data (`slide/EMIPS.pdf`) ทั้ง Core Instruction Set และตาราง OPCODES หน้า 2

- เลขคณิต/ตรรกะ: `ADD ADDU SUB SUBU ADDI ADDIU AND OR XOR NOR ANDI ORI XORI LUI SLT SLTU SLTI SLTIU`
- Shift: `SLL SRL SRA SLLV SRLV SRAV`
- คูณหาร: `MULT MULTU DIV DIVU MFHI MFLO MTHI MTLO` (ผลคูณอยู่ใน `hi`/`lo` ใช้ `MFLO` อ่านค่า)
- Move แบบมีเงื่อนไข: `MOVN MOVZ`
- Branch/Jump: `BEQ BNE BLEZ BGTZ J JAL JR JALR`
- Load/Store: `LB LBU LH LHU LW LWL LWR LL SB SH SW SWL SWR SC`
- Trap: `TEQ TNE TGE TGEU TLT TLTU BREAK`
- อื่นๆ: `NOP` (คือ `SLL $0 $0 0`), `HALT`, `.ORG`

คำสั่งที่ไม่อยู่ในการ์ด เช่น `BLTZ BGEZ BLTZAL BGEZAL MUL MADD CLZ` หรือ trap แบบ immediate (`TEQI` ฯลฯ) จะได้ error `Unknown opcode` ถ้าต้องการ `BLTZ $5 L` ให้เขียนเป็น `SLT $8 $5 $0` ตามด้วย `BNE $8 $0 L` แทน

## สิ่งที่ต่างจาก V7

| เรื่อง | V7 | V8 |
|---|---|---|
| PC | เลขบรรทัด (address ÷ 4) | address จริง |
| ไม่มี `.ORG` | ล่ม | เริ่มที่ address 0 |
| Memory | `SW` เก็บทั้งค่าไว้ใน address เดียว | เก็บทีละ byte แบบ big-endian โดย address ไม่ต้องหารด้วย 4 ลงตัวเหมือน V7 (MIPS จริงต้องหารลงตัว) |
| Immediate 16 บิต | ตัดเหลือ 16 บิต | รับ -32768 ถึง `0xffff` เหมือน V7 เช่น `ADDI $2 $3 0xffff` คือบวก -1 |
| Register | ค่าลบปนกับค่าบวกแบบ Python | เก็บเป็น 32 บิตเสมอ, `$0` เป็น 0 |
| Hex ของ `BEQ`/`BNE` | สลับ rs กับ rt | ตามมาตรฐาน MIPS |
| คำสั่งผิด | `exit(1)` | บอกเลขบรรทัดและสาเหตุทุกบรรทัดที่ผิด |
| Overflow ของ `ADD`/`ADDI`/`SUB` | ไม่ตรวจ | หยุดพร้อมบอกบรรทัด |

Machine code (hex) ของทุกบรรทัดถูกเขียนลง memory เพื่อให้ดูได้เหมือน V7 แต่ CPU รันจากบรรทัดข้อความ การเขียนทับโค้ดใน memory จึงไม่มีผล

## โครงสร้าง

| ไฟล์ | หน้าที่ |
|---|---|
| `main.py` | จุดเริ่มโปรแกรม |
| `isa.py` | ตารางคำสั่ง (`cmdDict`) และคลาส `Instruction`: `decode` / `decode2` / `decode3` |
| `cpu.py` | `fetch` / `execute` / `validate` / `run` / `debug` |
| `memory.py` | memory แบบ dict และ `dump` |
| `gui/app.py` | หน้าต่างแอป |
| `examples/` | โปรแกรมตัวอย่าง |
| `tests/` | เทสต์ |
