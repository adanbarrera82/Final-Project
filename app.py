from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

# Initialize Flask app
app = Flask(__name__, static_url_path='', static_folder='static')

# Secret key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# MongoDB setup
# Use MONGO_URI env var if set, otherwise default to localhost
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
# Database name
DB_NAME = os.environ.get('MONGO_DBNAME', 'final_project_db')
db = client[DB_NAME]

# Collections used:
# - db.groups
# - db.messages
# - db.users

def serialize_group(doc):
    """Return a dict suitable for templates from a MongoDB group document."""
    if not doc:
        return None
    return {
        'id': str(doc.get('_id')),
        'group_name': doc.get('group_name'),
        'subject': doc.get('subject'),
        'course_number': doc.get('course_number'),
        'description': doc.get('description'),
        'creator': doc.get('creator'),
        'members': doc.get('members') or [],
        'expiration_date': doc.get('expiration_date')
    }


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
        existing_user = db.users.find_one({'username': username})
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return render_template('register.html')

        # Create new user (store password hash)
        password_hash = generate_password_hash(password)
        db.users.insert_one({
            'username': username,
            'password_hash': password_hash,
            'created_at': datetime.now()
        })

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

        user = db.users.find_one({'username': username})

        if user and check_password_hash(user.get('password_hash', ''), password):
            session['user_id'] = str(user.get('_id'))
            session['username'] = user.get('username')
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
    expired_cursor = list(db.groups.find({'expiration_date': {'$lte': datetime.now()}}))
    expired_count = len(expired_cursor)
    if expired_count:
        db.groups.delete_many({'expiration_date': {'$lte': datetime.now()}})
        flash(f'{expired_count} expired group(s) have been automatically deleted.', 'info')

    subject_filter = request.args.get('subject', None)

    if subject_filter and subject_filter != 'All':
        cursor = db.groups.find({'subject': subject_filter})
    else:
        cursor = db.groups.find()

    groups = [serialize_group(g) for g in cursor]

    # Get all unique subjects for the filter dropdown
    subjects = sorted([s for s in db.groups.distinct('subject') if s])

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

        group_doc = {
            'group_name': name,
            'subject': subject,
            'course_number': course_number if course_number else None,
            'expiration_date': expiration_date,
            'description': description,
            'creator': creator,
            'members': [creator]
        }
        db.groups.insert_one(group_doc)
        flash(f'Study group "{name}" has been created!', 'success')
        return redirect(url_for('index'))

    return render_template('add_group.html')

# Edit group route
@app.route('/edit/<id>', methods=['GET', 'POST'])
@login_required
def edit_group(id):
    # Load group by ObjectId
    try:
        oid = ObjectId(id)
    except Exception:
        abort(404)

    group_doc = db.groups.find_one({'_id': oid})
    if not group_doc:
        abort(404)

    current_user = session.get('username')
    if current_user != group_doc.get('creator'):
        flash('Only the group creator can edit this group!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        group_name = request.form['group_name']
        subject = request.form['subject']
        custom_subject = request.form.get('custom_subject', '').strip()
        course_number = request.form.get('course_number', '').strip()
        expiration_date_str = request.form.get('expiration_date', '').strip()
        description = request.form['description']

        # Use custom_subject if "Other" was selected
        if subject == 'Other' and custom_subject:
            subject_final = custom_subject
        else:
            subject_final = subject

        expiration_date = None
        if expiration_date_str:
            try:
                expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Invalid expiration date format!', 'danger')
                return render_template('edit_group.html', group=serialize_group(group_doc))

        update_fields = {
            'group_name': group_name,
            'subject': subject_final,
            'course_number': course_number if course_number else None,
            'expiration_date': expiration_date,
            'description': description
        }

        db.groups.update_one({'_id': oid}, {'$set': update_fields})
        return redirect(url_for('index'))

    return render_template('edit_group.html', group=serialize_group(group_doc))

# Delete group route
@app.route('/delete/<id>', methods=['POST'])
@login_required
def delete_group(id):
    try:
        oid = ObjectId(id)
    except Exception:
        abort(404)

    group_doc = db.groups.find_one({'_id': oid})
    if not group_doc:
        abort(404)

    current_user = session.get('username')
    if current_user != group_doc.get('creator'):
        flash('Only the group creator can delete this group!', 'danger')
        return redirect(url_for('index'))

    group_name = group_doc.get('group_name')
    db.groups.delete_one({'_id': oid})
    flash(f'Study group "{group_name}" has been deleted!', 'success')
    return redirect(url_for('index'))

# Join group route
@app.route('/join/<id>', methods=['POST'])
@login_required
def join_group(id):
    username = session['username']
    try:
        oid = ObjectId(id)
    except Exception:
        abort(404)

    group_doc = db.groups.find_one({'_id': oid})
    if not group_doc:
        abort(404)

    # Try to add member if not present
    result = db.groups.update_one({'_id': oid, 'members': {'$ne': username}}, {'$push': {'members': username}})
    if result.modified_count == 0:
        flash(f'You are already a member of "{group_doc.get("group_name")}"!', 'warning')
    else:
        flash(f'You successfully joined "{group_doc.get("group_name")}"!', 'success')

    return redirect(url_for('index'))

# Leave group route
@app.route('/leave/<id>', methods=['POST'])
@login_required
def leave_group(id):
    username = session['username']
    try:
        oid = ObjectId(id)
    except Exception:
        abort(404)

    group_doc = db.groups.find_one({'_id': oid})
    if not group_doc:
        abort(404)

    # Remove member if present
    result = db.groups.update_one({'_id': oid, 'members': username}, {'$pull': {'members': username}})
    if result.modified_count == 0:
        flash(f'You are not a member of "{group_doc.get("group_name")}"!', 'danger')
    else:
        flash(f'You have left "{group_doc.get("group_name")}".', 'info')

    return redirect(url_for('index'))


# Chat route
@app.route('/chat/<id>', methods=['GET', 'POST'])
@login_required
def chat(id):
    try:
        oid = ObjectId(id)
    except Exception:
        abort(404)

    group_doc = db.groups.find_one({'_id': oid})
    if not group_doc:
        abort(404)

    username = session['username']
    members = group_doc.get('members', [])
    if username not in members:
        flash('Only group members can access the chat!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        message_text = request.form.get('message', '').strip()

        if not message_text:
            flash('Please enter a message!', 'danger')
            return redirect(url_for('chat', id=id))

        db.messages.insert_one({
            'group_id': oid,
            'sender_name': username,
            'message_text': message_text,
            'timestamp': datetime.now()
        })

        return redirect(url_for('chat', id=id))

    # Get all messages for this group
    cursor = db.messages.find({'group_id': oid}).sort('timestamp', 1)
    messages = []
    for m in cursor:
        messages.append({
            'sender_name': m.get('sender_name'),
            'message_text': m.get('message_text'),
            'timestamp': m.get('timestamp')
        })

    return render_template('chat.html', group=serialize_group(group_doc), messages=messages, current_user=username)


# Run app
if __name__ == '__main__':
    # MongoDB does not require creating tables; just run the app.
    app.run(debug=True)