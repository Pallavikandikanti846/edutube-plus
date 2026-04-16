# EduTube+ 🎓📺

EduTube+ is a web-based learning platform built using Django. It allows users to search for educational videos, watch them, track their progress, and view reviews. The system integrates frontend UI with backend database following the Model-View-Template (MVT) architecture.

---

## 🚀 Features

- User Registration & Login
- Search Videos / Playlists (YouTube API integration)
- Filter Playlists based on categories
- Watch Videos using embedded player
- Track Video Progress (Continue Watching)
- View Reviews and Ratings

---

## 🛠️ Technologies Used

- Python (Django Framework)
- SQLite (Database)
- HTML, CSS, JavaScript
- YouTube Data API
- Bootstrap (UI styling)

---

## 📂 Project Structure
EduTube+
│── app/
│── templates/
│── static/
│── db.sqlite3
│── manage.py


---


---

## 🔄 Application Flow

Login Page → Search Videos → Video Player → Progress Page → Profile

---

## ⚠️ Exception Handling

- Validates user input (empty fields, wrong credentials)
- Handles API failures and no search results
- Uses try-except blocks in backend
- Displays error messages to users

---

## 🚧 Challenges Faced

One major challenge was integrating YouTube videos into the application.  
Normal YouTube links (watch URLs) were not working inside the player.  

### Solution:
- Converted video URLs to embed format  
- Used `<iframe>` for video playback  
- Validated links before displaying  

---

## 📊 Database Tables

- Users
- Playlists
- Videos
- Video Progress
- Reviews

---

## 📌 Future Improvements

- Add recommendation system  
- Improve UI/UX design  
- Add comments section  
- Implement advanced filtering  

---

## 👨‍💻 Author

Pallavi Kandikanti  

---

## 📜 License

This project is for educational purposes only.

## Access The Site
https://edutube-plus.onrender.com

