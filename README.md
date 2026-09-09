# LinkedIn Job Scraper

A modern web application for searching and discovering job opportunities on LinkedIn. This application consists of a FastAPI backend for web scraping and an HTML/CSS/JavaScript frontend for a smooth user experience.

## Features

✨ **Key Features:**
- 🔍 Search jobs by skill/title and location
- 📊 View analytics on top hiring companies
- 🏢 Filter jobs by company
- 💾 Quick search suggestions
- 📱 Responsive design (desktop, tablet, mobile)
- ⚡ Fast and intuitive interface
- 🔗 Direct apply links to LinkedIn jobs

## Project Structure

```
job-finder/
├── index.html          # Main HTML file (frontend)
├── styles.css          # CSS styling and responsive design
├── script.js           # JavaScript for frontend functionality
├── app.py              # FastAPI backend for scraping
├── requirements.txt    # Python dependencies
├── run.sh             # Script to run the application
└── README.md          # This file
```

## Technology Stack

### Backend
- **FastAPI** - Modern web framework for building APIs
- **Uvicorn** - ASGI server for running FastAPI
- **Playwright** - Browser automation for web scraping
- **Pydantic** - Data validation using Python type hints

### Frontend
- **HTML5** - Semantic markup
- **CSS3** - Modern styling with responsive design
- **JavaScript (Vanilla)** - Interactive features
- **Chart.js** - Data visualization for analytics

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Clone/Navigate to Project
```bash
cd /Users/adarshbhagat/Desktop/job-finder
```

### Step 2: Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Install Playwright Browsers
```bash
playwright install chromium
```

## Running the Application

### Method 1: Using the Run Script
```bash
chmod +x run.sh
./run.sh
```

### Method 2: Manual Start

**Terminal 1 - Start the Backend API:**
```bash
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Start the Frontend Server:**
```bash
cd /Users/adarshbhagat/Desktop/job-finder
python3 -m http.server 8080
```

### Access the Application
- **Frontend**: http://localhost:8080
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Usage Guide

### Basic Search
1. Enter a job title or skill in the "Skill / Job Title" field
2. Enter a location in the "Location" field
3. Click "🔍 Search Jobs" button
4. Results will appear with job cards showing:
   - Job title
   - Company name
   - Location
   - Posted date
   - Apply link

### Quick Searches
Click any of the pre-defined quick search buttons for popular searches:
- Python, Bangalore
- Data Scientist, Noida
- React, New York
- Java, Singapore
- DevOps, London

### Filter Jobs
Use the "Filter by Company" dropdown to narrow down results to a specific company.

### View Analytics
Click the "📊 Analytics" tab to see:
- Top 10 companies by job count
- Visual bar chart representation

## API Endpoints

### 1. Root Endpoint
```
GET /
```
Returns API information and usage instructions.

### 2. Jobs Search
```
GET /jobs?skill=<skill>&location=<location>&mock=<true|false>
```

**Parameters:**
- `skill` (required): Job title or skill to search for
- `location` (required): Location to search in
- `mock` (optional): Set to `true` to use mock data (for testing)

**Response Example:**
```json
{
  "success": true,
  "totalJobs": 5,
  "jobs": [
    {
      "id": "job_1",
      "title": "Senior Python Developer",
      "company": "Tech Corp",
      "location": "Bangalore",
      "postedDate": "1 week ago",
      "url": "https://linkedin.com/jobs/view/123456",
      "applyLink": "https://linkedin.com/jobs/view/123456"
    }
  ],
  "searchCriteria": {
    "skill": "Python",
    "location": "Bangalore"
  },
  "message": "Successfully fetched 5 jobs"
}
```

### 3. Health Check
```
GET /health
```
Returns API health status.

## Testing

### Test with Mock Data
To test the frontend without scraping LinkedIn (which may require authentication):

1. Open http://localhost:8080
2. Frontend is configured to use mock data by default (in script.js: `USE_MOCK = true`)
3. Perform a search to see mock job results

### Test with Real LinkedIn Data
To scrape real job data from LinkedIn:

1. Edit `script.js` and set `USE_MOCK = false`
2. Ensure you're not behind a proxy or firewall
3. Note: LinkedIn may require authentication or rate limiting may apply

## Troubleshooting

### Issue: "address already in use" on port 8000
**Solution:** Kill the existing process:
```bash
lsof -i :8000
kill -9 <PID>
```

### Issue: CORS errors in browser console
**Solution:** The backend has CORS enabled for all origins. If issues persist:
- Clear browser cache
- Hard refresh (Cmd+Shift+R on Mac)
- Check that both servers are running

### Issue: No jobs found when searching
**Possible Causes:**
1. LinkedIn may require authentication
2. Rate limiting may be applied
3. Internet connection issue
4. Search criteria too specific

**Solution:**
- Use mock data for testing (set `USE_MOCK = true`)
- Try broader search terms
- Check internet connectivity

### Issue: Playwright browser crashes
**Solution:**
1. Reinstall Playwright browsers:
```bash
playwright install chromium --with-deps
```
2. Check available disk space
3. Ensure system meets minimum requirements

## Configuration

### Enable/Disable Mock Data
Edit `script.js`:
```javascript
const USE_MOCK = true; // Set to false for real LinkedIn data
```

### Change API Port
Edit `app.py` and run command:
```bash
uvicorn app:app --host 0.0.0.0 --port 9000
```

### Change Frontend Port
```bash
python3 -m http.server 8081
```

## Performance Optimizations

1. **Frontend:**
   - CSS animations are GPU-accelerated
   - Chart.js for efficient data visualization
   - Lazy loading of images

2. **Backend:**
   - Blocking unnecessary resources (CSS, fonts, images)
   - Asynchronous operations with asyncio
   - Efficient Playwright usage

## Security Considerations

1. **Input Validation:**
   - All user inputs are validated on both frontend and backend
   - SQL injection prevention (Pydantic models)

2. **CORS:**
   - CORS is enabled for development
   - Restrict origins in production

3. **API Rate Limiting:**
   - Consider implementing rate limiting for production

## Future Enhancements

- [ ] User authentication and saved searches
- [ ] Email notifications for new jobs
- [ ] Advanced filtering (salary range, experience level, etc.)
- [ ] Job application tracking
- [ ] Dark mode
- [ ] Export to CSV/Excel
- [ ] Database integration for job caching
- [ ] Webhook support

## Contributing

To contribute to this project:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and personal use only. Users are responsible for complying with LinkedIn's Terms of Service and local laws regarding web scraping. The authors assume no liability for misuse.

## Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review API documentation at `/docs` endpoint

## Changelog

### Version 1.0.0 (Initial Release)
- ✅ Complete HTML/CSS/JavaScript frontend
- ✅ FastAPI backend with LinkedIn scraping
- ✅ Job filtering and analytics
- ✅ Responsive design
- ✅ Mock data for testing
- ✅ CORS support
- ✅ Error handling

---

**Made with ❤️ for job seekers everywhere**
