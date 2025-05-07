import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from dotenv import load_dotenv
from flask_restful import Api
from flask_jwt_extended import JWTManager
from models import db, User, Item,Complaint
from flask import current_app

from resources import (
    RegisterResource,
    LoginResource,
    AddComplaintResource,
    AllComplaintsResource,
    DeleteComplaintResource,
    UpdateComplaintResource,
    SingleComplaintResource
)

from flask_cors import CORS


# Load environment variables
load_dotenv()

# Initialize app
app = Flask(__name__, static_folder='static')
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')


CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///lostfound.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'super-secret-key'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
api = Api(app)
jwt = JWTManager(app)

# Create tables
with app.app_context():
    db.create_all()

# Dummy lost items data by category
lost_items = {
    "electronics": [],
    "accessories": [],
    "documents": [],
    "keys": [],
    "clothing": [],
    "other": []
}

# API Routes
api.add_resource(RegisterResource, '/api/register')
api.add_resource(LoginResource, '/api/login')
api.add_resource(AddComplaintResource, '/add-complaint')
api.add_resource(AllComplaintsResource, '/all-complaints')
api.add_resource(DeleteComplaintResource, '/delete-complaint/<int:complaint_id>')
api.add_resource(UpdateComplaintResource, '/complaints/<int:complaint_id>/update')
api.add_resource(SingleComplaintResource, '/complaint/<int:complaint_id>')


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


# Routes
@app.route('/')
def home():
    items = Item.query.order_by(Item.date_posted.desc()).all()
    return render_template('home.html', items=items)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('home'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(username=request.form['username']).first():
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=request.form['email']).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))

        user = User(
            username=request.form['username'],
            email=request.form['email'],
            password_hash=generate_password_hash(request.form['password']),
            role=request.form.get('role', 'student')
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('home'))

@app.route('/item/new', methods=['GET', 'POST'])
@login_required
def new_item():
    if request.method == 'POST':
        file = request.files.get('image')
        image_filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            image_filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))

        item = Item(
            title=request.form['title'],
            description=request.form['description'],
            category=request.form['category'],
            location=request.form['location'],
            status=request.form['status'],
            image_filename=image_filename,
            user_id=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        flash('Item reported successfully!', 'success')
        return redirect(url_for('home'))
    return render_template('new_item.html')

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    item.views += 1
    db.session.commit()
    return render_template('item_detail.html', item=item)

@app.route('/profile')
@login_required
def profile():
    user_items = Item.query.filter_by(user_id=current_user.id).order_by(Item.date_posted.desc()).all()
    return render_template('profile.html', user_items=user_items)

@app.route('/item/<int:item_id>/status', methods=['POST'])
@login_required
def update_item_status(item_id):
    item = Item.query.get_or_404(item_id)
    if item.user_id != current_user.id:
        flash('Permission denied', 'error')
        return redirect(url_for('item_detail', item_id=item_id))
    
    new_status = request.form.get('status')
    if new_status in ['lost', 'found', 'returned']:
        item.status = new_status
        db.session.commit()
        flash(f'Item status updated to {new_status}', 'success')
    return redirect(url_for('profile'))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/search', methods=['GET'])
def search():
    category = request.args.get('category', '').strip().lower()
    status = request.args.get('status', '').strip().lower()

    # Start with base query
    items = Item.query

    # Apply category filter
    if category:
        items = items.filter(Item.category.ilike(f'%{category}%'))

    # Apply status filter
    if status:
        items = items.filter(Item.status.ilike(f'%{status}%'))

    # Get final results
    items = items.all()

    return render_template('search_results.html', items=items, category=category, status=status)


@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/electronics-lost', methods=['GET', 'POST'])
def electronics_lost():
    if request.method == 'POST':
        item_name = request.form['item_name']
        location = request.form['location']
        date_lost = request.form['date_lost']
        description = request.form['description']
        contact = request.form['contact']
        
        # Save the item details
        lost_items.append({
            'id': len(lost_items) + 1,  # Assign a unique ID
            'item_name': item_name,
            'location': location,
            'date_lost': date_lost,
            'description': description,
            'contact': contact
        })
        
        return redirect(url_for('electronics_lost'))  # Reload the page

    return render_template('electronics_lost.html', lost_items=lost_items)


# Route to delete an item
@app.route('/electronics-lost/delete/<int:item_id>', methods=['POST'])
def delete_lost_item(item_id):
    global lost_items
    lost_items = [item for item in lost_items if item['id'] != item_id]
    flash('Item deleted successfully!', 'success')
    return redirect(url_for('electronics_lost'))


# Route to edit an item
# @app.route('/electronics-lost/edit/<int:item_id>', methods=['GET', 'POST'])
# def edit_lost_item(item_id):
#     item = next((item for item in lost_items if item['id'] == item_id), None)
#     if not item:
#         flash('Item not found!', 'error')
#         return redirect(url_for('electronics_lost'))

#     if request.method == 'POST':
#         item['item_name'] = request.form['item_name']
#         item['location'] = request.form['location']
#         item['date_lost'] = request.form['date_lost']
#         item['description'] = request.form['description']
#         item['contact'] = request.form['contact']
        
#         flash('Item updated successfully!', 'success')
#         return redirect(url_for('electronics_lost'))

#     return render_template('edit_lost_electronics.html', item=item)

def lost_item_category(category):
    if request.method == 'POST':
        item = {
            "id": len(lost_items[category]) + 1,  # Assign a unique ID
            "item_name": request.form["item_name"],
            "location": request.form["location"],
            "date_lost": request.form["date_lost"],
            "description": request.form["description"],
            "contact": request.form["contact"]
        }
        lost_items[category].append(item)
        flash(f"Lost {category.capitalize()} item reported successfully!", "success")
        return redirect(url_for(f"lost_{category}"))
    
    return render_template("lost_item.html", category=category, items=lost_items[category])


# Routes for each category
@app.route("/lost-electronics", methods=["GET", "POST"])
def lost_electronics():
    return lost_item_category("electronics")

@app.route("/lost-accessories", methods=["GET", "POST"])
def lost_accessories():
    return lost_item_category("accessories")

@app.route("/lost-documents", methods=["GET", "POST"])
def lost_documents():
    return lost_item_category("documents")

@app.route("/lost-keys", methods=["GET", "POST"])
def lost_keys():
    return lost_item_category("keys")

@app.route("/lost-clothing", methods=["GET", "POST"])
def lost_clothing():
    return lost_item_category("clothing")

@app.route("/lost-other", methods=["GET", "POST"])
def lost_other():
    return lost_item_category("other")


# Delete item function
@app.route("/delete/<category>/<int:item_id>", methods=["POST"])
def delete_item(category, item_id):
    global lost_items
    lost_items[category] = [item for item in lost_items[category] if item["id"] != item_id]
    flash(f"{category.capitalize()} item deleted successfully!", "success")
    return redirect(url_for(f"lost_{category}"))


# Edit item function
@app.route("/edit/<category>/<int:item_id>", methods=["GET", "POST"])
def edit_item(category, item_id):
    item = next((i for i in lost_items[category] if i["id"] == item_id), None)
    if not item:
        flash("Item not found!", "danger")
        return redirect(url_for(f"lost_{category}"))

    if request.method == "POST":
        item["item_name"] = request.form["item_name"]
        item["location"] = request.form["location"]
        item["date_lost"] = request.form["date_lost"]
        item["description"] = request.form["description"]
        item["contact"] = request.form["contact"]
        flash(f"{category.capitalize()} item updated successfully!", "success")
        return redirect(url_for(f"lost_{category}"))

    return render_template("edit_item.html", category=category, item=item)


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/electronics')
def electronics():
    return render_template('electronics.html')

@app.route('/documents')
def documents():
    return render_template('documents.html')

@app.route('/accessories')
def accessories():
    return render_template('accessories.html')

@app.route('/keys')
def keys():
    return render_template('keys.html')

@app.route('/clothing')
def clothing():
    return render_template('clothing.html')

@app.route('/others')
def others():
    return render_template('others.html')

@app.route('/edit_db_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_db_item(item_id):
    item = Item.query.get_or_404(item_id)

    # Ensure the user can only edit their own items
    if item.user_id != current_user.id:
        flash("You don't have permission to edit this item.", "danger")
        return redirect(url_for('electronics'))

    if request.method == 'POST':
        item.title = request.form['title']
        item.description = request.form['description']
        db.session.commit()
        flash('Item updated successfully!', 'success')
        return redirect(url_for('electronics'))

    return render_template('edit_db_item.html', item=item)


@app.route('/delete_report_item/<int:item_id>', methods=['POST'])
@login_required
def delete_report_item(item_id):
    item = Item.query.get_or_404(item_id)

    # Ensure the user can only delete their own items
    if item.user_id != current_user.id:
        flash("You don't have permission to delete this item.", "danger")
        return redirect(url_for('electronics'))

    db.session.delete(item)
    db.session.commit()
    flash('Item deleted successfully!', 'success')
    return redirect(url_for('electronics'))


@app.route("/report_lost_electronics", methods=["POST"])
@login_required
def report_lost_electronics():
    item_name = request.form["item_name"]
    location = request.form["location"]
    date_lost = request.form["date_lost"]
    description = request.form["description"]
    contact = request.form["contact"]

    new_item = {
        "id": len(lost_items["electronics"]) + 1,
        "item_name": item_name,
        "location": location,
        "date_lost": date_lost,
        "description": description,
        "contact": contact,
    }

    lost_items["electronics"].append(new_item)
    flash("Lost electronics item reported successfully!", "success")
    return redirect(url_for("home"))


# @app.route('/')
# def home():
#     items = Item.query.order_by(Item.date_posted.desc()).all()
#     return render_template('home.html', items=items, lost_items=lost_items)  # Pass lost_items

@app.route('/category/<string:category_name>')
def category_page(category_name):
    # Fetch items based on the category
    items = Item.query.filter_by(category=category_name).order_by(Item.date_posted.desc()).all()
    return render_template('category.html', category_name=category_name, items=items)


@app.route('/report-choice/electronics')
def report_choice():
    return render_template('report_choice.html')

@app.route('/report-lost/<category>')
def report_lost(category):
    return render_template('report_lost.html', category=category)

@app.route('/report-found/<category>')
def report_found(category):
    return render_template('report_found.html', category=category)

@app.route('/static/uploads/<path:filename>')
def serve_image(filename):
    return send_from_directory('static/uploads', filename)

# Create tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)