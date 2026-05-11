// Form Validation JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Custom validation for all forms
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
                e.stopPropagation();
            }
        });
    });

    // Real-time validation for inputs
    const inputs = document.querySelectorAll('input[data-validate], select[data-validate], textarea[data-validate]');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            validateField(this);
        });
        
        input.addEventListener('input', function() {
            clearFieldError(this);
        });
    });

    // Password strength meter
    const passwordInputs = document.querySelectorAll('input[type="password"][data-strength]');
    passwordInputs.forEach(input => {
        input.addEventListener('input', function() {
            checkPasswordStrength(this);
        });
    });

    // Date validation
    const dateInputs = document.querySelectorAll('input[type="date"][data-validation]');
    dateInputs.forEach(input => {
        input.addEventListener('change', function() {
            validateDate(this);
        });
    });

    // File validation
    const fileInputs = document.querySelectorAll('input[type="file"][data-validation]');
    fileInputs.forEach(input => {
        input.addEventListener('change', function() {
            validateFile(this);
        });
    });


    // Email validation
const emailInputs = document.querySelectorAll('input[type="email"]');
emailInputs.forEach(input => {
    input.addEventListener('blur', function() {
        validateField(this); // <-- Fix: use validateField instead of validateEmail
    });
});

    // Phone number validation
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(input => {
        input.addEventListener('blur', function() {
            validatePhone(this);
        });
    });
});

// Form validation function
function validateForm(form) {
    let isValid = true;
    const inputs = form.querySelectorAll('input, select, textarea');
    
    inputs.forEach(input => {
        if (!validateField(input)) {
            isValid = false;
        }
    });
    
    return isValid;
}

// Field validation function
function validateField(field) {
    const value = field.value.trim();
    const rules = field.dataset.validate ? field.dataset.validate.split(' ') : [];
    
    // Clear previous errors
    clearFieldError(field);
    
    // Required validation
    if (rules.includes('required') && !value) {
        showFieldError(field, 'This field is required');
        return false;
    }
    
    // Email validation
    if (rules.includes('email') && value && !isValidEmail(value)) {
        showFieldError(field, 'Please enter a valid email address');
        return false;
    }
    
    // Phone validation
    if (rules.includes('phone') && value && !isValidPhone(value)) {
        showFieldError(field, 'Please enter a valid phone number');
        return false;
    }
    
    // Min length validation
    if (rules.includes('minlength') && value) {
        const minLength = parseInt(field.dataset.minlength) || 0;
        if (value.length < minLength) {
            showFieldError(field, `Minimum ${minLength} characters required`);
            return false;
        }
    }
    
    // Max length validation
    if (rules.includes('maxlength') && value) {
        const maxLength = parseInt(field.dataset.maxlength) || 255;
        if (value.length > maxLength) {
            showFieldError(field, `Maximum ${maxLength} characters allowed`);
            return false;
        }
    }
    
    // Pattern validation
    if (rules.includes('pattern') && value) {
        const pattern = new RegExp(field.dataset.pattern);
        if (!pattern.test(value)) {
            showFieldError(field, field.dataset.patternMessage || 'Invalid format');
            return false;
        }
    }
    
    // Match validation (for password confirmation)
    if (rules.includes('match') && value) {
        const matchField = document.querySelector(field.dataset.match);
        if (matchField && value !== matchField.value) {
            showFieldError(field, 'Values do not match');
            return false;
        }
    }
    
    // File type validation
    if (field.type === 'file' && value) {
        if (!validateFile(field)) {
            return false;
        }
    }
    
    // Date validation
    if (field.type === 'date' && value) {
        if (!validateDate(field)) {
            return false;
        }
    }
    
    return true;
}

// Show field error
function showFieldError(field, message) {
    field.classList.add('is-invalid');
    
    // Create error message
    const errorDiv = document.createElement('div');
    errorDiv.className = 'invalid-feedback';
    errorDiv.textContent = message;
    
    // Insert after field
    field.parentNode.appendChild(errorDiv);
    
    // Scroll to error
    field.scrollIntoView({ behavior: 'smooth', block: 'center' });
    field.focus();
}

// Clear field error
function clearFieldError(field) {
    field.classList.remove('is-invalid');
    
    // Remove error message
    const errorDiv = field.parentNode.querySelector('.invalid-feedback');
    if (errorDiv) {
        errorDiv.remove();
    }
}

// Email validation
function isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// Phone validation
function isValidPhone(phone) {
    const re = /^[+]?[0-9]{10,15}$/;
    return re.test(phone);
}

// Password strength check
function checkPasswordStrength(passwordField) {
    const password = passwordField.value;
    const strengthMeter = document.getElementById('passwordStrength');
    
    if (!strengthMeter || !password) return;
    
    let strength = 0;
    let messages = [];
    
    // Length check
    if (password.length >= 8) strength++;
    else messages.push('at least 8 characters');
    
    // Uppercase check
    if (/[A-Z]/.test(password)) strength++;
    else messages.push('one uppercase letter');
    
    // Lowercase check
    if (/[a-z]/.test(password)) strength++;
    else messages.push('one lowercase letter');
    
    // Number check
    if (/[0-9]/.test(password)) strength++;
    else messages.push('one number');
    
    // Special character check
    if (/[^A-Za-z0-9]/.test(password)) strength++;
    else messages.push('one special character');
    
    // Update strength meter
    const strengthClasses = ['bg-danger', 'bg-warning', 'bg-info', 'bg-success'];
    const strengthText = ['Very Weak', 'Weak', 'Medium', 'Strong', 'Very Strong'];
    
    strengthMeter.style.width = (strength * 20) + '%';
    strengthMeter.className = 'progress-bar ' + (strengthClasses[strength - 1] || 'bg-danger');
    strengthMeter.textContent = strengthText[strength];
    
    // Update help text
    const helpText = document.getElementById('passwordHelp');
    if (helpText) {
        if (messages.length > 0) {
            helpText.textContent = 'Password must contain: ' + messages.join(', ');
        } else {
            helpText.textContent = 'Password is strong!';
        }
    }
}

// File validation
function validateFile(fileInput) {
    const file = fileInput.files[0];
    if (!file) return true;
    
    const allowedTypes = fileInput.dataset.allowedTypes ? fileInput.dataset.allowedTypes.split(',') : [];
    const maxSize = parseInt(fileInput.dataset.maxSize) || 10 * 1024 * 1024; // 10MB default
    
    // File type validation
    if (allowedTypes.length > 0) {
        const fileExtension = file.name.split('.').pop().toLowerCase();
        const mimeType = file.type;
        
        if (!allowedTypes.includes(fileExtension) && !allowedTypes.includes(mimeType)) {
            showFieldError(fileInput, `File type not allowed. Allowed types: ${allowedTypes.join(', ')}`);
            return false;
        }
    }
    
    // File size validation
    if (file.size > maxSize) {
        showFieldError(fileInput, `File too large. Maximum size: ${formatFileSize(maxSize)}`);
        return false;
    }
    
    return true;
}

// Date validation
function validateDate(dateInput) {
    const value = dateInput.value;
    if (!value) return true;
    
    const date = new Date(value);
    const today = new Date();
    
    // Past date validation
    if (dateInput.dataset.noPast && date < today.setHours(0, 0, 0, 0)) {
        showFieldError(dateInput, 'Date cannot be in the past');
        return false;
    }
    
    // Future date validation
    if (dateInput.dataset.noFuture && date > today) {
        showFieldError(dateInput, 'Date cannot be in the future');
        return false;
    }
    
    // Date range validation
    if (dateInput.dataset.minDate) {
        const minDate = new Date(dateInput.dataset.minDate);
        if (date < minDate) {
            showFieldError(dateInput, `Date must be after ${minDate.toLocaleDateString()}`);
            return false;
        }
    }
    
    if (dateInput.dataset.maxDate) {
        const maxDate = new Date(dateInput.dataset.maxDate);
        if (date > maxDate) {
            showFieldError(dateInput, `Date must be before ${maxDate.toLocaleDateString()}`);
            return false;
        }
    }
    
    return true;
}

// Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Bulk form validation
function validateBulkForm(formId, fields) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    let isValid = true;
    fields.forEach(fieldName => {
        const field = form.querySelector(`[name="${fieldName}"]`);
        if (field && !validateField(field)) {
            isValid = false;
        }
    });
    
    return isValid;
}

// Reset form validation
function resetFormValidation(form) {
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        clearFieldError(input);
        input.classList.remove('is-valid');
    });
}

// Export validation functions for global use
window.validateForm = validateForm;
window.validateField = validateField;
window.showFieldError = showFieldError;
window.clearFieldError = clearFieldError;
window.isValidEmail = isValidEmail;
window.isValidPhone = isValidPhone;
window.validateFile = validateFile;
window.validateDate = validateDate;