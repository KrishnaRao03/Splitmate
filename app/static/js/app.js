// ========================================
// Modal Functions
// ========================================
function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
    document.body.style.overflow = '';
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
        document.body.style.overflow = '';
    }
});

// Close modal with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.body.style.overflow = '';
    }
});

// ========================================
// Flash Message Auto-dismiss
// ========================================
document.querySelectorAll('.flash-message').forEach(msg => {
    setTimeout(() => {
        msg.style.opacity = '0';
        msg.style.transform = 'translateY(-10px)';
        setTimeout(() => msg.remove(), 300);
    }, 5000);
});

// ========================================
// Mobile Sidebar Toggle
// ========================================
function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('open');
}

// ========================================
// Form Validation Helpers
// ========================================
function validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function validatePassword(password) {
    return password.length >= 6;
}

// ========================================
// Number Formatting
// ========================================
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD'
    }).format(amount);
}

// ========================================
// Date Formatting
// ========================================
function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

function formatDateTime(dateString) {
    return new Date(dateString).toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// ========================================
// Initialize
// ========================================
document.addEventListener('DOMContentLoaded', () => {
    const passwordIcons = {
        eye: `
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"></path>
                <circle cx="12" cy="12" r="3"></circle>
            </svg>
        `,
        eyeOff: `
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                <path d="M3 3l18 18"></path>
                <path d="M10.6 10.6A2 2 0 0 0 13.4 13.4"></path>
                <path d="M9.9 4.2A10.6 10.6 0 0 1 12 4c6.5 0 10 8 10 8a17.8 17.8 0 0 1-3.2 4.3"></path>
                <path d="M6.6 6.6C3.6 8.7 2 12 2 12s3.5 8 10 8a10.5 10.5 0 0 0 5.4-1.5"></path>
            </svg>
        `
    };

    function setPasswordToggleIcon(toggle, isVisible) {
        toggle.innerHTML = isVisible ? passwordIcons.eyeOff : passwordIcons.eye;
        toggle.setAttribute('aria-label', isVisible ? 'Hide password' : 'Show password');
        toggle.setAttribute('title', isVisible ? 'Hide password' : 'Show password');
    }

    document.querySelectorAll('input[type="password"]').forEach(input => {
        if (input.closest('.password-field')) {
            return;
        }

        const wrapper = document.createElement('div');
        wrapper.className = 'password-field';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);

        const toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'password-toggle';
        setPasswordToggleIcon(toggle, false);

        toggle.addEventListener('click', () => {
            const shouldShow = input.type === 'password';
            input.type = shouldShow ? 'text' : 'password';
            setPasswordToggleIcon(toggle, shouldShow);
        });

        wrapper.appendChild(toggle);
    });

    // Set minimum date for datetime inputs to now
    const now = new Date();
    const localDatetime = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16);

    document.querySelectorAll('input[type="datetime-local"]').forEach(input => {
        if (!input.value) {
            input.min = localDatetime;
        }
    });
});


