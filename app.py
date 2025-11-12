from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime

# Initialize Flask app
app = Flask(__name__, static_url_path='', static_folder='static')

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Initialize database
db = SQLAlchemy(app)

# Define database model
class StudyGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    course_number = db.Column(db.String(50), nullable=True)  # course number (optional)
    description = db.Column(db.Text, nullable=False)
    members = db.Column(db.String(500), default="")  # list of member names
    creator = db.Column(db.String(100), nullable=False)  # name of group creator
    expiration_date = db.Column(db.DateTime, nullable=True)  # expiration date (optional)

    def __repr__(self):
        return f'<StudyGroup {self.group_name}>'

    def get_members(self):
        return [m.strip() for m in self.members.split(',') if m.strip()]

    def is_expired(self):
        if self.expiration_date:
            return datetime.now() > self.expiration_date
        return False


# Define Message model
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('study_group.id'), nullable=False)
    sender_name = db.Column(db.String(100), nullable=False)
    message_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now, nullable=False)

    def __repr__(self):
        return f'<Message from {self.sender_name} in group {self.group_id}>'


# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# Register route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not username or not password:
            flash('Username and password are required!', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long!', 'danger')
            return render_template('register.html')

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html')

        # Create new user
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash(f'Account created successfully for {username}! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect to index
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Please enter both username and password!', 'danger')
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password!', 'danger')
            return render_template('login.html')

    return render_template('login.html')


# Logout route
@app.route('/logout')
def logout():
    username = session.get('username')
    session.clear()
    flash(f'Goodbye, {username}!', 'info')
    return redirect(url_for('login'))


# Home route — list all groups
@app.route('/')
@login_required
def index():
    # Delete expired groups automatically
    expired_groups = StudyGroup.query.filter(StudyGroup.expiration_date <= datetime.now()).all()
    for group in expired_groups:
        db.session.delete(group)
    if expired_groups:
        db.session.commit()
        flash(f'{len(expired_groups)} expired group(s) have been automatically deleted.', 'info')

    subject_filter = request.args.get('subject', None)

    if subject_filter and subject_filter != 'All':
        groups = StudyGroup.query.filter_by(subject=subject_filter).all()
    else:
        groups = StudyGroup.query.all()

    # Get all unique subjects for the filter dropdown
    all_subjects = db.session.query(StudyGroup.subject).distinct().order_by(StudyGroup.subject).all()
    subjects = [s[0] for s in all_subjects]

    return render_template('index.html', groups=groups, subjects=subjects, selected_subject=subject_filter)

# Add group route
@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_group():
    if request.method == 'POST':
        name = request.form['group_name']
        subject = request.form['subject']
        custom_subject = request.form.get('custom_subject', '').strip()
        course_number = request.form.get('course_number', '').strip()
        expiration_date_str = request.form.get('expiration_date', '').strip()
        description = request.form['description']
        creator = session['username']  # Get from session instead

        # Use custom_subject if "Other" was selected
        if subject == 'Other' and custom_subject:
            subject = custom_subject

        # Parse expiration date
        expiration_date = None
        if expiration_date_str:
            try:
                expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid expiration date format!', 'danger')
                return render_template('add_group.html')

        new_group = StudyGroup(
            group_name=name,
            subject=subject,
            course_number=course_number if course_number else None,
            expiration_date=expiration_date,
            description=description,
            creator=creator,
            members=creator  # Add creator as first member
        )
        db.session.add(new_group)
        db.session.commit()
        flash(f'Study group "{name}" has been created!', 'success')
        return redirect(url_for('index'))

    return render_template('add_group.html')

# Edit group route
@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_group(id):
    group = StudyGroup.query.get_or_404(id)
    current_user = session.get('username')

    # Only the group creator can edit the group
    if current_user != group.creator:
        flash('Only the group creator can edit this group!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        group.group_name = request.form['group_name']
        subject = request.form['subject']
        custom_subject = request.form.get('custom_subject', '').strip()
        course_number = request.form.get('course_number', '').strip()
        expiration_date_str = request.form.get('expiration_date', '').strip()
        group.description = request.form['description']

        # Use custom_subject if "Other" was selected
        if subject == 'Other' and custom_subject:
            group.subject = custom_subject
        else:
            group.subject = subject

        group.course_number = course_number if course_number else None

        # Parse expiration date
        if expiration_date_str:
            try:
                group.expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid expiration date format!', 'danger')
                return render_template('edit_group.html', group=group)
        else:
            group.expiration_date = None

        db.session.commit()
        return redirect(url_for('index'))

    return render_template('edit_group.html', group=group)

# Delete group route
@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_group(id):
    group = StudyGroup.query.get_or_404(id)
    current_user = session['username']

    if current_user != group.creator:
        flash('Only the group creator can delete this group!', 'danger')
        return redirect(url_for('index'))

    group_name = group.group_name
    db.session.delete(group)
    db.session.commit()
    flash(f'Study group "{group_name}" has been deleted!', 'success')
    return redirect(url_for('index'))

# Join group route
@app.route('/join/<int:id>', methods=['POST'])
@login_required
def join_group(id):
    username = session['username']
    group = StudyGroup.query.get_or_404(id)

    members = group.get_members()

    # Check if already a member
    if username in members:
        flash(f'You are already a member of "{group.group_name}"!', 'warning')
    else:
        members.append(username)
        group.members = ', '.join(members)
        db.session.commit()
        flash(f'You successfully joined "{group.group_name}"!', 'success')

    return redirect(url_for('index'))

# Leave group route
@app.route('/leave/<int:id>', methods=['POST'])
@login_required
def leave_group(id):
    username = session['username']
    group = StudyGroup.query.get_or_404(id)

    members = group.get_members()

    # Check if user is a member
    if username not in members:
        flash(f'You are not a member of "{group.group_name}"!', 'danger')
    else:
        members.remove(username)
        group.members = ', '.join(members)
        db.session.commit()
        flash(f'You have left "{group.group_name}".', 'info')

    return redirect(url_for('index'))


# Chat route
@app.route('/chat/<int:id>', methods=['GET', 'POST'])
@login_required
def chat(id):
    group = StudyGroup.query.get_or_404(id)
    username = session['username']

    # Check if user is a member
    members = group.get_members()
    if username not in members:
        flash('Only group members can access the chat!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        message_text = request.form.get('message', '').strip()

        if not message_text:
            flash('Please enter a message!', 'danger')
            return redirect(url_for('chat', id=id))

        # Save message
        new_message = Message(
            group_id=id,
            sender_name=username,
            message_text=message_text
        )
        db.session.add(new_message)
        db.session.commit()

        return redirect(url_for('chat', id=id))

    # Get all messages for this group
    messages = Message.query.filter_by(group_id=id).order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', group=group, messages=messages, current_user=username)


# Run app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)