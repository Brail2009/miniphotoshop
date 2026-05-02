import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
from flask import session

# Инициализация
app = Flask(__name__)
app.config['SECRET_KEY'] = ':)'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///miniphoto.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 мб

# Папка uploads, если её нет
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

# Загрузка пользователя
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Создание таблиц
with app.app_context():
    db.create_all()

# Маршруты
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

    # Расширение
    true_perm = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
    ex = file.filename.rsplit('.', 1)[1].lower()
    if ex not in true_perm:
        flash('Можно загружать только изображения png, jpg, jpeg, gif, bmp')
        return redirect(url_for('index'))

    # Уникальное имя
    filename = secure_filename(f"{current_user.id}_{uuid.uuid4().hex}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    session['current_image'] = filepath
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

@app.route('/')
@login_required
def index():
    # Путь к текущему изображению если есть
    current_image = session.get('current_image')
    return render_template('index.html', active_menu='filters', current_image=current_image)

@app.route('/filters')
@login_required
def filters():
    current_image = session.get('current_image')
    return render_template('index.html', active_menu='filters', current_image=current_image)

@app.route('/transform')
@login_required
def transform():
    current_image = session.get('current_image')
    return render_template('index.html', active_menu='transform', current_image=current_image)

@app.route('/correction')
@login_required
def correction():
    current_image = session.get('current_image')
    return render_template('index.html', active_menu='correction', current_image=current_image)

@app.route('/ai')
@login_required
def ai():
    current_image = session.get('current_image')
    return render_template('index.html', active_menu='ai', current_image=current_image)

@app.route('/library')
@login_required
def library():
    return render_template('library.html')

# Регистрация
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

# Вход
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

# Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('current_image', None)  # очистка при выходе
    flash('Вы вышли из аккаунта')
    return redirect(url_for('login'))

# Отдача загруженных изображений
@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

app.run(debug=True)
