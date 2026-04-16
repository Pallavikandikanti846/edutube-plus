from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.login_page, name="home"),
    path("login/", views.login_page, name="login"),
    path("register/", views.register_page, name="register"),
    path("logout/", views.logout_stub, name="logout"),

    path("search/", views.search_page, name="search"),
    path("search/run/", views.search_run_stub, name="search_run"),

    path("course-detail/", views.course_detail_page, name="course_detail"),
    path("video_player/", views.video_player_page, name="video_player"),
    path("clear-videos/", views.clear_videos, name="clear_videos"),

    path("reviews/submit/", views.review_submit_stub, name="review_submit"),
    path("like-video/", views.like_video_toggle, name="like_video"),
    path("mark-progress/", views.mark_progress, name="mark_progress"),

    path("progress/", views.progress_page, name="progress"),
    path("profile/", views.profile_page, name="profile"),

    path("settings/", views.settings_page, name="settings"),
    path("settings/update-name/", views.update_name, name="update_name"),
    path("settings/toggle-history/", views.toggle_history, name="toggle_history"),
    path("settings/delete-account/", views.delete_account, name="delete_account"),
    path("stub/watch_history/", views.watch_history_stub, name="watch_history"),
    path("stub/in_progress/", views.in_progress_stub, name="in_progress"),
]