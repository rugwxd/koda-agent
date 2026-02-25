# Twitter Clone

A basic Twitter-like social media application built with Flask and SQLite.

## Features

- **User Authentication**: Register, login, and logout functionality
- **Tweet Creation**: Post tweets up to 280 characters
- **Timeline**: View all tweets from all users in chronological order
- **User Profiles**: View user profiles with their tweets and stats
- **Follow System**: Follow and unfollow other users
- **Like System**: Like and unlike tweets
- **Responsive Design**: Mobile-friendly interface using Bootstrap

## Installation

1. **Clone or download the project files**

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

1. **Start the Flask development server**:
   ```bash
   python app.py
   ```

2. **Open your web browser** and navigate to:
   ```
   http://localhost:5000
   ```

3. **Create an account** by clicking "Sign up" and filling out the registration form

4. **Start tweeting!** Once logged in, you can:
   - Post new tweets
   - View the timeline
   - Visit user profiles
   - Follow other users
   - Like tweets

## Database

The application uses SQLite database (`twitter_clone.db`) which will be created automatically when you first run the app. The database includes the following tables:

- `users`: User account information
- `tweets`: Tweet content and metadata
- `followers`: Follow relationships between users
- `likes`: Like relationships between users and tweets

## File Structure

```
twitter_clone/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── README.md          # This file
├── twitter_clone.db   # SQLite database (created automatically)
└── templates/         # HTML templates
    ├── base.html      # Base template with common layout
    ├── home.html      # Home page with tweet timeline
    ├── login.html     # Login page
    ├── register.html  # Registration page
    └── profile.html   # User profile page
```

## Security Notes

- Change the `secret_key` in `app.py` before deploying to production
- This is a basic implementation for learning purposes
- For production use, consider adding:
  - Input validation and sanitization
  - Rate limiting
  - CSRF protection
  - Email verification
  - Password strength requirements
  - Image upload for profile pictures
  - Real-time updates

## Customization

You can easily extend this application by:

- Adding retweet functionality
- Implementing direct messaging
- Adding image/media upload
- Creating hashtag support
- Adding search functionality
- Implementing notifications
- Adding admin panel

## Troubleshooting

- If you get import errors, make sure you've installed the requirements: `pip install -r requirements.txt`
- If the database seems corrupted, delete `twitter_clone.db` and restart the app
- Make sure you're running Python 3.6 or higher

## License

This project is open source and available under the MIT License.