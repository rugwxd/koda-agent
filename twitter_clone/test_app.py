import unittest
import tempfile
import os
from app import app, init_db, get_db_connection

class TwitterCloneTestCase(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.db_fd, app.config['DATABASE'] = tempfile.mkstemp()
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()
        
        with app.app_context():
            init_db()
    
    def tearDown(self):
        """Clean up after each test method."""
        os.close(self.db_fd)
        os.unlink(app.config['DATABASE'])
    
    def test_home_redirect_when_not_logged_in(self):
        """Test that home page redirects to login when not authenticated."""
        rv = self.app.get('/')
        assert b'Sign in to Twitter Clone' in rv.data or rv.status_code == 302
    
    def test_register_user(self):
        """Test user registration."""
        rv = self.app.post('/register', data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass',
            'bio': 'Test bio'
        }, follow_redirects=True)
        assert b'Registration successful' in rv.data
    
    def test_login_user(self):
        """Test user login after registration."""
        # First register a user
        self.app.post('/register', data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass'
        })
        
        # Then try to login
        rv = self.app.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        }, follow_redirects=True)
        
        # Should be redirected to home page after successful login
        assert rv.status_code == 200
    
    def test_invalid_login(self):
        """Test login with invalid credentials."""
        rv = self.app.post('/login', data={
            'username': 'nonexistent',
            'password': 'wrongpass'
        })
        assert b'Invalid username or password' in rv.data
    
    def register_and_login(self):
        """Helper method to register and login a user."""
        self.app.post('/register', data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass'
        })
        
        return self.app.post('/login', data={
            'username': 'testuser',
            'password': 'testpass'
        }, follow_redirects=True)
    
    def test_create_tweet(self):
        """Test creating a tweet."""
        # Register and login
        self.register_and_login()
        
        # Create a tweet
        rv = self.app.post('/tweet', data={
            'content': 'This is a test tweet!'
        }, follow_redirects=True)
        
        assert rv.status_code == 200
        assert b'This is a test tweet!' in rv.data
    
    def test_tweet_character_limit(self):
        """Test tweet character limit."""
        # Register and login
        self.register_and_login()
        
        # Try to create a tweet that's too long
        long_content = 'a' * 281  # 281 characters
        rv = self.app.post('/tweet', data={
            'content': long_content
        }, follow_redirects=True)
        
        assert b'Tweet must be between 1 and 280 characters' in rv.data
    
    def test_empty_tweet(self):
        """Test creating an empty tweet."""
        # Register and login
        self.register_and_login()
        
        # Try to create an empty tweet
        rv = self.app.post('/tweet', data={
            'content': ''
        }, follow_redirects=True)
        
        assert b'Tweet must be between 1 and 280 characters' in rv.data

if __name__ == '__main__':
    unittest.main()