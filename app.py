from flask import Flask, render_template


app = Flask(__name__)


@app.route('/')
def index():
    act_menu = 'filters'
    return render_template('index.html', active_menu=act_menu)


@app.route('/filters')
def filters():
    act_menu = 'filters'
    return render_template('index.html', active_menu=act_menu)


@app.route('/transform')
def transform():
    act_menu = 'transform'
    return render_template('index.html', active_menu=act_menu)


@app.route('/correction')
def correction():
    act_menu = 'correction'
    return render_template('index.html', active_menu=act_menu)


@app.route('/ai')
def ai():
    act_menu = 'ai'
    return render_template('index.html', active_menu=act_menu)


app.run(debug=True)
