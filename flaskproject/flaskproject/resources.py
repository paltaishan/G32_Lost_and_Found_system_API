import os
from flask import request, jsonify, current_app
from flask_restful import Resource
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from models import db, User, Item, Complaint
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app


# Define upload folder and allowed extensions
UPLOAD_FOLDER = 'static/uploads/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Check if file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# User Registration
class RegisterResource(Resource):
    def post(self):
        data = request.get_json()
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")

        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            return {"message": "Username or email already exists"}, 409

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password_hash=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return {"message": "User registered successfully"}, 201


# User Login
# User Login
class LoginResource(Resource):
    def post(self):
        data = request.get_json()
        username = data.get("username")
        password = data.get("password")

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return {"message": "Invalid username or password"}, 401

        access_token = create_access_token(identity=str(user.id))

        return {"access_token": access_token, "role": user.role}, 200


# Get All Complaints
class AllComplaintsResource(Resource):
    def get(self):
        items = Item.query.order_by(Item.date_posted.desc()).all()
        result = []
        for item in items:
            # Return full image URL if image exists
            image_url = f"{request.host_url}static/uploads/{item.image_filename}" if item.image_filename else None
            result.append({
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "category": item.category,
                "location": item.location,
                "status": item.status,
                "image_filename": image_url,
                "views": item.views,
                "date_posted": item.date_posted.isoformat(),
                "user_id": item.user_id,
                "username": item.user.username
            })
        return jsonify(result)



class AddComplaintResource(Resource):
    @jwt_required()
    def post(self):
        current_user_id = int(get_jwt_identity())
        data = request.get_json()

        # Check if file is provided in the request
        image_filename = None
        if 'image_filename' in data:
            image_filename = data.get('image_filename')

        item = Item(
            title=data.get("title"),
            description=data.get("description"),
            category=data.get("category"),
            location=data.get("location"),
            status=data.get("status", "lost"),
            image_filename=image_filename,
            date_posted=datetime.utcnow(),
            user_id=current_user_id
        )
        db.session.add(item)
        db.session.commit()

        return {"message": "Complaint added successfully", "item_id": item.id}, 201


# Delete Complaint (Item)
class DeleteComplaintResource(Resource):
    @jwt_required()
    def delete(self, complaint_id):
        current_user_id = int(get_jwt_identity())

        complaint = Item.query.get(complaint_id)
        if not complaint:
            return {"message": "Complaint not found"}, 404

        if complaint.user_id != current_user_id:
            return {"message": "You are not authorized to delete this complaint"}, 403

        # Delete the image file if it exists
        if complaint.image_filename:
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], complaint.image_filename)
            if os.path.exists(image_path):
                os.remove(image_path)

        db.session.delete(complaint)
        db.session.commit()

        return {"message": "Complaint deleted successfully"}, 200




# Update Complaint (Item)
# Update Complaint (Item)
class UpdateComplaintResource(Resource):
    @jwt_required()
    def put(self, complaint_id):
        current_user_id = int(get_jwt_identity())

        complaint = Item.query.get(complaint_id)
        if not complaint:
            return {"message": "Complaint not found"}, 404

        # Check if the current user is the owner of the complaint
        if complaint.user_id != current_user_id:
            return {"message": "You are not authorized to update this complaint"}, 403

        data = request.form  # Form data for title, description, etc.
        file = request.files.get("image")  # Image file if uploaded

        # Update image if a new one is uploaded
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(image_path)
            complaint.image_filename = filename

        # Update other complaint fields from form data (if provided)
        complaint.title = data.get("title", complaint.title)
        complaint.description = data.get("description", complaint.description)
        complaint.category = data.get("category", complaint.category)
        complaint.location = data.get("location", complaint.location)
        complaint.status = data.get("status", complaint.status)

        db.session.commit()

        # Return the full image URL if available
        image_url = f"{request.host_url}static/uploads/{complaint.image_filename}" if complaint.image_filename else None

        return {"message": "Complaint updated successfully", "item_id": complaint.id, "image_url": image_url}, 200




# Get Single Complaint
class SingleComplaintResource(Resource):
    @jwt_required()
    def get(self, complaint_id):
        complaint = Item.query.get(complaint_id)
        if not complaint:
            return {"message": "Complaint not found"}, 404

        image_url = f"{request.host_url}static/uploads/{complaint.image_filename}" if complaint.image_filename else None

        return {
            "id": complaint.id,
            "title": complaint.title,
            "description": complaint.description,
            "category": complaint.category,
            "location": complaint.location,
            "status": complaint.status,
            "image_filename": image_url,
            "views": complaint.views,
            "date_posted": complaint.date_posted.isoformat(),
            "user_id": complaint.user_id,
            "username": complaint.user.username
        }, 200
