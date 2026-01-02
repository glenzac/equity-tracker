/**
 * Equity Tracker - Main JavaScript Application
 */

const API_BASE = '/api/v1';

// Table Sorting Utility
const TableSorter = {
    // Store sort state per table
    sortState: {},

    /**
     * Initialize sortable table headers
     * @param {string} tableId - The table's ID or unique identifier
     * @param {Array} columns - Array of column configs: {key, type, defaultSort?}
     *                          type: 'string', 'number', 'currency', 'date', 'percent'
     * @param {Array} data - The data array to sort
     * @param {Function} renderCallback - Function to call after sorting with sorted data
     */
    init(tableId, columns, data, renderCallback) {
        this.sortState[tableId] = {
            column: null,
            direction: 'asc',
            columns: columns,
            data: data,
            renderCallback: renderCallback
        };
    },

    /**
     * Generate sortable table header HTML
     * @param {string} tableId - Table identifier
     * @param {Array} headers - Array of {key, label, class?} objects
     */
    renderHeaders(tableId, headers) {
        const state = this.sortState[tableId];
        return headers.map(h => {
            const isSorted = state && state.column === h.key;
            const arrow = isSorted ? (state.direction === 'asc' ? ' <i class="bi bi-caret-up-fill"></i>' : ' <i class="bi bi-caret-down-fill"></i>') : ' <i class="bi bi-caret-up-fill text-muted opacity-25"></i>';
            const sortable = h.sortable !== false;
            return `<th class="${h.class || ''}" ${sortable ? `style="cursor: pointer; user-select: none;" onclick="TableSorter.sort('${tableId}', '${h.key}')"` : ''}>
                ${h.label}${sortable ? arrow : ''}
            </th>`;
        }).join('');
    },

    /**
     * Sort the table data by a column
     */
    sort(tableId, columnKey) {
        const state = this.sortState[tableId];
        if (!state) return;

        // Toggle direction if same column, otherwise default to asc
        if (state.column === columnKey) {
            state.direction = state.direction === 'asc' ? 'desc' : 'asc';
        } else {
            state.column = columnKey;
            state.direction = 'asc';
        }

        // Find column config
        const colConfig = state.columns.find(c => c.key === columnKey);
        if (!colConfig) return;

        // Sort the data
        const sorted = [...state.data].sort((a, b) => {
            let valA = this.getValue(a, columnKey);
            let valB = this.getValue(b, columnKey);

            // Handle null/undefined
            if (valA === null || valA === undefined) valA = '';
            if (valB === null || valB === undefined) valB = '';

            let comparison = 0;

            switch (colConfig.type) {
                case 'number':
                case 'currency':
                case 'percent':
                    comparison = (parseFloat(valA) || 0) - (parseFloat(valB) || 0);
                    break;
                case 'date':
                    comparison = new Date(valA) - new Date(valB);
                    break;
                case 'string':
                default:
                    comparison = String(valA).localeCompare(String(valB));
            }

            return state.direction === 'asc' ? comparison : -comparison;
        });

        // Update data and trigger re-render
        state.data = sorted;
        if (state.renderCallback) {
            state.renderCallback(sorted);
        }
    },

    /**
     * Get nested value from object using dot notation
     */
    getValue(obj, key) {
        return key.split('.').reduce((o, k) => (o || {})[k], obj);
    },

    /**
     * Update the data for a table (call when data changes)
     */
    updateData(tableId, data) {
        if (this.sortState[tableId]) {
            this.sortState[tableId].data = data;
            // Re-apply current sort if exists
            if (this.sortState[tableId].column) {
                this.sort(tableId, this.sortState[tableId].column);
                // Toggle direction back since sort() toggles it
                this.sortState[tableId].direction =
                    this.sortState[tableId].direction === 'asc' ? 'desc' : 'asc';
                this.sort(tableId, this.sortState[tableId].column);
            }
        }
    }
};

// Utility functions
const Utils = {
    /**
     * Escape HTML special characters to prevent XSS
     * @param {string} str - String to escape
     * @returns {string} - Escaped string safe for HTML insertion
     */
    escapeHtml(str) {
        if (str === null || str === undefined) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    formatCurrency(value, showSymbol = true) {
        if (value === null || value === undefined) return '--';
        const formatted = new Intl.NumberFormat('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(Math.abs(value));
        const sign = value < 0 ? '-' : '';
        return showSymbol ? `${sign}\u20B9${formatted}` : `${sign}${formatted}`;
    },

    formatPercent(value) {
        if (value === null || value === undefined) return '--';
        const sign = value >= 0 ? '+' : '';
        return `${sign}${value.toFixed(2)}%`;
    },

    formatNumber(value) {
        if (value === null || value === undefined) return '--';
        return new Intl.NumberFormat('en-IN').format(value);
    },

    getPnlClass(value) {
        if (value === null || value === undefined) return '';
        return value >= 0 ? 'text-profit' : 'text-loss';
    },

    showLoading(container) {
        container.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        `;
    },

    showError(container, message) {
        container.innerHTML = `
            <div class="alert alert-danger">${message}</div>
        `;
    },

    showEmpty(container, message) {
        container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="bi bi-inbox display-1"></i>
                <p class="mt-3">${message}</p>
            </div>
        `;
    }
};

// API Client
const API = {
    async get(endpoint) {
        const response = await fetch(`${API_BASE}${endpoint}`);
        const data = await response.json();
        if (data.status === 'error') {
            throw new Error(data.message);
        }
        return data.data;
    },

    async post(endpoint, body) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();
        if (data.status === 'error') {
            throw new Error(data.message);
        }
        return data.data;
    },

    async put(endpoint, body) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await response.json();
        if (data.status === 'error') {
            throw new Error(data.message);
        }
        return data.data;
    },

    async delete(endpoint) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        if (data.status === 'error') {
            throw new Error(data.message);
        }
        return data.data;
    },

    async upload(endpoint, formData) {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (data.status === 'error') {
            throw new Error(data.message);
        }
        return data.data;
    }
};

// Dashboard Module
const Dashboard = {
    sectorChart: null,
    fyPnlChart: null,
    holdingsData: [],

    // Column config for sorting
    holdingsColumns: [
        { key: 'symbol', type: 'string' },
        { key: 'quantity', type: 'number' },
        { key: 'avg_buy_price', type: 'currency' },
        { key: 'current_price', type: 'currency' },
        { key: 'current_value', type: 'currency' },
        { key: 'unrealized_pnl', type: 'currency' },
        { key: 'unrealized_pnl_percent', type: 'percent' }
    ],

    holdingsHeaders: [
        { key: 'symbol', label: 'Stock' },
        { key: 'quantity', label: 'Qty', class: 'text-end' },
        { key: 'avg_buy_price', label: 'Avg Price', class: 'text-end' },
        { key: 'current_price', label: 'Current', class: 'text-end' },
        { key: 'current_value', label: 'Value', class: 'text-end' },
        { key: 'unrealized_pnl', label: 'P&L', class: 'text-end' },
        { key: 'unrealized_pnl_percent', label: '%', class: 'text-end' }
    ],

    async init() {
        // Load dashboard data immediately
        await Promise.all([
            this.loadSummary(),
            this.loadHoldings(),
            this.loadSectorChart(),
            this.loadPnlChart(),
            this.loadFilters()
        ]);

        // Refresh prices in background (don't block dashboard load)
        this.refreshPricesInBackground();
    },

    async refreshPricesInBackground() {
        try {
            await API.post('/portfolio/prices/refresh', {});
            // Prices refreshed in background - next user action will show updated prices
        } catch (error) {
            console.log('Background price refresh failed:', error.message);
        }
    },

    async refreshPrices() {
        try {
            await API.post('/portfolio/prices/refresh', {});
        } catch (error) {
            console.log('Price refresh failed:', error.message);
        }
    },

    async loadSummary() {
        try {
            const summary = await API.get('/portfolio/summary');

            document.getElementById('total-value').textContent =
                Utils.formatCurrency(summary.total_current_value);
            document.getElementById('total-invested').textContent =
                Utils.formatCurrency(summary.total_buy_value);

            const pnlEl = document.getElementById('unrealized-pnl');
            const pnlClass = Utils.getPnlClass(summary.total_unrealized_pnl);
            pnlEl.innerHTML = `
                ${Utils.formatCurrency(summary.total_unrealized_pnl)}
                <span class="metric-pill ${pnlClass}">${Utils.formatPercent(summary.total_unrealized_pnl_percent)}</span>
            `;
            pnlEl.className = `metric-value ${pnlClass}`;

        } catch (error) {
            console.error('Error loading summary:', error);
        }
    },

    async loadHoldings() {
        try {
            const data = await API.get('/portfolio/holdings');
            const table = document.querySelector('#holdings-table');
            const thead = table.querySelector('thead tr');
            const tbody = table.querySelector('tbody');

            if (data.holdings.length === 0) {
                thead.innerHTML = this.holdingsHeaders.map(h => `<th class="${h.class || ''}">${h.label}</th>`).join('');
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center text-muted">
                            No holdings yet. <a href="/import">Import data</a> to get started.
                        </td>
                    </tr>
                `;
                return;
            }

            // Store holdings, sort alphabetically, and initialize sorter
            this.holdingsData = data.holdings
                .sort((a, b) => a.symbol.localeCompare(b.symbol))
                .slice(0, 10);
            TableSorter.init('dashboard-holdings', this.holdingsColumns, this.holdingsData, (sorted) => {
                this.renderHoldingsTable(sorted);
            });

            // Render headers and rows
            thead.innerHTML = TableSorter.renderHeaders('dashboard-holdings', this.holdingsHeaders);
            this.renderHoldingsTable(this.holdingsData);
        } catch (error) {
            console.error('Error loading holdings:', error);
        }
    },

    renderHoldingsTable(holdings) {
        const tbody = document.querySelector('#holdings-table tbody');
        tbody.innerHTML = holdings.map(h => `
            <tr onclick="window.location='/portfolio/${parseInt(h.stock_id)}'" style="cursor: pointer;">
                <td>
                    <strong>${Utils.escapeHtml(h.symbol)}</strong>
                    <br><small class="text-muted">${Utils.escapeHtml(h.stock_name || '')}</small>
                </td>
                <td class="text-end">${Utils.formatNumber(h.quantity)}</td>
                <td class="text-end">${Utils.formatCurrency(h.avg_buy_price)}</td>
                <td class="text-end">${Utils.formatCurrency(h.current_price)}</td>
                <td class="text-end">${Utils.formatCurrency(h.current_value || h.total_buy_value)}</td>
                <td class="text-end ${Utils.getPnlClass(h.unrealized_pnl)}">${Utils.formatCurrency(h.unrealized_pnl)}</td>
                <td class="text-end ${Utils.getPnlClass(h.unrealized_pnl_percent)}">${Utils.formatPercent(h.unrealized_pnl_percent)}</td>
            </tr>
        `).join('');
    },

    async loadSectorChart() {
        try {
            const data = await API.get('/portfolio/sector-allocation');
            const ctx = document.getElementById('sector-chart');
            if (!ctx) return;

            if (this.sectorChart) {
                this.sectorChart.destroy();
            }

            // Distinct color palette for sectors - each color is visually different
            const colors = [
                '#3B82F6', // Blue
                '#10B981', // Emerald
                '#F59E0B', // Amber
                '#EF4444', // Red
                '#8B5CF6', // Violet
                '#EC4899', // Pink
                '#06B6D4', // Cyan
                '#F97316', // Orange
                '#14B8A6', // Teal
                '#6366F1', // Indigo
                '#84CC16', // Lime
                '#A855F7', // Purple
                '#22D3EE', // Sky
                '#FB7185', // Rose
                '#FBBF24', // Yellow
            ];

            this.sectorChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.allocations.map(s => s.sector),
                    datasets: [{
                        data: data.allocations.map(s => s.value),
                        backgroundColor: colors.slice(0, data.allocations.length),
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    layout: {
                        padding: 10
                    },
                    plugins: {
                        legend: {
                            position: 'right',
                            align: 'center',
                            labels: {
                                font: {
                                    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                    size: 12
                                },
                                color: '#475569',
                                padding: 10,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                boxWidth: 8
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1E293B',
                            titleFont: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                size: 12
                            },
                            padding: 10,
                            cornerRadius: 6,
                            callbacks: {
                                label: (context) => {
                                    const value = Utils.formatCurrency(context.raw);
                                    const pct = data.allocations[context.dataIndex].percentage.toFixed(1);
                                    return `${context.label}: ${value} (${pct}%)`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error loading sector chart:', error);
        }
    },

    async loadPnlChart() {
        try {
            const data = await API.get('/portfolio/pnl/summary');
            const ctx = document.getElementById('fy-pnl-chart');
            if (!ctx) return;

            if (this.fyPnlChart) {
                this.fyPnlChart.destroy();
            }

            const summary = data.summary || [];

            // Color helper: green for profit, red for loss
            // STCG: lighter shade, LTCG: darker shade
            const stcgProfitColor = '#22C55E';  // Green 500 (lighter)
            const stcgLossColor = '#EF4444';    // Red 500 (lighter)
            const ltcgProfitColor = '#15803D';  // Green 700 (darker)
            const ltcgLossColor = '#B91C1C';    // Red 700 (darker)

            const getStcgColor = (value) => value >= 0 ? stcgProfitColor : stcgLossColor;
            const getLtcgColor = (value) => value >= 0 ? ltcgProfitColor : ltcgLossColor;

            this.fyPnlChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: summary.map(s => s.financial_year),
                    datasets: [
                        {
                            label: 'STCG (Short Term)',
                            data: summary.map(s => s.stcg),
                            backgroundColor: summary.map(s => getStcgColor(s.stcg)),
                            borderRadius: 4,
                            borderWidth: 0
                        },
                        {
                            label: 'LTCG (Long Term)',
                            data: summary.map(s => s.ltcg),
                            backgroundColor: summary.map(s => getLtcgColor(s.ltcg)),
                            borderRadius: 4,
                            borderWidth: 2,
                            borderColor: summary.map(s => s.ltcg >= 0 ? '#166534' : '#991B1B'),
                            borderSkipped: false
                        }
                    ]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            labels: {
                                font: {
                                    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                    size: 12
                                },
                                color: '#475569',
                                usePointStyle: true,
                                pointStyle: 'rect'
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1E293B',
                            titleFont: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                size: 12
                            },
                            padding: 10,
                            cornerRadius: 6,
                            callbacks: {
                                label: (context) => {
                                    const value = context.raw;
                                    const prefix = value >= 0 ? 'Profit' : 'Loss';
                                    return `${context.dataset.label} (${prefix}): ${Utils.formatCurrency(Math.abs(value))}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                font: {
                                    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                    size: 11
                                },
                                color: '#64748B'
                            }
                        },
                        y: {
                            grid: {
                                color: '#E2E8F0'
                            },
                            ticks: {
                                font: {
                                    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                    size: 11
                                },
                                color: '#64748B',
                                callback: (value) => Utils.formatCurrency(value, false)
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error loading P&L chart:', error);
        }
    },

    filters: {
        owner: '',
        goal: '',
        account: ''
    },

    async loadFilters() {
        try {
            const [owners, goals, accounts] = await Promise.all([
                API.get('/settings/owners'),
                API.get('/settings/goals'),
                API.get('/settings/accounts')
            ]);

            const ownerFilter = document.getElementById('owner-filter');
            if (ownerFilter) {
                ownerFilter.innerHTML = `
                    <option value="">All Owners</option>
                    ${owners.owners.map(o => `<option value="${parseInt(o.id)}">${Utils.escapeHtml(o.name)}</option>`).join('')}
                `;
                ownerFilter.addEventListener('change', () => this.applyFilters());
            }

            const goalFilter = document.getElementById('goal-filter');
            if (goalFilter) {
                goalFilter.innerHTML = `
                    <option value="">All Goals</option>
                    ${goals.goals.map(g => `<option value="${parseInt(g.id)}">${Utils.escapeHtml(g.name)}</option>`).join('')}
                `;
                goalFilter.addEventListener('change', () => this.applyFilters());
            }

            const accountFilter = document.getElementById('account-filter');
            if (accountFilter) {
                accountFilter.innerHTML = `
                    <option value="">All Accounts</option>
                    ${accounts.accounts.map(a => `<option value="${parseInt(a.id)}">${Utils.escapeHtml(a.account_number)}</option>`).join('')}
                `;
                accountFilter.addEventListener('change', () => this.applyFilters());
            }
        } catch (error) {
            console.error('Error loading filters:', error);
        }
    },

    async applyFilters() {
        const ownerFilter = document.getElementById('owner-filter');
        const goalFilter = document.getElementById('goal-filter');
        const accountFilter = document.getElementById('account-filter');

        this.filters.owner = ownerFilter ? ownerFilter.value : '';
        this.filters.goal = goalFilter ? goalFilter.value : '';
        this.filters.account = accountFilter ? accountFilter.value : '';

        // Build query params
        const params = new URLSearchParams();
        if (this.filters.owner) params.append('owner', this.filters.owner);
        if (this.filters.goal) params.append('goal', this.filters.goal);
        if (this.filters.account) params.append('account', this.filters.account);

        const queryString = params.toString();

        // Reload data with filters
        await Promise.all([
            this.loadSummaryFiltered(queryString),
            this.loadHoldingsFiltered(queryString),
            this.loadSectorChartFiltered(queryString)
        ]);
    },

    async loadSummaryFiltered(queryString) {
        try {
            const url = '/portfolio/summary' + (queryString ? '?' + queryString : '');
            const summary = await API.get(url);

            document.getElementById('total-value').textContent =
                Utils.formatCurrency(summary.total_current_value);
            document.getElementById('total-invested').textContent =
                Utils.formatCurrency(summary.total_buy_value);

            const pnlEl = document.getElementById('unrealized-pnl');
            const pnlClass = Utils.getPnlClass(summary.total_unrealized_pnl);
            pnlEl.innerHTML = `
                ${Utils.formatCurrency(summary.total_unrealized_pnl)}
                <span class="metric-pill ${pnlClass}">${Utils.formatPercent(summary.total_unrealized_pnl_percent)}</span>
            `;
            pnlEl.className = `metric-value ${pnlClass}`;
        } catch (error) {
            console.error('Error loading filtered summary:', error);
        }
    },

    async loadHoldingsFiltered(queryString) {
        try {
            const url = '/portfolio/holdings' + (queryString ? '?' + queryString : '');
            const data = await API.get(url);
            const table = document.querySelector('#holdings-table');
            const thead = table.querySelector('thead tr');
            const tbody = table.querySelector('tbody');

            if (data.holdings.length === 0) {
                thead.innerHTML = this.holdingsHeaders.map(h => `<th class="${h.class || ''}">${h.label}</th>`).join('');
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center text-muted">
                            No holdings match the selected filters.
                        </td>
                    </tr>
                `;
                return;
            }

            this.holdingsData = data.holdings
                .sort((a, b) => a.symbol.localeCompare(b.symbol))
                .slice(0, 10);
            TableSorter.init('dashboard-holdings', this.holdingsColumns, this.holdingsData, (sorted) => {
                this.renderHoldingsTable(sorted);
            });

            thead.innerHTML = TableSorter.renderHeaders('dashboard-holdings', this.holdingsHeaders);
            this.renderHoldingsTable(this.holdingsData);
        } catch (error) {
            console.error('Error loading filtered holdings:', error);
        }
    },

    async loadSectorChartFiltered(queryString) {
        try {
            const url = '/portfolio/sector-allocation' + (queryString ? '?' + queryString : '');
            const data = await API.get(url);
            const ctx = document.getElementById('sector-chart');
            if (!ctx) return;

            if (this.sectorChart) {
                this.sectorChart.destroy();
            }

            // Distinct color palette for sectors
            const colors = [
                '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
                '#EC4899', '#06B6D4', '#F97316', '#14B8A6', '#6366F1',
                '#84CC16', '#A855F7', '#22D3EE', '#FB7185', '#FBBF24'
            ];

            this.sectorChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.allocations.map(s => s.sector),
                    datasets: [{
                        data: data.allocations.map(s => s.value),
                        backgroundColor: colors.slice(0, data.allocations.length),
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    layout: {
                        padding: 10
                    },
                    plugins: {
                        legend: {
                            position: 'right',
                            align: 'center',
                            labels: {
                                font: {
                                    family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                    size: 12
                                },
                                color: '#475569',
                                padding: 10,
                                usePointStyle: true,
                                pointStyle: 'circle',
                                boxWidth: 8
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1E293B',
                            titleFont: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                size: 13,
                                weight: '600'
                            },
                            bodyFont: {
                                family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
                                size: 12
                            },
                            padding: 10,
                            cornerRadius: 6,
                            callbacks: {
                                label: (context) => {
                                    const value = Utils.formatCurrency(context.raw);
                                    const pct = data.allocations[context.dataIndex].percentage.toFixed(1);
                                    return `${context.label}: ${value} (${pct}%)`;
                                }
                            }
                        }
                    }
                }
            });
        } catch (error) {
            console.error('Error loading filtered sector chart:', error);
        }
    }
};

// Portfolio Module
const Portfolio = {
    holdings: [],
    filteredHoldings: [],
    summary: null,
    filters: {
        account: '',
        owner: '',
        goal: '',
        sector: '',
        search: ''
    },

    // Column config for sorting
    holdingsColumns: [
        { key: 'symbol', type: 'string' },
        { key: 'stock_name', type: 'string' },
        { key: 'sector_name', type: 'string' },
        { key: 'exchange', type: 'string' },
        { key: 'quantity', type: 'number' },
        { key: 'avg_buy_price', type: 'currency' },
        { key: 'current_price', type: 'currency' },
        { key: 'total_buy_value', type: 'currency' },
        { key: 'current_value', type: 'currency' },
        { key: 'unrealized_pnl', type: 'currency' },
        { key: 'unrealized_pnl_percent', type: 'percent' }
    ],

    holdingsHeaders: [
        { key: 'symbol', label: 'Symbol' },
        { key: 'stock_name', label: 'Name' },
        { key: 'sector_name', label: 'Sector' },
        { key: 'exchange', label: 'Exchange' },
        { key: 'quantity', label: 'Qty', class: 'text-end' },
        { key: 'avg_buy_price', label: 'Avg Price', class: 'text-end' },
        { key: 'current_price', label: 'Current', class: 'text-end' },
        { key: 'total_buy_value', label: 'Invested', class: 'text-end' },
        { key: 'current_value', label: 'Value', class: 'text-end' },
        { key: 'unrealized_pnl', label: 'P&L', class: 'text-end' },
        { key: 'unrealized_pnl_percent', label: '%', class: 'text-end' },
        { key: 'actions', label: '', sortable: false }
    ],

    async init() {
        await this.loadFilters();
        // Load holdings first, then refresh prices in background
        await this.loadHoldings();
        this.bindEvents();
        // Refresh prices in background (won't reload holdings again)
        this.refreshPricesInBackground();
    },

    async refreshPricesInBackground() {
        try {
            await API.post('/portfolio/prices/refresh', {});
            // Only update prices in the UI without full reload
            // The next user action or manual refresh will show updated prices
        } catch (error) {
            console.log('Background price refresh failed:', error.message);
        }
    },

    async loadFilters() {
        try {
            const [accounts, owners, goals, sectors] = await Promise.all([
                API.get('/settings/accounts'),
                API.get('/settings/owners'),
                API.get('/settings/goals'),
                API.get('/settings/sectors')
            ]);

            this.populateSelect('filter-account', accounts.accounts, 'id', 'account_number');
            this.populateSelect('filter-owner', owners.owners, 'id', 'name');
            this.populateSelect('filter-goal', goals.goals, 'id', 'name');
            this.populateSelect('filter-sector', sectors.sectors, 'id', 'name');
        } catch (error) {
            console.error('Error loading filters:', error);
        }
    },

    populateSelect(id, items, valueKey, textKey) {
        const select = document.getElementById(id);
        if (!select) return;

        select.innerHTML = `<option value="">All</option>` +
            items.map(item => `<option value="${Utils.escapeHtml(String(item[valueKey]))}">${Utils.escapeHtml(item[textKey])}</option>`).join('');
    },

    async loadHoldings() {
        const container = document.getElementById('holdings-container');
        if (!container) return;

        Utils.showLoading(container);

        try {
            let endpoint = '/portfolio/holdings?';
            if (this.filters.account) endpoint += `account=${this.filters.account}&`;
            if (this.filters.owner) endpoint += `owner=${this.filters.owner}&`;
            if (this.filters.goal) endpoint += `goal=${this.filters.goal}&`;
            if (this.filters.sector) endpoint += `sector=${this.filters.sector}&`;

            const data = await API.get(endpoint);
            this.holdings = data.holdings;
            this.summary = data.summary;

            if (this.holdings.length === 0) {
                Utils.showEmpty(container, 'No holdings yet. <a href="/import">Import data</a> to get started.');
                return;
            }

            // Apply search filter
            this.filteredHoldings = this.holdings;
            if (this.filters.search) {
                const search = this.filters.search.toLowerCase();
                this.filteredHoldings = this.filteredHoldings.filter(h =>
                    h.symbol.toLowerCase().includes(search) ||
                    (h.stock_name && h.stock_name.toLowerCase().includes(search))
                );
            }

            // Sort alphabetically by symbol by default
            this.filteredHoldings.sort((a, b) => a.symbol.localeCompare(b.symbol));

            // Initialize sorter
            TableSorter.init('portfolio-holdings', this.holdingsColumns, this.filteredHoldings, (sorted) => {
                this.renderHoldingsTable(sorted);
            });

            this.renderHoldings(container, this.filteredHoldings, this.summary);
        } catch (error) {
            Utils.showError(container, 'Failed to load holdings: ' + error.message);
        }
    },

    renderHoldings(container, holdings, summary) {
        container.innerHTML = `
            <!-- Summary Cards -->
            <div class="row mb-4 metric-row">
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-label">Holdings</div>
                        <div class="metric-value">${summary.total_holdings}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-label">Invested</div>
                        <div class="metric-value">${Utils.formatCurrency(summary.total_buy_value)}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-label">Current Value</div>
                        <div class="metric-value">${Utils.formatCurrency(summary.total_current_value)}</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-label">Unrealized P&L</div>
                        <div class="metric-value ${Utils.getPnlClass(summary.total_unrealized_pnl)}">
                            ${Utils.formatCurrency(summary.total_unrealized_pnl)}
                            <span class="metric-pill ${Utils.getPnlClass(summary.total_unrealized_pnl_percent)}">${Utils.formatPercent(summary.total_unrealized_pnl_percent)}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Holdings Table -->
            <div class="card">
                <div class="table-responsive">
                    <table class="table table-hover mb-0" id="portfolio-holdings-table">
                        <thead class="table-light">
                            <tr>
                                ${TableSorter.renderHeaders('portfolio-holdings', this.holdingsHeaders)}
                            </tr>
                        </thead>
                        <tbody>
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        this.renderHoldingsTable(holdings);
    },

    renderHoldingsTable(holdings) {
        const tbody = document.querySelector('#portfolio-holdings-table tbody');
        if (!tbody) return;
        tbody.innerHTML = holdings.map(h => this.renderHoldingRow(h)).join('');
    },

    renderHoldingRow(h) {
        const pnlClass = Utils.getPnlClass(h.unrealized_pnl);
        return `
            <tr>
                <td><strong>${Utils.escapeHtml(h.symbol)}</strong></td>
                <td>${Utils.escapeHtml(h.stock_name) || '--'}</td>
                <td>${h.sector_name ? `<span class="badge bg-secondary">${Utils.escapeHtml(h.sector_name)}</span>` : '<span class="text-muted">--</span>'}</td>
                <td>${Utils.escapeHtml(h.exchange) || '<span class="text-muted">--</span>'}</td>
                <td class="text-end">${Utils.formatNumber(h.quantity)}</td>
                <td class="text-end">${Utils.formatCurrency(h.avg_buy_price)}</td>
                <td class="text-end">${Utils.formatCurrency(h.current_price)}</td>
                <td class="text-end">${Utils.formatCurrency(h.total_buy_value)}</td>
                <td class="text-end">${Utils.formatCurrency(h.current_value)}</td>
                <td class="text-end ${pnlClass}">${Utils.formatCurrency(h.unrealized_pnl)}</td>
                <td class="text-end ${pnlClass}">${Utils.formatPercent(h.unrealized_pnl_percent)}</td>
                <td>
                    <a href="/portfolio/${parseInt(h.stock_id)}?account=${parseInt(h.account_id)}" class="btn btn-sm btn-outline-primary">
                        <i class="bi bi-eye"></i>
                    </a>
                </td>
            </tr>
        `;
    },

    bindEvents() {
        // Filter change events
        ['filter-account', 'filter-owner', 'filter-goal', 'filter-sector'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', () => {
                    this.filters[id.replace('filter-', '')] = el.value;
                    this.loadHoldings();
                });
            }
        });

        // Search
        const searchEl = document.getElementById('filter-search');
        if (searchEl) {
            searchEl.addEventListener('input', () => {
                this.filters.search = searchEl.value;
                this.loadHoldings();
            });
        }

        // Refresh prices
        const refreshBtn = document.getElementById('refresh-prices');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                refreshBtn.disabled = true;
                refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Refreshing...';
                try {
                    await API.post('/portfolio/prices/refresh', {});
                    await this.loadHoldings();
                } catch (error) {
                    alert('Failed to refresh prices: ' + error.message);
                } finally {
                    refreshBtn.disabled = false;
                    refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Refresh Prices';
                }
            });
        }
    }
};

// Trades Module
const Trades = {
    tradesData: [],

    // Column config for sorting
    tradesColumns: [
        { key: 'trade_date', type: 'date' },
        { key: 'symbol', type: 'string' },
        { key: 'trade_type', type: 'string' },
        { key: 'quantity', type: 'number' },
        { key: 'price', type: 'currency' },
        { key: 'value', type: 'currency' },
        { key: 'trade_id', type: 'string' }
    ],

    tradesHeaders: [
        { key: 'trade_date', label: 'Date' },
        { key: 'symbol', label: 'Stock' },
        { key: 'trade_type', label: 'Type' },
        { key: 'quantity', label: 'Qty', class: 'text-end' },
        { key: 'price', label: 'Price', class: 'text-end' },
        { key: 'value', label: 'Value', class: 'text-end' },
        { key: 'trade_id', label: 'Trade ID' }
    ],

    async init() {
        await this.loadTrades();
    },

    async loadTrades() {
        const container = document.getElementById('trades-container');
        if (!container) return;

        Utils.showLoading(container);

        try {
            const data = await API.get('/portfolio/trades?limit=200');

            if (data.trades.length === 0) {
                Utils.showEmpty(container, 'No trades yet. <a href="/import">Import data</a> to get started.');
                return;
            }

            // Add computed value field for sorting
            this.tradesData = data.trades.map(t => ({
                ...t,
                value: t.quantity * t.price
            }));

            // Initialize sorter
            TableSorter.init('trades', this.tradesColumns, this.tradesData, (sorted) => {
                this.renderTradesTable(sorted);
            });

            container.innerHTML = `
                <div class="card">
                    <div class="table-responsive">
                        <table class="table table-hover mb-0" id="trades-table">
                            <thead class="table-light">
                                <tr>
                                    ${TableSorter.renderHeaders('trades', this.tradesHeaders)}
                                </tr>
                            </thead>
                            <tbody>
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
            this.renderTradesTable(this.tradesData);
        } catch (error) {
            Utils.showError(container, 'Failed to load trades: ' + error.message);
        }
    },

    renderTradesTable(trades) {
        const tbody = document.querySelector('#trades-table tbody');
        if (!tbody) return;
        tbody.innerHTML = trades.map(t => this.renderTradeRow(t)).join('');
    },

    renderTradeRow(t) {
        const typeClass = t.trade_type === 'buy' ? 'text-success' : 'text-danger';
        const typeIcon = t.trade_type === 'buy' ? 'bi-arrow-down-circle' : 'bi-arrow-up-circle';
        return `
            <tr>
                <td>${Utils.escapeHtml(t.trade_date)}</td>
                <td>
                    <strong>${Utils.escapeHtml(t.symbol)}</strong>
                    <br><small class="text-muted">${Utils.escapeHtml(t.stock_name || '')}</small>
                </td>
                <td class="${typeClass}">
                    <i class="bi ${typeIcon}"></i> ${Utils.escapeHtml(t.trade_type.toUpperCase())}
                </td>
                <td class="text-end">${Utils.formatNumber(t.quantity)}</td>
                <td class="text-end">${Utils.formatCurrency(t.price)}</td>
                <td class="text-end">${Utils.formatCurrency(t.value)}</td>
                <td><small class="text-muted">${Utils.escapeHtml(t.trade_id || '')}</small></td>
            </tr>
        `;
    }
};

// Import Module
const Import = {
    async init() {
        console.log('Import module initializing...');
        try {
            this.setupUploadAreas();
            this.bindEvents();
            await this.loadLogs();
            console.log('Import module initialized successfully');
        } catch (error) {
            console.error('Error initializing Import module:', error);
        }
    },

    setupUploadAreas() {
        const self = this;

        // Setup tradebook upload area
        const tradebookArea = document.getElementById('upload-area');
        const tradebookInput = document.getElementById('file-input');
        const tradebookList = document.getElementById('file-list');

        if (tradebookArea && tradebookInput) {
            console.log('Setting up tradebook upload area');

            tradebookArea.style.cursor = 'pointer';

            tradebookArea.addEventListener('click', function (e) {
                console.log('Tradebook area clicked');
                tradebookInput.click();
            });

            tradebookArea.addEventListener('dragover', function (e) {
                e.preventDefault();
                this.classList.add('dragover');
            });

            tradebookArea.addEventListener('dragleave', function (e) {
                e.preventDefault();
                this.classList.remove('dragover');
            });

            tradebookArea.addEventListener('drop', function (e) {
                e.preventDefault();
                this.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    tradebookInput.files = e.dataTransfer.files;
                    self.updateFileList(tradebookInput, tradebookList);
                    self.updateUploadButton();
                }
            });

            tradebookInput.addEventListener('change', function () {
                console.log('Tradebook input changed, files:', this.files.length);
                self.updateFileList(tradebookInput, tradebookList);
                self.updateUploadButton();
            });
        } else {
            console.log('Tradebook upload area not found');
        }

        // Setup Tax P&L upload area
        const taxpnlArea = document.getElementById('taxpnl-upload-area');
        const taxpnlInput = document.getElementById('taxpnl-input');
        const taxpnlList = document.getElementById('taxpnl-list');

        if (taxpnlArea && taxpnlInput) {
            console.log('Setting up Tax P&L upload area');

            taxpnlArea.style.cursor = 'pointer';

            taxpnlArea.addEventListener('click', function (e) {
                console.log('Tax P&L area clicked');
                taxpnlInput.click();
            });

            taxpnlArea.addEventListener('dragover', function (e) {
                e.preventDefault();
                this.classList.add('dragover');
            });

            taxpnlArea.addEventListener('dragleave', function (e) {
                e.preventDefault();
                this.classList.remove('dragover');
            });

            taxpnlArea.addEventListener('drop', function (e) {
                e.preventDefault();
                this.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    taxpnlInput.files = e.dataTransfer.files;
                    self.updateFileList(taxpnlInput, taxpnlList);
                }
            });

            taxpnlInput.addEventListener('change', function () {
                console.log('Tax P&L input changed, files:', this.files.length);
                self.updateFileList(taxpnlInput, taxpnlList);
            });
        } else {
            console.log('Tax P&L upload area not found');
        }
    },

    updateFileList(input, list) {
        if (!list) return;
        list.innerHTML = '';

        Array.from(input.files).forEach(file => {
            const div = document.createElement('div');
            div.className = 'd-flex justify-content-between align-items-center p-2 border rounded mb-2';

            const nameSpan = document.createElement('span');
            const icon = document.createElement('i');
            icon.className = 'bi bi-file-earmark-excel text-success me-2';
            nameSpan.appendChild(icon);
            nameSpan.appendChild(document.createTextNode(file.name));

            const sizeSpan = document.createElement('span');
            sizeSpan.className = 'text-muted';
            sizeSpan.textContent = `${(file.size / 1024).toFixed(1)} KB`;

            div.appendChild(nameSpan);
            div.appendChild(sizeSpan);
            list.appendChild(div);
        });

        console.log(`Updated file list with ${input.files.length} files`);
    },

    updateUploadButton() {
        const uploadBtn = document.getElementById('upload-btn');
        const mainInput = document.getElementById('file-input');
        if (uploadBtn && mainInput) {
            uploadBtn.disabled = mainInput.files.length === 0;
            console.log(`Upload button ${uploadBtn.disabled ? 'disabled' : 'enabled'}, files: ${mainInput.files.length}`);
        }
    },

    bindEvents() {
        const self = this;
        const uploadForm = document.getElementById('upload-form');

        if (uploadForm) {
            uploadForm.addEventListener('submit', function (e) {
                e.preventDefault();
                console.log('Form submitted');
                self.uploadFiles();
            });
            console.log('Form submit handler bound');
        } else {
            console.log('Upload form not found');
        }
    },

    async uploadFiles() {
        const fileInput = document.getElementById('file-input');
        const taxpnlInput = document.getElementById('taxpnl-input');

        const tradebookFiles = fileInput ? fileInput.files : [];
        const taxpnlFiles = taxpnlInput ? taxpnlInput.files : [];

        if (!tradebookFiles.length) {
            alert('Please select at least one tradebook file');
            return;
        }

        const uploadBtn = document.getElementById('upload-btn');
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Importing...';

        const resultDiv = document.getElementById('import-result');
        resultDiv.innerHTML = '';

        try {
            const formData = new FormData();

            // Add all tradebook files
            for (let i = 0; i < tradebookFiles.length; i++) {
                formData.append('tradebook_files', tradebookFiles[i]);
            }

            // Add all Tax P&L files
            for (let i = 0; i < taxpnlFiles.length; i++) {
                formData.append('taxpnl_files', taxpnlFiles[i]);
            }

            formData.append('broker', 'Zerodha');

            const response = await fetch(`${API_BASE}/import/full`, {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            if (data.status === 'error') {
                throw new Error(data.message);
            }

            const result = data.data;

            // Calculate totals from all imports
            let totalTradesImported = 0;
            let totalTradesSkipped = 0;
            let totalPnlImported = 0;
            let totalPnlSkipped = 0;

            if (result.tradebook_imports) {
                result.tradebook_imports.forEach(imp => {
                    totalTradesImported += imp.trades_imported || 0;
                    totalTradesSkipped += imp.trades_skipped || 0;
                });
            }

            if (result.taxpnl_imports) {
                result.taxpnl_imports.forEach(imp => {
                    totalPnlImported += imp.entries_imported || 0;
                    totalPnlSkipped += imp.entries_skipped || 0;
                });
            }

            // Build result HTML
            let resultHtml = `
                <div class="alert alert-${result.errors && result.errors.length ? 'warning' : 'success'}">
                    <h5><i class="bi bi-check-circle"></i> Import Complete</h5>
                    <div class="row">
                        <div class="col-md-6">
                            <h6>Tradebook (${tradebookFiles.length} file${tradebookFiles.length > 1 ? 's' : ''})</h6>
                            <ul class="mb-2">
                                <li>Trades imported: <strong>${totalTradesImported}</strong></li>
                                ${totalTradesSkipped > 0 ? `<li class="text-warning">Duplicates skipped: ${totalTradesSkipped}</li>` : ''}
                            </ul>
                        </div>
            `;

            if (taxpnlFiles.length > 0) {
                resultHtml += `
                        <div class="col-md-6">
                            <h6>Tax P&L (${taxpnlFiles.length} file${taxpnlFiles.length > 1 ? 's' : ''})</h6>
                            <ul class="mb-2">
                                <li>Entries imported: <strong>${totalPnlImported}</strong></li>
                                ${totalPnlSkipped > 0 ? `<li class="text-warning">Duplicates skipped: ${totalPnlSkipped}</li>` : ''}
                            </ul>
                        </div>
                `;
            }

            resultHtml += `</div>`;

            // Show allocation results
            if (result.allocations) {
                resultHtml += `
                    <hr>
                    <small class="text-muted">
                        Default allocations: ${result.allocations.allocations_created} created,
                        ${result.allocations.allocations_updated} updated
                    </small>
                `;
            }

            // Show errors if any
            if (result.errors && result.errors.length > 0) {
                resultHtml += `
                    <hr>
                    <h6 class="text-danger">Errors:</h6>
                    <ul class="mb-0 text-danger">
                        ${result.errors.map(e => `<li>${Utils.escapeHtml(e.file)}: ${Utils.escapeHtml(e.error)}</li>`).join('')}
                    </ul>
                `;
            }

            resultHtml += `</div>`;
            resultDiv.innerHTML = resultHtml;

            await this.loadLogs();
        } catch (error) {
            resultDiv.innerHTML = `
                <div class="alert alert-danger">
                    <h5><i class="bi bi-x-circle"></i> Import Failed</h5>
                    <p class="mb-0">${Utils.escapeHtml(error.message)}</p>
                </div>
            `;
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="bi bi-upload"></i> Import';
        }
    },

    async loadLogs() {
        const logsContainer = document.getElementById('import-logs');
        if (!logsContainer) return;

        try {
            const data = await API.get('/import/logs');

            if (data.logs.length === 0) {
                logsContainer.innerHTML = '<p class="text-muted">No import history yet.</p>';
                return;
            }

            logsContainer.innerHTML = `
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Type</th>
                            <th>File</th>
                            <th>Status</th>
                            <th>Records</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.logs.slice(0, 10).map(log => `
                            <tr>
                                <td>${Utils.escapeHtml(new Date(log.created_at).toLocaleString())}</td>
                                <td>${Utils.escapeHtml(log.import_type)}</td>
                                <td><small>${Utils.escapeHtml(log.filename)}</small></td>
                                <td>
                                    <span class="badge bg-${log.status === 'completed' ? 'success' : log.status === 'failed' ? 'danger' : 'warning'}">
                                        ${Utils.escapeHtml(log.status)}
                                    </span>
                                </td>
                                <td>${log.records_processed || 0}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } catch (error) {
            console.error('Error loading import logs:', error);
        }
    }
};

// Reports Module
const Reports = {
    fySummaryData: [],
    pnlDetailsData: [],

    // FY Summary columns
    fySummaryColumns: [
        { key: 'financial_year', type: 'string' },
        { key: 'stcg', type: 'currency' },
        { key: 'ltcg', type: 'currency' },
        { key: 'total', type: 'currency' },
        { key: 'trades', type: 'number' }
    ],

    fySummaryHeaders: [
        { key: 'financial_year', label: 'FY' },
        { key: 'stcg', label: 'STCG', class: 'text-end' },
        { key: 'ltcg', label: 'LTCG', class: 'text-end' },
        { key: 'total', label: 'Total', class: 'text-end' },
        { key: 'trades', label: 'Trades', class: 'text-end' }
    ],

    // P&L Details columns
    pnlDetailsColumns: [
        { key: 'symbol', type: 'string' },
        { key: 'exit_date', type: 'date' },
        { key: 'quantity', type: 'number' },
        { key: 'buy_value', type: 'currency' },
        { key: 'sell_value', type: 'currency' },
        { key: 'profit', type: 'currency' },
        { key: 'tax_term', type: 'string' }
    ],

    pnlDetailsHeaders: [
        { key: 'symbol', label: 'Stock' },
        { key: 'exit_date', label: 'Exit Date' },
        { key: 'quantity', label: 'Qty', class: 'text-end' },
        { key: 'buy_value', label: 'Buy Value', class: 'text-end' },
        { key: 'sell_value', label: 'Sell Value', class: 'text-end' },
        { key: 'profit', label: 'P&L', class: 'text-end' },
        { key: 'tax_term', label: 'Term' }
    ],

    filters: {
        fy: '',
        account: '',
        owner: ''
    },

    async init() {
        await this.loadFilters();
        await this.loadPnlReport();
        this.bindFilterEvents();
    },

    async loadFilters() {
        try {
            const [accounts, owners, pnlSummary] = await Promise.all([
                API.get('/settings/accounts'),
                API.get('/settings/owners'),
                API.get('/portfolio/pnl/summary')
            ]);

            // Populate account filter
            const accountFilter = document.getElementById('filter-account');
            if (accountFilter) {
                accountFilter.innerHTML = `
                    <option value="">All Accounts</option>
                    ${accounts.accounts.map(a => `<option value="${parseInt(a.id)}">${Utils.escapeHtml(a.account_number)}</option>`).join('')}
                `;
            }

            // Populate owner filter
            const ownerFilter = document.getElementById('filter-owner');
            if (ownerFilter) {
                ownerFilter.innerHTML = `
                    <option value="">All Owners</option>
                    ${owners.owners.map(o => `<option value="${parseInt(o.id)}">${Utils.escapeHtml(o.name)}</option>`).join('')}
                `;
            }

            // Populate financial year filter from P&L summary
            const fyFilter = document.getElementById('filter-fy');
            if (fyFilter && pnlSummary.summary) {
                const fys = pnlSummary.summary.map(s => s.financial_year).sort().reverse();
                fyFilter.innerHTML = `
                    <option value="">All Years</option>
                    ${fys.map(fy => `<option value="${Utils.escapeHtml(fy)}">${Utils.escapeHtml(fy)}</option>`).join('')}
                `;
            }
        } catch (error) {
            console.error('Error loading report filters:', error);
        }
    },

    bindFilterEvents() {
        const filterIds = ['filter-fy', 'filter-account', 'filter-owner'];
        filterIds.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', () => this.applyFilters());
            }
        });

        const reportType = document.getElementById('report-type');
        if (reportType) {
            reportType.addEventListener('change', () => this.loadPnlReport());
        }
    },

    async applyFilters() {
        const fyFilter = document.getElementById('filter-fy');
        const accountFilter = document.getElementById('filter-account');
        const ownerFilter = document.getElementById('filter-owner');

        this.filters.fy = fyFilter ? fyFilter.value : '';
        this.filters.account = accountFilter ? accountFilter.value : '';
        this.filters.owner = ownerFilter ? ownerFilter.value : '';

        await this.loadPnlReport();
    },

    async loadPnlReport() {
        const container = document.getElementById('pnl-report');
        if (!container) return;

        Utils.showLoading(container);

        try {
            // Build query params from filters
            const params = new URLSearchParams();
            if (this.filters.fy) params.append('fy', this.filters.fy);
            if (this.filters.account) params.append('account', this.filters.account);
            if (this.filters.owner) params.append('owner', this.filters.owner);
            const queryString = params.toString();
            const suffix = queryString ? '?' + queryString : '';

            const [realized, summary] = await Promise.all([
                API.get('/portfolio/pnl/realized' + suffix),
                API.get('/portfolio/pnl/summary' + suffix)
            ]);

            // Store data
            this.fySummaryData = summary.summary || [];
            this.pnlDetailsData = realized.entries.slice(0, 50);

            // Initialize sorters
            TableSorter.init('fy-summary', this.fySummaryColumns, this.fySummaryData, (sorted) => {
                this.renderFySummaryTable(sorted);
            });

            TableSorter.init('pnl-details', this.pnlDetailsColumns, this.pnlDetailsData, (sorted) => {
                this.renderPnlDetailsTable(sorted);
            });

            container.innerHTML = `
                <!-- Summary Cards -->
                <div class="row mb-4">
                    <div class="col-md-4">
                        <div class="card bg-success text-white">
                            <div class="card-body">
                                <h6>Total STCG</h6>
                                <h3>${Utils.formatCurrency(realized.summary.stcg_total)}</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card bg-primary text-white">
                            <div class="card-body">
                                <h6>Total LTCG</h6>
                                <h3>${Utils.formatCurrency(realized.summary.ltcg_total)}</h3>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card bg-info text-white">
                            <div class="card-body">
                                <h6>Total Realized</h6>
                                <h3>${Utils.formatCurrency(realized.summary.total)}</h3>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- FY Summary -->
                <div class="card mb-4">
                    <div class="card-header">
                        <h5 class="mb-0">Financial Year Summary</h5>
                    </div>
                    <div class="card-body">
                        <table class="table" id="fy-summary-table">
                            <thead>
                                <tr>
                                    ${TableSorter.renderHeaders('fy-summary', this.fySummaryHeaders)}
                                </tr>
                            </thead>
                            <tbody>
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Detailed P&L -->
                <div class="card">
                    <div class="card-header">
                        <h5 class="mb-0">Realized P&L Details</h5>
                    </div>
                    <div class="table-responsive">
                        <table class="table table-hover mb-0" id="pnl-details-table">
                            <thead class="table-light">
                                <tr>
                                    ${TableSorter.renderHeaders('pnl-details', this.pnlDetailsHeaders)}
                                </tr>
                            </thead>
                            <tbody>
                            </tbody>
                        </table>
                    </div>
                </div>
            `;

            // Render table bodies
            this.renderFySummaryTable(this.fySummaryData);
            this.renderPnlDetailsTable(this.pnlDetailsData);
        } catch (error) {
            Utils.showError(container, 'Failed to load P&L report: ' + error.message);
        }
    },

    renderFySummaryTable(data) {
        const tbody = document.querySelector('#fy-summary-table tbody');
        if (!tbody) return;
        tbody.innerHTML = data.map(s => `
            <tr>
                <td><strong>${Utils.escapeHtml(s.financial_year)}</strong></td>
                <td class="text-end ${Utils.getPnlClass(s.stcg)}">${Utils.formatCurrency(s.stcg)}</td>
                <td class="text-end ${Utils.getPnlClass(s.ltcg)}">${Utils.formatCurrency(s.ltcg)}</td>
                <td class="text-end ${Utils.getPnlClass(s.total)}"><strong>${Utils.formatCurrency(s.total)}</strong></td>
                <td class="text-end">${s.trades}</td>
            </tr>
        `).join('');
    },

    renderPnlDetailsTable(data) {
        const tbody = document.querySelector('#pnl-details-table tbody');
        if (!tbody) return;
        tbody.innerHTML = data.map(e => `
            <tr>
                <td><strong>${Utils.escapeHtml(e.symbol)}</strong></td>
                <td>${Utils.escapeHtml(e.exit_date)}</td>
                <td class="text-end">${Utils.formatNumber(e.quantity)}</td>
                <td class="text-end">${Utils.formatCurrency(e.buy_value)}</td>
                <td class="text-end">${Utils.formatCurrency(e.sell_value)}</td>
                <td class="text-end ${Utils.getPnlClass(e.profit)}">${Utils.formatCurrency(e.profit)}</td>
                <td>
                    <span class="badge bg-${e.tax_term === 'LTCG' ? 'primary' : 'success'}">
                        ${Utils.escapeHtml(e.tax_term)}
                    </span>
                </td>
            </tr>
        `).join('');
    }
};

// Settings Module
const Settings = {
    sectors: [],
    stocks: [],

    // Stock table columns for sorting
    stocksColumns: [
        { key: 'symbol', type: 'string' },
        { key: 'name', type: 'string' },
        { key: 'exchange', type: 'string' },
        { key: 'sector_name', type: 'string' }
    ],

    stocksHeaders: [
        { key: 'symbol', label: 'Symbol' },
        { key: 'name', label: 'Name' },
        { key: 'exchange', label: 'Exchange' },
        { key: 'sector_name', label: 'Sector' },
        { key: 'status', label: '', sortable: false }
    ],

    async init() {
        // Load sectors first (needed for stock dropdown)
        await this.loadSectors();

        // Then load everything else in parallel
        await Promise.all([
            this.loadOwners(),
            this.loadGoals(),
            this.loadBrokers(),
            this.loadAccounts(),
            this.loadStocks()
        ]);
        this.bindEvents();
    },

    async loadOwners() {
        const container = document.getElementById('owners-list');
        if (!container) return;

        try {
            const data = await API.get('/settings/owners');
            container.innerHTML = data.owners.map(o => `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <span>
                        ${Utils.escapeHtml(o.name)}
                        ${o.is_default ? '<span class="badge bg-secondary ms-2">Default</span>' : ''}
                    </span>
                    ${!o.is_default ? `
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-secondary" onclick="Settings.showEditOwner(${parseInt(o.id)}, '${Utils.escapeHtml(o.name).replace(/'/g, "\\'")}')">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-outline-danger" onclick="Settings.deleteOwner(${parseInt(o.id)})">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    ` : ''}
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = `<div class="text-danger">${Utils.escapeHtml(error.message)}</div>`;
        }
    },

    async loadGoals() {
        const container = document.getElementById('goals-list');
        if (!container) return;

        try {
            const data = await API.get('/settings/goals');
            container.innerHTML = data.goals.map(g => `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <span>
                        ${Utils.escapeHtml(g.name)}
                        ${g.target_amount ? `<small class="text-muted ms-2">(Target: ${Utils.formatCurrency(g.target_amount)})</small>` : ''}
                        ${g.is_default ? '<span class="badge bg-secondary ms-2">Default</span>' : ''}
                    </span>
                    ${!g.is_default ? `
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-secondary" onclick="Settings.showEditGoal(${parseInt(g.id)}, '${Utils.escapeHtml(g.name).replace(/'/g, "\\'")}', ${g.target_amount || 'null'})">
                                <i class="bi bi-pencil"></i>
                            </button>
                            <button class="btn btn-outline-danger" onclick="Settings.deleteGoal(${parseInt(g.id)})">
                                <i class="bi bi-trash"></i>
                            </button>
                        </div>
                    ` : ''}
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = `<div class="text-danger">${Utils.escapeHtml(error.message)}</div>`;
        }
    },

    async loadBrokers() {
        const container = document.getElementById('brokers-list');
        if (!container) return;

        try {
            const data = await API.get('/settings/brokers');
            container.innerHTML = data.brokers.map(b => `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <span>${Utils.escapeHtml(b.name)}</span>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-secondary" onclick="Settings.showEditBroker(${parseInt(b.id)}, '${Utils.escapeHtml(b.name).replace(/'/g, "\\'")}')">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="Settings.deleteBroker(${parseInt(b.id)})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = `<div class="text-danger">${Utils.escapeHtml(error.message)}</div>`;
        }
    },

    async loadAccounts() {
        const container = document.getElementById('accounts-list');
        if (!container) return;

        try {
            const data = await API.get('/settings/accounts');
            container.innerHTML = data.accounts.map(a => `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <span>
                        ${Utils.escapeHtml(a.account_number)}
                        ${a.name ? `<small class="text-muted ms-1">(${Utils.escapeHtml(a.name)})</small>` : ''}
                        <small class="text-muted ms-2">- ${Utils.escapeHtml(a.broker_name)}</small>
                    </span>
                    <div class="btn-group btn-group-sm">
                        <button class="btn btn-outline-secondary" onclick="Settings.showEditAccount(${parseInt(a.id)}, '${Utils.escapeHtml(a.account_number).replace(/'/g, "\\'")}', '${Utils.escapeHtml(a.name || '').replace(/'/g, "\\'")}')">
                            <i class="bi bi-pencil"></i>
                        </button>
                        <button class="btn btn-outline-danger" onclick="Settings.deleteAccount(${parseInt(a.id)})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            container.innerHTML = `<div class="text-danger">${Utils.escapeHtml(error.message)}</div>`;
        }
    },

    async loadSectors() {
        const container = document.getElementById('sectors-container');
        if (!container) return;

        try {
            const data = await API.get('/settings/sectors');
            this.sectors = data.sectors;
            container.innerHTML = data.sectors.map(s => `
                <span class="badge bg-secondary">${Utils.escapeHtml(s.name)}</span>
            `).join('');
        } catch (error) {
            container.innerHTML = `<div class="text-danger">${Utils.escapeHtml(error.message)}</div>`;
        }
    },

    async loadStocks() {
        const container = document.getElementById('stocks-container');
        if (!container) return;

        try {
            const data = await API.get('/portfolio/stocks');
            // Sort alphabetically by symbol by default
            this.stocks = data.stocks.sort((a, b) => a.symbol.localeCompare(b.symbol));

            if (this.stocks.length === 0) {
                container.innerHTML = '<div class="p-4 text-center"><p class="text-muted mb-0">No stocks found. Import tradebook files first.</p></div>';
                return;
            }

            // Initialize sorter
            TableSorter.init('settings-stocks', this.stocksColumns, this.stocks, (sorted) => {
                this.renderStocksTable(sorted);
            });

            container.innerHTML = `
                <div class="table-responsive">
                    <table class="table table-sm table-hover mb-0" id="settings-stocks-table">
                        <thead class="table-light">
                            <tr>
                                ${TableSorter.renderHeaders('settings-stocks', this.stocksHeaders)}
                            </tr>
                        </thead>
                        <tbody>
                        </tbody>
                    </table>
                </div>
            `;

            this.renderStocksTable(this.stocks);
        } catch (error) {
            container.innerHTML = `<div class="text-danger">${Utils.escapeHtml(error.message)}</div>`;
        }
    },

    renderStocksTable(stocks) {
        const tbody = document.querySelector('#settings-stocks-table tbody');
        if (!tbody) return;
        tbody.innerHTML = stocks.map(s => `
            <tr>
                <td><strong>${Utils.escapeHtml(s.symbol)}</strong></td>
                <td>
                    <input type="text" class="form-control form-control-sm"
                           value="${Utils.escapeHtml(s.name || s.symbol)}"
                           onblur="Settings.updateStockName(${parseInt(s.id)}, this.value)"
                           onkeypress="if(event.key==='Enter'){this.blur();}"
                           style="min-width: 150px;"
                           placeholder="Enter stock name">
                </td>
                <td>
                    <select class="form-select form-select-sm"
                            onchange="Settings.updateStockExchange(${parseInt(s.id)}, this.value)"
                            style="width: auto; min-width: 80px;">
                        <option value="">--</option>
                        <option value="NSE" ${s.exchange === 'NSE' ? 'selected' : ''}>NSE</option>
                        <option value="BSE" ${s.exchange === 'BSE' ? 'selected' : ''}>BSE</option>
                    </select>
                </td>
                <td>
                    <select class="form-select form-select-sm"
                            onchange="Settings.updateStockSector(${parseInt(s.id)}, this.value)"
                            style="width: auto; min-width: 150px;">
                        <option value="">-- Select Sector --</option>
                        ${this.sectors.map(sec => `
                            <option value="${parseInt(sec.id)}" ${s.sector_id === sec.id ? 'selected' : ''}>
                                ${Utils.escapeHtml(sec.name)}
                            </option>
                        `).join('')}
                    </select>
                </td>
                <td>
                    ${s.sector_id && s.exchange ? '<i class="bi bi-check-circle text-success"></i>' : '<i class="bi bi-exclamation-circle text-warning"></i>'}
                </td>
            </tr>
        `).join('');
    },

    async updateStockName(stockId, name) {
        try {
            await API.put(`/portfolio/stocks/${stockId}`, {
                name: name.trim() || null
            });
        } catch (error) {
            alert('Error updating stock name: ' + error.message);
            await this.loadStocks(); // Reload to restore original value
        }
    },

    async updateStockExchange(stockId, exchange) {
        try {
            await API.put(`/portfolio/stocks/${stockId}`, {
                exchange: exchange || null
            });
            // Reload to update the check icon
            await this.loadStocks();
        } catch (error) {
            alert('Error updating exchange: ' + error.message);
        }
    },

    async updateStockSector(stockId, sectorId) {
        try {
            await API.put(`/portfolio/stocks/${stockId}`, {
                sector_id: sectorId ? parseInt(sectorId) : null
            });
            // Reload to update the check icon
            await this.loadStocks();
        } catch (error) {
            alert('Error updating sector: ' + error.message);
        }
    },

    bindEvents() {
        // Add Owner
        const addOwnerForm = document.getElementById('add-owner-form');
        if (addOwnerForm) {
            addOwnerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = document.getElementById('owner-name').value.trim();
                if (!name) return;

                try {
                    await API.post('/settings/owners', { name });
                    document.getElementById('owner-name').value = '';
                    await this.loadOwners();
                } catch (error) {
                    alert(error.message);
                }
            });
        }

        // Add Goal
        const addGoalForm = document.getElementById('add-goal-form');
        if (addGoalForm) {
            addGoalForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = document.getElementById('goal-name').value.trim();
                const target = document.getElementById('goal-target').value;
                if (!name) return;

                try {
                    await API.post('/settings/goals', {
                        name,
                        target_amount: target ? parseFloat(target) : null
                    });
                    document.getElementById('goal-name').value = '';
                    document.getElementById('goal-target').value = '';
                    await this.loadGoals();
                } catch (error) {
                    alert(error.message);
                }
            });
        }

        // Add Broker
        const addBrokerForm = document.getElementById('add-broker-form');
        if (addBrokerForm) {
            addBrokerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = document.getElementById('broker-name').value.trim();
                if (!name) return;

                try {
                    await API.post('/settings/brokers', { name });
                    document.getElementById('broker-name').value = '';
                    await this.loadBrokers();
                } catch (error) {
                    alert(error.message);
                }
            });
        }

        // Edit Owner
        const editOwnerForm = document.getElementById('edit-owner-form');
        if (editOwnerForm) {
            editOwnerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const id = document.getElementById('edit-owner-id').value;
                const name = document.getElementById('edit-owner-name').value.trim();
                if (!name) return;
                await this.saveOwner(id, name);
            });
        }

        // Edit Goal
        const editGoalForm = document.getElementById('edit-goal-form');
        if (editGoalForm) {
            editGoalForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const id = document.getElementById('edit-goal-id').value;
                const name = document.getElementById('edit-goal-name').value.trim();
                const target = document.getElementById('edit-goal-target').value;
                if (!name) return;
                await this.saveGoal(id, name, target);
            });
        }

        // Edit Broker
        const editBrokerForm = document.getElementById('edit-broker-form');
        if (editBrokerForm) {
            editBrokerForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const id = document.getElementById('edit-broker-id').value;
                const name = document.getElementById('edit-broker-name').value.trim();
                if (!name) return;
                await this.saveBroker(id, name);
            });
        }

        // Edit Account
        const editAccountForm = document.getElementById('edit-account-form');
        if (editAccountForm) {
            editAccountForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const id = document.getElementById('edit-account-id').value;
                const accountNumber = document.getElementById('edit-account-number').value.trim();
                const name = document.getElementById('edit-account-name').value.trim();
                if (!accountNumber) return;
                await this.saveAccount(id, accountNumber, name);
            });
        }
    },

    async deleteOwner(id) {
        if (!confirm('Are you sure you want to delete this owner?')) return;
        try {
            await API.delete(`/settings/owners/${id}`);
            await this.loadOwners();
        } catch (error) {
            alert(error.message);
        }
    },

    async deleteGoal(id) {
        if (!confirm('Are you sure you want to delete this goal?')) return;
        try {
            await API.delete(`/settings/goals/${id}`);
            await this.loadGoals();
        } catch (error) {
            alert(error.message);
        }
    },

    async deleteBroker(id) {
        if (!confirm('Are you sure you want to delete this broker?')) return;
        try {
            await API.delete(`/settings/brokers/${id}`);
            await this.loadBrokers();
        } catch (error) {
            alert(error.message);
        }
    },

    async deleteAccount(id) {
        if (!confirm('Are you sure you want to delete this account?')) return;
        try {
            await API.delete(`/settings/accounts/${id}`);
            await this.loadAccounts();
        } catch (error) {
            alert(error.message);
        }
    },

    // Edit functions
    showEditOwner(id, name) {
        document.getElementById('edit-owner-id').value = id;
        document.getElementById('edit-owner-name').value = name;
        new bootstrap.Modal(document.getElementById('editOwnerModal')).show();
    },

    showEditGoal(id, name, targetAmount) {
        document.getElementById('edit-goal-id').value = id;
        document.getElementById('edit-goal-name').value = name;
        document.getElementById('edit-goal-target').value = targetAmount || '';
        new bootstrap.Modal(document.getElementById('editGoalModal')).show();
    },

    showEditBroker(id, name) {
        document.getElementById('edit-broker-id').value = id;
        document.getElementById('edit-broker-name').value = name;
        new bootstrap.Modal(document.getElementById('editBrokerModal')).show();
    },

    showEditAccount(id, accountNumber, name) {
        document.getElementById('edit-account-id').value = id;
        document.getElementById('edit-account-number').value = accountNumber;
        document.getElementById('edit-account-name').value = name || '';
        new bootstrap.Modal(document.getElementById('editAccountModal')).show();
    },

    async saveOwner(id, name) {
        try {
            await API.put(`/settings/owners/${id}`, { name });
            bootstrap.Modal.getInstance(document.getElementById('editOwnerModal')).hide();
            await this.loadOwners();
        } catch (error) {
            alert(error.message);
        }
    },

    async saveGoal(id, name, targetAmount) {
        try {
            await API.put(`/settings/goals/${id}`, {
                name,
                target_amount: targetAmount ? parseFloat(targetAmount) : null
            });
            bootstrap.Modal.getInstance(document.getElementById('editGoalModal')).hide();
            await this.loadGoals();
        } catch (error) {
            alert(error.message);
        }
    },

    async saveBroker(id, name) {
        try {
            await API.put(`/settings/brokers/${id}`, { name });
            bootstrap.Modal.getInstance(document.getElementById('editBrokerModal')).hide();
            await this.loadBrokers();
        } catch (error) {
            alert(error.message);
        }
    },

    async saveAccount(id, accountNumber, name) {
        try {
            await API.put(`/settings/accounts/${id}`, {
                account_number: accountNumber,
                name: name || null
            });
            bootstrap.Modal.getInstance(document.getElementById('editAccountModal')).hide();
            await this.loadAccounts();
        } catch (error) {
            alert(error.message);
        }
    }
};

// Allocations Module
const Allocations = {
    async init() {
        await this.loadAllocations();
    },

    async loadAllocations() {
        const container = document.getElementById('allocations-container');
        if (!container) return;

        Utils.showLoading(container);

        try {
            const data = await API.get('/allocations');

            if (data.allocations.length === 0) {
                Utils.showEmpty(container, 'No allocations yet.');
                return;
            }

            container.innerHTML = `
                <div class="row mb-4">
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-body text-center">
                                <h6 class="text-muted">Total Allocations</h6>
                                <h4>${data.count}</h4>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="card">
                            <div class="card-body text-center">
                                <h6 class="text-muted">Total Value</h6>
                                <h4>${Utils.formatCurrency(data.total_value)}</h4>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="table-responsive">
                        <table class="table table-hover mb-0">
                            <thead class="table-light">
                                <tr>
                                    <th>Stock</th>
                                    <th>Owner</th>
                                    <th>Goal</th>
                                    <th class="text-end">Qty</th>
                                    <th class="text-end">Buy Price</th>
                                    <th class="text-end">Value</th>
                                    <th>Buy Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${data.allocations.map(a => `
                                    <tr>
                                        <td><strong>${a.symbol}</strong></td>
                                        <td>${a.owner_name}</td>
                                        <td>${a.goal_name}</td>
                                        <td class="text-end">${Utils.formatNumber(a.quantity)}</td>
                                        <td class="text-end">${Utils.formatCurrency(a.buy_price)}</td>
                                        <td class="text-end">${Utils.formatCurrency(a.quantity * a.buy_price)}</td>
                                        <td>${a.buy_date}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        } catch (error) {
            Utils.showError(container, 'Failed to load allocations: ' + error.message);
        }
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    const path = window.location.pathname;

    if (path === '/' || path === '/dashboard') {
        Dashboard.init();
    } else if (path === '/portfolio' || path.startsWith('/portfolio/')) {
        Portfolio.init();
    } else if (path === '/trades') {
        Trades.init();
    } else if (path === '/import') {
        Import.init();
    } else if (path === '/reports') {
        Reports.init();
    } else if (path === '/settings') {
        Settings.init();
    } else if (path === '/allocations') {
        Allocations.init();
    }
});
