from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

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
    description = db.Column(db.Text, nullable=False)
    members = db.Column(db.String(500), default="")  # list of member names
    creator = db.Column(db.String(100), nullable=False)  # name of group creator

    def __repr__(self):
        return f'<StudyGroup {self.group_name}>'

    def get_members(self):
        return [m.strip() for m in self.members.split(',') if m.strip()]


# Home route — list all groups
@app.route('/')
def index():
    groups = StudyGroup.query.all()
    return render_template('index.html', groups=groups)

# Add group route
@app.route('/add', methods=['GET', 'POST'])
def add_group():
    if request.method == 'POST':
        name = request.form['group_name']
        subject = request.form['subject']
        description = request.form['description']
        creator = request.form['creator']

        if not creator.strip():
            flash('Please enter your name as the creator!', 'danger')
            return render_template('add_group.html')

        new_group = StudyGroup(
            group_name=name,
            subject=subject,
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
def edit_group(id):
    group = StudyGroup.query.get_or_404(id)

    if request.method == 'POST':
        group.group_name = request.form['group_name']
        group.subject = request.form['subject']
        group.description = request.form['description']
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('edit_group.html', group=group)

# Delete group route
@app.route('/delete/<int:id>', methods=['POST'])
def delete_group(id):
    group = StudyGroup.query.get_or_404(id)
    username = request.form.get('username', '').strip()

    if not username:
        flash('Please enter your name to delete the group!', 'danger')
        return redirect(url_for('index'))

    if username != group.creator:
        flash('Only the group creator can delete this group!', 'danger')
        return redirect(url_for('index'))

    group_name = group.group_name
    db.session.delete(group)
    db.session.commit()
    flash(f'Study group "{group_name}" has been deleted!', 'success')
    return redirect(url_for('index'))

# Join group route
@app.route('/join/<int:id>', methods=['POST'])
def join_group(id):
    username = request.form.get('username', '').strip()
    group = StudyGroup.query.get_or_404(id)

    # Validate username
    if not username:
        flash('Please enter a valid name!', 'danger')
        return redirect(url_for('index'))

    members = group.get_members()
    
    # Check if already a member
    if username in members:
        flash(f'{username} is already a member of "{group.group_name}"!', 'warning')
    else:
        members.append(username)
        group.members = ', '.join(members)
        db.session.commit()
        flash(f'{username} successfully joined "{group.group_name}"!', 'success')

    return redirect(url_for('index'))

# Leave group route
@app.route('/leave/<int:id>', methods=['POST'])
def leave_group(id):
    username = request.form.get('username', '').strip()
    group = StudyGroup.query.get_or_404(id)

    # Validate username
    if not username:
        flash('Please enter a valid name!', 'danger')
        return redirect(url_for('index'))

    members = group.get_members()
    
    # Check if user is a member
    if username not in members:
        flash(f'{username} is not a member of "{group.group_name}"!', 'danger')
    else:
        members.remove(username)
        group.members = ', '.join(members)
        db.session.commit()
        flash(f'{username} has left "{group.group_name}".', 'info')

    return redirect(url_for('index'))


# Run app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)