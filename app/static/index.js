const API_BASE_URL = 'http://192.168.0.102:8000';
let selectedPlan = null;
let currentUser = null;
let paymentStatusInterval = null;
let countdownInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('authToken');
    const path = window.location.pathname;

    if (token) {
        const decodedToken = decodeJwt(token);

        // Check if token is expired
        if (isTokenExpired(decodedToken)) {
            localStorage.removeItem('authToken');
            window.location.href = '/otp-verification';
        } else {
            currentUser = decodedToken;
            
            // Check subscription status and redirect accordingly
            if (currentUser.subscription_active) {
                window.location.href = '/countdown';
            } else {
                window.location.href = '/subscription-success';
            }
        }
    } else {
        // Handle paths if no token
        if (path === "/") {
            initRegisterPage();
        } else if (path === "/otp-verification") {
            initOTPPage();
        } else if (path === "/subscription-success") {
            initSubscriptionPage();
        }
    }
});

// Utility: Decode JWT to Access Session Data
function decodeJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        return JSON.parse(atob(base64));
    } catch (error) {
        console.error("Invalid token format", error);
        return null;
    }
}

// Utility: Check if Token is Expired
function isTokenExpired(decodedToken) {
    if (!decodedToken || !decodedToken.exp) return true;
    const currentTime = Math.floor(Date.now() / 1000); // Current time in seconds
    return decodedToken.exp < currentTime;
}

// Helper to get auth headers with token
function getAuthHeaders() {
    const token = localStorage.getItem('authToken');
    if (!token) {
        window.location.href = '/otp-verification';
        return null;
    }
    return { headers: { Authorization: `Bearer ${token}` } };
}

// 1. Registration and MAC Retrieval
async function initRegisterPage() {
    document.querySelector('form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const phone = document.getElementById('phone').value;
        const macAddress = await getMacAddress();

        try {
            const response = await axios.post(`${API_BASE_URL}/user/register`, { phone_number: phone, mac_address: macAddress });
            showSuccess(response.data.message || "Registered successfully");
            window.location.href = '/otp-verification';
        } catch (error) {
            showError("Registration failed. Please try again.");
        }
    });
}

// Get MAC Address from backend
async function getMacAddress() {
    try {
        const response = await axios.get(`${API_BASE_URL}/mac-address`);
        return response.data.mac_address || "MAC not found";
    } catch (error) {
        console.error("Failed to retrieve MAC address:", error);
        return "Error retrieving MAC";
    }
}

// 2. OTP Verification and Store Token
async function initOTPPage() {
    document.querySelector('form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const otp = document.getElementById('otp').value;
        const phone = document.getElementById('phone').value;

        try {
            const response = await axios.post(`${API_BASE_URL}/user/verify-otp`, { phone_number: phone, otp_code: otp });
            const { token, user } = response.data;
            if (token) {
                localStorage.setItem('authToken', token);  // Save token to keep user logged in
                showSuccess(response.data.message || "OTP verified successfully");
                currentUser = decodeJwt(token);
                window.location.href = currentUser.subscription_active ? '/countdown' : '/subscription-success';
            }
        } catch (error) {
            showError("Invalid OTP. Please try again.");
        }
    });
}

// 3. Subscription Page Initialization
function initSubscriptionPage() {
    document.querySelectorAll('.plan-card').forEach(card => {
        card.addEventListener('click', (event) => selectPlan(event, card.getAttribute('data-plan')));
    });
    document.getElementById('subscribeBtn').addEventListener('click', subscribe);
}

// Subscription Plan Selection
function selectPlan(event, plan) {
    selectedPlan = plan;
    document.querySelectorAll('.plan-card').forEach(card => card.classList.remove('selected'));
    event.currentTarget.classList.add('selected');
    document.getElementById('subscribeBtn').classList.remove('hidden');
}

// 4. Subscribe to Plan with Authenticated Request
async function subscribe() {
    if (!selectedPlan) {
        showError("Please select a subscription plan.");
        return;
    }
    if (!currentUser || !currentUser.user_id) {
        showError("User information is missing. Please verify your OTP.");
        return;
    }
    try {
        const response = await axios.post(
            `${API_BASE_URL}/subscription`,
            { user_id: currentUser.user_id, plan_type: selectedPlan },
            getAuthHeaders()
        );
        showSuccess(response.data.message || "Subscription initiated. Please complete payment on your phone.");
        startPaymentStatusPolling();
    } catch (error) {
        showError("Subscription failed. Please try again.");
    }
}

// 5. Poll Payment Status until Successful
async function checkPaymentStatus() {
    try {
        const response = await axios.get(`${API_BASE_URL}/subscription-status`, { params: { user_id: currentUser.user_id } });
        if (response.data.subscription_active) {
            clearInterval(paymentStatusInterval);
            showSuccess("Payment successful. Subscription activated!");
            showSessionCountdown(response.data.time_left);
        } else {
            console.log("Payment still processing...");
        }
    } catch (error) {
        console.error("Error checking payment status:", error);
    }
}

// Start Polling for Payment Status
function startPaymentStatusPolling() {
    if (paymentStatusInterval) clearInterval(paymentStatusInterval);
    paymentStatusInterval = setInterval(checkPaymentStatus, 5000);
}

// 6. Show Session Countdown Timer
function showSessionCountdown(timeLeft) {
    const countdownContainer = document.createElement('div');
    countdownContainer.className = 'countdown-container';
    document.querySelector('.container').innerHTML = '';
    document.querySelector('.container').appendChild(countdownContainer);

    countdownContainer.innerHTML = `
        <div class="countdown-container-message">
            <h3>Tik Tok <br> Goes The Clock</h3>
            <p>Enjoy The Internet :)</p>
        </div>
    `;
    
    const timerText = document.createElement('p');
    timerText.className = 'timer-text';
    countdownContainer.appendChild(timerText);

    const buyMore = document.createElement('button');
    buyMore.className = 'buy-more-button';
    buyMore.textContent = "Buy More Time";
    countdownContainer.appendChild(buyMore);

    buyMore.addEventListener('click', () => {
        window.location.href = '/subscription-success';
    });

    function updateCountdown() {
        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            countdownContainer.innerHTML = "<p>Session expired. Please select a plan.</p>";
            document.getElementById('subscribeBtn').classList.remove('hidden');
            return;
        }

        const hours = Math.floor(timeLeft / 3600);
        const minutes = Math.floor((timeLeft % 3600) / 60);
        const seconds = Math.floor(timeLeft % 60);
        timerText.textContent = `Session time left: ${hours}h ${minutes}m ${seconds}s`;
        timeLeft--;
    }

    countdownInterval = setInterval(updateCountdown, 1000);
    updateCountdown();
}

// Utility Functions for Error/Success Messages
function showError(message) {
    const error = document.createElement('div');
    error.className = 'error';
    error.textContent = message;
    document.querySelector('.container').appendChild(error);
    setTimeout(() => error.remove(), 3000);
}

function showSuccess(message) {
    const success = document.createElement('div');
    success.className = 'success';
    success.textContent = message;
    document.querySelector('.container').appendChild(success);
    setTimeout(() => success.remove(), 3000);
}
