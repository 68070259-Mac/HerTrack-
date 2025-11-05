# 📄 app.py (V7.3 - Ultimate Dashboard API)

import os
import datetime
from datetime import timedelta 
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt

basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__,
            static_folder=os.path.join(basedir, 'static'),
            template_folder=os.path.join(basedir, 'templates'))
app.config['SECRET_KEY'] = 'a_very_secret_key_that_should_be_changed' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_mNkRXfiBvw62@ep-red-feather-a1w1jljl-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 
login_manager.login_message = 'กรุณาเข้าสู่ระบบเพื่อใช้งานหน้านี้'
login_manager.login_message_category = 'info' 

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    daily_logs = db.relationship('DailyLog', backref='user', lazy=True)
    cycle_history = db.relationship('CycleHistory', backref='user', lazy=True)
class DailyLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    log_date = db.Column(db.String(20), nullable=False)
    mood = db.Column(db.String(100))
    symptoms = db.Column(db.String(300))
    flow = db.Column(db.String(100))
    color = db.Column(db.String(100))
    notes = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
class CycleHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.String(100), nullable=False) 
    ovulation_date = db.Column(db.String(100), nullable=True) 
    next_date = db.Column(db.String(100), nullable=True) 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
def get_average_cycle_length():
    DEFAULT_CYCLE_LENGTH = 28
    try:
        cycles = CycleHistory.query.filter_by(user_id=current_user.id).order_by(CycleHistory.start_date.asc()).all()
        if len(cycles) < 2:
            return DEFAULT_CYCLE_LENGTH
        diffs = []
        for i in range(len(cycles) - 1):
            date_a = datetime.datetime.strptime(cycles[i].start_date, '%Y-%m-%d').date()
            date_b = datetime.datetime.strptime(cycles[i+1].start_date, '%Y-%m-%d').date()
            diff = (date_b - date_a).days
            if 21 <= diff <= 45:
                diffs.append(diff)
        if not diffs:
            return DEFAULT_CYCLE_LENGTH
        average = sum(diffs) / len(diffs)
        return int(round(average))
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการคำนวณค่าเฉลี่ย: {e}")
        return DEFAULT_CYCLE_LENGTH
def update_cycle_history(current_date_str):
    AVG_OVULATION_DAY = 14 
    MIN_DAYS_FOR_NEW_CYCLE = 21 
    try:
        current_date = datetime.datetime.strptime(current_date_str, '%Y-%m-%d').date()
        latest_cycle = CycleHistory.query.filter_by(user_id=current_user.id).order_by(CycleHistory.start_date.desc()).first()
        is_new_cycle = False
        if not latest_cycle:
            is_new_cycle = True
        else:
            latest_start_date = datetime.datetime.strptime(latest_cycle.start_date, '%Y-%m-%d').date()
            days_diff = (current_date - latest_start_date).days
            if days_diff >= MIN_DAYS_FOR_NEW_CYCLE:
                is_new_cycle = True
        if is_new_cycle:
            new_start_date = current_date
            new_cycle_entry = CycleHistory(
                start_date=new_start_date.strftime('%Y-%m-%d'),
                user_id=current_user.id 
            )
            db.session.add(new_cycle_entry)
            db.session.commit()
            print(f"✅ ตรวจพบรอบเดือนใหม่! (User: {current_user.id}) เริ่มวันที่ {new_start_date}")
            new_avg_length = get_average_cycle_length()
            print(f"ℹ️ ค่าเฉลี่ยรอบเดือนใหม่ (User: {current_user.id}) คือ {new_avg_length} วัน")
            ovulation_date = new_start_date + timedelta(days=AVG_OVULATION_DAY)
            next_date = new_start_date + timedelta(days=new_avg_length)
            new_cycle_entry.ovulation_date = ovulation_date.strftime('%Y-%m-%d')
            new_cycle_entry.next_date = next_date.strftime('%Y-%m-%d')
            db.session.commit()
        else:
            print(f"ℹ️ บันทึกวันที่มีประจำเดือน {current_date_str} (User: {current_user.id}) (ไม่ใช่การเริ่มรอบใหม่)")
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการอัปเดต CycleHistory (User: {current_user.id}): {e}")
        db.session.rollback() 
@app.route('/api/save-log', methods=['POST'])
@login_required 
def save_log():
    data = request.json
    log_date = data.get('date')
    if not log_date:
        return jsonify({"status": "error", "message": "ไม่พบวันที่"}), 400
    symptoms_text = ",".join(data.get('symptoms', []))
    log = DailyLog.query.filter_by(log_date=log_date, user_id=current_user.id).first()
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
            notes=data.get('notes'),
            user_id=current_user.id 
        )
        db.session.add(log)
        message = "บันทึกข้อมูลใหม่สำเร็จ"
    db.session.commit()
    if current_flow and current_flow != "None":
        update_cycle_history(log_date)
    calendar_events = get_events_data() 
    return jsonify({
        "status": "success", 
        "message": message,
        "new_events": calendar_events
    })
def get_events_data():
    events = []
    logs = DailyLog.query.filter_by(user_id=current_user.id).all()
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
    cycles = CycleHistory.query.filter_by(user_id=current_user.id).all()
    for cycle in cycles:
        if cycle.ovulation_date:
            events.append({
                "title": "🥚 วันตกไข่ (คาดการณ์)",
                "start": cycle.ovulation_date,
                "color": "#D4EDDA",
                "textColor": "#155724",
                "borderColor": "#C3E6CB",
                "display": "block"      
            })
        if cycle.next_date:
            events.append({
                "title": "🩸 รอบถัดไป (คาดการณ์)",
                "start": cycle.next_date,
                "color": "#FABAC6",      
                "textColor": "#333",     
                "borderColor": "#F08080",
                "display": "block"
            })
    return events
@app.route('/api/get-events')
@login_required 
def get_events():
    return jsonify(get_events_data())
@app.route('/api/analyze', methods=['GET'])
@login_required 
def analyze_day():
    date = request.args.get('date')
    if not date:
        return jsonify({"status": "error", "message": "กรุณาระบุวันที่"})
    log = DailyLog.query.filter_by(log_date=date, user_id=current_user.id).first()
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

@app.route('/api/get_home_summary')
@login_required 
def get_home_summary():
    """
    ดึงข้อมูลสรุปทั้งหมดสำหรับหน้า Home (V7.3)
    """
    try:
        latest_cycle = CycleHistory.query.filter_by(user_id=current_user.id).order_by(CycleHistory.start_date.desc()).first()
        
        if latest_cycle and latest_cycle.next_date:
            avg_length = get_average_cycle_length()
            
            return jsonify({
                "status": "success",
                "last_start_date": latest_cycle.start_date,
                "avg_cycle_length": avg_length,
                "ovulation_date": latest_cycle.ovulation_date,
                "next_date": latest_cycle.next_date 
            })
        else:
            return jsonify({"status": "no_data"})
            
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดใน /api/get_home_summary: {e}")
        return jsonify({"status": "error", "message": str(e)})


@app.route('/api/initial_setup', methods=['POST'])
@login_required 
def initial_setup():
    try:
        data = request.json
        last_start_str = data.get('lastStartDate')
        prev_start_str = data.get('prevStartDate')
        if not last_start_str or not prev_start_str:
            return jsonify({"status": "error", "message": "กรุณากรอกข้อมูลให้ครบทั้ง 2 ช่อง"}), 400
        last_start = datetime.datetime.strptime(last_start_str, '%Y-%m-%d').date()
        prev_start = datetime.datetime.strptime(prev_start_str, '%Y-%m-%d').date()
        if prev_start >= last_start:
            return jsonify({"status": "error", "message": "วันที่ 'รอบก่อนหน้า' ต้องมาก่อน 'รอบล่าสุด'"}), 400
        CycleHistory.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        entry1 = CycleHistory(start_date=prev_start_str, user_id=current_user.id)
        entry2 = CycleHistory(start_date=last_start_str, user_id=current_user.id)
        db.session.add_all([entry1, entry2])
        db.session.commit()
        avg_length = get_average_cycle_length()
        ovulation_date = last_start + timedelta(days=14) 
        next_date = last_start + timedelta(days=avg_length)
        entry2.ovulation_date = ovulation_date.strftime('%Y-%m-%d')
        entry2.next_date = next_date.strftime('%Y-%m-%d')
        db.session.commit()
        return jsonify({"status": "success", "message": "บันทึกข้อมูลตั้งต้นสำเร็จ"})
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดใน /api/initial_setup: {e}")
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('กรุณากรอกชื่อผู้ใช้และรหัสผ่าน', 'warning')
            return redirect(url_for('login'))
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user) 
            print(f"✅ User {username} ล็อกอินสำเร็จ")
            return redirect(url_for('home'))
        else:
            flash('ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')
@app.route('/register', methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    username = request.form.get('username')
    password = request.form.get('password')
    if not username or not password:
        flash('กรุณากรอกชื่อผู้ใช้และรหัสผ่าน', 'warning')
        return redirect(url_for('login'))
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash('ชื่อผู้ใช้นี้ถูกใช้งานแล้ว', 'danger')
        return redirect(url_for('login'))
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    new_user = User(username=username, password_hash=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    print(f"✅ User {username} สมัครสมาชิกสำเร็จ")
    flash('สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ', 'success')
    return redirect(url_for('login'))
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required 
def home():
    """แสดงหน้าแรก (home.html)"""
    return render_template('home.html')



@app.route('/show_result')
@login_required 
def show_result_page():
    """แสดงหน้าผลการวิเคราะห์"""
    return render_template('result_page.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
