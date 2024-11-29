let selectedPlan = null;
let currentUser = null;
let paymentStatusInterval = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('authToken');
    if (token) handleAuthenticatedUser(token);
    else handleUnauthenticatedUser();
});

// Handle authenticated users
function handleAuthenticatedUser(token) {
    console.log("Retreived token:", token);

    const decodedToken = decodeJwt(token);
    const subscriptionChecked = localStorage.getItem('subscriptionChecked');

    if (!decodedToken || isTokenExpired(decodedToken)) {
        localStorage.removeItem('authToken');
        redirectTo('/user/otp-verification');
        return;
    }

    currentUser = decodedToken;
    if (!subscriptionChecked) {
        checkUserSubscription(decodedToken.user_id);
    }
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

// Check if the token is expired
function isTokenExpired(decodedToken) {
    const currentTime = Math.floor(Date.now() / 1000);
    return decodedToken.exp < currentTime;
}

// Redirect to a specified path
function redirectTo(path) {
    window.location.href = path;
}

// MArk subscription check storage as true
function subIsChecked() {
    localStorage.setItem('subscriptionChecked', true);
}

// Check subscription status
async function checkUserSubscription(userId) {
    try {
        const response = await axios.get(`${API_BASE_URL}/subscription/subscription-status`, {
            params: { user_id: userId },
            headers: { Authorization: `Bearer ${localStorage.getItem('authToken')}` },
        });

        if (response.data.subscription_active) {
            showSessionCountdown(response.data.time_left)
        }
        else {
            subIsChecked();
            redirectTo('/subscription/subscription-success')
        }
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

//Subscribe action
document.addEventListener("DOMContentLoaded", function () {
    const planCards = document.querySelectorAll(".plan-card");
    const subscribeButton = document.getElementById("subscribeBtn");

    // Handle plan card selection
    planCards.forEach(function(card) {
        card.addEventListener("click", function() {
            // Deselect other cards
            planCards.forEach(card => card.classList.remove("selected"));
            // Mark the clicked card as selected
            card.classList.add("selected");
            // Show the subscribe button
            subscribeButton.classList.remove("hidden");
        });
    });

    // Handle subscribe button click
    subscribeButton.addEventListener("click", async function() {
        const selectedPlan = document.querySelector(".plan-card.selected");

        if (selectedPlan) {
            const planName = selectedPlan.getAttribute("data-plan");
            console.log("User selected plan:", planName);

            // Send subscription request to the backend
            await subscribe(planName);
        } else {
            console.log("Please select a plan first.");
        }
    });
});

// Function to send the subscription request to the backend
async function subscribe(selectedPlan) {
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
        console.log("Subscription request data:", requestData);
        
        const response = await axios.post(`${API_BASE_URL}/subscription/subscribe`, requestData, {
            headers: getAuthHeaders()
        });

        
        const additionalTime = response.data.time_in_seconds || 0;
        let timeLeft = 0;
        timeLeft += additionalTime;

        // Start polling for payment status
        startPaymentStatusPolling();
        
        if (response.data && response.data.message) {
            showSuccess(response.data.message);
        } else {
            showSuccess("Subscription initiated. Please complete payment on your phone.");
        }

    } catch (error) {
        // Enhanced error handling
        console.error("Subscription error:", error.response ? error.response.data : error.message);
        
        // Display user-friendly error message
        if (error.response && error.response.data && error.response.data.detail) {
            showError(error.response.data.detail);
        } else {
            showError("Subscription failed. Please try again.");
        }
    }
}

//getts authentication hedres
function getAuthHeaders() {
    const token = localStorage.getItem("authToken");
    return token ? { Authorization: `Bearer ${token}` } : {};
}

// Start polling every 5 seconds after initiating payment
function startPaymentStatusPolling() {
    if (paymentStatusInterval) clearInterval(paymentStatusInterval);
    paymentStatusInterval = setInterval(checkUserSubscription, 5000);
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

// Initialize the OTP verification page
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
            redirectTo("/");
        } catch (error) {
            console.error("OTP verification failed:", error);
            showError("Invalid OTP. Please try again.");
        }
    });
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
