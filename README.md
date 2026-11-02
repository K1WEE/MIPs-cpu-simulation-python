# CPU Simulator V8

ต่อยอดจาก V7 ที่อาจารย์ให้มา โครงสร้างไฟล์และวิธีทำงานเหมือนเดิม คืออ่านโปรแกรมทีละบรรทัดแล้วรันจากข้อความ ไม่มีขั้น compile/assemble และไม่มีการรับ input ส่วนที่เพิ่มคือคำสั่งจำนวนเต็มของ MIPS32 ครบชุด, label, หน้าต่างแอป และโปรแกรม nCk

V8 ตัวแรกที่ทำงานแบบ MARS (มี assembler, `.data` และ syscall) ย้ายไปอยู่ที่ `../cpu_simulator_python-main32V8_mars/`

ต้องใช้ Python 3.10 ขึ้นไปที่มี Tkinter บน macOS ควรใช้ Tk 8.6.13 ขึ้นไป เพราะรุ่นเก่ากว่าอาจรับคลิกปุ่มไม่ครบ แอปจะแจ้งเตือนเมื่อเปิดด้วย Tk รุ่นเก่า ในเครื่องนี้ Python ของ miniconda (`/Users/kawin/miniconda3/bin/python3`) มี Tk 8.6.15

## วิธีรัน

เปิดหน้าต่างแอป:

```bash
python3 main.py
```

รันใน Terminal และแสดง register ทุก step แบบ V7:

```bash
python3 main.py examples/instructions.txt
```

ดูเฉพาะผลสุดท้าย:

```bash
python3 main.py -q examples/ncr_iterative.txt
```

รันเทสต์:

```bash
python3 -m unittest discover tests
```

## เดโม nCk

1. เปิดแอป โปรแกรม `ncr_recursive.txt` จะอยู่ในแท็บ Edit
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

- เลขคณิต/ตรรกะ: `ADD ADDU SUB SUBU ADDI ADDIU AND OR XOR NOR ANDI ORI XORI LUI SLT SLTU SLTI SLTIU`
- Shift: `SLL SRL SRA SLLV SRLV SRAV`
- คูณหาร: `MULT MULTU DIV DIVU MUL MADD MADDU MSUB MSUBU MFHI MFLO MTHI MTLO CLZ CLO`
- Move แบบมีเงื่อนไข: `MOVN MOVZ`
- Branch/Jump: `BEQ BNE BLEZ BGTZ BLTZ BGEZ BLTZAL BGEZAL J JAL JR JALR`
- Load/Store: `LB LBU LH LHU LW LWL LWR LL SB SH SW SWL SWR SC`
- Trap: `TEQ TNE TGE TGEU TLT TLTU TEQI TNEI TGEI TGEIU TLTI TLTIU BREAK`
- อื่นๆ: `NOP HALT .ORG`

## สิ่งที่ต่างจาก V7

| เรื่อง | V7 | V8 |
|---|---|---|
| PC | เลขบรรทัด (address ÷ 4) | address จริง |
| ไม่มี `.ORG` | ล่ม | เริ่มที่ address 0 |
| Memory | `SW` เก็บทั้งค่าไว้ใน address เดียว | เก็บทีละ byte แบบ big-endian, word ต้อง align ด้วย 4 |
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
