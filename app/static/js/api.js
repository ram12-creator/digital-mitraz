// API utility functions
class ApiClient {
    constructor() {
        this.baseUrl = API_BASE_URL;
        this.defaultHeaders = {
            'Content-Type': 'application/json',
            'X-CSRF-Token': CSRF_TOKEN
        };
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: { ...this.defaultHeaders, ...options.headers },
            ...options
        };

        if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
            config.body = JSON.stringify(config.body);
        }

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || `HTTP error! status: ${response.status}`);
            }

            return data;
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }

    async post(endpoint, data) {
        return this.request(endpoint, { 
            method: 'POST', 
            body: data 
        });
    }

    async put(endpoint, data) {
        return this.request(endpoint, { 
            method: 'PUT', 
            body: data 
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }

    async uploadFile(endpoint, formData) {
        return this.request(endpoint, {
            method: 'POST',
            headers: { 
                'X-CSRF-Token': CSRF_TOKEN 
            },
            body: formData
        });
    }
}

// Initialize API client
const api = new ApiClient();