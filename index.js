const API_BASE_URL = 'https://fc70-41-209-3-162.ngrok-free.app';
let selectedPlan = null;
let currentUser = null;
let paymentStatusInterval = null;

async function getMacAddress() {
    try {
        const response = await axios.get(`${API_BASE_URL}/mac-address`);
        return response.data.mac_address || "MAC not found";
    } catch (error) {
        console.error("Failed to retrieve MAC address:", error);
        return "Error retrieving MAC";
    }
}

async function register() {
    const phone = document.getElementById('phone').value;
    const macAddress = await getMacAddress();
    console.log({
        phone_number: phone,
        mac_address: macAddress
    });
    try {
        const response = await axios.post(`${API_BASE_URL}/register`, {
            phone_number: phone,
            mac_address: macAddress
        });
        document.getElementById('registerForm').classList.add('hidden');
        document.getElementById('otpForm').classList.remove('hidden');
    } catch (error) {
        console.error("Registration failed:", error);
        showError('Registration failed. Please try again.');
    }
}

async function verifyOTP() {
    const otp = document.getElementById('otp').value;
    const phone = document.getElementById('phone').value;
    try {
        const response = await axios.post(`${API_BASE_URL}/verify-otp`, {
            phone_number: phone,
            otp_code: otp
        });

        const token = response.data.token;
        const decodedToken = parseJwt(token);
        console.log("This here is the decoded Token parsed with jwt");
        console.log(decodedToken);
        currentUser = decodedToken;

        if (decodedToken.subscription_active) {
            // User has an active subscription
            console.log("calling showSessionCountdwn()");
            showSessionCountdown(decodedToken.time_left);
        } else {
            console.log("no active subscription");
            document.getElementById('otpForm').classList.add('hidden');
            document.getElementById('plansForm').classList.remove('hidden');
        }

    } catch (error) {
        showError('Invalid OTP. Please try again.');
    }
}


async function subscribe() {
    // Ensuring selected plan and current user details are available
    if (!selectedPlan) {
        showError("Please select a subscription plan.");
        return;
    }
    
    if (!currentUser || !currentUser.user_id) {
        showError("User information is missing. Please try re-verifying your OTP.");
        return;
    }

    try {
        // request data
        const requestData = {
            user_id: currentUser.user_id,  // Ensure user_id is correct
            plan_type: selectedPlan        // Ensure plan_type is set to selected plan
        };
        console.log("Subscription request data:", requestData); // For debugging

        // Send request to backend
        const response = await axios.post(`${API_BASE_URL}/subscribe`, requestData);

        startPaymentStatusPolling();
        
        // Handle response after successful subscription initiation
        if (response.data && response.data.message) {
            showSuccess(response.data.message);
        } else {
            showSuccess("Subscription initiated. Please complete payment on your phone.");
        }
    } catch (error) {
        console.error("Subscription error:", error.response ? error.response.data : error.message);
        showError("Subscription failed. Please try again.");
    }
}

async function checkPaymentStatus() {
    try {
        const response = await axios.get(`${API_BASE_URL}/subscription-status`, {
            params: { user_id: currentUser.user_id }
        });
        console.log("Subscription status response: " + response);
        if (response.data.subscription_active) {
            showSuccess("Payment successful. Subscription activated!");
            clearInterval(paymentStatusInterval);
            console.log("update the UI Now")
            // Start countdown with time_left from the server
            showSessionCountdown(response.data.time_left);
        } else {
            console.log("Payment still processing...");
        }
    } catch (error) {
        console.error("Error checking payment status:", error);
    }
}

// functions //

function selectPlan(plan) {
    selectedPlan = plan;
    document.querySelectorAll('.plan-card').forEach(card => {
        card.classList.remove('selected');
    });
    event.currentTarget.classList.add('selected');
    document.getElementById('subscribeBtn').classList.remove('hidden');
}

function showError(message) {
    const error = document.createElement('div');
    error.className = 'error';
    error.textContent = message;
    document.querySelector('.card').appendChild(error);
    setTimeout(() => error.remove(), 3000);
}

function showSuccess(message) {
    const success = document.createElement('div');
    success.className = 'success';
    success.textContent = message;
    document.querySelector('.card').appendChild(success);
    setTimeout(() => success.remove(), 3000);
}

function parseJwt(token) {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function (c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    
    return JSON.parse(jsonPayload);
}

function showSessionCountdown(timeLeft) {
    console.log("now showing session countdown");
    const countdownContainer = document.createElement('div');
    countdownContainer.className = 'countdown-container';
    document.getElementById('plansForm').classList.add('hidden')
    document.querySelector('.card').innerHTML = '';
    document.querySelector('.card').appendChild(countdownContainer);
    
    function updateCountdown() {
        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            countdownContainer.textContent = 'Session expired. Please select a plan.';
            document.getElementById('plansForm').classList.remove('hidden');
            checkPaymentStatus();
            return;
        }
        
        const hours = Math.floor(timeLeft / 3600);
        const minutes = Math.floor((timeLeft % 3600) / 60);
        const seconds = Math.floor(timeLeft % 60);
        
        countdownContainer.textContent = `Session time left \n ${hours}h ${minutes}m ${seconds}s`;
        timeLeft--;
    }
    
    const countdownInterval = setInterval(updateCountdown, 1000);
    updateCountdown();
}

// Start polling every 5 seconds after initiating payment
function startPaymentStatusPolling() {
    if (paymentStatusInterval) clearInterval(paymentStatusInterval);
    paymentStatusInterval = setInterval(checkPaymentStatus, 5000);
}