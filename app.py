import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
import random
import requests

from image_work import apply_filter, apply_transform, apply_correction, save_bgr_im

app = Flask(__name__)
app.config['SECRET_KEY'] = ':)'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///miniphoto.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['USER_PHOTOS_FOLDER'] = 'user_photos'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['USER_PHOTOS_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Пользователь
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Фото
class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)  # имя
    filepath = db.Column(db.String(300), nullable=False)  # путь
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('photos'))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()

# ---------- Вспомогательные ----------
def get_curr_im():
    img = session.get('current_image')
    if not img or not os.path.exists(img):
        flash('Нет изображения')
        return None
    return img

def s_and_up(image_bgr, original_path=None):
    path = save_bgr_im(image_bgr, app.config['UPLOAD_FOLDER'], original_path)
    session['current_image'] = path
    return url_for('uploaded_file', filename=os.path.basename(path))

# Ии функции
def ask_pollinations(prompt):
    url = "https://text.pollinations.ai/v1/chat/completions"
    payload = {
        "model": "openai",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 500
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            print(f"Ошибка {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(e)
        return None


def parse_ai_response(user_message):
    system_prompt = f"""
Ты ии помощник в фоторедакторе. Тебе нужно вернуть ТОЛЬКО JSON, без пояснений.

Доступные действия:
- filter: grayscale, sepia, invert, blur, sharpen, edges, emboss, cartoon
- transform: rotate_90_cw, rotate_90_ccw, flip_horizontal, flip_vertical  
- correction: brightness (от -100 до 100), contrast (от -100 до 100), saturation (от -100 до 100)
- advice: дать совет
- reply: обычный ответ

Форматы ответа (строго JSON):
{{"action": "filter", "action_type": "grayscale", "message": "Применяю ч/б фильтр"}}
{{"action": "transform", "action_type": "rotate_90_cw", "message": "Поворачиваю вправо"}}
{{"action": "correction", "brightness": 30, "contrast": 0, "saturation": 0, "message": "Увеличиваю яркость"}}
{{"action": "advice", "message": "Попробуйте увеличить контраст"}}
{{"action": "reply", "message": "Привет! Я AI-помощник"}}

Команда пользователя: "{user_message}"
Ответь ТОЛЬКО JSON.
"""
    ai_resp = ask_pollinations(system_prompt)
    if ai_resp:
        try:
            start = ai_resp.find('{')
            end = ai_resp.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(ai_resp[start:end])
        except:
            pass
    return {"action": "reply",
            "message": "Скорее всего ИИ сейчас недоступен. Попробуйте позже"}

# Маршруты
@app.route('/')
@login_required
def index():
    current_image = session.get('current_image')
    sliders = {
        'brightness': session.get('last_brightness', 0),
        'contrast': session.get('last_contrast', 0),
        'saturation': session.get('last_saturation', 0)
    }
    return render_template('index.html', active_menu='filters', current_image=current_image, sliders=sliders)

@app.route('/filters', methods=['GET', 'POST'])
@login_required
def filters_page():
    if request.method == 'POST':
        image = get_curr_im()
        if not image:
            return redirect(url_for('filters_page'))

        act = request.form.get('action')

        if act == 'apply':
            fil_name = request.form.get('filter_name')
            if not fil_name:
                flash('Не указан фильтр')
                return redirect(url_for('filters_page'))

            # Не применён ли уже какой либо фильтр
            pre = session.get('pre_filter_image')
            if pre and os.path.exists(pre) and pre != image:
                flash('Сначала сбросьте фильтр чтобы применить другой')
                return redirect(url_for('filters_page'))

            # Состояние до фильтра (только если это 1)
            if not pre or not os.path.exists(pre):
                session['pre_filter_image'] = image

            try:
                resul = apply_filter(image, fil_name)
            except ValueError:
                flash(str(ValueError))
                return redirect(url_for('filters_page'))

            s_and_up(resul, image)
            return redirect(url_for('filters_page'))

        elif act == 'reset':
            pre = session.get('pre_filter_image')
            if pre and os.path.exists(pre):
                session['current_image'] = pre
            else:
                flash(random.choice(['Ты не применял фильтр!', 'Разве есть что сбрасывать?', 'Нечего сбрасывать']))
            return redirect(url_for('filters_page'))

    # Отрисовка
    current_image = session.get('current_image')
    sliders = {
        'brightness': session.get('last_brightness', 0),
        'contrast': session.get('last_contrast', 0),
        'saturation': session.get('last_saturation', 0)
    }
    return render_template('index.html', active_menu='filters', current_image=current_image, sliders=sliders)

@app.route('/transform', methods=['GET', 'POST'])
@login_required
def transform_page():
    if request.method == 'POST':
        image = get_curr_im()
        if not image:
            return redirect(url_for('transform_page'))

        act = request.form.get('action')

        if act == 'apply':
            transform_type = request.form.get('transform_type')
            if not transform_type:
                flash('Не указана трансформация')
                return redirect(url_for('transform_page'))

            # До начала трансформаций (только 1 раз)
            pre = session.get('pre_transform_image')
            if not pre or not os.path.exists(pre):
                session['pre_transform_image'] = image

            try:
                res = apply_transform(image, transform_type)
            except ValueError as e:
                flash(str(e))
                return redirect(url_for('transform_page'))

            s_and_up(res, image)
            return redirect(url_for('transform_page'))

        elif act == 'reset':
            pre = session.get('pre_transform_image')
            if pre and os.path.exists(pre):
                session['current_image'] = pre
                session.pop('pre_transform_image', None)
                flash('Трансформации сброшены')
            else:
                flash(random.choice(['Ты не применял трансформацию!', 'Разве есть что сбрасывать?', 'Нечего сбрасывать']))
            return redirect(url_for('transform_page'))

    current_image = session.get('current_image')
    sliders = {
        'brightness': session.get('last_brightness', 0),
        'contrast': session.get('last_contrast', 0),
        'saturation': session.get('last_saturation', 0)
    }
    return render_template('index.html', active_menu='transform', current_image=current_image, sliders=sliders)

@app.route('/correction', methods=['GET', 'POST'])
@login_required
def correction_page():
    if request.method == 'POST':
        image = get_curr_im()
        if not image:
            return redirect(url_for('correction_page'))

        act = request.form.get('action')

        if act == 'apply':
            try:
                brightness = int(request.form.get('brightness', 0))
                contrast = int(request.form.get('contrast', 0))
                saturation = int(request.form.get('saturation', 0))
            except ValueError:
                flash('Невозможные значения')
                return redirect(url_for('correction_page'))

            # До 1 коррекции
            pre = session.get('pre_correction_image')
            if not pre or not os.path.exists(pre):
                session['pre_correction_image'] = image

            session['last_brightness'] = brightness
            session['last_contrast'] = contrast
            session['last_saturation'] = saturation

            try:
                result = apply_correction(image, brightness, contrast, saturation)
            except Exception:
                flash(str(Exception))
                return redirect(url_for('correction_page'))

            s_and_up(result, image)
            return redirect(url_for('correction_page'))

        elif act == 'reset':
            pre = session.get('pre_correction_image')
            if pre and os.path.exists(pre):
                session['current_image'] = pre
                session.pop('pre_correction_image', None)
                session.pop('last_brightness', None)
                session.pop('last_contrast', None)
                session.pop('last_saturation', None)
                flash('Коррекции сброшены')
            else:
                flash(random.choice(['Ты не применял коррекции!', 'Разве есть что сбрасывать?', 'Нечего сбрасывать']))
            return redirect(url_for('correction_page'))

    current_image = session.get('current_image')
    sliders = {
        'brightness': session.get('last_brightness', 0),
        'contrast': session.get('last_contrast', 0),
        'saturation': session.get('last_saturation', 0)
    }
    return render_template('index.html', active_menu='correction', current_image=current_image, sliders=sliders)

@app.route('/ai', methods=['GET', 'POST'])
@login_required
def ai():
    current_image = session.get('current_image')

    if request.method == 'POST':
        user_message = request.form.get('message', '').strip()
        if not user_message:
            flash('Введите сообщение')
            return redirect(url_for('ai'))

        command = parse_ai_response(user_message)
        response_message = command.get('message', '')

        # Применяем
        if current_image and command.get('action') == 'filter':
            try:
                pre = session.get('pre_filter_image')
                if not pre or not os.path.exists(pre):
                    session['pre_filter_image'] = current_image
                result = apply_filter(current_image, command['action_type'])
                s_and_up(result, current_image)
            except Exception as e:
                response_message = f"Ошибка: {e}"

        elif current_image and command.get('action') == 'transform':
            try:
                pre = session.get('pre_transform_image')
                if not pre or not os.path.exists(pre):
                    session['pre_transform_image'] = current_image
                result = apply_transform(current_image, command['action_type'])
                s_and_up(result, current_image)
            except Exception as e:
                response_message = f"Ошибка: {e}"

        elif current_image and command.get('action') == 'correction':
            try:
                pre = session.get('pre_correction_image')
                if not pre or not os.path.exists(pre):
                    session['pre_correction_image'] = current_image
                result = apply_correction(
                    current_image,
                    command.get('brightness', 0),
                    command.get('contrast', 0),
                    command.get('saturation', 0)
                )
                s_and_up(result, current_image)
                if command.get('brightness', 0) != 0:
                    session['last_brightness'] = command.get('brightness', 0)
                if command.get('contrast', 0) != 0:
                    session['last_contrast'] = command.get('contrast', 0)
                if command.get('saturation', 0) != 0:
                    session['last_saturation'] = command.get('saturation', 0)
            except Exception as e:
                response_message = f"Ошибка: {e}"

        chat_history = session.get('chat_history', [])
        chat_history.append({'user': user_message, 'ai': response_message})
        if len(chat_history) > 10:
            chat_history = chat_history[-10:]
        session['chat_history'] = chat_history

        return redirect(url_for('ai'))

    # GET-запрос
    return render_template('index.html', active_menu='ai', current_image=current_image, sliders={
        'brightness': session.get('last_brightness', 0),
        'contrast': session.get('last_contrast', 0),
        'saturation': session.get('last_saturation', 0)
    })

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('Файл не выбран')
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        flash('Файл не выбран')
        return redirect(url_for('index'))

    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in {'png', 'jpg', 'jpeg', 'gif', 'bmp'}:
        flash('Можно загружать только изображения png, jpg, jpeg, gif, bmp')
        return redirect(url_for('index'))

    filename = secure_filename(f"{current_user.id}_{uuid.uuid4().hex}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    session['original_image'] = filepath
    session['current_image'] = filepath
    session.pop('pre_filter_image', None)
    session.pop('pre_transform_image', None)
    session.pop('pre_correction_image', None)
    session.pop('last_brightness', None)
    session.pop('last_contrast', None)
    session.pop('last_saturation', None)
    session.pop('chat_history', None)

    flash('Изображение загружено')
    return redirect(url_for('index'))

@app.route('/save', methods=['GET', 'POST'])
@login_required
def save():
    image_f = session.get('current_image')
    if not image_f or not os.path.exists(image_f):
        flash('Нет изображения')
        return redirect(url_for('index'))

    origin = os.path.basename(image_f)
    return send_file(image_f, as_attachment=True, download_name=origin)

@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

# Регистрация, вход, выход
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Заполните все поля')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже есть')
            return redirect(url_for('register'))
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Вы зарегистрировались! Теперь войдите.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=False)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('current_image', None)
    flash('Вы вышли из аккаунта')
    return redirect(url_for('login'))

@app.route('/save_to_library', methods=['POST'])
@login_required
def save_to_library():
    curr_path = session.get('current_image')
    if not curr_path or not os.path.exists(curr_path):
        flash('Нет изображения для сохранения')
        return redirect(url_for('index'))

    # Уникальное имя для копии
    ext = os.path.splitext(curr_path)[1]
    un_name = f"{current_user.id}_{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(app.config['USER_PHOTOS_FOLDER'], un_name)

    # Копируем
    import shutil
    shutil.copy2(curr_path, dest_path)

    # Сохраняем в БД
    orig_name = os.path.basename(curr_path)
    photo = Photo(
        user_id=current_user.id,
        filename=orig_name,
        filepath=dest_path
    )
    db.session.add(photo)
    db.session.commit()

    flash('Изображение сохранено в библиотеку')
    return redirect(url_for('index'))

@app.route('/library')
@login_required
def library():
    photos = Photo.query.filter_by(user_id=current_user.id).order_by(Photo.created_at.desc()).all()
    return render_template('library.html', photos=photos)

@app.route('/delete_from_library/<int:photo_id>', methods=['POST'])
@login_required
def delete_from_library(photo_id):
    photo = Photo.query.get_or_404(photo_id)
    if photo.user_id != current_user.id:
        flash('Доступ закрыт')
        return redirect(url_for('library'))

    if os.path.exists(photo.filepath):
        os.remove(photo.filepath)

    db.session.delete(photo)
    db.session.commit()
    flash('Фото удалено из библиотеки')
    return redirect(url_for('library'))

@app.route('/user_photos/<path:filename>')
@login_required
def user_photo_file(filename):
    return send_file(os.path.join(app.config['USER_PHOTOS_FOLDER'], filename))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)