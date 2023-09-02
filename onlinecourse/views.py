from django.shortcuts import render
from django.http import HttpResponseRedirect
# <HINT> Import any new Models here
from .models import Course, Enrollment, Question, Choice, Submission
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views import generic
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth import login, logout, authenticate
from django.http import HttpResponseBadRequest
import logging
# Get an instance of a logger
logger = logging.getLogger(__name__)
# Create your views here.


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(request, 'onlinecourse/user_registration_bootstrap.html', context)
    elif request.method == 'POST':
        # Check if user exists
        username = request.POST['username']
        password = request.POST['psw']
        first_name = request.POST['firstname']
        last_name = request.POST['lastname']
        user_exist = False
        try:
            User.objects.get(username=username)
            user_exist = True
        except:
            logger.error("New user")
        if not user_exist:
            user = User.objects.create_user(username=username, first_name=first_name, last_name=last_name,
                                            password=password)
            login(request, user)
            return redirect("onlinecourse:index")
        else:
            context['message'] = "User already exists."
            return render(request, 'onlinecourse/user_registration_bootstrap.html', context)


def login_request(request):
    context = {}
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['psw']
        user = authenticate(username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        else:
            context['message'] = "Invalid username or password."
            return render(request, 'onlinecourse/user_login_bootstrap.html', context)
    else:
        return render(request, 'onlinecourse/user_login_bootstrap.html', context)


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    is_enrolled = False
    if user.id is not None:
        # Check if user enrolled
        num_results = Enrollment.objects.filter(user=user, course=course).count()
        if num_results > 0:
            is_enrolled = True
    return is_enrolled


# CourseListView
class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        user = self.request.user
        courses = Course.objects.order_by('-total_enrollment')[:10]
        for course in courses:
            if user.is_authenticated:
                course.is_enrolled = check_if_enrolled(user, course)
        return courses


class CourseDetailView(generic.DetailView):
    model = Course
    template_name = 'onlinecourse/course_detail_bootstrap.html'


def enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    user = request.user

    is_enrolled = check_if_enrolled(user, course)
    if not is_enrolled and user.is_authenticated:
        # Create an enrollment
        Enrollment.objects.create(user=user, course=course, mode='honor')
        course.total_enrollment += 1
        course.save()

    return HttpResponseRedirect(reverse(viewname='onlinecourse:course_details', args=(course.id,)))

def calculate_total_score(question_results):
    # Calculate the total score by summing the grades from question results
    total_score = sum(result['grade'] for result in question_results)
    return total_score

# <HINT> Create a submit view to create an exam submission record for a course enrollment,
# you may implement it based on following logic:
         # Get user and course object, then get the associated enrollment object created when the user enrolled the course
         # Create a submission object referring to the enrollment
         # Collect the selected choices from exam form
         # Add each selected choice object to the submission object
         # Redirect to show_exam_result with the submission id
@csrf_protect
def submit(request, course_id):
    if request.method == 'POST':
        # Getting user and course object
        user = request.user
        course = get_object_or_404(Course, pk=course_id)

        # Getting the associated enrollment object created when the user enrolled in the course
        enrollment = get_object_or_404(Enrollment, user=user, course=course)

        # Creating a submission object referring to the enrollment
        submission = Submission.objects.create(enrollment=enrollment)

        # Collecting the selected choices from the exam form
        selected_choices = extract_answers(request)

        # Adding each selected choice object to the submission object
        for choice_id in selected_choices:
            choice = get_object_or_404(Choice, id=choice_id)
            submission.choices.add(choice)

        # Redirecting to show_exam_result with the submission id
        return redirect('onlinecourse:show_exam_result', course_id=course_id, submission_id=submission.id)
    else:
        # If the request method is not POST, return a 400 Bad Request response
        return HttpResponseBadRequest("Invalid request method")


# <HINT> A example method to collect the selected choices from the exam form from the request object
def extract_answers(request):
    submitted_answers = []
    for key, value in request.POST.items():
        if key.startswith('choice'):
            choice_id = int(value)
            submitted_answers.append(choice_id)
    return submitted_answers


# <HINT> Create an exam result view to check if learner passed exam and show their question results and result for each question,
# you may implement it based on the following logic:
        # Get course and submission based on their ids
        # Get the selected choice ids from the submission record
        # For each selected choice, check if it is a correct answer or not
        # Calculate the total score
def show_exam_result(request, course_id, submission_id):
    # Get the course object and submission object based on their IDs
    course = get_object_or_404(Course, pk=course_id)
    submission = get_object_or_404(Submission, pk=submission_id)

    # Get the selected choice IDs from the submission record
    selected_choice_ids = submission.choices.values_list('id', flat=True)

    # Initialize variables for total score and question results
    total_score = 0
    question_results = []

    # Loop through all questions in the course
    for question in course.question_set.all():
        # Get the correct choice IDs for the question
        correct_choice_ids = question.choice_set.filter(is_correct=True).values_list('id', flat=True)

        # Check if the user's selected choice IDs are a subset of the correct choice IDs
        is_correct = set(selected_choice_ids).issubset(set(correct_choice_ids))

        # Calculate the question's grade
        question_grade = question.grade if is_correct else 0

        # Add the question result to the list
        question_results.append({
            'question_text': question.question_text,
            'is_correct': is_correct,
            'grade': question_grade,
        })

        # Add the question's grade to the total score
        total_score += question_grade

    # Determine if the learner passed the exam based on your passing criteria
    # You can implement this logic based on the total score and passing threshold
    passing_threshold = 80.00  # Score
    passed_exam = total_score >= passing_threshold

    # Calculate the total score using the added method
    total_score = calculate_total_score(question_results)

    # Add the course, selected choice IDs, total score, and question results to the context
    context = {
        'course': course,
        'selected_ids': selected_choice_ids,
        'total_score': total_score,
        'question_results': question_results,
        'passed_exam': passed_exam,
    }

    # Render the HTML page to display exam results
    return render(request, 'onlinecourse/exam_result_bootstrap.html', context)

