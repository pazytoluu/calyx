from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-moi-en-prod'


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')


@app.route("/connexion")
def login():
    
    return render_template("login.html")


@app.route("/inscription")
def register():
    return render_template("register.html")


if __name__ == '__main__':
    app.run(debug=True)
