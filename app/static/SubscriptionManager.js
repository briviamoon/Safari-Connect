let paymentStatusInterval = null;
let isSubscriptionBeingChecked = false;
let cancelToken = null;

// on DOM Load
document.addEventListener('DOMContentLoaded', () => {
    initializeApplication();
});

// Initialize the application
function initializeApplication() {
    setupEventListeners();
}

function setupEventListeners() {
    if (window.location.pathname === "/subscription/subscription-plans") {
        setupSubscriptionPage();
    } else if (window.location.pathname === "/") {
        initRegisterPage();
    } else if (window.location.pathname === "/user/otp-verification") {
        initOTPPage();
    }
}

// Initialize the registration page
function initRegisterPage() {
    const form = document.querySelector('form');
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        registerUser();
    });
}

async function registerUser() {
    const phone = document.getElementById('phone').value;
    const macAddress = await getMacAddress();
    try {
        const response = await axios.post(`${API_BASE_URL}/user/register`, {
            phone_number: phone,
            mac_address: macAddress
        });
        localStorage.setItem('phone_number', phone);
        redirectTo('/user/otp-verification');
    } catch (error) {
        console.error("Registration failed:", error);
        showError("Registration failed. Please try again.");
    }
}

async function getMacAddress() {
    try {
        const response = await axios.get(`${API_BASE_URL}/mac_address/mac-address`);
        return response.data.mac_address || "00:00:00:00:00:00";
    } catch (error) {
        console.error("Failed to retrieve MAC address:", error);
        return "00:00:00:00:00:00";
    }
}

function initOTPPage() {
    const form = document.querySelector("form");
    const phoneNumberDisplay = document.getElementById("phone-number-display");

    const phoneNumber = localStorage.getItem("phone_number");
    if (phoneNumber && phoneNumberDisplay) {
        phoneNumberDisplay.textContent = phoneNumber;
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const otp = document.getElementById("otp").value;

        try {
            const response = await axios.post(`${API_BASE_URL}/user/verify-otp`, {
                phone_number: phoneNumber,
                otp_code: otp,
            });
            const { access_token, message } = response.data;
            localStorage.setItem("authToken", access_token);
            redirectTo('/');
        } catch (error) {
            console.error("OTP verification failed:", error);
            showError("Invalid OTP. Please try again.");
        }
    });
}

// Set up the subscription page interactions
function setupSubscriptionPage() {
    const planCards = document.querySelectorAll(".plan-card");
    const subscribeButton = document.getElementById("subscribeBtn");

    // Handle plan card selection
    planCards.forEach(card => {
        card.addEventListener("click", () => {
            planCards.forEach(c => c.classList.remove("selected"));
            card.classList.add("selected");
            subscribeButton.classList.remove("hidden");
        });
    });

    // Handle subscribe button click
    subscribeButton.addEventListener("click", async function () {
        const selectedPlan = document.querySelector(".plan-card.selected");
        if (selectedPlan) {
            const planName = selectedPlan.getAttribute("data-plan");
            console.log("User selected plan:", planName);
            await subscribeUserForPlan(planName);
        } else {
            console.log("Please select a plan first.");
        }
    });
}

// Function to send the subscription request to the backend
async function subscribeUserForPlan(selectedPlan) {
    const currentUser = getCurrentUser();
    if (!selectedPlan) {
        showError("Please select a subscription plan.");
        return;
    }

    if (!currentUser || !currentUser.user_id) {
        showError("User information is missing. Please try re-verifying your OTP.");
        return;
    }

    try {
        const requestData = {
            user_id: currentUser.user_id,
            plan_type: selectedPlan
        };
        const response = await axios.post(`${API_BASE_URL}/subscription/subscribe`, requestData, {
            headers: getAuthHeaders()
        });

        const additionalTime = response.data.time_in_seconds || 0;
        let timeLeft = 0;
        timeLeft += additionalTime;

        if (response.data && response.data.message) {
            showSuccess(response.data.message);
        } else {
            showSuccess("Subscription initiated. Please complete payment on your phone.");
        }

        startPaymentStatusPolling();
    } catch (error) {
        console.error("Subscription error:", error.response ? error.response.data : error.message);
        if (error.response && error.response.data && error.response.data.detail) {
            showError(error.response.data.detail);
        } else {
            showError("Subscription failed. Please try again.");
        }
    }
}


// Start polling every 5 seconds after initiating payment
function startPaymentStatusPolling() {
    if (paymentStatusInterval) {
        clearInterval(paymentStatusInterval);
    }
    if (!isCheckingSubscription) {
        paymentStatusInterval = setInterval(() => checkUserSubscription(getCurrentUser().user_id), 5000);
    }
}

// Check subscription status (moved from redirectionManager.js)
async function checkUserSubscription(userId) {
    cancelOngoingRequest();
    cancelTokenSource = axios.CancelToken.source();
    try {
        const response = await axios.get(`${API_BASE_URL}/subscription/subscription-status`, {
            params: { user_id: userId },
            headers: getAuthHeaders(),
            cancelToken: cancelTokenSource.token,
        });
        console.log("Subscription Response Data: ", response.data);
        handleSubscriptionResponse(response);
    } catch (error) {
        handleSubscriptionError(error);
    } finally {
        finalizeSubscriptionRequest();
    }
}

function handleSubscriptionResponse(response) {
    const activeSub = response.data.subscription_active;
    const timeLeft = response.data.time_left;
    console.log("Subscription state: ", activeSub);
    console.log("Time left in seconds: ", timeLeft);

    localStorage.setItem('subscriptionActive', activeSub); // Update local storage

    if (activeSub) {
        clearInterval(paymentStatusInterval);
        markSubscriptionChecked();
        showSessionCountdown(timeLeft);
    } else {
        markSubscriptionChecked();
    }
}

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

function finalizeSubscriptionCheck() {
    isSubscriptionBeingChecked = false;
}

function cancelOngoingRequest() {
    if (cancelTokenSource) {
        cancelTokenSource.cancel('Operation canceled due to new request.');
    }
}

function handleSubscriptionError(error) {
    if (axios.isCancel(error)) {
        console.log('Request canceled:', error.message);
    } else {
        console.error("Error checking subscription:", error);
        showError("Failed to verify subscription. Please try again.");
    }
}

function finalizeSubscriptionRequest() {
    cancelTokenSource = null;
    isSubscriptionBeingChecked = false;
    clearInterval(paymentStatusInterval);
}

// Utility Functions
// Gets user data from local storage
function getCurrentUser() {
    const authToken = localStorage.getItem('authToken');
    return authToken ? decodeJwt(authToken) : null;
}

// Get authentication headers
function getAuthHeaders() {
    const token = localStorage.getItem("authToken");
    return token ? { Authorization: `Bearer ${token}` } : {};
}

// Utility for error messages
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

// Decode JWT for user data
function decodeJwt(token) {
    try {
        const payload = atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'));
        return JSON.parse(payload);
    } catch (error) {
        console.error("Invalid JWT token:", error);
        return null;
    }
}
