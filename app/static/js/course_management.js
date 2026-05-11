document.addEventListener('DOMContentLoaded', function() {
    const submitCourseButton = document.getElementById('submitCourse');
    
    if (submitCourseButton) {
        submitCourseButton.addEventListener('click', function(e) {
            e.preventDefault();
            submitCourseForm();
        });
    }
});

function submitCourseForm() {
    // Collect form data
    const courseData = {
        course_name: document.getElementById('course_name').value,
        description: document.getElementById('description').value,
        duration_weeks: document.getElementById('duration_weeks').value,
        max_leaves: document.getElementById('max_leaves').value || 5, // Default value
        start_date: document.getElementById('start_date').value,
        end_date: document.getElementById('end_date').value,
        max_capacity: document.getElementById('max_capacity').value
    };
    
    // For update, include is_active and course_id
    const courseId = document.getElementById('course_id') ? document.getElementById('course_id').value : null;
    if (courseId) {
        courseData.is_active = document.getElementById('is_active').checked;
        courseData.course_id = courseId;
    }
    
    // Validate required fields
    if (!courseData.course_name || !courseData.duration_weeks || 
        !courseData.start_date || !courseData.end_date || !courseData.max_capacity) {
        alert('Please fill all required fields (marked with *)');
        return;
    }
    
    // Validate dates
    if (new Date(courseData.start_date) >= new Date(courseData.end_date)) {
        alert('End date must be after start date');
        return;
    }
    
    // Determine URL
    const url = courseId ? '/update_course/' + courseId : '/create_course';
    
    // Show loading state
    const submitButton = document.getElementById('submitCourse');
    const originalText = submitButton.textContent;
    submitButton.textContent = 'Saving...';
    submitButton.disabled = true;
    
    // Send data using Fetch API
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(courseData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            alert(data.message);
            // Redirect to course management page
            window.location.href = '/courses';
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while saving the course. Please check your input and try again.');
    })
    .finally(() => {
        // Restore button state
        submitButton.textContent = originalText;
        submitButton.disabled = false;
    });
}