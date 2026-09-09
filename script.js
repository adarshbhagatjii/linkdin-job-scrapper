// Configuration
const API_URL = 'http://localhost:8000/jobs';
let jobsData = null;
let chart = null;

// DOM Elements
const skillInput = document.getElementById('skill-input');
const locationInput = document.getElementById('location-input');
const searchBtn = document.getElementById('search-btn');
const loadingSpinner = document.getElementById('loading-spinner');
const errorAlert = document.getElementById('error-alert');
const successAlert = document.getElementById('success-alert');
const metricsSection = document.getElementById('metrics-section');
const tabsSection = document.getElementById('tabs-section');
const emptyState = document.getElementById('empty-state');
const jobsContainer = document.getElementById('jobs-container');
const companyFilter = document.getElementById('company-filter');
const infoBar = document.getElementById('info-bar');
const tabButtons = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');
const quickButtons = document.querySelectorAll('.btn[data-search]');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadDefaultSearch();
});

function loadDefaultSearch() {
    // Auto-load with default values
    if (skillInput.value && locationInput.value) {
        setTimeout(() => {
            performSearch();
        }, 300);
    }
}

function setupEventListeners() {
    searchBtn.addEventListener('click', performSearch);
    skillInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });
    locationInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    quickButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const [skill, location] = btn.dataset.search.split(', ');
            skillInput.value = skill;
            locationInput.value = location;
            performSearch();
        });
    });

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            switchTab(tabId);
        });
    });

    companyFilter.addEventListener('change', () => {
        displayJobList();
    });
}

/**
 * Perform job search
 */
async function performSearch() {
    const skill = skillInput.value.trim();
    const location = locationInput.value.trim();

    if (!skill || !location) {
        showError('⚠️ Please enter both skill and location');
        return;
    }

    await fetchJobs(skill, location);
}

/**
 * Fetch jobs from API
 */
async function fetchJobs(skill, location) {
    showLoading(true, `🔍 Searching for ${skill} jobs in ${location}...`);
    clearAlerts();

    try {
        const response = await fetch(
            `${API_URL}?skill=${encodeURIComponent(skill)}&location=${encodeURIComponent(location)}`,
            {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            }
        );

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        if (data.success && data.totalJobs > 0) {
            jobsData = data;
            showSuccess(`✅ Found ${data.totalJobs} amazing jobs!`);
            displayResults();
        } else {
            showError(data.message || '😔 No jobs found. Try a different search');
            hideResults();
        }
    } catch (error) {
        console.error('Error fetching jobs:', error);
        showError(`❌ Error: ${error.message}`);
        hideResults();
    } finally {
        showLoading(false);
    }
}

/**
 * Display search results
 */
function displayResults() {
    emptyState.classList.add('hidden');
    metricsSection.classList.remove('hidden');
    tabsSection.classList.remove('hidden');

    // Update metrics
    document.getElementById('total-jobs').textContent = jobsData.totalJobs.toLocaleString();
    document.getElementById('metric-skill').textContent = jobsData.searchCriteria.keyword;
    document.getElementById('metric-location').textContent = jobsData.searchCriteria.location;

    // Update company filter
    updateCompanyFilter();

    // Display jobs
    displayJobList();

    // Display analytics
    displayAnalytics();

    // Scroll to results on mobile
    if (window.innerWidth <= 768) {
        metricsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/**
 * Hide search results
 */
function hideResults() {
    emptyState.classList.remove('hidden');
    metricsSection.classList.add('hidden');
    tabsSection.classList.add('hidden');
    jobsData = null;
}

/**
 * Update company filter dropdown
 */
function updateCompanyFilter() {
    const companies = [...new Set(
        jobsData.jobs
            .map(job => job.company)
            .filter(company => company && company.length > 0)
    )].sort();
    
    companyFilter.innerHTML = '<option value="">All Companies (' + companies.length + ')</option>';

    if (companies.length === 0) {
        companyFilter.innerHTML += '<option disabled>No companies available</option>';
        return;
    }

    companies.forEach(company => {
        const option = document.createElement('option');
        option.value = company;
        option.textContent = company;
        companyFilter.appendChild(option);
    });
}

/**
 * Display job list
 */
function displayJobList() {
    jobsContainer.innerHTML = '';

    if (!jobsData || !jobsData.jobs || jobsData.jobs.length === 0) {
        jobsContainer.innerHTML = '<p style="text-align: center; color: #999; padding: 2rem;">No jobs available</p>';
        return;
    }

    let filteredJobs = jobsData.jobs;
    const selectedCompany = companyFilter.value;

    if (selectedCompany) {
        filteredJobs = filteredJobs.filter(job => job.company === selectedCompany);
    }

    infoBar.textContent = `📊 Showing ${filteredJobs.length} of ${jobsData.totalJobs} jobs`;

    if (filteredJobs.length === 0) {
        jobsContainer.innerHTML = '<p style="text-align: center; color: #999; padding: 2rem;">No jobs found for this company filter</p>';
        return;
    }

    filteredJobs.forEach((job, index) => {
        const jobCard = createJobCard(job, index);
        jobsContainer.appendChild(jobCard);
    });
}

/**
 * Create job card element
 */
function createJobCard(job, index) {
    const card = document.createElement('div');
    card.className = 'job-card';
    card.style.animationDelay = `${index * 50}ms`;

    // Ensure data exists and provide defaults
    const title = job.title || 'Job Title Not Available';
    const company = job.company || 'Company Not Specified';
    const location = job.location || 'Location Not Specified';
    const postedDate = job.postedDate || 'Posted Recently';

    const titleDiv = document.createElement('div');
    titleDiv.className = 'job-title';
    titleDiv.textContent = title;

    const companyDiv = document.createElement('div');
    companyDiv.className = 'job-company';
    companyDiv.textContent = company;

    const locationDiv = document.createElement('div');
    locationDiv.className = 'job-location';
    locationDiv.textContent = `📍 ${location}`;

    const dateDiv = document.createElement('div');
    dateDiv.className = 'job-posted';
    dateDiv.textContent = `📅 ${postedDate}`;

    card.appendChild(titleDiv);
    card.appendChild(companyDiv);
    card.appendChild(locationDiv);
    card.appendChild(dateDiv);

    // Only add link if it exists and is valid
    if (job.applyLink && job.applyLink.length > 0) {
        const link = document.createElement('a');
        link.href = job.applyLink;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.className = 'job-link';
        link.textContent = '🔗 Apply Now';
        card.appendChild(link);
    }

    return card;
}

/**
 * Display analytics
 */
function displayAnalytics() {
    if (!jobsData || !jobsData.jobs || jobsData.jobs.length === 0) {
        document.getElementById('chart-container').innerHTML = '<p style="text-align: center; padding: 2rem;">No data available for analytics</p>';
        return;
    }

    // Count jobs by company
    const companyCount = {};
    jobsData.jobs.forEach(job => {
        const company = job.company || 'Unknown';
        companyCount[company] = (companyCount[company] || 0) + 1;
    });

    // Get top 10 companies
    const topCompanies = Object.entries(companyCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 12);

    const labels = topCompanies.map(([company]) => company.length > 20 ? company.substring(0, 20) + '...' : company);
    const data = topCompanies.map(([, count]) => count);

    // Destroy existing chart if it exists
    if (chart) {
        chart.destroy();
    }

    // Create new chart
    const chartCanvas = document.getElementById('companiesChart');
    
    if (!chartCanvas) {
        console.error('Chart canvas not found');
        return;
    }

    const ctx = chartCanvas.getContext('2d');

    chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Number of Jobs',
                data: data,
                backgroundColor: [
                    '#667eea',
                    '#764ba2',
                    '#5568dd',
                    '#6a3f96',
                    '#4d5cd1',
                    '#7a3fa0',
                    '#5a6bd4',
                    '#6c429a',
                    '#536cca',
                    '#75459e',
                    '#5a73d2',
                    '#6d4899'
                ],
                borderColor: 'rgba(255, 255, 255, 0.2)',
                borderWidth: 2,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        font: { size: 12, weight: '600' },
                        padding: 15,
                        color: '#333'
                    }
                },
                title: {
                    display: true,
                    text: 'Top Companies by Job Count',
                    font: { size: 14, weight: '700' },
                    color: '#333',
                    padding: { bottom: 20 }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                        font: { size: 11 },
                        color: '#666'
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                y: {
                    ticks: {
                        font: { size: 11 },
                        color: '#666'
                    },
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

/**
 * Switch between tabs
 */
function switchTab(tabId) {
    // Remove active class from all buttons and contents
    tabButtons.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(content => content.classList.remove('active'));

    // Add active class to selected button and content
    const activeBtn = document.querySelector(`[data-tab="${tabId}"]`);
    const activeContent = document.getElementById(tabId);

    if (activeBtn) activeBtn.classList.add('active');
    if (activeContent) {
        activeContent.classList.add('active');
        // Re-render chart if switching to analytics tab
        if (tabId === 'analytics' && chart) {
            setTimeout(() => chart.resize(), 100);
        }
    }
}

/**
 * Show loading spinner
 */
function showLoading(show, message = 'Loading...') {
    if (show) {
        loadingSpinner.classList.remove('hidden');
        document.getElementById('loading-message').textContent = message;
        searchBtn.disabled = true;
    } else {
        loadingSpinner.classList.add('hidden');
        searchBtn.disabled = false;
    }
}

/**
 * Show error alert
 */
function showError(message) {
    errorAlert.textContent = message;
    errorAlert.classList.remove('hidden');
    setTimeout(() => {
        errorAlert.classList.add('hidden');
    }, 6000);
}

/**
 * Show success alert
 */
function showSuccess(message) {
    successAlert.textContent = message;
    successAlert.classList.remove('hidden');
    setTimeout(() => {
        successAlert.classList.add('hidden');
    }, 4000);
}

/**
 * Clear all alerts
 */
function clearAlerts() {
    errorAlert.classList.add('hidden');
    successAlert.classList.add('hidden');
}
