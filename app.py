import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Инициализация
app = Flask(__name__)
app.config['SECRET_KEY'] = ':)'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///miniphoto.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'          # пенаправление

# Пользователь
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        #self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

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
@app.route('/')
@login_required
def index():
    return render_template('index.html', active_menu='filters')

@app.route('/filters')
@login_required
def filters():
    return render_template('index.html', active_menu='filters')

@app.route('/transform')
@login_required
def transform():
    return render_template('index.html', active_menu='transform')

@app.route('/correction')
@login_required
def correction():
    return render_template('index.html', active_menu='correction')

@app.route('/ai')
@login_required
def ai():
    return render_template('index.html', active_menu='ai')

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
            next = request.args.get('next')
            return redirect(next or url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль')
            return redirect(url_for('login'))

    return render_template('login.html')

# Выход
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта')
    return redirect(url_for('login'))


app.run(debug=True)
