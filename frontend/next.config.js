/** @type {import('next').NextConfig} */
const nextConfig = {
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: process.env.NEXT_PUBLIC_API_URL ?
                    `${process.env.NEXT_PUBLIC_API_URL.replace('/api/v1', '')}/:path*` :
                    // In Docker environment, use backend service name
                    (process.env.NODE_ENV === 'production' || process.env.DOCKER_ENV === 'true') ?
                        'http://backend:8000/:path*' :
                        'http://localhost:8000/:path*',
            },
        ]
    },
    images: {
        // Disable image optimization for API routes to avoid proxy issues
        unoptimized: Boolean(process.env.NODE_ENV === 'production' || process.env.DOCKER_ENV === 'true'),
        domains: ['localhost', 'backend'],
        remotePatterns: [
            {
                protocol: 'http',
                hostname: 'backend',
                port: '8000',
                pathname: '/api/v1/photos/**',
            },
            {
                protocol: 'http',
                hostname: 'localhost',
                port: '8000',
                pathname: '/api/v1/photos/**',
            }
        ],
    },
}

module.exports = nextConfig 