

// Main JavaScript for Training Management System
// This file contains global scripts for UI enhancements, form handling, and reusable utilities.

document.addEventListener('DOMContentLoaded', function() {
    
    // ===============================================================
    // INITIALIZERS (Bootstrap Components)
    // ===============================================================

    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert.alert-dismissible');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // ===============================================================
    // UI ENHANCEMENTS & EVENT HANDLERS
    // ===============================================================

    // Generic form validation for Bootstrap's built-in validation
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Password visibility toggle
    const passwordToggles = document.querySelectorAll('.password-toggle');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const passwordInput = this.previousElementSibling;
            const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
            passwordInput.setAttribute('type', type);
            this.classList.toggle('fa-eye');
            this.classList.toggle('fa-eye-slash');
        });
    });

    // Auto-resize textareas
    const autoResizeTextareas = document.querySelectorAll('textarea[data-auto-resize]');
    autoResizeTextareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
        textarea.dispatchEvent(new Event('input')); // Initial resize
    });

    // CORRECTED: Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            // This check prevents errors on simple "#" links used by Bootstrap components
            if (href && href.length > 1) {
                try {
                    const target = document.querySelector(href);
                    if (target) {
                        e.preventDefault(); // Only prevent default if we find a valid target
                        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                } catch (error) {
                    console.error("Smooth scroll failed: Invalid selector", href);
                }
            }
        });
    });

    // Lazy loading for images
    if ('IntersectionObserver' in window) {
        const lazyImages = document.querySelectorAll('img[data-src]');
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    img.src = img.dataset.src;
                    img.removeAttribute('data-src');
                    imageObserver.unobserve(img);
                }
            });
        });
        lazyImages.forEach(img => {
            imageObserver.observe(img);
        });
    }
    
    // Add debounced search functionality
    const searchInputs = document.querySelectorAll('input[data-debounce-search]');
    searchInputs.forEach(input => {
        const debounceTime = input.dataset.debounceTime || 300;
        input.addEventListener('input', debounce(function() {
            if (typeof window.filterTable === 'function') {
                window.filterTable(this.value);
            }
        }, debounceTime));
    });

    // Session timeout warning
    const sessionWarningModalEl = document.getElementById('sessionWarningModal');
    if (sessionWarningModalEl) {
        let inactivityTime = function() {
            let time;
            const sessionWarningModal = new bootstrap.Modal(sessionWarningModalEl);
            
            function showWarning() {
                sessionWarningModal.show();
            }
            function resetTimer() {
                clearTimeout(time);
                time = setTimeout(showWarning, 29 * 60 * 1000); // 29 minutes
            }
            window.onload = resetTimer;
            document.onmousemove = resetTimer;
            document.onkeypress = resetTimer;
        };
        inactivityTime();
    }
    
    // ===============================================================
    // CHANGE PASSWORD MODAL LOGIC
    // ===============================================================
    const passwordForm = document.getElementById('changePasswordForm');
    if (passwordForm) {
        const submitButton = document.getElementById('submitPasswordChange');
        const alertPlaceholder = document.getElementById('passwordAlertPlaceholder');
        const changePasswordModalEl = document.getElementById('changePasswordModal');
        const changePasswordModal = bootstrap.Modal.getOrCreateInstance(changePasswordModalEl);

        const showPasswordAlert = (message, type) => {
            alertPlaceholder.innerHTML = `<div class="alert alert-${type} alert-dismissible fade show" role="alert">${message}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button></div>`;
        };

        changePasswordModalEl.addEventListener('hidden.bs.modal', function() {
            alertPlaceholder.innerHTML = '';
            passwordForm.reset();
        });

        passwordForm.addEventListener('submit', function(event) {
            event.preventDefault();
            const currentPassword = document.getElementById('currentPassword').value;
            const newPassword = document.getElementById('newPassword').value;
            const confirmPassword = document.getElementById('confirmPassword').value;
            const originalButtonText = submitButton.innerHTML;
            
            alertPlaceholder.innerHTML = '';

            if (!currentPassword || !newPassword || !confirmPassword) {
                showPasswordAlert('All fields are required.', 'danger');
                return;
            }
            if (newPassword !== confirmPassword) {
                showPasswordAlert('New passwords do not match.', 'danger');
                return;
            }
            
            submitButton.innerHTML = `<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Changing...`;
            submitButton.disabled = true;

            fetch('/change_password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                    confirm_password: confirmPassword
                })
            })
            .then(async response => {
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.message || `HTTP error! Status: ${response.status}`);
                }
                return data;
            })
            .then(data => {
                showPasswordAlert(data.message, 'success');
                setTimeout(() => {
                    changePasswordModal.hide();
                }, 2000);
            })
            .catch(error => {
                showPasswordAlert(error.message, 'danger');
            })
            .finally(() => {
                submitButton.innerHTML = originalButtonText;
                submitButton.disabled = false;
            });
        });
    }

    // ===============================================================
    // GLOBAL CONFIGURATIONS & ERROR HANDLING
    // ===============================================================

    // DataTable default configuration
    if (window.jQuery && $.fn.DataTable) {
        $.extend(true, $.fn.dataTable.defaults, {
            language: {
                search: "_INPUT_",
                searchPlaceholder: "Search...",
                lengthMenu: "_MENU_ per page",
                info: "Showing _START_ to _END_ of _TOTAL_",
                infoEmpty: "Showing 0 of 0",
                infoFiltered: "(filtered from _MAX_ total)",
                paginate: { first: "First", last: "Last", next: "Next", previous: "Previous" }
            },
            responsive: true,
            stateSave: false, // Set to false to avoid caching issues during development
            autoWidth: false,
            pageLength: 10,
            lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "All"]]
        });
    }

    // AJAX error handling for jQuery
    if (window.jQuery) {
        $(document).ajaxError(function(event, jqxhr, settings, thrownError) {
            if (jqxhr.status === 401) {
                showNotification('Session expired. Please login again.', 'danger');
                setTimeout(() => { window.location.href = '/login'; }, 2000);
            } else if (jqxhr.status === 403) {
                showNotification('Access denied.', 'danger');
            } else if (jqxhr.status === 500) {
                showNotification('Server error. Please try again later.', 'danger');
            }
        });
    }

    // Improved Global error handler
    window.addEventListener('error', function(e) {
        console.error('A global error occurred:', e.message, 'in', e.filename, 'at line', e.lineno);
    });

    // Modern Performance monitoring
    if ('performance' in window && performance.getEntriesByType) {
        window.addEventListener('load', function() {
            const perfEntries = performance.getEntriesByType("navigation");
            if (perfEntries.length > 0) {
                const p = perfEntries[0];
                const loadTime = p.loadEventEnd - p.startTime;
                console.log('Page load time:', Math.round(loadTime) + 'ms');
                if (loadTime > 3000) {
                    console.warn('Page load time is slow');
                }
            }
        });
    }

    // Fix for the aria-hidden focus warning on all modals
    const modals = document.querySelectorAll('.modal');
    modals.forEach(modal => {
        modal.addEventListener('hidden.bs.modal', function (event) {
            try {
                const trigger = event.relatedTarget;
                if (trigger) {
                    trigger.blur();
                }
            } catch (error) {
                // Failsafe to prevent crash if relatedTarget is not available
            }
        });
    });

}); // End of DOMContentLoaded


// ===============================================================
// GLOBAL UTILITY FUNCTIONS (Available on the window object)
// ===============================================================

// Debounce function for rate-limiting function calls
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Notification system
window.showNotification = function(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show`;
    notification.innerHTML = `${message}<button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '1060';
    notification.style.minWidth = '300px';
    document.body.appendChild(notification);
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(notification);
        bsAlert.close();
    }, 5000);
};

// Print functionality
window.printPage = function() {
    window.print();
};

// Export functionality
window.exportData = function(format, tableId) {
    const table = document.getElementById(tableId || 'dataTable');
    if (!table) {
        console.error("Export failed: Table not found.");
        return;
    }
    let data;
    
    switch (format) {
        case 'csv':
            data = tableToCSV(table);
            downloadFile(data, 'export.csv', 'text/csv;charset=utf-8;');
            break;
        case 'excel':
            data = tableToExcel(table);
            downloadFile(data, 'export.xls', 'application/vnd.ms-excel');
            break;
        case 'pdf':
            showNotification('PDF export requires additional libraries and is not implemented.', 'info');
            break;
    }
};

function tableToCSV(table) {
    const rows = table.querySelectorAll('tr');
    return Array.from(rows).map(row => {
        const cells = row.querySelectorAll('th, td');
        return Array.from(cells).map(cell => {
            let cellText = cell.textContent.trim();
            cellText = cellText.replace(/"/g, '""'); // Escape double quotes
            if (cellText.search(/("|,|\n)/g) >= 0) {
                cellText = `"${cellText}"`; // Enclose in quotes if it contains comma, newline, or quotes
            }
            return cellText;
        }).join(',');
    }).join('\n');
}

function tableToExcel(table) {
    return `
        <html xmlns:o="urn:schemas-microsoft-com:office:office" 
              xmlns:x="urn:schemas-microsoft-com:office:excel" 
              xmlns="http://www.w3.org/TR/REC-html40">
        <head>
            <meta charset="UTF-8">
            <!--[if gte mso 9]>
            <xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet>
            <x:Name>Sheet1</x:Name><x:WorksheetOptions><x:DisplayGridlines/></x:WorksheetOptions>
            </x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml>
            <![endif]-->
            <style>td { mso-number-format:\\@; }</style>
        </head>
        <body>${table.outerHTML}</body>
        </html>
    `;
}

function downloadFile(data, filename, type) {
    const BOM = "\uFEFF"; // Byte Order Mark for Excel UTF-8 compatibility
    const file = new Blob([BOM + data], { type: type });
    const a = document.createElement('a');
    const url = URL.createObjectURL(file);
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }, 0);
}

// Theme switcher
window.toggleTheme = function() {
    const currentTheme = document.documentElement.getAttribute('data-bs-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-bs-theme', newTheme);
    localStorage.setItem('theme', newTheme);
};

// Formatting and validation utilities
window.formatDate = function(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
};

window.isValidEmail = function(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(String(email).toLowerCase());
};

window.isValidPhone = function(phone) {
    const re = /^[+]?[0-9]{10,15}$/;
    return re.test(String(phone));
};
























