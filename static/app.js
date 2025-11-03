/* ============================================================================
   Flight Data Verification System
   Author: Muntasir Al Mamun
   Date: 2025-11-03
   Version: 3.0.0 - Enterprise RBAC System with Stuck Flight Management
   ============================================================================ */

const API_BASE_URL = 'http://127.0.0.1:5000/api/';

let flightDataCache = {};
let activeFlightIds = new Set();
let liveActivityLog = [];
let lastFlightCount = 0;
let lastActivityCheck = Date.now();
let flightChart = null;

// Global user state
let currentUser = {
    username: '',
    role: 'user',
    token: ''
};

let statsData = {
    total: 0,
    secured: 0,
    active: 0,
    blocks: 0
};

// ============================================================================
// AUTHENTICATION & SESSION MANAGEMENT
// ============================================================================

/**
 * Check if user is authenticated on page load
 * Redirect to login if not authenticated
 */
function checkAuthentication() {
    const token = localStorage.getItem('auth_token');
    const username = localStorage.getItem('username');
    
    // Check if we're on the login or register page
    const currentPage = window.location.pathname;
    const isAuthPage = currentPage.includes('login.html') || currentPage.includes('register.html');
    
    if (!token || !username) {
        // No token found
        if (!isAuthPage) {
            console.log('⚠️ No authentication token found. Redirecting to login...');
            window.location.href = 'login.html';
        }
        return false;
    }
    
    // Store in global state
    currentUser.token = token;
    currentUser.username = username;
    
    // Verify token with server
    verifyToken(token, username);
    return true;
}

/**
 * Verify token with backend API and get user role
 */
async function verifyToken(token, username) {
    try {
        const response = await fetch(`${API_BASE_URL}verify_token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        });
        
        const data = await response.json();
        
        if (!data.valid) {
            // Token invalid or expired, redirect to login
            console.log('❌ Token validation failed. Redirecting to login...');
            localStorage.removeItem('auth_token');
            localStorage.removeItem('username');
            localStorage.removeItem('user_role');
            window.location.href = 'login.html';
        } else {
            // Token valid, store role and display username
            currentUser.role = data.role || 'user';
            localStorage.setItem('user_role', currentUser.role);
            
            console.log(`✅ User authenticated: ${username} (${currentUser.role})`);
            displayUsername(username, currentUser.role);
            
            // Show admin features if user is admin
            if (currentUser.role === 'admin') {
                showAdminFeatures();
            }
        }
    } catch (error) {
        console.error('Token verification error:', error);
        // On error, allow access but show warning
        console.warn('⚠️ Could not verify token with server. Proceeding anyway...');
        displayUsername(username, localStorage.getItem('user_role') || 'user');
    }
}

/**
 * Display username and role in navbar
 */
function displayUsername(username, role) {
    const usernameDisplay = document.getElementById('username-display');
    const dropdownUsername = document.getElementById('dropdown-username');
    
    if (usernameDisplay) {
        if (role === 'admin') {
            usernameDisplay.innerHTML = `${username} <span class="text-xs bg-red-500 px-2 py-0.5 rounded ml-1">ADMIN</span>`;
        } else {
            usernameDisplay.textContent = username;
        }
    }
    
    if (dropdownUsername) {
        dropdownUsername.textContent = username;
    }
    
    console.log(`👤 Welcome, ${username}!`);
    
    // Initialize dropdown menu functionality
    initializeUserMenu();
    
    // Show admin features if user is admin
    if (role === 'admin') {
        showAdminFeatures();
    }
}

/**
 * Initialize user dropdown menu
 */
function initializeUserMenu() {
    const userMenuButton = document.getElementById('user-menu-button');
    const userDropdown = document.getElementById('user-dropdown');
    
    if (!userMenuButton || !userDropdown) {
        console.warn('⚠️ User menu elements not found');
        return;
    }
    
    // Remove any existing listeners to avoid duplicates
    const newButton = userMenuButton.cloneNode(true);
    userMenuButton.parentNode.replaceChild(newButton, userMenuButton);
    
    // Toggle dropdown on button click
    newButton.addEventListener('click', (e) => {
        e.stopPropagation();
        userDropdown.classList.toggle('hidden');
        console.log('User menu toggled:', !userDropdown.classList.contains('hidden'));
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!newButton.contains(e.target) && !userDropdown.contains(e.target)) {
            userDropdown.classList.add('hidden');
        }
    });
    
    console.log('✅ User menu initialized');
}

/**
 * Show admin-only features in UI
 */
function showAdminFeatures() {
    console.log('👑 Admin features enabled');
    // Show admin link in dropdown
    const adminDropdownLink = document.getElementById('admin-dropdown-link');
    if (adminDropdownLink) {
        adminDropdownLink.classList.remove('hidden');
        console.log('✅ Admin Panel link shown in dropdown');
    } else {
        console.warn('⚠️ Admin dropdown link element not found');
    }
}

/**
 * Show admin panel modal
 */
function showAdminPanel() {
    const modal = document.createElement('div');
    modal.id = 'admin-modal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center';
    modal.innerHTML = `
        <div class="bg-white rounded-2xl shadow-2xl max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div class="sticky top-0 bg-gradient-to-r from-gray-900 to-gray-700 text-white p-6 rounded-t-2xl z-10">
                <div class="flex items-center justify-between">
                    <h2 class="text-2xl font-bold flex items-center">
                        <svg class="w-8 h-8 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
                        </svg>
                        Admin Control Panel
                    </h2>
                    <button onclick="closeAdminPanel()" class="text-white hover:text-gray-200 transition">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
            </div>
            
            <div class="p-6">
                <!-- Tabs -->
                <div class="flex border-b border-gray-200 mb-6">
                    <button onclick="showAdminTab('users')" id="tab-users" class="admin-tab active px-4 py-2 font-semibold border-b-2 border-gray-900 text-gray-900">
                        Users
                    </button>
                    <button onclick="showAdminTab('uavs')" id="tab-uavs" class="admin-tab px-4 py-2 font-semibold text-gray-500 hover:text-gray-700">
                        UAV Assignments
                    </button>
                    <button onclick="showAdminTab('system')" id="tab-system" class="admin-tab px-4 py-2 font-semibold text-gray-500 hover:text-gray-700">
                        System Stats
                    </button>
                </div>
                
                <!-- Tab Content -->
                <div id="admin-tab-content">
                    <div class="text-center py-8">
                        <div class="animate-spin w-12 h-12 border-4 border-gray-900 border-t-transparent rounded-full mx-auto"></div>
                        <p class="mt-4 text-gray-600">Loading...</p>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Load users tab by default
    showAdminTab('users');
}

function closeAdminPanel() {
    const modal = document.getElementById('admin-modal');
    if (modal) {
        modal.remove();
    }
}

async function showAdminTab(tab) {
    // Update tab styling
    document.querySelectorAll('.admin-tab').forEach(t => {
        t.classList.remove('active', 'border-gray-900', 'text-gray-900');
        t.classList.add('text-gray-500');
    });
    
    const activeTab = document.getElementById(`tab-${tab}`);
    if (activeTab) {
        activeTab.classList.add('active', 'border-gray-900', 'text-gray-900');
        activeTab.classList.remove('text-gray-500');
    }
    
    const content = document.getElementById('admin-tab-content');
    
    if (tab === 'users') {
        content.innerHTML = '<div class="text-center py-8"><div class="animate-spin w-12 h-12 border-4 border-gray-900 border-t-transparent rounded-full mx-auto"></div></div>';
        await loadUsersTab();
    } else if (tab === 'uavs') {
        content.innerHTML = '<div class="text-center py-8"><div class="animate-spin w-12 h-12 border-4 border-gray-900 border-t-transparent rounded-full mx-auto"></div></div>';
        await loadUAVsTab();
    } else if (tab === 'system') {
        content.innerHTML = '<div class="text-center py-8"><div class="animate-spin w-12 h-12 border-4 border-gray-900 border-t-transparent rounded-full mx-auto"></div></div>';
        await loadSystemTab();
    }
}

async function loadUsersTab() {
    try {
        const response = await fetch(`${API_BASE_URL}admin/users`, {
            headers: { 'Authorization': currentUser.token }
        });
        
        const data = await response.json();
        const content = document.getElementById('admin-tab-content');
        
        content.innerHTML = `
            <div class="mb-6">
                <h3 class="text-lg font-bold mb-4 text-gray-900">User Management (${data.total} users)</h3>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    ${data.users.map(user => `
                        <div class="border border-gray-200 rounded-lg p-4 ${user.is_active ? '' : 'opacity-50 bg-gray-50'}">
                            <div class="flex items-center justify-between mb-2">
                                <span class="font-bold text-gray-800">${user.username}</span>
                                <span class="badge ${user.role === 'admin' ? 'bg-gray-900 text-white' : 'bg-gray-200 text-gray-800'}">
                                    ${user.role.toUpperCase()}
                                </span>
                            </div>
                            <p class="text-xs text-gray-600 mb-2">${user.email || 'No email'}</p>
                            <p class="text-xs text-gray-500 mb-2">
                                <strong>Created:</strong> ${new Date(user.created_at).toLocaleDateString()}
                            </p>
                            <p class="text-xs text-gray-500 mb-3">
                                <strong>UAVs:</strong> ${user.assigned_uavs && user.assigned_uavs.length > 0 ? user.assigned_uavs.join(', ') : 'None'}
                            </p>
                            <div class="flex gap-2">
                                <button onclick="toggleUserRole('${user.username}', '${user.role}')" class="text-xs px-3 py-1 bg-gray-900 text-white rounded hover:bg-gray-800 transition">
                                    ${user.role === 'admin' ? 'Demote' : 'Promote'}
                                </button>
                                <button onclick="toggleUserStatus('${user.username}')" class="text-xs px-3 py-1 ${user.is_active ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'} text-white rounded transition">
                                    ${user.is_active ? 'Disable' : 'Enable'}
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading users:', error);
        document.getElementById('admin-tab-content').innerHTML = '<p class="text-red-600 text-center py-8">Error loading users</p>';
    }
}

async function loadUAVsTab() {
    try {
        const [usersRes, uavsRes, assignmentsRes] = await Promise.all([
            fetch(`${API_BASE_URL}admin/users`, { headers: { 'Authorization': currentUser.token } }),
            fetch(`${API_BASE_URL}admin/available_uavs`, { headers: { 'Authorization': currentUser.token } }),
            fetch(`${API_BASE_URL}admin/uav_assignments`, { headers: { 'Authorization': currentUser.token } })
        ]);
        
        const users = await usersRes.json();
        const uavs = await uavsRes.json();
        const assignments = await assignmentsRes.json();
        
        const content = document.getElementById('admin-tab-content');
        
        content.innerHTML = `
            <div class="mb-6">
                <h3 class="text-lg font-bold mb-4 text-gray-900">Assign UAV to User</h3>
                <div class="bg-gray-50 border border-gray-200 rounded-lg p-4">
                    <div class="grid grid-cols-2 gap-4 mb-4">
                        <select id="assign-user" class="border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-gray-900 focus:border-gray-900">
                            <option value="">Select User...</option>
                            ${users.users.map(u => `<option value="${u.username}">${u.username} (${u.role})</option>`).join('')}
                        </select>
                        <select id="assign-uav" class="border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-gray-900 focus:border-gray-900">
                            <option value="">Select UAV...</option>
                            ${uavs.uavs.map(u => `<option value="${u.uav_supi}">${u.uav_supi} (${u.assignment_count} assignments)</option>`).join('')}
                        </select>
                    </div>
                    <button onclick="assignUAV()" class="bg-gray-900 hover:bg-gray-800 text-white px-6 py-2 rounded font-semibold transition">
                        Assign UAV
                    </button>
                </div>
            </div>
            
            <div>
                <h3 class="text-lg font-bold mb-4 text-gray-900">Current Assignments (${assignments.total})</h3>
                <div class="space-y-2">
                    ${assignments.assignments.length === 0 ? 
                        '<p class="text-gray-500 text-center py-8">No UAV assignments found</p>' :
                        assignments.assignments.map(a => `
                        <div class="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition">
                            <div>
                                <span class="font-semibold text-gray-800">${a.username}</span>
                                <span class="mx-3 text-gray-400">→</span>
                                <span class="text-gray-900 font-semibold">${a.uav_supi}</span>
                                <span class="text-xs text-gray-500 ml-3">
                                    (assigned by <strong>${a.assigned_by}</strong> on ${new Date(a.assigned_at).toLocaleDateString()})
                                </span>
                            </div>
                            <button onclick="unassignUAV('${a.username}', '${a.uav_supi}')" class="text-xs px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded transition">
                                Unassign
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading UAVs:', error);
        document.getElementById('admin-tab-content').innerHTML = '<p class="text-red-600 text-center py-8">Error loading UAV data</p>';
    }
}

async function loadSystemTab() {
    try {
        const response = await fetch(`${API_BASE_URL}admin/system_stats`, {
            headers: { 'Authorization': currentUser.token }
        });
        
        const data = await response.json();
        const content = document.getElementById('admin-tab-content');
        
        content.innerHTML = `
            <div>
                <h3 class="text-lg font-bold mb-4 text-gray-900">System Statistics</h3>
                
                <!-- STUCK FLIGHTS MANAGEMENT BUTTON -->
                <div class="mb-6">
                    <button onclick="showStuckFlights()" class="w-full py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg transition font-medium shadow-md">
                        Manage Active Flights (Fix Stuck Flights)
                    </button>
                </div>
                
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200">
                        <p class="text-sm text-gray-600 font-semibold">Total Users</p>
                        <p class="text-3xl font-bold text-gray-900">${data.auth_stats.total_users}</p>
                    </div>
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200">
                        <p class="text-sm text-gray-600 font-semibold">Total Flights</p>
                        <p class="text-3xl font-bold text-gray-900">${data.total_flights}</p>
                    </div>
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200">
                        <p class="text-sm text-gray-600 font-semibold">Active Sessions</p>
                        <p class="text-3xl font-bold text-gray-900">${data.auth_stats.active_sessions}</p>
                    </div>
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200">
                        <p class="text-sm text-gray-600 font-semibold">UAV Assignments</p>
                        <p class="text-3xl font-bold text-gray-900">${data.auth_stats.total_assignments}</p>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200">
                        <p class="text-sm text-gray-600 font-semibold">Admins</p>
                        <p class="text-3xl font-bold text-gray-900">${data.auth_stats.total_admins}</p>
                    </div>
                    <div class="bg-gray-50 p-6 rounded-lg border border-gray-200">
                        <p class="text-sm text-gray-600 font-semibold">Registered UAVs</p>
                        <p class="text-3xl font-bold text-gray-900">${data.registered_uavs}</p>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error loading system stats:', error);
        document.getElementById('admin-tab-content').innerHTML = '<p class="text-red-600 text-center py-8">Error loading system stats</p>';
    }
}

/**
 * Show stuck flights management
 */
async function showStuckFlights() {
    try {
        const response = await fetch(`${API_BASE_URL}active_flights`, {
            headers: { 'Authorization': currentUser.token }
        });
        const data = await response.json();
        
        if (data.active_flights.length === 0) {
            alert('No active flights found\n\nAll flights have been properly archived.');
            return;
        }
        
        let message = 'Active Flights:\n\n';
        data.active_flights.forEach(flight => {
            const startTime = new Date(flight.start_time * 1000).toLocaleString();
            message += `Flight ${flight.flight_id} (${flight.uav_supi})\n`;
            message += `Started: ${startTime}\n\n`;
        });
        
        const flightId = prompt(message + '\nEnter Flight ID to force end (or cancel):');
        
        if (flightId) {
            await forceEndFlight(parseInt(flightId));
        }
        
    } catch (error) {
        console.error('Error fetching active flights:', error);
        alert('Failed to fetch active flights. Check console for details.');
    }
}

/**
 * Force end a stuck flight
 */
async function forceEndFlight(flightId) {
    if (!confirm(`Force end Flight ${flightId}?\n\nThis will archive the flight data and remove it from active flights.`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}end_flight`, {
            method: 'POST',
            headers: {
                'Authorization': currentUser.token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ flight_id: flightId })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert(`Success!\n\n${data.message}\n\nFlight ${flightId} has been archived.`);
            // Refresh the page to update active flights
            window.location.reload();
        } else {
            alert(`Failed to end flight:\n${data.message || 'Unknown error'}`);
        }
        
    } catch (error) {
        console.error('Error ending flight:', error);
        alert('Failed to end flight. Check console for details.');
    }
}

async function toggleUserRole(username, currentRole) {
    const newRole = currentRole === 'admin' ? 'user' : 'admin';
    
    if (!confirm(`Change ${username}'s role from ${currentRole} to ${newRole}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}admin/user/${username}/role`, {
            method: 'PUT',
            headers: {
                'Authorization': currentUser.token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ role: newRole })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            loadUsersTab();
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error updating role:', error);
        alert('Failed to update role');
    }
}

async function toggleUserStatus(username) {
    if (!confirm(`Toggle account status for ${username}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}admin/user/${username}/status`, {
            method: 'PUT',
            headers: { 'Authorization': currentUser.token }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            loadUsersTab();
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error updating status:', error);
        alert('Failed to update status');
    }
}

async function assignUAV() {
    const username = document.getElementById('assign-user').value;
    const uav_supi = document.getElementById('assign-uav').value;
    
    if (!username || !uav_supi) {
        alert('Please select both user and UAV');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}admin/assign_uav`, {
            method: 'POST',
            headers: {
                'Authorization': currentUser.token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, uav_supi })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            loadUAVsTab();
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error assigning UAV:', error);
        alert('Failed to assign UAV');
    }
}

async function unassignUAV(username, uav_supi) {
    if (!confirm(`Unassign ${uav_supi} from ${username}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}admin/unassign_uav`, {
            method: 'POST',
            headers: {
                'Authorization': currentUser.token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ username, uav_supi })
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(data.message);
            loadUAVsTab();
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error unassigning UAV:', error);
        alert('Failed to unassign UAV');
    }
}

/**
 * Handle user logout
 */
async function handleLogout() {
    const token = localStorage.getItem('auth_token');
    const username = localStorage.getItem('username');
    
    // Show confirmation
    if (!confirm('Are you sure you want to logout?')) {
        return;
    }
    
    console.log(`🚪 Logging out user: ${username}`);
    
    try {
        // Call logout API to invalidate session on server
        await fetch(`${API_BASE_URL}logout`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
        });
        console.log('✅ Server session invalidated');
    } catch (error) {
        console.error('Logout API error:', error);
    }
    
    // Clear local storage
    localStorage.removeItem('auth_token');
    localStorage.removeItem('username');
    localStorage.removeItem('user_role');
    
    // Redirect to login page
    console.log('✅ Logged out successfully. Redirecting to login...');
    window.location.href = 'login.html';
}

// ============================================================================
// HASH VERIFICATION FUNCTIONS
// ============================================================================

function hashBlock(block) {
    let tempBlock = JSON.parse(JSON.stringify(block));
    delete tempBlock.current_hash;

    function deepSort(obj) {
        if (Array.isArray(obj)) {
            return obj.map(item => deepSort(item));
        } else if (obj !== null && typeof obj === 'object') {
            const sorted = {};
            Object.keys(obj).sort().forEach(key => {
                sorted[key] = deepSort(obj[key]);
            });
            return sorted;
        }
        return obj;
    }

    const sortedBlock = deepSort(tempBlock);
    const blockString = JSON.stringify(sortedBlock);
    
    return CryptoJS.SHA256(blockString).toString(CryptoJS.enc.Hex);
}

function verifyIntegrity(chain) {
    if (!chain || chain.length < 2) {
        return { secured: false, message: "Log too short for verification" };
    }

    for (let i = 1; i < chain.length; i++) {
        const currentBlock = chain[i];
        const previousBlock = chain[i - 1];
        
        const recalculatedHash = hashBlock(previousBlock);
        
        if (currentBlock.previous_hash !== recalculatedHash) {
            return { 
                secured: false, 
                message: `TAMPERED: Hash mismatch at Block ${i}`,
                lastHash: currentBlock.previous_hash 
            };
        }

        if (currentBlock.timestamp <= previousBlock.timestamp) {
            return { 
                secured: false, 
                message: `TAMPERED: Chronology violation at Block ${i}`,
                lastHash: currentBlock.previous_hash 
            };
        }
    }
    
    return { 
        secured: true, 
        message: "SECURED: Integrity Verified", 
        lastHash: chain[chain.length - 1].current_hash 
    };
}

// ============================================================================
// STATISTICS UPDATE
// ============================================================================

function updateStats() {
    document.getElementById('stat-total').textContent = statsData.total;
    document.getElementById('stat-secured').textContent = statsData.secured;
    document.getElementById('stat-active').textContent = statsData.active;
    document.getElementById('stat-blocks').textContent = statsData.blocks;
}

// ============================================================================
// LIVE ACTIVITY TRACKING
// ============================================================================

async function checkActiveFlights() {
    try {
        const response = await fetch(`${API_BASE_URL}active_flights`, {
            headers: currentUser.token ? { 'Authorization': currentUser.token } : {}
        });
        const data = await response.json();
        
        statsData.active = data.count;
        updateStats();
        
        const currentActiveIds = new Set(data.active_flights.map(f => f.flight_id));
        
        for (const flight of data.active_flights) {
            if (!activeFlightIds.has(flight.flight_id)) {
                addLiveActivity('info', `Flight ${flight.flight_id} (${flight.uav_supi}) started`, true);
            }
            fetchFlightActivity(flight.flight_id);
        }
        
        for (const oldId of activeFlightIds) {
            if (!currentActiveIds.has(oldId)) {
                addLiveActivity('success', `Flight ${oldId} completed and archived`, true);
            }
        }
        
        activeFlightIds = currentActiveIds;
        
    } catch (error) {
        console.error('Error checking active flights:', error);
        statsData.active = 0;
        updateStats();
    }
}

async function fetchFlightActivity(flightId) {
    try {
        const response = await fetch(`${API_BASE_URL}flight_activity/${flightId}`);
        const data = await response.json();
        
        if (data.activity && data.activity.length > 0 && Date.now() - lastActivityCheck > 2000) {
            const latestActivity = data.activity[data.activity.length - 1];
            
            if (latestActivity.type === 'telemetry') {
                const message = `Flight ${flightId} • ${latestActivity.coordinates} • Alt: ${latestActivity.altitude} • Speed: ${latestActivity.speed}`;
                addLiveActivity('info', message, true);
                lastActivityCheck = Date.now();
            }
        }
    } catch (error) {
        console.error(`Error fetching activity for flight ${flightId}:`, error);
    }
}

function addLiveActivity(type, message, isLiveFlight = false) {
    const timestamp = new Date().toLocaleTimeString();
    const activity = { type, message, timestamp, isLiveFlight };
    
    if (isLiveFlight) {
        const isDuplicate = liveActivityLog.some(a => 
            a.message === message && 
            (Date.now() - getTimeInMs(a.timestamp)) < 1000
        );
        
        if (!isDuplicate) {
            liveActivityLog.unshift(activity);
            
            if (liveActivityLog.length > 30) {
                liveActivityLog = liveActivityLog.slice(0, 30);
            }
            
            renderLiveActivity();
        }
    }
}

function getTimeInMs(timeString) {
    const now = new Date();
    const [time, period] = timeString.split(' ');
    const [hours, minutes, seconds] = time.split(':');
    now.setHours(parseInt(hours), parseInt(minutes), parseInt(seconds));
    return now.getTime();
}

function renderLiveActivity() {
    const feed = document.getElementById('activity-feed');
    
    const liveFlightActivities = liveActivityLog.filter(a => a.isLiveFlight);
    
    if (liveFlightActivities.length === 0) {
        feed.innerHTML = `
            <div class="empty-state py-8">
                <svg class="w-16 h-16 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                </svg>
                <p class="text-sm font-medium text-gray-600">No Active UAV Flights</p>
                <p class="text-xs text-gray-500 mt-1">Start a UAV client to see live telemetry</p>
            </div>
        `;
        return;
    }
    
    feed.innerHTML = liveFlightActivities.map(activity => {
        return `
            <div class="activity-item live-flight pl-4 py-2 rounded">
                <div class="flex items-start justify-between">
                    <div class="flex-1">
                        <p class="text-sm text-gray-800">${activity.message}</p>
                        <p class="text-xs text-gray-500 mt-1">${activity.timestamp}</p>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// ============================================================================
// FLIGHT LIST MANAGEMENT
// ============================================================================

function formatFlightTime(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('en-US', {
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
}

async function renderFlightList(files) {
    const container = document.getElementById('flight-list-container');
    
    if (files.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg class="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"></path>
                </svg>
                <p class="text-sm font-medium">No flight logs found</p>
                <p class="text-xs mt-1">Run a UAV client to create logs</p>
            </div>
        `;
        return;
    }
    
    if (files.length > lastFlightCount) {
        console.log(`New flight detected! Total: ${files.length} (was ${lastFlightCount})`);
    }
    lastFlightCount = files.length;
    
    container.innerHTML = '';
    
    statsData.total = files.length;
    statsData.secured = 0;
    statsData.blocks = 0;
    
    const sortedFiles = files.sort((a, b) => {
        const numA = parseInt(a.name.replace('Flight_', ''));
        const numB = parseInt(b.name.replace('Flight_', ''));
        return numB - numA;
    });
    
    for (const file of sortedFiles) {
        try {
            const response = await fetch(`${API_BASE_URL}get_log/${file.id}`, {
                headers: currentUser.token ? { 'Authorization': currentUser.token } : {}
            });
            
            if (response.status === 403) {
                // Access denied - skip this flight
                continue;
            }
            
            const data = await response.json();
            flightDataCache[file.id] = data;
            
            const verification = verifyIntegrity(data.chain);
            if (verification.secured) statsData.secured++;
            
            statsData.blocks += data.chain.length;
            
            const flightNumber = file.name.replace('Flight_', '');
            const flightTime = formatFlightTime(data.chain[0].timestamp);
            
            const statusBadge = verification.secured 
                ? '<span class="badge badge-success">Secured</span>'
                : '<span class="badge badge-danger">Tampered</span>';
            
            const flightItem = document.createElement('div');
            flightItem.className = 'flight-item p-4 border-b border-gray-200 last:border-b-0';
            flightItem.onclick = () => selectFlight(file.id);
            flightItem.innerHTML = `
                <div class="flex items-start justify-between mb-2">
                    <div class="flex items-center">
                        <svg class="w-5 h-5 text-gray-600 mr-2 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                        </svg>
                        <span class="font-semibold text-gray-800">Flight ${flightNumber}</span>
                    </div>
                    ${statusBadge}
                </div>
                <div class="ml-7">
                    <p class="text-xs text-gray-600 mb-1">
                        <svg class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        ${flightTime}
                    </p>
                    <p class="text-xs text-gray-500">
                        <svg class="w-3 h-3 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"></path>
                        </svg>
                        ${data.chain.length} Blocks
                    </p>
                </div>
            `;
            
            container.appendChild(flightItem);
            
        } catch (error) {
            console.error(`Error loading ${file.id}:`, error);
        }
    }
    
    updateStats();
}

function selectFlight(filename) {
    const select = document.getElementById('flight-select');
    select.value = filename;
    
    document.querySelectorAll('.flight-item').forEach(item => {
        item.classList.remove('selected');
    });
    event.currentTarget.classList.add('selected');
    
    loadFlightLog(filename);
}

async function populateFlightList() {
    const select = document.getElementById('flight-select');
    select.innerHTML = '<option value="">Loading flights...</option>';

    try {
        const response = await fetch(`${API_BASE_URL}list_flights`, {
            headers: currentUser.token ? { 'Authorization': currentUser.token } : {}
        });
        const files = await response.json();
        
        select.innerHTML = '';
        select.add(new Option('-- Select a Flight for Verification --', ''));

        if (files.length === 0) {
            select.add(new Option('No flights recorded', ''));
            select.disabled = true;
        } else {
            const sortedFiles = files.sort((a, b) => {
                const numA = parseInt(a.name.replace('Flight_', ''));
                const numB = parseInt(b.name.replace('Flight_', ''));
                return numB - numA;
            });
            
            sortedFiles.forEach((file, index) => {
                const flightNumber = file.name.replace('Flight_', 'Flight ');
                const option = new Option(`${flightNumber}`, file.id);
                select.add(option);
            });
            select.disabled = false;
            
            await renderFlightList(files);
        }
        
    } catch (error) {
        console.error('Error loading flights:', error);
        select.innerHTML = '';
        select.add(new Option('Error: Run GCS_LeaderNode.py first', ''));
        select.disabled = true;
        
        const container = document.getElementById('flight-list-container');
        container.innerHTML = `
            <div class="empty-state">
                <svg class="w-16 h-16 mx-auto mb-4 text-red-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <p class="text-sm font-medium text-red-600">Connection Error</p>
                <p class="text-xs mt-1">Please start GCS_LeaderNode.py</p>
            </div>
        `;
    }
}

function refreshFlights() {
    populateFlightList();
    checkActiveFlights();
}

// ============================================================================
// LOG FORMATTING & DISPLAY
// ============================================================================

function formatLogContent(chain) {
    let content = "Idx | Time Stamp        | Event Tag     | Path Coordinates (X, Y)  | Altitude (Z) | Speed (m/s)\n";
    content += "════════════════════════════════════════════════════════════════════════════════════════════════════\n";
    
    chain.forEach(block => {
        block.transactions.forEach(tx => {
            const data = tx.data || {};
            const tag = data.status === 'LANDING_FINAL' ? 'LANDING' : tx.status || (data.x_pos ? 'PATH' : 'INIT');
            const txTime = new Date(block.timestamp * 1000).toLocaleTimeString('en-US', { 
                hour12: false, 
                second: '2-digit', 
                minute: '2-digit', 
                hour: '2-digit', 
                fractionalSecondDigits: 3 
            });

            let detail;
            if (tx.status === 'AUTHENTICATED') {
                detail = `AUTH OK | Session Key: ${tx.session_key_sim.substring(0, 16)}...`;
            } else if (data.x_pos !== undefined) {
                detail = `(${data.x_pos.toFixed(2).padStart(7, ' ')}, ${data.y_pos.toFixed(2).padStart(7, ' ')}) | ${Math.abs(data.z_alt).toFixed(2).padStart(6, ' ')}m | ${data.vel_mag.toFixed(2).padStart(5, ' ')} m/s`;
            } else if (tx.tx_id === 'GENESIS_TX') {
                const flightId = block.event_log[0].flight_id;
                const uavSupi = block.event_log[0].uav_supi;
                detail = `Flight ${flightId} Initialized - Blockchain Genesis Block (${uavSupi})`;
            } else {
                detail = 'Flight Data Transaction';
            }

            content += `[${String(block.index).padStart(2, '0')}] ${txTime} | ${tag.padEnd(13)} | ${detail}\n`;
        });
    });
    
    content += "\n════════════════════════════════════════════════════════════════════════════════════════════════════\n";
    content += `Total Blocks: ${chain.length} | Blockchain Height: ${chain.length - 1}\n`;
    
    return content;
}
async function loadFlightLog(filename) {
    if (!filename) return;

    const statusElement = document.getElementById('status-message');
    const hashElement = document.getElementById('last-hash');
    const hashValue = document.getElementById('hash-value');
    const logTable = document.getElementById('log-table-content');
    const statusPanel = document.getElementById('status-panel');
    const blockCount = document.getElementById('block-count');

    statusElement.textContent = `Verifying ${filename}...`;
    statusElement.className = 'text-yellow-600 font-semibold text-base';
    logTable.textContent = 'Loading blockchain data...\n\nVerifying integrity and chronology...';
    hashElement.classList.add('hidden');
    blockCount.classList.add('hidden');
    
    statusPanel.className = 'status-panel p-6 rounded-xl transition-all duration-300';

    try {
        let data;
        
        if (flightDataCache[filename]) {
            data = flightDataCache[filename];
        } else {
            const response = await fetch(`${API_BASE_URL}get_log/${filename}`, {
                headers: currentUser.token ? { 'Authorization': currentUser.token } : {}
            });
            
            if (response.status === 403) {
                throw new Error('Access denied: You do not have permission to view this flight');
            }
            
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            data = await response.json();
            flightDataCache[filename] = data;
        }
        
        const verificationResult = verifyIntegrity(data.chain);
        const chain = data.chain;

        statusElement.textContent = verificationResult.message;
        hashValue.textContent = verificationResult.lastHash || 'N/A';
        hashElement.classList.remove('hidden');
        
        blockCount.textContent = `${chain.length} Blocks`;
        blockCount.classList.remove('hidden');
        
        logTable.textContent = formatLogContent(chain);
        
        render2DFlightPath(chain);
        
        if (verificationResult.secured) {
            statusElement.className = 'text-green-700 font-bold text-lg';
            statusPanel.className = 'status-panel secured p-6 rounded-xl transition-all duration-300';
            blockCount.className = 'badge badge-success';
        } else {
            statusElement.className = 'text-red-700 font-bold text-lg';
            statusPanel.className = 'status-panel tampered p-6 rounded-xl transition-all duration-300';
            blockCount.className = 'badge badge-danger';
        }

    } catch (error) {
        statusElement.textContent = `FATAL ERROR: ${error.message}`;
        statusElement.className = 'text-red-600 font-bold text-base';
        hashValue.textContent = `Error: ${error.message}`;
        hashElement.classList.remove('hidden');
        logTable.textContent = "Connection Error\n\nPlease ensure:\n1. GCS Leader Node is running (python3 GCS_LeaderNode.py)\n2. The API is accessible at http://127.0.0.1:5000\n3. You have permission to view this flight\n4. Flight logs exist in the flight_archives directory";
        statusPanel.className = 'status-panel tampered p-6 rounded-xl transition-all duration-300';
    }
}

function exportLog() {
    const logContent = document.getElementById('log-table-content').textContent;
    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `flight_log_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}

// ============================================================================
// 2D FLIGHT PATH VISUALIZATION
// ============================================================================

function render2DFlightPath(chain) {
    const positions = [];
    const altitudes = [];
    const speeds = [];
    const labels = [];
    
    let totalDistance = 0;
    let maxAltitude = 0;
    let totalSpeed = 0;
    let speedCount = 0;
    
    let prevX = null, prevY = null, prevZ = null;
    let dataPointIndex = 0;
    
    chain.forEach(block => {
        block.transactions.forEach(tx => {
            if (tx.data && tx.data.x_pos !== undefined) {
                const xPos = tx.data.x_pos;
                const yPos = tx.data.y_pos;
                const zAlt = Math.abs(tx.data.z_alt);
                const speed = tx.data.vel_mag || 0;
                
                positions.push({x: xPos, y: yPos});
                altitudes.push(zAlt);
                speeds.push(speed);
                labels.push(dataPointIndex++);
                
                if (prevX !== null) {
                    const dist = Math.sqrt(
                        Math.pow(xPos - prevX, 2) + 
                        Math.pow(yPos - prevY, 2) + 
                        Math.pow(zAlt - prevZ, 2)
                    );
                    totalDistance += dist;
                }
                
                prevX = xPos;
                prevY = yPos;
                prevZ = zAlt;
                
                if (zAlt > maxAltitude) maxAltitude = zAlt;
                
                if (speed > 0) {
                    totalSpeed += speed;
                    speedCount++;
                }
            }
        });
    });
    
    if (positions.length === 0) {
        const ctx = document.getElementById('flightPathChart');
        if (ctx) {
            ctx.parentElement.innerHTML = `
                <div class="flex items-center justify-center h-full text-gray-400">
                    <div class="text-center">
                        <svg class="w-16 h-16 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                        </svg>
                        <p>No telemetry data available</p>
                    </div>
                </div>
            `;
        }
        return;
    }
    
    document.getElementById('stat-distance').textContent = `${totalDistance.toFixed(1)} m`;
    document.getElementById('stat-max-alt').textContent = `${maxAltitude.toFixed(1)} m`;
    document.getElementById('stat-avg-speed').textContent = `${(totalSpeed / speedCount).toFixed(2)} m/s`;
    
    const duration = chain[chain.length - 1].timestamp - chain[0].timestamp;
    document.getElementById('stat-duration').textContent = `${Math.round(duration)} s`;
    
    if (flightChart) {
        flightChart.destroy();
    }
    
    const ctx = document.getElementById('flightPathChart');
    if (!ctx) return;
    
    flightChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Altitude (m)',
                    data: altitudes,
                    borderColor: 'rgb(16, 185, 129)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBackgroundColor: 'rgb(16, 185, 129)',
                    tension: 0.4,
                    yAxisID: 'y'
                },
                {
                    label: 'Speed (m/s)',
                    data: speeds,
                    borderColor: 'rgb(168, 85, 247)',
                    backgroundColor: 'rgba(168, 85, 247, 0.1)',
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBackgroundColor: 'rgb(168, 85, 247)',
                    tension: 0.4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 15,
                        font: {
                            size: 12,
                            weight: '600'
                        }
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: 'rgba(255, 255, 255, 0.2)',
                    borderWidth: 1,
                    displayColors: true,
                    callbacks: {
                        title: function(context) {
                            return `Data Point: ${context[0].label}`;
                        },
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            label += context.parsed.y.toFixed(2);
                            return label;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    title: {
                        display: true,
                        text: 'Flight Progress',
                        color: '#6b7280',
                        font: {
                            size: 12,
                            weight: '600'
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        color: '#6b7280'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Altitude (m)',
                        color: 'rgb(16, 185, 129)',
                        font: {
                            size: 12,
                            weight: '600'
                        }
                    },
                    grid: {
                        color: 'rgba(16, 185, 129, 0.1)'
                    },
                    ticks: {
                        color: 'rgb(16, 185, 129)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Speed (m/s)',
                        color: 'rgb(168, 85, 247)',
                        font: {
                            size: 12,
                            weight: '600'
                        }
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                    ticks: {
                        color: 'rgb(168, 85, 247)'
                    }
                }
            }
        }
    });
}

// ============================================================================
// SMART CONTRACTS
// ============================================================================

async function refreshContracts() {
    try {
        const response = await fetch(`${API_BASE_URL}contracts/stats`);
        const data = await response.json();
        
        const container = document.getElementById('contracts-list');
        
        if (data.contracts && data.contracts.length === 0) {
            container.innerHTML = '<p class="text-center text-gray-500 text-sm">No contracts active</p>';
            return;
        }
        
        if (data.contracts) {
            container.innerHTML = data.contracts.map(contract => {
                const statusColor = contract.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800';
                const violationColor = contract.violations > 0 ? 'text-red-600' : 'text-green-600';
                
                return `
                    <div class="border border-gray-200 rounded-lg p-3">
                        <div class="flex items-center justify-between mb-2">
                            <span class="font-semibold text-sm">${contract.name}</span>
                            <span class="badge ${statusColor}">${contract.enabled ? 'Active' : 'Disabled'}</span>
                        </div>
                        <p class="text-xs text-gray-600 mb-2">${contract.description}</p>
                        <div class="flex justify-between text-xs">
                            <span>Executions: <strong>${contract.executions}</strong></span>
                            <span class="${violationColor} font-semibold">Violations: ${contract.violations}</span>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            container.innerHTML = '<p class="text-center text-gray-500 text-sm">Smart contracts not available</p>';
        }
        
    } catch (error) {
        console.error('Error fetching contract stats:', error);
        document.getElementById('contracts-list').innerHTML = '<p class="text-center text-red-500 text-sm">Error loading contracts</p>';
    }
}

// ============================================================================
// ANOMALY DETECTION
// ============================================================================

async function retrainModel() {
    if (currentUser.role !== 'admin') {
        alert('Admin access required to retrain AI model');
        return;
    }
    
    if (!confirm('Retrain AI anomaly detection model? This may take a few moments.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}anomaly/retrain`, {
            method: 'POST',
            headers: { 'Authorization': currentUser.token }
        });
        const data = await response.json();
        
        if (data.status === 'success') {
            alert('AI Model retrained successfully!\n\n' + data.message);
        } else {
            alert(data.message);
        }
    } catch (error) {
        console.error('Error retraining model:', error);
        alert('Failed to retrain model. Check console for details.');
    }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('='.repeat(70));
    console.log('Flight Data Verification System v3.0.0 - Enterprise RBAC');
    console.log('Author: Muntasir Al Mamun (@Muntasir-Mamun7)');
    console.log('Date: 2025-11-03');
    console.log('='.repeat(70));
    
    // Check if we're on an auth page
    const currentPage = window.location.pathname;
    const isAuthPage = currentPage.includes('login.html') || currentPage.includes('register.html');
    
    if (isAuthPage) {
        console.log('On authentication page, skipping auth check');
        return; // Don't check auth on login/register pages
    }
    
    // IMPORTANT: Check authentication FIRST before loading anything
    if (!checkAuthentication()) {
        console.log('Authentication failed, stopping initialization');
        return; // Stop execution if not authenticated
    }
    
    console.log('Authentication verified, loading dashboard...');
    
    // Initialize the dashboard
    populateFlightList();
    checkActiveFlights();
    refreshContracts();
    
    // Set up periodic updates
    setInterval(() => {
        checkActiveFlights();
        refreshContracts();
    }, 5000); // Update every 5 seconds
    
    console.log('Dashboard initialized');
});