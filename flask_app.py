from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, MultipleFileField, PasswordField, SelectField
from wtforms.validators import DataRequired
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///projects.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Add this line
app.config['UPLOAD_FOLDER'] = 'static/uploads/'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    images = db.relationship('ProjectImage', backref='project', lazy=True)

class ProjectImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(200), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.String(500), nullable=True)
    visit_date = db.Column(db.DateTime, default=datetime.utcnow)
    page_visited = db.Column(db.String(200), nullable=True)

class ProjectForm(FlaskForm):
    title = StringField('العنوان الرئيسي', validators=[DataRequired()])
    description = TextAreaField('ترويجي')
    images = MultipleFileField('اختار الصور ', validators=[DataRequired()])
    submit = SubmitField('رفع')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class ImageUploadForm(FlaskForm):
    project_id = SelectField('ادخال للعنوان الرئيسي', coerce=int, validators=[DataRequired()])
    images = MultipleFileField('اختار الصور', validators=[DataRequired()])
    submit = SubmitField('رفع')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    # Track visitor
    visitor_ip = request.environ.get('HTTP_X_REAL_IP', request.remote_addr)
    user_agent = request.headers.get('User-Agent', '')
    
    # Check if visitor already visited today
    today = datetime.utcnow().date()
    existing_visitor = Visitor.query.filter(
        Visitor.ip_address == visitor_ip,
        db.func.date(Visitor.visit_date) == today
    ).first()
    
    if not existing_visitor:
        new_visitor = Visitor(
            ip_address=visitor_ip,
            user_agent=user_agent,
            page_visited='/'
        )
        db.session.add(new_visitor)
        db.session.commit()
    
    projects = Project.query.all()
    return render_template('index.html', projects=projects)

@app.route('/google9d856a34b71a3561.html')
def google_verification():
    return render_template('google9d856a34b71a3561.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.password == form.password.data:
            login_user(user)
            return redirect(url_for('admin'))
        else:
            flash('Login Unsuccessful. Check username and password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    projects = Project.query.all()
    
    # Get visitor statistics
    total_visitors = Visitor.query.count()
    today_visitors = Visitor.query.filter(
        db.func.date(Visitor.visit_date) == datetime.utcnow().date()
    ).count()
    
    return render_template('admin.html', 
                         projects=projects, 
                         total_visitors=total_visitors,
                         today_visitors=today_visitors)

@app.route('/add_project', methods=['GET', 'POST'])
@login_required
def add_project():
    form = ProjectForm()
    if form.validate_on_submit():
        title = form.title.data
        description = form.description.data
        images = form.images.data

        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        new_project = Project(title=title, description=description)
        db.session.add(new_project)
        db.session.commit()

        for image in images:
            if image and image.filename:
                # Generate unique filename to prevent conflicts
                file_extension = os.path.splitext(image.filename)[1].lower()
                if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    try:
                        image.save(image_path)
                        image_url = url_for('static', filename='uploads/' + unique_filename)
                        new_image = ProjectImage(image_url=image_url, project_id=new_project.id)
                        db.session.add(new_image)
                    except Exception as e:
                        flash(f'خطأ في رفع الصورة: {str(e)}', 'error')
                        continue

        db.session.commit()
        flash('تم إضافة المشروع بنجاح!', 'success')
        return redirect(url_for('admin'))

    return render_template('add_project.html', form=form)

@app.route('/delete_project/<int:project_id>', methods=['POST'])
@login_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    images = ProjectImage.query.filter_by(project_id=project_id).all()

    for image in images:
        try:
            # Extract filename from URL
            filename = image.image_url.split('/')[-1]
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
        
        db.session.delete(image)

    db.session.delete(project)
    db.session.commit()
    flash('تم حذف المشروع والصور بنجاح.', 'success')
    return redirect(url_for('admin'))

@app.route('/upload_images', methods=['GET', 'POST'])
@login_required
def upload_images():
    form = ImageUploadForm()
    form.project_id.choices = [(p.id, p.title) for p in Project.query.all()]
    if form.validate_on_submit():
        project_id = form.project_id.data
        images = form.images.data

        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        uploaded_count = 0
        for image in images:
            if image and image.filename:
                # Generate unique filename to prevent conflicts
                file_extension = os.path.splitext(image.filename)[1].lower()
                if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                    
                    try:
                        image.save(image_path)
                        image_url = url_for('static', filename='uploads/' + unique_filename)
                        new_image = ProjectImage(image_url=image_url, project_id=project_id)
                        db.session.add(new_image)
                        uploaded_count += 1
                    except Exception as e:
                        flash(f'خطأ في رفع الصورة: {str(e)}', 'error')
                        continue

        db.session.commit()
        flash(f'تم رفع {uploaded_count} صورة بنجاح.', 'success')
        return redirect(url_for('admin'))

    return render_template('upload_images.html', form=form)

# SEO Routes
@app.route('/sitemap.xml')
def sitemap():
    response = make_response(render_template('sitemap.xml'))
    response.headers['Content-Type'] = 'application/xml'
    return response

@app.route('/robots.txt')
def robots():
    response = make_response("""User-agent: *
Allow: /
Sitemap: {}/sitemap.xml""".format(request.url_root.rstrip('/')))
    response.headers['Content-Type'] = 'text/plain'
    return response

# API endpoint for visitor count
@app.route('/api/visitor-count')
def visitor_count_api():
    total_visitors = Visitor.query.count()
    today_visitors = Visitor.query.filter(
        db.func.date(Visitor.visit_date) == datetime.utcnow().date()
    ).count()
    
    return jsonify({
        'total_visitors': total_visitors,
        'today_visitors': today_visitors
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='735103418').first():
            admin_user = User(username='735103418', password='735103418')
            db.session.add(admin_user)
            db.session.commit()
    
    app.run(host='0.0.0.0', port=5001, debug=True)
