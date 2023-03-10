from flask import Flask, render_template, request, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)

# manage worst case situations
# maintain log file, try catch(.get), healthcheck, pass sensitive content through env, config(), docker,threading

class Blogpost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50))
    subtitle = db.Column(db.String(50))
    author = db.Column(db.String(50))
    date_posted = db.Column(db.DateTime, default = datetime.utcnow)
    content = db.Column(db.Text)


@app.route('/')
def index():
    posts = Blogpost.query.all()
    return render_template('index.html', posts = posts)
    
@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/post/<int:post_id>')
def post(post_id):
    post = Blogpost.query.filter_by(id=post_id).one()
    
    return render_template('post.html', post=post)


@app.route('/add')
def add():
    return render_template('add.html')

@app.route('/addpost', methods = ['POST'])
def addpost():
    title = request.form['title']
    subtitle = request.form['subtitle']
    author = request.form['author']
    content = request.form['content']

    post = Blogpost(title=title, subtitle= subtitle, author=author, content= content)
    db.session.add(post)
    db.session.commit()

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
