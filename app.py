from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html', active_menu='filters')

@app.route('/filters')
def filters():
    return render_template('index.html', active_menu='filters')

@app.route('/transform')
def transform():
    return render_template('index.html', active_menu='transform')

@app.route('/correction')
def correction():
    return render_template('index.html', active_menu='correction')

@app.route('/ai')
def ai():
    return render_template('index.html', active_menu='ai')

@app.route('/library')
def library():
    return render_template('library.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

app.run(debug=True)
