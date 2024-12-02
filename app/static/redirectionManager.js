let isRedirectionHandled = false;

// Initialize redirection management
function initRedirectionManager() {
    document.addEventListener('DOMContentLoaded', () => {
        clearRedirectionFlag();
        manageRedirects();
    });
}

// Core function to manage redirects based on user state
function manageRedirects() {
    if (isRedirectionHandled) return;

    const authToken = authenticateUser();
    if (!authToken) {
        handleUnauthenticatedRedirect();
    } else {
        handleAuthenticatedRedirect(authToken);
    }
}

// Handle redirection for unauthenticated users
function handleUnauthenticatedRedirect() {
    const path = window.location.pathname;
    let phone_number = localStorage.getItem('phone_number');
    if (path !== '/' && phone_number == null) {
        redirectTo('/');
    }
}

// Handle redirection for authenticated users based on subscription
function handleAuthenticatedRedirect(token) {
    const decodedToken = decodeJwt(token);
    console.log("Decoded Token: ",decodedToken);
    if (!decodedToken || isTokenExpired(decodedToken)) {
        redirectTo('/user/otp-verification');
    } else if (!getSubscriptionStatus(decodedToken.user_id) && !isRedirectionHandled) {
        redirectTo('/subscription/subscription-plans');
    }
}

// Check and get the subscription status
function getSubscriptionStatus(userId) {
    // Fetch subscription status from the server if needed, else use localStorage
    return localStorage.getItem('subscription_active') === 'true';
}

// Utility to perform redirects
function redirectTo(path) {
    window.location.href = path;
    isRedirectionHandled = true;
}

// Utility to clear any redirection flags
function clearRedirectionFlag() {
    localStorage.removeItem('redirectedOnInactive');
}

// Decode JWT to extract user details
function decodeJwt(token) {
    try {
        if (!token || typeof token !== "string") {
            throw new Error("Invalid token");
        }
        const payload = atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"));
        return JSON.parse(payload);
    } catch (error) {
        console.error("Invalid JWT token:", error);
        return null; // Return null for invalid tokens
    }
}

// Check JWT token expiration
function isTokenExpired(decodedToken) {
    return Math.floor(Date.now() / 1000) > decodedToken.exp;
}

// Simulate authentication by checking for an auth token
function authenticateUser() {
    // Mock authentication logic: retrieve token from local storage
    return localStorage.getItem('authToken');
}

function showError(message) {
    console.error(message);

    // Create a div element for the alert
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-danger alert-dismissible fade show'; // Added Bootstrap classes
    alertDiv.innerHTML = message + '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>'; //Added close button

    // Append to the body (or a more specific container if preferred)
    document.body.appendChild(alertDiv);

    // Remove the alert after a timeout (optional)
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Utility for success messages
function showSuccess(message) {
    console.log(message);

    // Create a div element for the alert
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-success alert-dismissible fade show'; // Added Bootstrap classes
    alertDiv.innerHTML = message + '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>'; //Added close button

    // Append the alert to the body (or a more specific container if preferred)
    document.body.appendChild(alertDiv);

    // Remove the alert after a timeout (optional)
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Initialize the redirection flow
initRedirectionManager();