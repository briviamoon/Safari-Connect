const API_BASE_URL = 'http://192.169.0.102:8000';
let selectedPlan = null;
let currentUser = null;

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
    try {
        const response = await axios.post(`${API_BASE_URL}/register`, {
            phone_number: phone,
            mac_address: await getMacAddress()
        });
        document.getElementById('registerForm').classList.add('hidden');
        document.getElementById('otpForm').classList.remove('hidden');
    } catch (error) {
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

        if (decodedToken.subscription_active) {
            // User has an active subscription
            showSessionCountdown(decodedToken.time_left);
        } else {
            // No active subscription
            document.getElementById('otpForm').classList.add('hidden');
            document.getElementById('plansForm').classList.remove('hidden');
        }

        currentUser = token;
    } catch (error) {
        showError('Invalid OTP. Please try again.');
    }
}


async function subscribe() {
    if (!selectedPlan || !currentUser) return;
    try {
        const response = await axios.post(`${API_BASE_URL}/subscribe`, {
            plan_type: selectedPlan
        }, {
            headers: { Authorization: `Bearer ${currentUser}` }
        });
        // Handle M-Pesa payment initiation
        showSuccess('Subscription initiated. Please complete payment on your phone.');
    } catch (error) {
        showError('Subscription failed. Please try again.');
    }
}


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
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));

    return JSON.parse(jsonPayload);
}

function showSessionCountdown(timeLeft) {
    const countdownContainer = document.createElement('div');
    countdownContainer.className = 'countdown-container';
    document.querySelector('.card').innerHTML = ''; // Clear previous content
    document.querySelector('.card').appendChild(countdownContainer);

    function updateCountdown() {
        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            countdownContainer.textContent = 'Session expired. Please select a plan.';
            document.getElementById('plansForm').classList.remove('hidden');
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
