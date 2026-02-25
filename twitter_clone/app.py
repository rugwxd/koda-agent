from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Database setup
DATABASE = 'twitter_clone.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with required tables"""
    conn = get_db_connection()
    
    # Users table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tweets table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tweets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Followers table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS followers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER NOT NULL,
            following_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (follower_id) REFERENCES users (id),
            FOREIGN KEY (following_id) REFERENCES users (id),
            UNIQUE(follower_id, following_id)
        )
    ''')
    
    # Likes table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tweet_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (tweet_id) REFERENCES tweets (id),
            UNIQUE(user_id, tweet_id)
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def home():
    """Home page showing all tweets"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    tweets = conn.execute('''
        SELECT t.id, t.content, t.created_at, u.username,
               COUNT(l.id) as like_count,
               EXISTS(SELECT 1 FROM likes WHERE user_id = ? AND tweet_id = t.id) as user_liked
        FROM tweets t
        JOIN users u ON t.user_id = u.id
        LEFT JOIN likes l ON t.id = l.tweet_id
        GROUP BY t.id
        ORDER BY t.created_at DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()
    
    return render_template('home.html', tweets=tweets)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        bio = request.form.get('bio', '')
        
        if not username or not email or not password:
            flash('All fields are required!')
            return render_template('register.html')
        
        conn = get_db_connection()
        
        # Check if user already exists
        existing_user = conn.execute(
            'SELECT id FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()
        
        if existing_user:
            flash('Username or email already exists!')
            conn.close()
            return render_template('register.html')
        
        # Create new user
        password_hash = generate_password_hash(password)
        conn.execute(
            'INSERT INTO users (username, email, password_hash, bio) VALUES (?, ?, ?, ?)',
            (username, email, password_hash, bio)
        )
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password!')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/tweet', methods=['POST'])
def tweet():
    """Create a new tweet"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    content = request.form['content']
    if not content or len(content) > 280:
        flash('Tweet must be between 1 and 280 characters!')
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO tweets (user_id, content) VALUES (?, ?)',
        (session['user_id'], content)
    )
    conn.commit()
    conn.close()
    
    return redirect(url_for('home'))

@app.route('/like/<int:tweet_id>')
def like_tweet(tweet_id):
    """Like or unlike a tweet"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Check if already liked
    existing_like = conn.execute(
        'SELECT id FROM likes WHERE user_id = ? AND tweet_id = ?',
        (session['user_id'], tweet_id)
    ).fetchone()
    
    if existing_like:
        # Unlike
        conn.execute(
            'DELETE FROM likes WHERE user_id = ? AND tweet_id = ?',
            (session['user_id'], tweet_id)
        )
    else:
        # Like
        conn.execute(
            'INSERT INTO likes (user_id, tweet_id) VALUES (?, ?)',
            (session['user_id'], tweet_id)
        )
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('home'))

@app.route('/profile/<username>')
def profile(username):
    """User profile page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get user info
    user = conn.execute(
        'SELECT * FROM users WHERE username = ?', (username,)
    ).fetchone()
    
    if not user:
        flash('User not found!')
        return redirect(url_for('home'))
    
    # Get user's tweets
    tweets = conn.execute('''
        SELECT t.id, t.content, t.created_at,
               COUNT(l.id) as like_count,
               EXISTS(SELECT 1 FROM likes WHERE user_id = ? AND tweet_id = t.id) as user_liked
        FROM tweets t
        LEFT JOIN likes l ON t.id = l.tweet_id
        WHERE t.user_id = ?
        GROUP BY t.id
        ORDER BY t.created_at DESC
    ''', (session['user_id'], user['id'])).fetchall()
    
    # Get follower/following counts
    follower_count = conn.execute(
        'SELECT COUNT(*) as count FROM followers WHERE following_id = ?',
        (user['id'],)
    ).fetchone()['count']
    
    following_count = conn.execute(
        'SELECT COUNT(*) as count FROM followers WHERE follower_id = ?',
        (user['id'],)
    ).fetchone()['count']
    
    # Check if current user is following this user
    is_following = conn.execute(
        'SELECT id FROM followers WHERE follower_id = ? AND following_id = ?',
        (session['user_id'], user['id'])
    ).fetchone() is not None
    
    conn.close()
    
    return render_template('profile.html', 
                         user=user, 
                         tweets=tweets, 
                         follower_count=follower_count,
                         following_count=following_count,
                         is_following=is_following,
                         is_own_profile=user['id'] == session['user_id'])

@app.route('/follow/<username>')
def follow_user(username):
    """Follow or unfollow a user"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get target user
    target_user = conn.execute(
        'SELECT id FROM users WHERE username = ?', (username,)
    ).fetchone()
    
    if not target_user or target_user['id'] == session['user_id']:
        conn.close()
        return redirect(url_for('home'))
    
    # Check if already following
    existing_follow = conn.execute(
        'SELECT id FROM followers WHERE follower_id = ? AND following_id = ?',
        (session['user_id'], target_user['id'])
    ).fetchone()
    
    if existing_follow:
        # Unfollow
        conn.execute(
            'DELETE FROM followers WHERE follower_id = ? AND following_id = ?',
            (session['user_id'], target_user['id'])
        )
    else:
        # Follow
        conn.execute(
            'INSERT INTO followers (follower_id, following_id) VALUES (?, ?)',
            (session['user_id'], target_user['id'])
        )
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('profile', username=username))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)