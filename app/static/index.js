const API_BASE_URL = "{{ ngrok_url }}";
console.log("API Base URL:", API_BASE_URL);
let selectedPlan = null;
let currentUser = null;
let paymentStatusInterval = null;
let countdownInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    console.log("Document loaded, checking for authentication token...");
    const token = localStorage.getItem('authToken');
    const path = window.location.pathname;

    if (token) {
        console.log("Token found. Decoding...");
        const decodedToken = decodeJwt(token);

        if (!decodedToken) {
            console.error("Failed to decode token. Redirecting to OTP verification...");
            localStorage.removeItem('authToken');
            window.location.href = '/user/otp-verification';
            return;
        }

        console.log("Decoded Token:", decodedToken);

        if (isTokenExpired(decodedToken)) {
            console.warn("Token is expired. Removing token and redirecting to OTP verification...");
            localStorage.removeItem('authToken');
            window.location.href = '/user/otp-verification';
        } else {
            console.log("Token is valid. Proceeding with user session...");
            currentUser = decodedToken;
            checkUserSubscription(decodedToken);
        }
    } else {
        console.warn("No token found. Handling paths for unauthenticated user...");
        if (path === "/") {
            console.log("Initializing registration page...");
            initRegisterPage();
        } else if (path === "/user/otp-verification") {
            console.log("Initializing OTP verification page...");
            initOTPPage();
        } else {
            console.error("Unhandled path for unauthenticated user. Redirecting to registration...");
            window.location.href = '/';
        }
    }
});

// Utility: Decode JWT to access session data
function decodeJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const decoded = JSON.parse(atob(base64));
        console.log("Successfully decoded JWT:", decoded);
        return decoded;
    } catch (error) {
        console.error("Error decoding JWT:", error);
        return null;
    }
}

// Utility: Check if token is expired
function isTokenExpired(decodedToken) {
    console.log("Checking token expiry...");
    if (!decodedToken || !decodedToken.exp) return true;
    const currentTime = Math.floor(Date.now() / 1000);
    console.log(`Token expiry time: ${decodedToken.exp}, current time: ${currentTime}`);
    return decodedToken.exp < currentTime;
}

// Helper to get auth headers with token
function getAuthHeaders() {
    const token = localStorage.getItem('authToken');
    if (!token) {
        console.warn("No auth token found. Redirecting to OTP verification...");
        window.location.href = '/user/otp-verification';
        return null;
    }
    return { headers: { Authorization: `Bearer ${token}` } };
}

// Check user's subscription status by calling the backend
async function checkUserSubscription(decodedToken) {
    console.log("Checking user subscription status...");
    try {
        const response = await axios.get(`${API_BASE_URL}/user/check-subscription`, {
            params: { user_id: decodedToken.user_id },
            headers: { Authorization: `Bearer ${localStorage.getItem('authToken')}` }
        });

        console.log("Response:", response);

        if (typeof response.data !== 'object') {
            console.error("Unexpected response format. Received non-JSON response:", response);
            showError("Failed to check subscription status. Please try again later.");
            return;
        }

        console.log("Subscription status response:", response.data);

        if (response.data.subscription_active) {
            console.log("User has an active subscription. Redirecting to countdown page...");
            showSessionCountdown(response.data.time_left);
        } else {
            // Prevent redirect loop if already on the subscription page
            if (window.location.pathname !== '/subscription/subscription-success') {
                console.log("User does not have an active subscription. Redirecting to subscription page...");
                window.location.href = '/subscription/subscription-success';
            } else {
                console.log("Already on the subscription page, not redirecting.");
                initSubscriptionPage();
            }
        }
    } catch (error) {
        console.error("Error while checking subscription status:", error);
        showError("Failed to check subscription status. Please try again.");
    }
}




// 1. Registration and MAC Retrieval
async function initRegisterPage() {
    document.querySelector('form').addEventListener('submit', async (event) => {
        event.preventDefault();
        const phone = document.getElementById('phone').value;
        console.log("Form submitted. Phone number entered:", phone);
        const macAddress = await getMacAddress();

        try {
            console.log("Sending registration request...");
            const response = await axios.post(`${API_BASE_URL}/user/register`, { phone_number: phone, mac_address: macAddress });
            if (response) {
                console.log("Registration successful:", response.data);
                showSuccess(response.data.message || "Registered successfully");
                localStorage.setItem('phone_number', phone);
                setTimeout(5000);
                window.location.href = '/user/otp-verification';
            }
            else {
                console.log("couldn't get response from server\n");
            }
        } catch (error) {
            console.error("Registration failed:", error.response ? error.response.data : error.message);
            showError("Registration failed. Please try again.");
        }
    });
}

// Get MAC Address from backend
async function getMacAddress() {
    try {
        console.log("Fetching MAC address from backend...");
        const response = await axios.get(`${API_BASE_URL}/mac_address/mac-address`, getAuthHeaders());
        console.log("MAC address retrieved:", response.data.mac_address);
        return response.data.mac_address || "MAC not found";
    } catch (error) {
        console.error("Error retrieving MAC address:", error);
        return "Error retrieving MAC";
    }
}

// 2. OTP Verification and Store Token
async function initOTPPage() {
    const otpForm = document.getElementById('otp-form');
    if (otpForm) {
        otpForm.addEventListener('submit', async (event) => {
            event.preventDefault();
            const otp = document.getElementById('otp').value;
            const phone = localStorage.getItem('phone_number');
            console.log("OTP form submitted. OTP entered:", otp);

            if (!phone) {
                console.error("Phone number is missing from local storage.");
                showError("Phone number is missing. Please register again.");
                window.location.href = '/';
                return;
            }

            try {
                console.log("Sending OTP verification request...");
                const { data } = await axios.post(`${API_BASE_URL}/user/verify-otp`, { phone_number: phone, otp_code: otp });
                console.log("OTP verified successfully:", data);
                handleOtpSuccess(data);
            } catch (error) {
                console.error("OTP verification failed:", error.response ? error.response.data : error.message);
                handleOtpError(error);
            }
        });
    }
}

function handleOtpSuccess(data) {
    const { token, message } = data;
    if (token) {
        console.log("Storing new auth token and redirecting...");
        localStorage.setItem('authToken', token);
        showSuccess(message || "OTP verified successfully");
        const decodedUser = decodeJwt(token);
        window.location.href = decodedUser.subscription_active ? '/countdown' : '/subscription/subscription-success';
    } else {
        console.warn("No token received from OTP verification.");
    }
}

function handleOtpError(error) {
    console.error("Handling OTP error...");
    showError("Invalid OTP. Please try again.");
}

// 3. Subscription Page Initialization
function initSubscriptionPage() {
    console.log("Initializing subscription page...");
    document.querySelectorAll('.plan-card').forEach(card => {
        card.addEventListener('click', (event) => selectPlan(event, card.getAttribute('data-plan')));
    });
    document.getElementById('subscribeBtn').addEventListener('click', subscribe);
}

// Subscription Plan Selection
function selectPlan(event, plan) {
    console.log(`Plan selected: ${plan}`);
    selectedPlan = plan;
    document.querySelectorAll('.plan-card').forEach(card => card.classList.remove('selected'));
    event.currentTarget.classList.add('selected');
    document.getElementById('subscribeBtn').classList.remove('hidden');
}

// 4. Subscribe to Plan with Authenticated Request
async function subscribe() {
    if (!selectedPlan) {
        showError("Please select a subscription plan.");
        console.warn("Subscription attempt without selecting a plan.");
        return;
    }
    if (!currentUser || !currentUser.user_id) {
        showError("User information is missing. Please verify your OTP.");
        console.error("User data is missing during subscription attempt:", currentUser);
        return;
    }

    try {
        console.log("Sending subscription request...");
        const response = await axios.post(
            `${API_BASE_URL}/subscription/subscribe`,
            { user_id: currentUser.user_id, plan_type: selectedPlan },
            getAuthHeaders()
        );
        console.log("Subscription initiated successfully:", response.data);
        showSuccess(response.data.message || "Subscription initiated. Please complete payment on your phone.");
        startPaymentStatusPolling();
    } catch (error) {
        console.error("Subscription request failed:", error.response ? error.response.data : error.message);
        showError("Subscription failed. Please try again.");
    }
}

// 5. Poll Payment Status until Successful
async function checkPaymentStatus() {
    console.log("Checking payment status...");
    try {
        const response = await axios.get(`${API_BASE_URL}/subscription/subscription-status`, {
            params: { user_id: currentUser.user_id },
            headers: { Authorization: `Bearer ${localStorage.getItem('authToken')}` }
        });
        console.log("Payment status response:", response.data);

        if (response.data.subscription_active) {
            console.log("Subscription is active. Stopping polling...");
            clearInterval(paymentStatusInterval);
            showSuccess("Payment successful. Subscription activated!");
            showSessionCountdown(response.data.time_left);
        } else {
            console.log("Subscription not active yet. Polling continues...");
        }
    } catch (error) {
        console.error("Error while checking payment status:", error);
    }
}

// Start Polling for Payment Status
function startPaymentStatusPolling() {
    console.log("Starting payment status polling...");
    if (paymentStatusInterval) clearInterval(paymentStatusInterval);
    paymentStatusInterval = setInterval(checkPaymentStatus, 5000);
}

// 6. Show Session Countdown Timer
function showSessionCountdown(timeLeft) {
    console.log("Starting session countdown. Time left:", timeLeft);
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

    const plansContainer = document.createElement('div');
    plansContainer.className = 'plans-container hidden';  // Hidden by default
    plansContainer.innerHTML = `
        <div class="plans">
        <div class="plan-card" data-plan="1hr">
            <h3>1 Hour</h3>
            <p>KSh 10</p>
        </div>
        <div class="plan-card" data-plan="2hrs">
            <h3>2 Hours</h3>
            <p>KSh 20</p>
        </div>
        <div class="plan-card" data-plan="3hrs">
            <h3>3 Hours</h3>
            <p>KSh 30</p>
        </div>
        <div class="plan-card" data-plan="8hrs">
            <h3>8 Hours</h3>
            <p>KSh 80</p>
        </div>
        <div class="plan-card" data-plan="12hrs">
            <h3>12 Hours</h3>
            <p>KSh 100</p>
        </div>
        <div class="plan-card" data-plan="24hrs">
            <h3>24 Hours</h3>
            <p>KSh 150</p>
        </div>
        <div class="plan-card" data-plan="3 days">
            <h3>3 Days</h3>
            <p>KSh 300</p>
        </div>
        <div class="plan-card" data-plan="1 week">
            <h3>1 Week</h3>
            <p>KSh 550</p>
        </div>
        <div class="plan-card" data-plan="2 weeks">
            <h3>2 Weeks</h3>
            <p>KSh 1000</p>
        </div>
        <div class="plan-card" data-plan="monthly">
            <h3>Monthly</h3>
            <p>KSh 1750</p>
        </div>
    </div>
    <button id="subscribeBtn" class="hidden">Subscribe</button>
    `;
    document.querySelector('.container').appendChild(plansContainer);

    buyMore.addEventListener('click', () => {
        console.log("User clicked 'Buy More Time'. Showing available plans...");
        plansContainer.classList.toggle('hidden');
    });

    plansContainer.addEventListener('click', (event) => {
        if (event.target.classList.contains('plan-card')) {
            console.log(`Plan selected: ${event.target.getAttribute('data-plan')}`);
            initSubscriptionPage();
        }
    });

    function updateCountdown() {
        if (timeLeft <= 0) {
            console.warn("Session expired. Redirecting user...");
            clearInterval(countdownInterval);
            countdownContainer.innerHTML = "<p>Session expired. Please select a plan.</p>";
            return;
        }

        const hours = Math.floor(timeLeft / 3600);
        const minutes = Math.floor((timeLeft % 3600) / 60);
        const seconds = Math.floor(timeLeft % 60);
        timerText.textContent = `Session time left: ${hours}h ${minutes}m ${seconds}s`;
        console.log(`Updated countdown: ${hours}h ${minutes}m ${seconds}s`);
        timeLeft--;
    }

    countdownInterval = setInterval(updateCountdown, 1000);
    updateCountdown();
}

// time utilty function
function displayTimeInLocalFormat(utcTime) {
    const date = new Date(utcTime);
    const options = { timeZone: 'Africa/Nairobi', hour12: false };
    console.log(new Intl.DateTimeFormat('en-KE', options).format(date));
}


// Utility Functions for Error/Success Messages
function showError(message) {
    console.error("Displaying error message:", message);
    const error = document.createElement('div');
    error.className = 'error';
    error.textContent = message;
    document.querySelector('.container').appendChild(error);
    setTimeout(() => error.remove(), 3000);
}

function showSuccess(message) {
    console.log("Displaying success message:", message);
    const success = document.createElement('div');
    success.className = 'success';
    success.textContent = message;
    document.querySelector('.container').appendChild(success);
    setTimeout(() => success.remove(), 3000);
}
