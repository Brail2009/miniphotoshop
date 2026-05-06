import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
import random

from image_work import apply_filter, apply_transform, apply_correction, save_bgr_im

app = Flask(__name__)
app.config['SECRET_KEY'] = ':)'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///miniphoto.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

@app.route('/ai')
@login_required
def ai():
    current_image = session.get('current_image')
    return render_template('index.html', active_menu='ai', current_image=current_image)

@app.route('/library')
@login_required
def library():
    return render_template('library.html')

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

app.run(debug=True)
