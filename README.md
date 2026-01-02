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

## Development
- **Database Migrations**:
    - If you change `models/*.py`, run:
        ```bash
        flask db migrate -m "Description of change"
        flask db upgrade
        ```

## License
[GPL-3.0](LICENSE)
