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
        toggle.textContent = 'Show';
        toggle.setAttribute('aria-label', 'Show password');

        toggle.addEventListener('click', () => {
            const shouldShow = input.type === 'password';
            input.type = shouldShow ? 'text' : 'password';
            toggle.textContent = shouldShow ? 'Hide' : 'Show';
            toggle.setAttribute('aria-label', shouldShow ? 'Hide password' : 'Show password');
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


