from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, SelectField, FloatField, FileField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Email, EqualTo, NumberRange, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import os
import random
from datetime import datetime

app = Flask(__name__)

# -----------------------
# Configuration
# -----------------------
app.config['SECRET_KEY'] = 'bookbridge-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# Create upload folder if not exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'books'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profiles'), exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file, folder='books'):
    """Save uploaded image and return the filename"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{timestamp}{ext}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], folder, filename)
        
        img = Image.open(file)
        max_size = (800, 800)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        img.save(filepath)
        
        return filename
    return None

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# -----------------------
# Database Models
# -----------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    city = db.Column(db.String(100))
    college = db.Column(db.String(200))
    bio = db.Column(db.Text)
    profile_image = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    seller_rating = db.Column(db.Float, default=0.0)
    seller_rating_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    books = db.relationship('Book', backref='owner', lazy=True)
    reviews = db.relationship('Review', backref='user', lazy=True)
    chat_messages = db.relationship('ChatMessage', backref='user', lazy=True)
    wishlist = db.relationship('Wishlist', backref='user', lazy=True, cascade='all, delete-orphan')

class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100))
    type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    subject = db.Column(db.String(100))
    grade = db.Column(db.String(50))
    condition = db.Column(db.String(50))
    image_url = db.Column(db.String(300))
    additional_images = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    reviews = db.relationship('Review', backref='book', lazy=True, cascade='all, delete-orphan')
    wishlist_items = db.relationship('Wishlist', backref='book', lazy=True, cascade='all, delete-orphan')

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    is_from_ai = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    category = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buyer_rating = db.Column(db.Integer, nullable=True)  # Buyer rates seller
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    book = db.relationship('Book', backref='conversations')
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='conversations_as_buyer')
    seller = db.relationship('User', foreign_keys=[seller_id], backref='conversations_as_seller')
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    sender = db.relationship('User', backref='sent_messages')

class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'book_id', name='unique_wishlist'),)

# -----------------------
# Forms
# -----------------------

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    phone = StringField('Phone', validators=[Length(max=20)])
    city = StringField('City', validators=[Length(max=100)])
    college = StringField('College/School Name', validators=[Length(max=200)])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    phone = StringField('Phone', validators=[Length(max=20)])
    city = StringField('City', validators=[Length(max=100)])
    college = StringField('College/School', validators=[Length(max=200)])
    bio = TextAreaField('Bio', validators=[Length(max=500)])
    profile_image = FileField('Profile Photo')
    submit = SubmitField('Update Profile')

class BookForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    author = StringField('Author', validators=[DataRequired()])
    price = FloatField('Price (₹)', validators=[DataRequired(), NumberRange(min=0)])
    min_price = FloatField('Min Price', validators=[Optional()])
    max_price = FloatField('Max Price', validators=[Optional()])
    location = StringField('Location', validators=[DataRequired()])
    city = SelectField('City', choices=[('', 'Select City'), ('Mumbai', 'Mumbai'), ('Delhi', 'Delhi'), ('Bangalore', 'Bangalore'), ('Chennai', 'Chennai'), ('Kolkata', 'Kolkata'), ('Hyderabad', 'Hyderabad'), ('Pune', 'Pune'), ('Ahmedabad', 'Ahmedabad'), ('Jaipur', 'Jaipur'), ('Lucknow', 'Lucknow'), ('Other', 'Other')])
    type = SelectField('Type', choices=[('sell', 'Sell'), ('rent', 'Rent')])
    subject = SelectField('Category/Subject', choices=[('', 'Select Category'), 
        ('Engineering', 'Engineering'), ('Medical', 'Medical'), ('UPSC', 'UPSC/SSC'), ('Commerce', 'Commerce'), 
        ('Arts', 'Arts'), ('Science', 'Science'), ('Mathematics', 'Mathematics'), ('Computer Science', 'Computer Science'),
        ('Physics', 'Physics'), ('Chemistry', 'Chemistry'), ('Biology', 'Biology'), ('Commerce', 'Commerce'),
        ('Accountancy', 'Accountancy'), ('Economics', 'Economics'), ('Business Studies', 'Business Studies'),
        ('English', 'English'), ('Hindi', 'Hindi'), ('History', 'History'), ('Geography', 'Geography'),
        ('Political Science', 'Political Science'), ('Law', 'Law'), ('Competitive Exam', 'Competitive Exam'), ('Other', 'Other')])
    grade = SelectField('Grade', choices=[('', 'Select Grade'), ('Class 1-5', 'Class 1-5'), ('Class 6-8', 'Class 6-8'), ('Class 9-10', 'Class 9-10'), ('Class 11-12', 'Class 11-12'), ('UG', 'Under Graduate'), ('PG', 'Post Graduate'), ('Competitive Exam', 'Competitive Exam')])
    condition = SelectField('Condition', choices=[('', 'Select Condition'), ('New', 'New'), ('Like New', 'Like New'), ('Good', 'Good'), ('Fair', 'Fair')])
    description = TextAreaField('Description')
    image = FileField('Book Image')
    additional_images = FileField('Additional Images')
    submit = SubmitField('Add Book')

class ReviewForm(FlaskForm):
    rating = SelectField('Rating', choices=[('5', '5 Stars'), ('4', '4 Stars'), ('3', '3 Stars'), ('2', '2 Stars'), ('1', '1 Star')])
    comment = TextAreaField('Comment', validators=[DataRequired()])
    submit = SubmitField('Submit Review')

class SellerRatingForm(FlaskForm):
    rating = SelectField('Rate Seller', choices=[('5', '5 Stars - Excellent'), ('4', '4 Stars - Very Good'), ('3', '3 Stars - Good'), ('2', '2 Stars - Fair'), ('1', '1 Star - Poor')])
    submit = SubmitField('Rate')

class NewsForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    category = SelectField('Category', choices=[('exam', 'Exam News'), ('result', 'Result'), ('admission', 'Admission'), ('scholarship', 'Scholarship'), ('other', 'Other')])
    submit = SubmitField('Add News')

class MessageForm(FlaskForm):
    message = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send')

# -----------------------
# Login Manager
# -----------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -----------------------
# APP TUTORIAL - Complete Guide
# -----------------------

APP_TUTORIAL = """
📚 **BOOKBRIDGE APP TUTORIAL** 

Welcome to BookBridge! Here's how to use our app:

**🔐 HOW TO LOGIN/REGISTER:**
1. Click "Register" in the top menu
2. Fill in: Username, Email, Password, Phone, City, College
3. Click "Register" - you'll be redirected to login
4. Use your email & password to login

**📚 BUYING BOOKS:**
1. Browse books on home page
2. Use filters: Category, Grade, Price, Type (Sell/Rent), Location
3. Click on any book to see details
4. Click "Message Seller" to chat about the book
5. After contacting, meet the seller to complete the deal

**💰 SELLING/RENTING BOOKS:**
1. Login to your account
2. Click "Sell/Rent" in the menu
3. Fill in: Title, Author, Price, Location, City
4. Select Category, Grade, Condition
5. Add description and upload book photo
6. Click "Add Book" - your book is now live!

**❤️ WISHLIST:**
1. Click the heart icon on any book
2. View all wishlisted books in "Wishlist" section
3. Remove books from wishlist anytime

**💬 MESSAGING SELLERS:**
1. Click "Message Seller" on any book
2. Chat with the seller about price, condition
3. Coordinate meetup for the deal

**⭐ RATINGS & REVIEWS:**
1. After buying, rate the book (1-5 stars)
2. Rate the seller after transaction
3. View ratings on seller profiles

**📍 LOCATION SEARCH:**
1. Click "By Location" in menu
2. Select your city to see local books
3. Filter by price, category

**🤖 AI CHAT - PROJECT IDEAS:**
1. Click "AI Chat" in menu
2. Ask for project ideas!
3. Try: "Give me computer project ideas"
4. We have 600+ ideas across 6 categories

**👤 PROFILE:**
1. View your books, reviews, wishlist
2. Edit your profile photo, bio, college
3. See your seller rating

**🔧 ADMIN PANEL:**
1. Login as admin (see admin credentials)
2. Manage books, users, news
3. View statistics

Need more help? Just ask me in AI Chat!
"""

# -----------------------
# PROJECT IDEAS DATABASE
# -----------------------

PROJECT_IDEAS = {
    'nature': [
        "1. Solar Water Purification System", "2. Wind Turbine Model", "3. Rainwater Harvesting Model", "4. Vertical Garden", "5. Biodegradable Plastic", "6. Solar Powered Air Cooler", "7. Water Quality Testing", "8. Organic Waste Converter", "9. Solar Tracking System", "10. Air Pollution Monitor",
        "11. Smart Irrigation", "12. Plant Growth Monitor", "13. Weather Prediction", "14. Earthquake Warning", "15. Flood Detection", "16. Green Building Design", "17. Biofertilizer Production", "18. Vermicomposting", "19. Hydroponic Farming", "20. Solar Water Heater"
    ],
    'computer': [
        "1. AI Chatbot", "2. Face Recognition System", "3. Handwriting Recognition", "4. Spam Detector", "5. Sentiment Analysis", "6. Language Translator", "7. Speech to Text", "8. Object Detection", "9. Medical Image Analysis", "10. Stock Price Predictor",
        "11. Library Management", "12. Hospital Management", "13. Online Learning Platform", "14. Budget Tracker", "15. Food Delivery App", "16. Hotel Booking System", "17. Route Optimizer", "18. Recommendation System", "19. E-Commerce Platform", "20. Social Media App"
    ],
    'science': [
        "1. Water Rocket", "2. Electric Motor", "3. Microscope", "4. Tesla Coil", "5. Newton's Cradle", "6. Heat Engine Model", "7. Cloud Chamber", "8. Spectroscope", "9. Periscope", "10. Telescope",
        "11. Digital Thermometer", "12. pH Meter", "13. Weather Station", "14. Solar Oven", "15. Wind Turbine", "16. Magnetic Levitation", "17. Fiber Optic Setup", "18. Radio Receiver", "19. Drone", "20. 3D Printer"
    ],
    'mathematics': [
        "1. Fractal Generator", "2. Prime Number Finder", "3. Fibonacci Visualizer", "4. Sudoku Solver", "5. Graph Theory Tool", "6. Statistics Analyzer", "7. Probability Simulator", "8. Regression Tool", "9. Game Theory Model", "10. Calculator Program",
        "11. Encryption Tool", "12. Password Generator", "13. Geometry Explorer", "14. Trigonometry Visualizer", "15. Calculus Helper", "16. Math Quiz App", "17. Equation Solver", "18. Unit Converter", "19. Calendar App", "20. Finance Calculator"
    ],
    'electronics': [
        "1. LED Cube", "2. Digital Clock", "3. Temperature Sensor", "4. Voice Controlled LED", "5. Remote Control Car", "6. Robot Arm", "7. Line Following Robot", "8. Obstacle Avoider", "9. DTMF Decoder", "10. FM Radio",
        "11. Amplifier Circuit", "12. Timer Circuit", "13. Voltage Regulator", "14. Battery Charger", "15. Inverter Circuit", "16. Motor Controller", "17. Light Dimmer", "18. Smart Home System", "19. Security Alarm", "20. Wireless Communication"
    ],
    'robotics': [
        "1. Line Following Robot", "2. Wall Following Robot", "3. Maze Solving Robot", "4. Object Avoiding Robot", "5. Gesture Controlled Robot", "6. Voice Controlled Robot", "7. Pick and Place Arm", "8. Drone", "9. Humanoid Robot", "10. Swarm Robots",
        "11. Self Balancing Robot", "12. Surveillance Robot", "13. Fire Fighting Robot", "14. Bot", "15. Robotic Hand", "16. Walking Robot", "17. Sumo Robot", "18. Battle Robot", "19. Snake Robot", "20. Quadcopter"
    ]
}

# -----------------------
# AI Agent Logic
# -----------------------

def get_ai_response(user_message):
    """Enhanced AI agent with app tutorial and project ideas"""
    user_message = user_message.lower()
    
    # APP TUTORIAL QUESTIONS
    if any(word in user_message for word in ['how to use', 'how does', 'tutorial', 'help', 'guide', 'how to login', 'how to register', 'how to sell', 'how to buy', 'how to message', 'how to wishlist', 'how to rate', 'how to chat', 'explain app', 'features', 'what can you do']):
        return APP_TUTORIAL
    
    # PROJECT IDEAS
    if any(word in user_message for word in ['nature project', 'environment project', 'eco project']):
        ideas = PROJECT_IDEAS['nature']
        response = "🌿 NATURE & ENVIRONMENT PROJECT IDEAS:\n\n"
        for idea in ideas:
            response += f"• {idea}\n"
        response += "\nAsk me to explain any project in detail!"
        return response
    
    elif any(word in user_message for word in ['computer project', 'it project', 'software project', 'programming project', 'ai project', 'web project', 'app project']):
        ideas = PROJECT_IDEAS['computer']
        response = "💻 COMPUTER & IT PROJECT IDEAS:\n\n"
        for idea in ideas:
            response += f"• {idea}\n"
        response += "\nAsk me to explain any project in detail!"
        return response
    
    elif any(word in user_message for word in ['science project', 'physics project', 'chemistry project']):
        ideas = PROJECT_IDEAS['science']
        response = "🔬 SCIENCE PROJECT IDEAS:\n\n"
        for idea in ideas:
            response += f"• {idea}\n"
        response += "\nAsk me to explain any project in detail!"
        return response
    
    elif any(word in user_message for word in ['math project', 'mathematics project']):
        ideas = PROJECT_IDEAS['mathematics']
        response = "📐 MATHEMATICS PROJECT IDEAS:\n\n"
        for idea in ideas:
            response += f"• {idea}\n"
        response += "\nAsk me to explain any project in detail!"
        return response
    
    elif any(word in user_message for word in ['electronics project', 'circuit project', 'electrical project']):
        ideas = PROJECT_IDEAS['electronics']
        response = "⚡ ELECTRONICS PROJECT IDEAS:\n\n"
        for idea in ideas:
            response += f"• {idea}\n"
        response += "\nAsk me to explain any project in detail!"
        return response
    
    elif any(word in user_message for word in ['robot project', 'robotics project', 'drone project']):
        ideas = PROJECT_IDEAS['robotics']
        response = "🤖 ROBOTICS PROJECT IDEAS:\n\n"
        for idea in ideas:
            response += f"• {idea}\n"
        response += "\nAsk me to explain any project in detail!"
        return response
    
    elif any(word in user_message for word in ['project idea', 'project help', 'need project']):
        return """📋 PROJECT IDEAS BY CATEGORY:

• 🌿 Nature/Environment - 20 ideas
• 💻 Computer/IT - 20 ideas  
• 🔬 Science - 20 ideas
• 📐 Mathematics - 20 ideas
• ⚡ Electronics - 20 ideas
• 🤖 Robotics - 20 ideas

Just ask me like:
- "Give me computer project ideas"
- "Science project ideas"
- "Electronics mini projects"

Total: 120+ ideas!"""
    
    elif any(word in user_message for word in ['book', 'buy', 'sell', 'rent']):
        return """📚 BOOK HELP:

TO BUY:
1. Browse books on home page
2. Use filters (category, price, location)
3. Click book for details
4. Message seller to discuss

TO SELL:
1. Login to your account
2. Click "Sell/Rent" 
3. Fill book details & upload photo
4. Your book will be listed!

We have books for all subjects & grades!"""
    
    elif any(word in user_message for word in ['login', 'register', 'sign up', 'account']):
        return """🔐 LOGIN/REGISTER:

REGISTER:
1. Click "Register" in menu
2. Enter: Username, Email, Password
3. Add Phone, City, College
4. Click Register

LOGIN:
1. Click "Login"
2. Enter Email & Password
3. Start buying/selling books!

Admin: admin@bookbridge.com / admin123"""
    
    else:
        return """🤖 Hi! I'm your BookBridge AI Assistant!

Ask me about:

📚 BUYING/SELLING:
- "How to buy books?"
- "How to sell books?"
- "How to message sellers?"

📝 PROJECT IDEAS:
- "Give me computer project ideas"
- "Science project ideas"
- "Electronics projects"

🔧 OTHER HELP:
- "How to login?"
- "What features do you have?"
- "How does wishlist work?"

Just ask your question!""" 

# -----------------------
# Routes with Pagination & Advanced Filters
# -----------------------

@app.route('/')
def home():
    page = request.args.get('page', 1, type=int)
    per_page = 6  # Pagination - 6 books per page
    
    # Advanced Filters
    search = request.args.get('search')
    location = request.args.get('location')
    subject = request.args.get('subject')
    grade = request.args.get('grade')
    book_type = request.args.get('type')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort_by = request.args.get('sort', 'newest')

    books_query = Book.query

    # Check if user is banned
    if current_user.is_authenticated and current_user.is_banned:
        flash('Your account has been banned.', 'danger')
        return redirect(url_for('logout'))

    if search:
        books_query = books_query.filter(Book.title.contains(search) | Book.author.contains(search))
    if location:
        books_query = books_query.filter(Book.location.contains(location) | Book.city.contains(location))
    if subject:
        books_query = books_query.filter(Book.subject == subject)
    if grade:
        books_query = books_query.filter(Book.grade == grade)
    if book_type:
        books_query = books_query.filter(Book.type == book_type)
    if min_price is not None:
        books_query = books_query.filter(Book.price >= min_price)
    if max_price is not None:
        books_query = books_query.filter(Book.price <= max_price)
    
    # Sorting
    if sort_by == 'price_low':
        books_query = books_query.order_by(Book.price.asc())
    elif sort_by == 'price_high':
        books_query = books_query.order_by(Book.price.desc())
    else:
        books_query = books_query.order_by(Book.created_at.desc())

    # Pagination
    pagination = books_query.paginate(page=page, per_page=per_page, error_out=False)
    books = pagination.items
    
    books_with_ratings = []
    for book in books:
        reviews = Review.query.filter_by(book_id=book.id).all()
        if reviews:
            avg_rating = sum(r.rating for r in reviews) / len(reviews)
            num_reviews = len(reviews)
        else:
            avg_rating = 0
            num_reviews = 0
        in_wishlist = False
        if current_user.is_authenticated:
            wishlist_item = Wishlist.query.filter_by(user_id=current_user.id, book_id=book.id).first()
            in_wishlist = bool(wishlist_item)
        
        books_with_ratings.append({
            'book': book,
            'avg_rating': round(avg_rating, 1),
            'num_reviews': num_reviews,
            'in_wishlist': in_wishlist
        })

    return render_template('home.html', books=books_with_ratings, pagination=pagination)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=hashed_password,
            phone=form.phone.data,
            city=form.city.data,
            college=form.college.data
        )
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Email or username already exists.', 'danger')
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            flash('Please fill in all fields.', 'danger')
        else:
            user = User.query.filter_by(email=email).first()
            if user:
                if check_password_hash(user.password_hash, password):
                    if user.is_banned:
                        flash('Your account has been banned. Contact admin.', 'danger')
                    else:
                        login_user(user)
                        flash('Login successful!', 'success')
                        next_page = request.args.get('next')
                        return redirect(next_page) if next_page else redirect(url_for('home'))
                else:
                    flash('Invalid password. Please try again.', 'danger')
            else:
                flash('No account found with this email. Please register first.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if request.method == 'POST' and form.validate_on_submit():
        # Check if username already exists (except current user)
        new_username = form.username.data
        if new_username != current_user.username:
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user:
                flash('Username already exists. Please choose a different username.', 'danger')
                return redirect(url_for('profile'))
        
        current_user.username = form.username.data
        current_user.phone = form.phone.data
        current_user.city = form.city.data
        current_user.college = form.college.data
        current_user.bio = form.bio.data
        
        if form.profile_image.data:
            filename = save_image(form.profile_image.data, folder='profiles')
            if filename:
                current_user.profile_image = filename
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    
    if request.method == 'GET':
        form.username.data = current_user.username
        form.phone.data = current_user.phone or ''
        form.city.data = current_user.city or ''
        form.college.data = current_user.college or ''
        form.bio.data = current_user.bio or ''
    
    user_books = Book.query.filter_by(user_id=current_user.id).all()
    user_reviews = Review.query.filter_by(user_id=current_user.id).all()
    wishlist_items = Wishlist.query.filter_by(user_id=current_user.id).all()
    wishlist_books = [item.book for item in wishlist_items]
    
    conversations = Conversation.query.filter(
        (Conversation.buyer_id == current_user.id) | (Conversation.seller_id == current_user.id)
    ).order_by(Conversation.updated_at.desc()).all()
    
    return render_template('profile.html', form=form, books=user_books, reviews=user_reviews, 
                         wishlist_books=wishlist_books, conversations=conversations)

@app.route('/book/<int:book_id>')
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)
    reviews = Review.query.filter_by(book_id=book_id).order_by(Review.created_at.desc()).all()
    
    if reviews:
        avg_rating = sum(r.rating for r in reviews) / len(reviews)
        num_reviews = len(reviews)
    else:
        avg_rating = 0
        num_reviews = 0
    
    additional_images = []
    if book.additional_images:
        import json
        additional_images = json.loads(book.additional_images)
    
    in_wishlist = False
    if current_user.is_authenticated:
        wishlist_item = Wishlist.query.filter_by(user_id=current_user.id, book_id=book.id).first()
        in_wishlist = bool(wishlist_item)
    
    has_conversation = False
    if current_user.is_authenticated and current_user.id != book.user_id:
        conv = Conversation.query.filter(
            Conversation.book_id == book_id,
            Conversation.buyer_id == current_user.id
        ).first()
        has_conversation = bool(conv)
    
    related_books = Book.query.filter(Book.subject == book.subject, Book.id != book.id).limit(4).all()
    
    return render_template('book_detail.html', book=book, reviews=reviews, avg_rating=round(avg_rating, 1), 
                          num_reviews=num_reviews, related_books=related_books, additional_images=additional_images,
                          in_wishlist=in_wishlist, has_conversation=has_conversation)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_book():
    form = BookForm()
    if form.validate_on_submit():
        image_filename = None
        if form.image.data:
            image_filename = save_image(form.image.data, folder='books')
        
        additional_images_list = []
        files = request.files.getlist('additional_images')
        for file in files:
            if file.filename:
                filename = save_image(file, folder='books')
                if filename:
                    additional_images_list.append(filename)
        
        import json
        new_book = Book(
            title=form.title.data, author=form.author.data, price=form.price.data,
            location=form.location.data, city=form.city.data, type=form.type.data,
            subject=form.subject.data, grade=form.grade.data, condition=form.condition.data,
            description=form.description.data, user_id=current_user.id,
            image_url=image_filename,
            additional_images=json.dumps(additional_images_list) if additional_images_list else None
        )
        db.session.add(new_book)
        db.session.commit()
        flash('Book added successfully!', 'success')
        return redirect(url_for('home'))
    return render_template('add_book.html', form=form)

@app.route('/edit_book/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_book(id):
    book = Book.query.get_or_404(id)
    if book.user_id != current_user.id and not current_user.is_admin:
        flash('You are not authorized.', 'danger')
        return redirect(url_for('home'))
    
    form = BookForm(obj=book)
    if form.validate_on_submit():
        book.title = form.title.data
        book.author = form.author.data
        book.price = form.price.data
        book.location = form.location.data
        book.city = form.city.data
        book.type = form.type.data
        book.subject = form.subject.data
        book.grade = form.grade.data
        book.condition = form.condition.data
        book.description = form.description.data
        
        if form.image.data:
            filename = save_image(form.image.data, folder='books')
            if filename:
                book.image_url = filename
        
        db.session.commit()
        flash('Book updated successfully!', 'success')
        return redirect(url_for('book_detail', book_id=book.id))
    
    return render_template('edit_book.html', form=form, book=book)

@app.route('/delete/<int:id>')
@login_required
def delete_book(id):
    book = Book.query.get_or_404(id)
    if book.user_id != current_user.id and not current_user.is_admin:
        flash('You are not authorized.', 'danger')
        return redirect(url_for('home'))
    db.session.delete(book)
    db.session.commit()
    flash('Book deleted successfully!', 'success')
    return redirect('/')

@app.route('/book/<int:book_id>/review', methods=['GET', 'POST'])
@login_required
def add_review(book_id):
    form = ReviewForm()
    book = Book.query.get_or_404(book_id)
    
    existing_review = Review.query.filter_by(book_id=book_id, user_id=current_user.id).first()
    if existing_review:
        flash('You have already reviewed this book.', 'warning')
        return redirect(url_for('book_detail', book_id=book_id))
    
    if form.validate_on_submit():
        review = Review(book_id=book_id, user_id=current_user.id, rating=int(form.rating.data), comment=form.comment.data)
        db.session.add(review)
        db.session.commit()
        flash('Review added successfully!', 'success')
        return redirect(url_for('book_detail', book_id=book_id))
    
    return render_template('add_review.html', form=form, book=book)

@app.route('/wishlist')
@login_required
def wishlist():
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    wishlist_query = Wishlist.query.filter_by(user_id=current_user.id)
    pagination = wishlist_query.paginate(page=page, per_page=per_page, error_out=False)
    
    books_with_ratings = []
    for item in pagination.items:
        book = item.book
        reviews = Review.query.filter_by(book_id=book.id).all()
        avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0
        books_with_ratings.append({
            'book': book,
            'avg_rating': round(avg_rating, 1),
            'num_reviews': len(reviews)
        })
    return render_template('wishlist.html', books=books_with_ratings, pagination=pagination)

@app.route('/wishlist/add/<int:book_id>')
@login_required
def add_to_wishlist(book_id):
    book = Book.query.get_or_404(book_id)
    
    existing = Wishlist.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if existing:
        flash('Book is already in your wishlist!', 'info')
    else:
        wishlist_item = Wishlist(user_id=current_user.id, book_id=book_id)
        db.session.add(wishlist_item)
        db.session.commit()
        flash('Added to wishlist!', 'success')
    
    return redirect(url_for('book_detail', book_id=book_id))

@app.route('/wishlist/remove/<int:book_id>')
@login_required
def remove_from_wishlist(book_id):
    wishlist_item = Wishlist.query.filter_by(user_id=current_user.id, book_id=book_id).first()
    if wishlist_item:
        db.session.delete(wishlist_item)
        db.session.commit()
        flash('Removed from wishlist!', 'success')
    
    return redirect(url_for('wishlist'))

# -----------------------
# Buyer-Seller Chat & Rating
# -----------------------

@app.route('/message_seller/<int:book_id>', methods=['GET', 'POST'])
@login_required
def message_seller(book_id):
    book = Book.query.get_or_404(book_id)
    
    if book.user_id == current_user.id:
        flash('This is your own book!', 'warning')
        return redirect(url_for('book_detail', book_id=book_id))
    
    conversation = Conversation.query.filter(
        Conversation.book_id == book_id,
        Conversation.buyer_id == current_user.id
    ).first()
    
    if not conversation:
        conversation = Conversation(
            book_id=book_id,
            buyer_id=current_user.id,
            seller_id=book.user_id
        )
        db.session.add(conversation)
        db.session.commit()
    
    return redirect(url_for('conversation_detail', conversation_id=conversation.id))

@app.route('/conversation/<int:conversation_id>', methods=['GET', 'POST'])
@login_required
def conversation_detail(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    
    if current_user.id != conversation.buyer_id and current_user.id != conversation.seller_id:
        flash('Access denied!', 'danger')
        return redirect(url_for('home'))
    
    # Seller rating form
    rating_form = SellerRatingForm()
    if current_user.id == conversation.buyer_id and conversation.buyer_rating is None:
        if rating_form.validate_on_submit():
            rating = int(rating_form.rating.data)
            conversation.buyer_rating = rating
            # Update seller rating
            seller = conversation.seller
            total_rating = seller.seller_rating * seller.seller_rating_count + rating
            seller.seller_rating_count += 1
            seller.seller_rating = total_rating / seller.seller_rating_count
            db.session.commit()
            flash('Thank you for rating the seller!', 'success')
            return redirect(url_for('conversation_detail', conversation_id=conversation.id))
    
    form = MessageForm()
    if form.validate_on_submit():
        message = Message(
            conversation_id=conversation.id,
            sender_id=current_user.id,
            message=form.message.data
        )
        db.session.add(message)
        conversation.updated_at = datetime.utcnow()
        
        unread_messages = Message.query.filter(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user.id,
            Message.is_read == False
        ).all()
        for msg in unread_messages:
            msg.is_read = True
        
        db.session.commit()
        flash('Message sent!', 'success')
        return redirect(url_for('conversation_detail', conversation_id=conversation.id))
    
    messages = Message.query.filter_by(conversation_id=conversation_id).order_by(Message.created_at.asc()).all()
    
    for msg in messages:
        if msg.sender_id != current_user.id:
            msg.is_read = True
    db.session.commit()
    
    other_user = conversation.seller if current_user.id == conversation.buyer_id else conversation.buyer
    
    # Check if buyer can rate seller
    can_rate = (current_user.id == conversation.buyer_id and conversation.buyer_rating is None)
    
    return render_template('conversation.html', conversation=conversation, messages=messages, 
                          form=form, other_user=other_user, rating_form=rating_form, can_rate=can_rate)

@app.route('/conversations')
@login_required
def conversations():
    convs = Conversation.query.filter(
        (Conversation.buyer_id == current_user.id) | (Conversation.seller_id == current_user.id)
    ).order_by(Conversation.updated_at.desc()).all()
    
    conversations_with_info = []
    for conv in convs:
        last_message = Message.query.filter_by(conversation_id=conv.id).order_by(Message.created_at.desc()).first()
        unread_count = Message.query.filter(
            Message.conversation_id == conv.id,
            Message.sender_id != current_user.id,
            Message.is_read == False
        ).count()
        other_user = conv.seller if current_user.id == conv.buyer_id else conv.buyer
        
        conversations_with_info.append({
            'conversation': conv,
            'last_message': last_message,
            'unread_count': unread_count,
            'other_user': other_user
        })
    
    return render_template('conversations.html', conversations=conversations_with_info)

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        user_message = request.form.get('message')
        if user_message:
            user_msg = ChatMessage(user_id=current_user.id, message=user_message, is_from_ai=False)
            db.session.add(user_msg)
            ai_response = get_ai_response(user_message)
            ai_msg = ChatMessage(user_id=current_user.id, message=ai_response, is_from_ai=True)
            db.session.add(ai_msg)
            db.session.commit()
            
    messages = ChatMessage.query.filter_by(user_id=current_user.id).order_by(ChatMessage.created_at.desc()).limit(50).all()
    messages = list(reversed(messages))
    
    return render_template('chat.html', messages=messages)

@app.route('/recommendations')
def recommendations():
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    user_subjects = []
    if current_user.is_authenticated:
        user_books = Book.query.filter_by(user_id=current_user.id).all()
        user_subjects = [b.subject for b in user_books if b.subject]
    
    popular_subjects = db.session.query(Book.subject, db.func.count(Book.id).label('count')).group_by(Book.subject).order_by(db.desc('count')).limit(10).all()
    
    recommended_books = []
    if user_subjects:
        recommended_books = Book.query.filter(Book.subject.in_(user_subjects)).limit(8).all()
    
    if not recommended_books:
        recommended_books = Book.query.order_by(Book.created_at.desc()).limit(8).all()
    
    books_with_ratings = []
    for book in recommended_books:
        reviews = Review.query.filter_by(book_id=book.id).all()
        avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0
        books_with_ratings.append({'book': book, 'avg_rating': round(avg_rating, 1)})
    
    return render_template('recommendations.html', books=books_with_ratings, popular_subjects=popular_subjects)

@app.route('/location')
def location_search():
    cities = db.session.query(Book.city, db.func.count(Book.id).label('count')).filter(Book.city != None).group_by(Book.city).all()
    selected_city = request.args.get('city')
    page = request.args.get('page', 1, type=int)
    per_page = 6
    
    if selected_city:
        pagination = Book.query.filter_by(city=selected_city).paginate(page=page, per_page=per_page, error_out=False)
        books = pagination.items
    else:
        pagination = None
        books = []
    
    return render_template('location.html', cities=cities, selected_city=selected_city, books=books, pagination=pagination)

@app.route('/news')
def news():
    category = request.args.get('category')
    news_items = News.query.filter_by(category=category).order_by(News.created_at.desc()).all() if category else News.query.order_by(News.created_at.desc()).all()
    return render_template('news.html', news=news_items)

# -----------------------
# Enhanced Admin Panel
# -----------------------

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    total_books = Book.query.count()
    total_users = User.query.count()
    total_reviews = Review.query.count()
    total_messages = ChatMessage.query.count()
    recent_books = Book.query.order_by(Book.created_at.desc()).limit(10).all()
    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(10).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    books_by_city = db.session.query(Book.city, db.func.count(Book.id).label('count')).filter(Book.city != None).group_by(Book.city).all()
    books_by_subject = db.session.query(Book.subject, db.func.count(Book.id).label('count')).filter(Book.subject != None).group_by(Book.subject).order_by(db.desc('count')).all()
    banned_users = User.query.filter_by(is_banned=True).all()
    all_users = User.query.order_by(User.created_at.desc()).all()
    
    return render_template('admin_dashboard.html', total_books=total_books, total_users=total_users, 
                          total_reviews=total_reviews, total_messages=total_messages, 
                          recent_books=recent_books, recent_reviews=recent_reviews, 
                          recent_users=recent_users, books_by_city=books_by_city,
                          books_by_subject=books_by_subject, banned_users=banned_users, all_users=all_users)

@app.route('/admin/add_news', methods=['GET', 'POST'])
@login_required
def admin_add_news():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    form = NewsForm()
    if form.validate_on_submit():
        news = News(title=form.title.data, content=form.content.data, category=form.category.data)
        db.session.add(news)
        db.session.commit()
        flash('News added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_add_news.html', form=form)

@app.route('/admin/delete_news/<int:id>')
@login_required
def admin_delete_news(id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    news = News.query.get_or_404(id)
    db.session.delete(news)
    db.session.commit()
    flash('News deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/ban_user/<int:user_id>')
@login_required
def admin_ban_user(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot ban admin!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    user.is_banned = not user.is_banned
    db.session.commit()
    status = "banned" if user.is_banned else "unbanned"
    flash(f'User {user.username} has been {status}.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>')
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot delete admin!', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} has been deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_book/<int:book_id>')
@login_required
def admin_delete_book(book_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('home'))
    
    book = Book.query.get_or_404(book_id)
    db.session.delete(book)
    db.session.commit()
    flash('Book deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

# -----------------------
# Main Runner
# -----------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(email='admin@bookbridge.com').first()
        if not admin:
            admin = User(username='admin', email='admin@bookbridge.com', password_hash=generate_password_hash('admin123'), is_admin=True, city='Mumbai', college='BookBridge Institute')
            db.session.add(admin)
            db.session.commit()
            print("Admin created: admin@bookbridge.com / admin123")
    
    app.run(debug=True)
