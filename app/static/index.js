const API_BASE_URL = "{{ ngrok_url }}";
let selectedPlan = null;
let currentUser = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('authToken');
    if (token) handleAuthenticatedUser(token);
    else handleUnauthenticatedUser();
});

// Handle authenticated users
function handleAuthenticatedUser(token) {
    const decodedToken = decodeJwt(token);

    if (!decodedToken || isTokenExpired(decodedToken)) {
        localStorage.removeItem('authToken');
        redirectTo('/user/otp-verification');
        return;
    }

    currentUser = decodedToken;
    checkUserSubscription(decodedToken.user_id);
}

// Handle unauthenticated users
function handleUnauthenticatedUser() {
    const path = window.location.pathname;
    if (path === "/") initRegisterPage();
    else if (path === "/user/otp-verification") initOTPPage();
    else redirectTo('/');
}

// Decode JWT token
function decodeJwt(token) {
    try {
        const payload = atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'));
        return JSON.parse(payload);
    } catch (error) {
        console.error("Invalid JWT token:", error);
        return null;
    }
}

// Check if the token is expired
function isTokenExpired(decodedToken) {
    const currentTime = Math.floor(Date.now() / 1000);
    return decodedToken.exp < currentTime;
}

// Redirect to a specified path
function redirectTo(path) {
    window.location.href = path;
}

// Check subscription status
async function checkUserSubscription(userId) {
    try {
        const response = await axios.get(`${API_BASE_URL}/subscription/subscription-status`, {
            params: { user_id: userId },
            headers: { Authorization: `Bearer ${localStorage.getItem('authToken')}` },
        });

        if (response.data.subscription_active) showSessionCountdown(response.data.time_left);
        else redirectTo('/subscription/subscription-success');
    } catch (error) {
        console.error("Error checking subscription:", error);
        showError("Failed to verify subscription. Please try again.");
    }
}

// Initialize the registration page
function initRegisterPage() {
    const form = document.querySelector('form');
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const phone = document.getElementById('phone').value;
        const macAddress = await getMacAddress();

        try {
            const response = await axios.post(`${API_BASE_URL}/user/register`, { phone_number: phone, mac_address: macAddress });
            localStorage.setItem('phone_number', phone);
            redirectTo('/user/otp-verification');
        } catch (error) {
            console.error("Registration failed:", error);
            showError("Registration failed. Please try again.");
        }
    });
}

// Fetch MAC address from the backend
async function getMacAddress() {
    try {
        const response = await axios.get(`${API_BASE_URL}/mac_address/mac-address`);
        return response.data.mac_address || "00:00:00:00:00:00";
    } catch (error) {
        console.error("Failed to retrieve MAC address:", error);
        return "00:00:00:00:00:00";
    }
}

// Utility for error messages
function showError(message) {
    console.error(message);
    alert(message); // Simple error alert for now
}

// Utility for success messages
function showSuccess(message) {
    console.log(message);
    alert(message); // Simple success alert for now
}

// Session countdown timer
function showSessionCountdown(timeLeft) {
    const countdownContainer = document.createElement('div');
    countdownContainer.className = 'countdown-container';
    document.body.innerHTML = '';
    document.body.appendChild(countdownContainer);

    const timerText = document.createElement('p');
    countdownContainer.appendChild(timerText);

    const interval = setInterval(() => {
        if (timeLeft <= 0) {
            clearInterval(interval);
            showError("Session expired.");
        } else {
            const hours = Math.floor(timeLeft / 3600);
            const minutes = Math.floor((timeLeft % 3600) / 60);
            const seconds = timeLeft % 60;
            timerText.textContent = `Time left: ${hours}h ${minutes}m ${seconds}s`;
            timeLeft--;
        }
    }, 1000);
}
