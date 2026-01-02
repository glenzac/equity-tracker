# Equity Tracker

A Python Flask-based web application for tracking equity stock portfolios with support for:

- Unit-level allocation to owners and goals
- Automatic FIFO-based P&L calculation
- Hybrid import from Zerodha Tradebook and Tax P&L with corporate action detection
- Real-time price fetching and unrealized P&L tracking
- Multi-account portfolio management
- Financial year-wise reporting and analytics

## Setup

### Prerequisites
- **Python 3.11+**

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/equity-tracker.git
    cd equity-tracker
    ```

2.  **Create and Activate Virtual Environment**:
    *   **Windows (PowerShell)**:
        ```powershell
        python -m venv venv
        .\venv\Scripts\Activate.ps1
        ```
    *   **Linux/Mac**:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Database Setup**:
    Initialize the database with the pre-configured schema:
    ```bash
    flask db upgrade
    ```
    *Note: You do NOT need to run `flask db init` or `migrate` unless you are developing and modifying the database models.*

5.  **Environment Variables**:
    Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
    (On Windows: `Copy-Item .env.example .env`)
    
    Edit `.env` to set your `SECRET_KEY` (required for Flask session security).
    *(Your .env already has a default development key)*.

## Usage

### Running the Application
```bash
flask run
```
Access the application at `http://127.0.0.1:5000`.

### Importing Data
1.  Navigate to the "Import" section.
2.  Select your broker and upload your Tradebook and Tax P&L files.
3.  The system will parse and reconcile trades.

## Platform Notes
- **Windows**: This application is fully compatible with Windows. Use PowerShell for best experience.
- **Linux/Mac**: Fully compatible.

## Core Concepts

### FIFO (First-In-First-Out)
Stocks purchased first are sold first. This is mandatory in India for tax calculations.

**Example:**
```
Buy 50 units @ ₹100 on Jan 1
Buy 50 units @ ₹120 on Feb 1
Sell 30 units @ ₹150 on Mar 1

FIFO matching:
- 30 units sold are matched to Jan 1 purchase @ ₹100
- Profit = 30 × (₹150 - ₹100) = ₹1,500
- Remaining: 20 units @ ₹100 + 50 units @ ₹120
```

### Tax Terms (India)
- **STCG (Short Term Capital Gains)**: Holding period ≤ 12 months
- **LTCG (Long Term Capital Gains)**: Holding period > 12 months

### Financial Year (India)
- Runs from April 1 to March 31
- Example: FY 2024-25 = April 1, 2024 to March 31, 2025

### Unit-Level Allocation
Each stock holding can be split into allocations with:
- Fixed buy price (locked at allocation time)
- Assigned owner
- Assigned goal
- Quantity of units

## Technology Stack

### Backend
- **Framework**: Flask 2.x
- **Database**: SQLite (development)
- **ORM**: SQLAlchemy
- **Migrations**: Flask-Migrate (Alembic)
- **Excel Parsing**: pandas, openpyxl
- **Price API**: yfinance

### Frontend
- **Templates**: Jinja2
- **CSS**: Bootstrap 5
- **Charts**: Chart.js
- **Tables**: DataTables.js (for pivot/filtering)
- **Icons**: Bootstrap Icons or Font Awesome

## Future Enhancements

1. **Multi-broker Support**: Add parsers for Groww, Upstox, Angel, etc.
2. **Mutual Funds**: Extend to track mutual fund investments
3. **Tax Reports**: Generate ITR-compatible capital gains reports
4. **Alerts**: Price alerts, goal progress notifications
5. **Performance Analytics**: XIRR, benchmark comparison
6. **Dividend Tracking**: Track dividend income

## Design Constraints & Caveats

### Price Updates & Caching
To avoid hitting Yahoo Finance API rate limits, stock prices are cached server-side:
- **Market Hours** (09:15 - 15:30 IST): Prices update every **5 minutes**.
- **Off-Market Hours**: Prices update every **1 hour**.
- **Force Refresh**: Restarting the application clears the cache.

### Data Limitations (YFinance)
This application uses the `yfinance` library, which relies on Yahoo Finance's public API.
- **Unofficial API**: This is not a production-grade feed. It may effectively stop working if Yahoo changes their API signature.
- **Delayed Data**: Live prices may be delayed by 1-15 minutes.
- **Rate Limits**: Excessive refreshing may cause temporary IP bans from Yahoo.

### File Support
- Currently optimized for **Zerodha** tradebook and P&L Excel formats.


## Development
- **Database Migrations**:
    - If you change `models/*.py`, run:
        ```bash
        flask db migrate -m "Description of change"
        flask db upgrade
        ```

## License
[GPL-3.0](LICENSE)
