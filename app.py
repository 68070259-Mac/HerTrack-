# 📄 app.py (V5.4 - Auto Cycle Calculation, Home page enabled)

import os
import datetime
from datetime import timedelta 
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

# --- Database Config (เหมือนเดิม) ---
# NOTE: Using PostgreSQL for Vercel deployment
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_mNkRXfiBvw62@ep-red-feather-a1w1jljl-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Models (เหมือนเดิม) ---
class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.String(20), nullable=False)
    mood = db.Column(db.String(100))
    symptoms = db.Column(db.String(300))
    flow = db.Column(db.String(100))
    color = db.Column(db.String(100))
    notes = db.Column(db.Text)

class CycleHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.String(100))
    ovulation_date = db.Column(db.String(100))
    next_date = db.Column(db.String(100))

# --- ฟังก์ชันสำหรับคำนวณรอบเดือน ---
def update_cycle_history(current_date_str):
    """
    ตรวจสอบและอัปเดตตาราง CycleHistory โดยอัตโนมัติ
    """
    # ค่าคงที่ (สามารถปรับแต่งได้ในอนาคต)
    AVG_CYCLE_LENGTH = 28 # รอบเดือนเฉลี่ย 28 วัน
    AVG_OVULATION_DAY = 14 # ตกไข่ประมาณวันที่ 14
    MIN_DAYS_FOR_NEW_CYCLE = 21 # ต้องห่างจากรอบที่แล้วอย่างน้อย 21 วัน
    
    try:
        current_date = datetime.datetime.strptime(current_date_str, '%Y-%m-%d').date()

        # 1. ค้นหารอบเดือนล่าสุดที่บันทึกไว้
        latest_cycle = CycleHistory.query.order_by(CycleHistory.start_date.desc()).first()

        is_new_cycle = False
        if not latest_cycle:
            # กรณี 1: ไม่เคยมีข้อมูลมาก่อน นี่คือรอบเดือนแรก
            is_new_cycle = True
        else:
            # กรณี 2: มีข้อมูลอยู่แล้ว ตรวจสอบว่าห่างกันพอที่จะเป็นรอบใหม่หรือไม่
            latest_start_date = datetime.datetime.strptime(latest_cycle.start_date, '%Y-%m-%d').date()
            days_diff = (current_date - latest_start_date).days
            
            if days_diff > MIN_DAYS_FOR_NEW_CYCLE:
                # ถ้าห่างจากวันเริ่มรอบที่แล้วเกิน 21 วัน ให้ถือว่าเป็นรอบใหม่
                is_new_cycle = True

        # 3. ถ้าเป็นรอบใหม่จริง ให้คำนวณและบันทึก
        if is_new_cycle:
            new_start_date = current_date
            
            # คำนวณวันคาดการณ์
            ovulation_date = new_start_date + timedelta(days=AVG_OVULATION_DAY)
            next_date = new_start_date + timedelta(days=AVG_CYCLE_LENGTH)

            # สร้างแถวใหม่ในตาราง
            new_cycle_entry = CycleHistory(
                start_date=new_start_date.strftime('%Y-%m-%d'),
                ovulation_date=ovulation_date.strftime('%Y-%m-%d'),
                next_date=next_date.strftime('%Y-%m-%d')
            )
            db.session.add(new_cycle_entry)
            db.session.commit()
            print(f"✅ ตรวจพบรอบเดือนใหม่! บันทึกประวัติรอบเดือน เริ่มวันที่ {new_start_date}")
        else:
            # ถ้าไม่ใช่วันเริ่มรอบใหม่ ก็ไม่ต้องทำอะไร
            print(f"ℹ️ บันทึกวันที่มีประจำเดือน {current_date_str} (ไม่ใช่การเริ่มรอบใหม่)")

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการอัปเดต CycleHistory: {e}")
        db.session.rollback() # ย้อนกลับถ้ามีปัญหา
# --- สิ้นสุดฟังก์ชันใหม่ ---


# --- API บันทึกข้อมูล (อัปเดต) ---
@app.route('/api/save-log', methods=['POST'])
def save_log():
    data = request.json
    log_date = data.get('date')
    if not log_date:
        return jsonify({"status": "error", "message": "ไม่พบวันที่"}), 400

    symptoms_text = ",".join(data.get('symptoms', []))
    log = DailyLog.query.filter_by(log_date=log_date).first()
    
    current_flow = data.get('flow') 

    if log:
        log.mood = data.get('mood')
        log.symptoms = symptoms_text
        log.flow = current_flow 
        log.color = data.get('color')
        log.notes = data.get('notes')
        message = "อัปเดตข้อมูลสำเร็จ"
    else:
        log = DailyLog(
            log_date=log_date,
            mood=data.get('mood'),
            symptoms=symptoms_text,
            flow=current_flow, 
            color=data.get('color'),
            notes=data.get('notes')
        )
        db.session.add(log)
        message = "บันทึกข้อมูลใหม่สำเร็จ"

    db.session.commit()

    # หลังจากบันทึก DailyLog สำเร็จ
    # ถ้ามีการบันทึก "flow" (แปลว่ามีประจำเดือน) ให้ไปตรวจสอบว่าต้องอัปเดต cycle history หรือไม่
    if current_flow and current_flow != "None":
        update_cycle_history(log_date)

    calendar_events = get_events_data() 
    return jsonify({
        "status": "success", 
        "message": message,
        "new_events": calendar_events
    })

# --- ฟังก์ชันดึง Event (V5.4 - อัปเกรดให้แสดงผลคาดการณ์) ---
def get_events_data():
    events = []
    
    # --- 1. ดึงข้อมูลบันทึกจริงจาก DailyLog ---
    logs = DailyLog.query.all()
    for log in logs:
        title = ""
        color = "#CCCCCC"
        textColor = "#333"
        display_mode = "block" 

        if log.flow and log.flow != "None":
            title = f"🩸 {log.flow}"
            if log.flow == "มาก": color = "#E53E3E"
            elif log.flow == "ปานกลาง": color = "#FB6A90"
            else: color = "#FABAC6"
            if log.mood and log.mood != "None":
                title += f" ({log.mood})"
            textColor = "white" if color != "#FABAC6" else "#333"
        elif log.mood and log.mood != "None":
            title = f"{log.mood}"
            if log.mood in ['😊 ร่าเริง', '⚡ กระปรี้กระเปร่า']:
                color = "#48BB78"; textColor = "white"
            elif log.mood in ['😢 เศร้า', '😣 เครียด']:
                color = "#4299E1"; textColor = "white"
            elif log.mood == '😴 อ่อนเพลีย':
                color = "#A0AEC0"; textColor = "white"
            else:
                color = "#ECC94B"
        elif log.symptoms or log.notes:
            title = "📝 (มีบันทึก)"
            color = "#B0D3F2"
        else:
            continue
            
        events.append({
            "title": title, 
            "start": log.log_date, 
            "color": color, 
            "textColor": textColor,
            "display": display_mode 
        })

    # --- 2. ดึงข้อมูลคาดการณ์จาก CycleHistory ---
    cycles = CycleHistory.query.all()
    for cycle in cycles:
        
        # 🥚 สร้าง Event วันตกไข่
        if cycle.ovulation_date:
            events.append({
                "title": "🥚 วันตกไข่ (คาดการณ์)",
                "start": cycle.ovulation_date,
                "color": "#FFF9E6",      
                "textColor": "#8C5A00",  
                "borderColor": "#FFD633",
                "display": "block"      
            })
            
        # 🩸 สร้าง Event วันรอบเดือนถัดไป
        if cycle.next_date:
            events.append({
                "title": "🩸 รอบถัดไป (คาดการณ์)",
                "start": cycle.next_date,
                "color": "#FFF5F7",      
                "textColor": "#D9002E",  
                "borderColor": "#FFB6C1",
                "display": "block"
            })
            
    return events
@app.route('/api/get-events')
def get_events():
    return jsonify(get_events_data())

@app.route('/api/analyze', methods=['GET'])
def analyze_day():
    # (โค้ดส่วนนี้เหมือนเดิม)
    date = request.args.get('date')
    if not date:
        return jsonify({"status": "error", "message": "กรุณาระบุวันที่"})
    log = DailyLog.query.filter_by(log_date=date).first()
    if not log:
        return jsonify({"status": "error", "message": "ไม่พบข้อมูลของวันนี้"})
    score = 0
    symptoms_list = log.symptoms.split(',') if log.symptoms else [] 
    mood_str = log.mood or "" 
    flow_str = log.flow or ""
    color_str = log.color or ""
    notes_str = log.notes or ""
    mood_points = { '😊 ร่าเริง': 30, '⚡ กระปรี้กระเปร่า': 25, '😢 เศร้า': 10, '😴 อ่อนเพลีย': 10, '😣 เครียด': 5 }
    flow_points = { 'น้อย': 20, 'ปานกลาง': 15, 'มาก': 10 }
    color_points = { 'ชมพู': 20, 'แดงสด': 15, 'ส้ม': 10, 'แดงเข้มหรือน้ำตาล': 5, 'เขียวปนเทา': 0, 'ดำคล้ำ': 0 }
    score += mood_points.get(mood_str, 15)
    score += flow_points.get(flow_str, 15)
    score += color_points.get(color_str, 10)
    symptom_score = 35 - (len(symptoms_list) * 5)
    if '⚡ ปวดท้อง' in symptoms_list:
        symptom_score -= 5
    score += max(0, symptom_score) 
    score = max(0, min(100, score))
    mascot = '🙂' 
    if score >= 80: mascot = '🥰' 
    elif score >= 50: mascot = '🙂' 
    else: 
        if '⚡ ปวดท้อง' in symptoms_list: mascot = '😖' 
        elif '😴 อ่อนเพลีย' in mood_str or '💤 เหนื่อย' in symptoms_list: mascot = '😵' 
        elif '😢 เศร้า' in mood_str or '😣 เครียด' in mood_str: mascot = '😟' 
        else: mascot = '😴' 
    tips = []
    if '⚡ ปวดท้อง' in symptoms_list: tips.append("ปวดท้องเหรอ? ลองใช้ถุงน้ำร้อนประคบท้องน้อย หรือดื่มน้ำขิงอุ่นๆ จะช่วยให้รู้สึกดีขึ้นนะคะ 🍵")
    if '💤 เหนื่อย' in symptoms_list: tips.append("รู้สึกเหนื่อย... พยายามอย่านอนดึก และหาเวลางีบหลับสั้นๆ ระหว่างวันสัก 15-20 นาทีนะคะ 💤")
    if '😴 อ่อนเพลีย' in mood_str: tips.append("รู้สึกอ่อนเพลีย... ร่างกายอาจต้องการการพักผ่อน ลองทานอาหารที่มีธาตุเหล็กสูง เช่น ตับ หรือผักใบเขียวนะคะ 🥬")
    if '☕ ปวดหัว' in symptoms_list: tips.append("ปวดหัวเหรอ? ลองนวดเบาๆ ที่ขมับ หรือพักสายตาจากหน้าจอสักครู่นะคะ 🖥️")
    if '💧 ท้องอืด' in symptoms_list: tips.append("ท้องอืดจัง... ลองทานอาหารย่อยง่ายๆ เช่น ขิง หรือโยเกิร์ต และหลีกเลี่ยงน้ำอัดลมไปก่อนนะคะ 🥣")
    if '🧡 เจ็บหน้าอก' in symptoms_list: tips.append("เจ็บคัดหน้าอกเป็นอาการปกติก่อนมีรอบเดือน ลองใส่บราที่สบายตัว ไม่รัดแน่นเกินไปนะคะ 👚")
    if '😢 เศร้า' in mood_str or '😣 เครียด' in mood_str: tips.append("อารมณ์ไม่คงที่เหรอ? ลองฟังเพลงผ่อนคลาย, ทำสมาธิสั้นๆ หรือทานดาร์กช็อกโกแลตสักชิ้น อาจจะช่วยได้นะ 🍫")
    if color_str == 'แดงเข้มหรือน้ำตาล': tips.append("สีแดงเข้ม/น้ำตาล เป็นเรื่องปกติในช่วงวันท้ายๆ ของรอบเดือนค่ะ ไม่ต้องกังวล เป็นเลือดเก่าที่เพิ่งไหลออกมา")
    if color_str == 'ชมพู': tips.append("สีชมพูจางๆ อาจหมายถึงเลือดที่ผสมกับตกขาว เป็นปกติในช่วงวันแรกๆ หรือวันท้ายๆ ค่ะ")
    if not tips: tips.append("เยี่ยม! ดูเหมือนวันนี้คุณอาการคงที่ ดื่มน้ำอุ่นๆ ตลอดวัน จะช่วยให้เลือดไหลเวียนดีขึ้น ทำให้สบายตัวมากขึ้นนะคะ 💧")
    self_care_tip = "<br><br>".join(tips)
    advice_list = []
    notes_lower = notes_str.lower()
    if color_str == 'เขียวปนเทา' or color_str == 'ดำคล้ำ': advice_list.append(f"สีของประจำเดือน ({color_str}) อาจเป็นสัญญาณของการติดเชื้อในช่องคลอด")
    if color_str == 'ส้ม': advice_list.append("สีส้มอาจเกิดจากการผสมกับตกขาว หรืออาจเป็นสัญญาณของการติดเชื้อเล็กน้อย หากมีอาการคันหรือกลิ่นผิดปกติร่วมด้วย ควรสังเกตอย่างใกล้ชิดนะคะ")
    if 'ก้อนเลือด' in notes_lower or 'ลิ่มเลือด' in notes_lower:
        if flow_str == 'มาก': advice_list.append("คุณบันทึกว่ามี 'ก้อนเลือด/ลิ่มเลือด' ร่วมกับมีประจำเดือน 'มาก' หากเป็นเช่นนี้หลายวัน ควรปรึกษาแพทย์ค่ะ")
        else: advice_list.append("คุณบันทึกเรื่อง 'ก้อนเลือด/ลิ่มเลือด' หากมีขนาดใหญ่ (เกิน 1 นิ้ว) หรือมีปริมาณมาก ควรปรึกษาแพทย์")
    if 'กลิ่นเหม็น' in notes_lower or 'กลิ่นผิดปกติ' in notes_lower: advice_list.append("คุณบันทึกเรื่อง 'กลิ่นผิดปกติ' ซึ่งอาจเป็นสัญญาณของการติดเชื้อ")
    if 'ปวดท้องรุนแรง' in notes_lower or 'ปวดจนทนไม่ไหว' in notes_lower: advice_list.append("คุณบันทึกว่า 'ปวดท้องรุนแรง' หากปวดมากจนยาแก้ปวดทั่วไปเอาไม่อยู่ ควรพบแพทย์เพื่อตรวจหาสาเหตุนะคะ")
    valid_symptoms = [s for s in symptoms_list if s] 
    if len(valid_symptoms) >= 4: advice_list.append("คุณมีอาการหลายอย่างพร้อมกัน (4+ รายการ) หากอาการเหล่านี้รบกวนชีวิตประจำวันเป็นประจำ ควรปรึกษาแพทย์เพื่อหาสาเหตุนะคะ")
    
    return jsonify({
        "status": "success", "date": log.log_date, "mood": mood_str,
        "symptoms": valid_symptoms, "flow": flow_str, "color": color_str,
        "notes": notes_str, "health_score": score, "mascot": mascot,
        "self_care_tip": self_care_tip, "doctor_advice": advice_list
    })

# --- Route แสดงหน้าเว็บ (มีการแก้ไข) ---
@app.route('/')
def home():
    """แสดงหน้าแรก (home.html)"""
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    """แสดงหน้าปฏิทิน (dashboard.html)"""
    return render_template('dashboard.html')

@app.route('/show_result')
def show_result_page():
    """แสดงหน้าผลการวิเคราะห์"""
    return render_template('result_page.html')

# --- Login page route (หากต้องการใช้) ---
@app.route('/login')
def login_page():
    """แสดงหน้า Login/Signup (login.html)"""
    # โค้ดส่วนนี้จะยังไม่ได้ถูกใช้ในหน้าหลัก แต่มีไว้สำหรับลิงก์จากหน้า login.html
    return render_template('login.html')

if __name__ == '__main__':
    # เมื่อรันบนเครื่องตัวเอง (Local)
    app.run(debug=True, port=5000)