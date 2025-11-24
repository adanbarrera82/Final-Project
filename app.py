from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
import os

# Initialize Flask app
app = Flask(__name__, static_url_path='', static_folder='static')

# Secret key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# File upload configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
# - db.tasks

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
        'expiration_date': doc.get('expiration_date'),
        'video_link': doc.get('video_link')
    }


def delete_group_files(group_id):
    """Delete all uploaded files associated with a group."""
    # Find all messages with file attachments for this group
    messages_with_files = db.messages.find({
        'group_id': group_id,
        'file_url': {'$exists': True, '$ne': None}
    })

    deleted_count = 0
    for msg in messages_with_files:
        file_url = msg.get('file_url')
        if file_url:
            # Extract filename from URL (format: /static/uploads/filename)
            # The file_url is like: /static/uploads/20251124_095227_Lab_11.pdf
            filename = file_url.split('/')[-1]
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Delete the file if it exists
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")

    # Delete all messages for this group
    db.messages.delete_many({'group_id': group_id})

    # Delete all tasks for this group
    db.tasks.delete_many({'group_id': group_id})

    return deleted_count


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
        # Delete files, messages, and tasks for each expired group
        total_files_deleted = 0
        for expired_group in expired_cursor:
            files_deleted = delete_group_files(expired_group['_id'])
            total_files_deleted += files_deleted

        # Delete the expired groups
        db.groups.delete_many({'expiration_date': {'$lte': datetime.now()}})

        if total_files_deleted > 0:
            flash(f'{expired_count} expired group(s) and {total_files_deleted} file(s) have been automatically deleted.', 'info')
        else:
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
        video_link = request.form.get('video_link', '').strip()
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
            'video_link': video_link if video_link else None,
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
        video_link = request.form.get('video_link', '').strip()

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
            'description': description,
            'video_link': video_link if video_link else None
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

    # Delete all uploaded files, messages, and tasks for this group
    deleted_files = delete_group_files(oid)

    # Delete the group itself
    db.groups.delete_one({'_id': oid})

    if deleted_files > 0:
        flash(f'Study group "{group_name}" and {deleted_files} uploaded file(s) have been deleted!', 'success')
    else:
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
        file = request.files.get('file')

        # Check if at least message or file is provided
        if not message_text and not file:
            flash('Please enter a message or attach a file!', 'danger')
            return redirect(url_for('chat', id=id))

        file_url = None
        file_name = None
        file_type = None

        # Handle file upload
        if file and file.filename:
            if allowed_file(file.filename):
                # Create unique filename with timestamp
                filename = secure_filename(file.filename)
                timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp_str}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

                try:
                    file.save(file_path)
                    file_url = url_for('static', filename=f'uploads/{unique_filename}')
                    file_name = filename
                    file_type = file.content_type
                except Exception as e:
                    flash(f'Error uploading file: {str(e)}', 'danger')
                    return redirect(url_for('chat', id=id))
            else:
                flash('Invalid file type! Allowed types: images, PDF, Word, and text files.', 'danger')
                return redirect(url_for('chat', id=id))

        # Insert message with optional file attachment
        message_doc = {
            'group_id': oid,
            'sender_name': username,
            'message_text': message_text,
            'timestamp': datetime.now()
        }

        if file_url:
            message_doc['file_url'] = file_url
            message_doc['file_name'] = file_name
            message_doc['file_type'] = file_type

        db.messages.insert_one(message_doc)

        return redirect(url_for('chat', id=id))

    # Get all messages for this group
    cursor = db.messages.find({'group_id': oid}).sort('timestamp', 1)
    messages = []
    for m in cursor:
        msg = {
            'sender_name': m.get('sender_name'),
            'message_text': m.get('message_text'),
            'timestamp': m.get('timestamp')
        }
        # Add file information if present
        if m.get('file_url'):
            msg['file_url'] = m.get('file_url')
            msg['file_name'] = m.get('file_name')
            msg['file_type'] = m.get('file_type')
        messages.append(msg)

    return render_template('chat.html', group=serialize_group(group_doc), messages=messages, current_user=username)


# Tasks route - view and manage tasks for a group
@app.route('/tasks/<id>', methods=['GET', 'POST'])
@login_required
def tasks(id):
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
        flash('Only group members can access the tasks!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        task_title = request.form.get('task_title', '').strip()
        task_description = request.form.get('task_description', '').strip()
        assigned_to = request.form.get('assigned_to', '').strip()

        if not task_title:
            flash('Please enter a task title!', 'danger')
            return redirect(url_for('tasks', id=id))

        db.tasks.insert_one({
            'group_id': oid,
            'title': task_title,
            'description': task_description,
            'assigned_to': assigned_to if assigned_to else None,
            'created_by': username,
            'completed': False,
            'created_at': datetime.now()
        })

        flash('Task added successfully!', 'success')
        return redirect(url_for('tasks', id=id))

    # Get all tasks for this group
    cursor = db.tasks.find({'group_id': oid}).sort('created_at', -1)
    tasks_list = []
    for t in cursor:
        tasks_list.append({
            'id': str(t.get('_id')),
            'title': t.get('title'),
            'description': t.get('description'),
            'assigned_to': t.get('assigned_to'),
            'created_by': t.get('created_by'),
            'completed': t.get('completed'),
            'created_at': t.get('created_at')
        })

    return render_template('tasks.html', group=serialize_group(group_doc), tasks=tasks_list, current_user=username)


# Toggle task completion
@app.route('/tasks/<group_id>/toggle/<task_id>', methods=['POST'])
@login_required
def toggle_task(group_id, task_id):
    try:
        group_oid = ObjectId(group_id)
        task_oid = ObjectId(task_id)
    except Exception:
        abort(404)

    group_doc = db.groups.find_one({'_id': group_oid})
    if not group_doc:
        abort(404)

    username = session['username']
    members = group_doc.get('members', [])
    if username not in members:
        flash('Only group members can modify tasks!', 'danger')
        return redirect(url_for('index'))

    task = db.tasks.find_one({'_id': task_oid})
    if not task:
        flash('Task not found!', 'danger')
        return redirect(url_for('tasks', id=group_id))

    # Toggle the completed status
    new_status = not task.get('completed', False)
    db.tasks.update_one({'_id': task_oid}, {'$set': {'completed': new_status}})

    return redirect(url_for('tasks', id=group_id))


# Delete task
@app.route('/tasks/<group_id>/delete/<task_id>', methods=['POST'])
@login_required
def delete_task(group_id, task_id):
    try:
        group_oid = ObjectId(group_id)
        task_oid = ObjectId(task_id)
    except Exception:
        abort(404)

    group_doc = db.groups.find_one({'_id': group_oid})
    if not group_doc:
        abort(404)

    username = session['username']
    members = group_doc.get('members', [])
    if username not in members:
        flash('Only group members can delete tasks!', 'danger')
        return redirect(url_for('index'))

    task = db.tasks.find_one({'_id': task_oid})
    if not task:
        flash('Task not found!', 'danger')
        return redirect(url_for('tasks', id=group_id))

    # Only creator or assigned person can delete
    if task.get('created_by') != username and task.get('assigned_to') != username:
        flash('Only the task creator or assigned person can delete this task!', 'danger')
        return redirect(url_for('tasks', id=group_id))

    db.tasks.delete_one({'_id': task_oid})
    flash('Task deleted successfully!', 'success')
    return redirect(url_for('tasks', id=group_id))


# Run app
if __name__ == '__main__':
    # MongoDB does not require creating tables; just run the app.
    app.run(debug=True)