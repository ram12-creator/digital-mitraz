// Notifications System JavaScript

class NotificationSystem {
    constructor() {
        this.notificationContainer = null;
        this.init();
    }

    init() {
        // Create notification container if it doesn't exist
        if (!document.getElementById('notification-container')) {
            this.notificationContainer = document.createElement('div');
            this.notificationContainer.id = 'notification-container';
            this.notificationContainer.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 1060;
                max-width: 350px;
            `;
            document.body.appendChild(this.notificationContainer);
        } else {
            this.notificationContainer = document.getElementById('notification-container');
        }

        // Listen for custom notification events
        document.addEventListener('showNotification', (e) => {
            this.show(e.detail.message, e.detail.type, e.detail.duration);
        });
    }

    show(message, type = 'info', duration = 5000) {
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show notification`;
        notification.style.cssText = `
            box-shadow: 0 0.15rem 1.75rem 0 rgba(58, 59, 69, 0.15);
            margin-bottom: 1rem;
            animation: slideInRight 0.3s ease;
        `;

        notification.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="${this.getIcon(type)} me-2"></i>
                <div class="flex-grow-1">${message}</div>
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;

        this.notificationContainer.appendChild(notification);

        // Auto dismiss after duration
        if (duration > 0) {
            setTimeout(() => {
                this.remove(notification);
            }, duration);
        }

        return notification;
    }

    remove(notification) {
        if (notification && notification.parentNode) {
            notification.style.animation = 'slideOutRight 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }

    clearAll() {
        while (this.notificationContainer.firstChild) {
            this.notificationContainer.removeChild(this.notificationContainer.firstChild);
        }
    }

    getIcon(type) {
        const icons = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle',
            'primary': 'fas fa-bell',
            'secondary': 'fas fa-bell',
            'dark': 'fas fa-bell'
        };
        return icons[type] || 'fas fa-bell';
    }

    // Toast notification
    toast(message, type = 'info', duration = 3000) {
        const toast = this.show(message, type, duration);
        toast.style.minWidth = '200px';
        toast.style.textAlign = 'center';
        return toast;
    }

    // Success notification
    success(message, duration = 5000) {
        return this.show(message, 'success', duration);
    }

    // Error notification
    error(message, duration = 0) { // 0 means no auto-dismiss
        return this.show(message, 'danger', duration);
    }

    // Warning notification
    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }

    // Info notification
    info(message, duration = 3000) {
        return this.show(message, 'info', duration);
    }

    // Loading notification
    loading(message = 'Loading...') {
        const notification = this.show(message, 'info', 0);
        notification.querySelector('.btn-close').style.display = 'none';
        notification.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="spinner-border spinner-border-sm me-2" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <div class="flex-grow-1">${message}</div>
            </div>
        `;
        return notification;
    }

    // Update loading notification
    updateLoading(notification, message, type = 'success') {
        if (notification && notification.parentNode) {
            notification.className = `alert alert-${type} alert-dismissible fade show notification`;
            notification.innerHTML = `
                <div class="d-flex align-items-center">
                    <i class="${this.getIcon(type)} me-2"></i>
                    <div class="flex-grow-1">${message}</div>
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            `;
            
            // Auto dismiss after 3 seconds
            setTimeout(() => {
                this.remove(notification);
            }, 3000);
        }
    }

    // Confirm dialog
    confirm(message, confirmText = 'Confirm', cancelText = 'Cancel') {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Confirmation</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelText}</button>
                            <button type="button" class="btn btn-primary" id="confirm-btn">${confirmText}</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();

            modal.querySelector('#confirm-btn').addEventListener('click', () => {
                bsModal.hide();
                resolve(true);
            });

            modal.addEventListener('hidden.bs.modal', () => {
                document.body.removeChild(modal);
                resolve(false);
            });
        });
    }

    // Prompt dialog
    prompt(message, defaultValue = '') {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Prompt</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                            <input type="text" class="form-control" id="prompt-input" value="${defaultValue}">
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="prompt-confirm">OK</button>
                        </div>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();

            const input = modal.querySelector('#prompt-input');
            input.focus();

            modal.querySelector('#prompt-confirm').addEventListener('click', () => {
                bsModal.hide();
                resolve(input.value);
            });

            modal.addEventListener('hidden.bs.modal', () => {
                document.body.removeChild(modal);
                resolve(null);
            });

            // Enter key support
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    modal.querySelector('#prompt-confirm').click();
                }
            });
        });
    }
}

// Initialize notification system
const notifications = new NotificationSystem();

// Global notification functions
window.showNotification = function(message, type = 'info', duration = 5000) {
    return notifications.show(message, type, duration);
};

window.showSuccess = function(message, duration = 5000) {
    return notifications.success(message, duration);
};

window.showError = function(message, duration = 0) {
    return notifications.error(message, duration);
};

window.showWarning = function(message, duration = 5000) {
    return notifications.warning(message, duration);
};

window.showInfo = function(message, duration = 3000) {
    return notifications.info(message, duration);
};

window.showLoading = function(message = 'Loading...') {
    return notifications.loading(message);
};

window.updateLoading = function(notification, message, type = 'success') {
    return notifications.updateLoading(notification, message, type);
};

window.showConfirm = function(message, confirmText = 'Confirm', cancelText = 'Cancel') {
    return notifications.confirm(message, confirmText, cancelText);
};

window.showPrompt = function(message, defaultValue = '') {
    return notifications.prompt(message, defaultValue);
};

// Custom event for notifications
window.dispatchNotification = function(message, type = 'info', duration = 5000) {
    document.dispatchEvent(new CustomEvent('showNotification', {
        detail: { message, type, duration }
    }));
};

// AJAX error handling with notifications
$(document).ajaxError(function(event, jqxhr, settings, thrownError) {
    let message = 'An error occurred';
    
    if (jqxhr.status === 0) {
        message = 'Network error. Please check your connection.';
    } else if (jqxhr.status === 401) {
        message = 'Session expired. Please login again.';
        setTimeout(() => {
            window.location.href = '/auth/login';
        }, 2000);
    } else if (jqxhr.status === 403) {
        message = 'Access denied.';
    } else if (jqxhr.status === 404) {
        message = 'Requested resource not found.';
    } else if (jqxhr.status === 500) {
        message = 'Server error. Please try again later.';
    } else {
        try {
            const response = JSON.parse(jqxhr.responseText);
            message = response.message || message;
        } catch (e) {
            message = `Error: ${jqxhr.status} ${thrownError}`;
        }
    }
    
    showError(message);
});

// Success handler for AJAX requests
$(document).ajaxSuccess(function(event, xhr, settings, data) {
    if (data && data.message && settings.type !== 'GET') {
        showSuccess(data.message);
    }
});

// Add CSS animations for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOutRight {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
    
    .notification {
        animation: slideInRight 0.3s ease;
    }
    
    .notification.fade {
        animation: slideOutRight 0.3s ease;
    }
`;
document.head.appendChild(style);

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NotificationSystem;
}