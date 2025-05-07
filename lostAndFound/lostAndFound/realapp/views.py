# views.py in your Django app
import requests
import os
from django.shortcuts import render, redirect , get_object_or_404
from django.contrib.auth import login as django_login
from django.contrib.auth.models import User
from django.conf import settings
from django.http import HttpResponse
from django.contrib import messages
from werkzeug.utils import secure_filename

from django.conf import settings


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'}

# Function to check if file is allowed
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

FLASK_API_BASE = "http://localhost:5000"  # Update with your actual Flask API base URL

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # Send request to Flask API for login
        response = requests.post(f"{FLASK_API_BASE}/api/login", json={"username": username, "password": password})
        
        if response.status_code == 200:
            data = response.json()
            access_token = data["access_token"]
            role = data["role"]

            # Optionally, save the token in session or cookies for frontend use
            request.session['access_token'] = access_token
            request.session['role'] = role

            # Create or update Django user if necessary
            user, created = User.objects.get_or_create(username=username)
            django_login(request, user)

            messages.success(request, "Login successful!")
            return redirect("home")  # Redirect to home or dashboard
        else:
            messages.error(request, "Invalid username or password.")
            return redirect("login")  # Stay on the login page

    return render(request, "login.html")


def register_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Send request to Flask API for registration
        response = requests.post(f"{FLASK_API_BASE}/api/register", json={
            "username": username,
            "email": email,
            "password": password
        })

        if response.status_code == 201:
            messages.success(request, "User registered successfully!")
            return redirect("login")  # Redirect to login page after successful registration
        elif response.status_code == 409:
            messages.error(request, "Username or email already exists.")
            return redirect("register")  # Stay on the register page if there's a conflict
        else:
            messages.error(request, "Something went wrong. Please try again.")
            return redirect("register")  # Stay on the register page if there's an unknown error

    return render(request, "register.html")


def all_complaints_view(request):
    access_token = request.session.get('access_token')
    
    if not access_token:
        messages.error(request, "You need to be logged in to view complaints.")
        return redirect('login')  # Redirect to login page if not logged in

    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(f"{FLASK_API_BASE}/all-complaints", headers=headers)  # Flask endpoint
        response.raise_for_status()
        complaints = response.json()
    except requests.exceptions.RequestException as e:
        complaints = []
        messages.error(request, f"Error fetching complaints: {e}")

    return render(request, "complaints.html", {"complaints": complaints})







# Add Complaint
def add_complaint_view(request):
    if request.method == "POST":
        # Check if the file exists in the request
        complaint_file = request.FILES.get('complaint_file')
        
        # Check if user is logged in
        access_token = request.session.get('access_token')
        if not access_token:
            messages.error(request, "You need to be logged in to add a complaint.")
            return redirect("login")  # Redirect to login page if not logged in

        # Get other form data
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")
        location = request.form.get("location")

        
        # Handle the file upload if a file is provided
        image_filename = ""
        if complaint_file and allowed_file(complaint_file.name):
            image_filename = secure_filename(complaint_file.name)
            # Ensure the 'uploads' directory exists
            upload_path = os.path.join(settings.MEDIA_ROOT, 'uploads')
            if not os.path.exists(upload_path):
                os.makedirs(upload_path)

            file_path = os.path.join(upload_path, image_filename)
            with open(file_path, 'wb') as f:
                for chunk in complaint_file.chunks():
                    f.write(chunk)

        # Prepare the data for the API request
        data = {
            "title": title,
            "description": description,
            "category": category,
            "location": location,
            "image_filename": image_filename
        }

        # Send the request to the Flask API to add the complaint
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.post(f"{FLASK_API_BASE}/add-complaint", json=data, headers=headers)

        if response.status_code == 201:
            messages.success(request, "Complaint added successfully!")
            return redirect("home")  # Redirect to all complaints view
        else:
            messages.error(request, "Error adding complaint.")
            return redirect("add_complaint")  # Stay on the add complaint page

    return render(request, "add_complaint.html")


# Delete Complaint
def delete_complaint_view(request, complaint_id):
    access_token = request.session.get('access_token')
    if not access_token:
        messages.error(request, "You need to be logged in to delete a complaint.")
        return redirect("login")  # Redirect to login page if not logged in

    # Send the request to the Flask API to delete the complaint
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.delete(f"{FLASK_API_BASE}/delete-complaint/{complaint_id}", headers=headers)

    if response.status_code == 200:
        messages.success(request, "Complaint deleted successfully!")
    else:
        messages.error(request, "Error deleting complaint.")

    return redirect("home")  # Redirect to all complaints view


def update_complaint_view(request, complaint_id):  # ✅ Correct argument name
    api_url = f"http://127.0.0.1:5000/api/complaints/{complaint_id}"  # Flask API route

    if request.method == "GET":
        response = requests.get(api_url)
        if response.status_code == 200:
            complaint = response.json()
            return render(request, "update_complaint.html", {"complaint": complaint})
        else:
            return HttpResponse("Complaint not found", status=404)

    elif request.method == "POST":
        payload = {
            "title": request.POST.get("title"),
            "description": request.POST.get("description"),
            "category": request.POST.get("category"),
            "location": request.POST.get("location"),
            "status": request.POST.get("status"),
            "image_filename": request.POST.get("image_filename")
        }

        token = request.session.get("jwt_token")  # assumes token is stored in session
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        response = requests.put(api_url, json=payload, headers=headers)
        if response.status_code == 200:
            return redirect("complaint_list")  # make sure this name matches your URL name
        else:
            return HttpResponse("Update failed", status=response.status_code)


def view_complaint_view(request, complaint_id):
    access_token = request.session.get('access_token')
    
    if not access_token:
        messages.error(request, "You need to be logged in to view complaint details.")
        return redirect("login")

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        response = requests.get(f"{FLASK_API_BASE}/complaint/{complaint_id}", headers=headers)
    except requests.exceptions.RequestException:
        messages.error(request, "Could not connect to the complaint service.")
        return redirect("home")

    if response.status_code == 200:
        data = response.json()
        complaint = {
            "id": data.get("id"),
            "title": data.get("title"),
            "description": data.get("description"),
            "category": data.get("category"),
            "location": data.get("location"),
            "status": data.get("status"),
            "username": data.get("username"),
            "date_posted": data.get("date_posted"),
            "image_filename": data.get("image_filename"),
            "views": data.get("views"),
        }
        return render(request, "view_complaint.html", {"complaint": complaint})
    elif response.status_code == 404:
        messages.error(request, "Complaint not found.")
    else:
        messages.error(request, "Failed to retrieve complaint details.")

    return redirect("home")
