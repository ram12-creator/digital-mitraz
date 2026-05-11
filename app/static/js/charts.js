// Charts and Data Visualization JavaScript - MITRAZ THEME EDITION

class ChartManager {
    constructor() {
        this.charts = new Map();
        this.defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                        font: {
                            family: "'Poppins', sans-serif",
                            size: 12,
                            weight: '600'
                        },
                        // Updated to Charcoal
                        color: '#2C3E50' 
                    }
                },
                tooltip: {
                    // Charcoal background for tooltips
                    backgroundColor: 'rgba(44, 62, 80, 0.95)', 
                    titleFont: {
                        size: 14,
                        family: "'Poppins', sans-serif",
                        weight: 'bold'
                    },
                    bodyFont: {
                        size: 13,
                        family: "'Poppins', sans-serif"
                    },
                    padding: 12,
                    cornerRadius: 6,
                    usePointStyle: true,
                    titleColor: '#ffffff',
                    bodyColor: '#ffffff',
                    borderColor: '#D32F2F', // Red border
                    borderWidth: 1
                }
            },
            animation: {
                duration: 1000,
                easing: 'easeOutQuart'
            },
            layout: {
                padding: 10
            }
        };
    }

    initAllCharts() {
        const chartElements = document.querySelectorAll('[data-chart]');
        chartElements.forEach(element => {
            this.initChart(element);
        });
    }

    initChart(element) {
        const ctx = element.getContext('2d');
        const chartType = element.dataset.chartType || 'bar';
        const chartData = element.dataset.chartData ? JSON.parse(element.dataset.chartData) : null;
        const chartOptions = element.dataset.chartOptions ? JSON.parse(element.dataset.chartOptions) : {};

        if (!chartData) return;

        const options = { ...this.defaultOptions, ...chartOptions };

        const chart = new Chart(ctx, {
            type: chartType,
            data: chartData,
            options: options
        });

        this.charts.set(element.id, chart);
        return chart;
    }

    createChart(ctx, type, data, options = {}) {
        const mergedOptions = { ...this.defaultOptions, ...options };
        const chart = new Chart(ctx, {
            type: type,
            data: data,
            options: mergedOptions
        });
        return chart;
    }

    updateChart(chartId, newData) {
        const chart = this.charts.get(chartId);
        if (chart) {
            chart.data = newData;
            chart.update();
        }
    }

    destroyChart(chartId) {
        const chart = this.charts.get(chartId);
        if (chart) {
            chart.destroy();
            this.charts.delete(chartId);
        }
    }

    // --- Chart Builders ---

    createBarChart(ctx, labels, datasets, options = {}) {
        const data = { labels: labels, datasets: datasets };
        const defaultOptions = {
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { drawBorder: false, color: '#f0f0f0' },
                    ticks: { color: '#666' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#666' }
                }
            }
        };
        return this.createChart(ctx, 'bar', data, { ...defaultOptions, ...options });
    }

    createLineChart(ctx, labels, datasets, options = {}) {
        const data = { labels: labels, datasets: datasets };
        const defaultOptions = {
            scales: {
                y: {
                    grid: { drawBorder: false, color: '#f0f0f0' },
                    ticks: { color: '#666' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#666' }
                }
            },
            elements: { line: { tension: 0.4 } }
        };
        return this.createChart(ctx, 'line', data, { ...defaultOptions, ...options });
    }

    createPieChart(ctx, labels, data, options = {}) {
        const chartData = {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: this.getDefaultColors(data.length),
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        };
        return this.createChart(ctx, 'pie', chartData, options);
    }

    createDoughnutChart(ctx, labels, data, options = {}) {
        const chartData = {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: this.getDefaultColors(data.length),
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        };
        const defaultOptions = { cutout: '65%' };
        return this.createChart(ctx, 'doughnut', chartData, { ...defaultOptions, ...options });
    }

    createPolarAreaChart(ctx, labels, data, options = {}) {
        const chartData = {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: this.getDefaultColors(data.length)
            }]
        };
        return this.createChart(ctx, 'polarArea', chartData, options);
    }

    createRadarChart(ctx, labels, datasets, options = {}) {
        const data = { labels: labels, datasets: datasets };
        const defaultOptions = {
             scales: {
                r: {
                    angleLines: { color: '#e0e0e0' },
                    grid: { color: '#e0e0e0' },
                    pointLabels: {
                        color: '#424242',
                        font: { family: "'Poppins', sans-serif", size: 12 }
                    }
                }
            }
        };
        return this.createChart(ctx, 'radar', data, { ...defaultOptions, ...options });
    }

    // --- COLOR THEME ENGINE (Red/Charcoal) ---
    getDefaultColors(count) {
        const colors = [
            '#D32F2F', // Brand Red
            '#2C3E50', // Brand Charcoal (NEW)
            '#757575', // Grey
            '#F9A825', // Gold
            '#1565C0', // Blue
            '#2E7D32', // Green
            '#6A1B9A', // Purple
            '#C62828', // Dark Red
            '#34495E', // Light Charcoal
            '#E67E22'  // Carrot Orange
        ];
        return colors.slice(0, count);
    }

    createGradient(ctx, color1, color2) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, color1 || 'rgba(211, 47, 47, 0.8)');
        gradient.addColorStop(1, color2 || 'rgba(211, 47, 47, 0.1)');
        return gradient;
    }

    handleResize() {
        this.charts.forEach(chart => {
            chart.resize();
        });
    }
}

const chartManager = new ChartManager();

document.addEventListener('DOMContentLoaded', function() {
    chartManager.initAllCharts();
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            chartManager.handleResize();
        }, 250);
    });
});

window.createChart = function(ctx, type, data, options) { return chartManager.createChart(ctx, type, data, options); };
window.updateChart = function(chartId, newData) { return chartManager.updateChart(chartId, newData); };
window.destroyChart = function(chartId) { return chartManager.destroyChart(chartId); };

if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChartManager;
}