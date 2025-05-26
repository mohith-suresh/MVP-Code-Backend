from django.urls import path
from . import views

urlpatterns = [
    path('gptStream', views.gptStream),
    path('getTeachingMethods', views.teachingMethods),
    path('getTests', views.generateTests),

    path('getFeedback', views.get_feedback, name='get_feedback')
]